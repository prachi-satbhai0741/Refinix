"""AF-012 and AF-014 checks: two workflows at once, and honest Proof Cards.

**Concurrency here means what the requester's topology actually is.** Documents
runs locally on the Mac; Code generation and validation run on the Ubuntu
worker. So the check drives one local document job and one remote code job at
the same time and asserts their state never crosses — not that two Redis
consumers exist, and not that Documents has a Pod, because neither is true.

The concurrency check is deterministic rather than timing-based: each side is
blocked on its own `threading.Event`, so "both were running before either
finished" is an assertion about released gates, not about a sleep.

Standard library only. No worker, no cluster, no model, no network.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from backend.contracts import v1
from backend.coordinator import db, device, proof
from backend.coordinator.server import Coordinator


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.c = Coordinator(Path(self.tmp.name) / "state" / "refinix.sqlite3")
        self.addCleanup(self.c.conn.close)
        self.chat = db.create_chat(self.c.conn, self.c.workspace_id, "work")

    def job(self, *, task_type="chat", request="do the thing"):
        return db.create_job(self.c.conn, workspace_id=self.c.workspace_id,
                             chat_id=self.chat, request=request,
                             task_type=task_type)

    def attempt(self, job_id, *, node_id=None, model=None, reason="local"):
        return db.create_attempt(self.c.conn, job_id=job_id,
                                 node_id=node_id or self.c.node_id,
                                 route_reason=reason, model=model)


# --------------------------------------------------------------------------
# Concurrency
# --------------------------------------------------------------------------

class TestConcurrentWorkflows(Base):
    def test_a_local_document_job_and_a_remote_code_job_run_at_the_same_time(self):
        """Both reach `running` before either completes, and never share state."""
        documents_job = self.job(request="draft the approval note")
        code_job = self.job(task_type="code", request="raise the limit")
        worker_node = str(uuid.uuid4())
        documents_attempt = self.attempt(
            documents_job, reason="local coordinator: Documents runs on this Mac")
        code_attempt = self.attempt(
            code_job, node_id=worker_node,
            reason="paired worker: healthy, qwen3.5:4b-q4_K_M",
            model={"model_id": "qwen3.5:4b-q4_K_M", "manifest_sha256": "a" * 64,
                   "runtime": "ollama", "runtime_version": "0.33.3"})

        both_running = threading.Barrier(3, timeout=10)
        release_documents = threading.Event()
        release_code = threading.Event()
        errors: list = []

        def run(job_id, attempt_id, release):
            try:
                db.set_attempt_state(self.c.conn, attempt_id, "running")
                # Both sides announce they are running, then wait. Nothing can
                # finish until the main thread has seen both.
                both_running.wait()
                release.wait(timeout=10)
                db.append_output(self.c.conn, attempt_id, f"output for {job_id}")
                db.set_attempt_state(self.c.conn, attempt_id, "validating")
                db.set_attempt_state(self.c.conn, attempt_id, "completed")
            except Exception as exc:                       # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=run, args=(documents_job, documents_attempt,
                                               release_documents)),
            threading.Thread(target=run, args=(code_job, code_attempt,
                                               release_code)),
        ]
        for thread in threads:
            thread.start()
        both_running.wait(timeout=10)

        states = self.states()
        self.assertEqual(states[documents_attempt], "running")
        self.assertEqual(states[code_attempt], "running")

        # Release one and let it finish while the other is still running.
        release_documents.set()
        threads[0].join(timeout=10)
        states = self.states()
        self.assertEqual(states[documents_attempt], "completed")
        self.assertEqual(states[code_attempt], "running")

        release_code.set()
        threads[1].join(timeout=10)
        self.assertEqual(errors, [])
        states = self.states()
        self.assertEqual(states[code_attempt], "completed")

    def states(self) -> dict:
        return {row["attempt_id"]: row["state"] for row in
                self.c.conn.execute("SELECT attempt_id, state FROM attempts")}

    def test_the_two_jobs_keep_separate_attempts_events_and_output(self):
        first, second = self.job(), self.job(task_type="code")
        one, two = self.attempt(first), self.attempt(second)
        db.append_output(self.c.conn, one, "documents text")
        db.append_output(self.c.conn, two, "code text")
        db.append_event(self.c.conn, job_id=first, attempt_id=one,
                        node_id=self.c.node_id,
                        data={"kind": "output.delta", "text": "documents text"})
        db.append_event(self.c.conn, job_id=second, attempt_id=two,
                        node_id=self.c.node_id,
                        data={"kind": "output.delta", "text": "code text"})
        rows = {row["attempt_id"]: row["output_text"] for row in
                self.c.conn.execute("SELECT attempt_id, output_text FROM attempts")}
        self.assertEqual(rows[one], "documents text")
        self.assertEqual(rows[two], "code text")
        events = {row["job_id"]: row["attempt_id"] for row in
                  self.c.conn.execute("SELECT job_id, attempt_id FROM events"
                                      " WHERE attempt_id IS NOT NULL")}
        self.assertEqual(events[first], one)
        self.assertEqual(events[second], two)

    def test_cancelling_one_job_does_not_cancel_the_other(self):
        first, second = self.job(), self.job(task_type="code")
        self.attempt(first)
        self.attempt(second)
        self.c.request_cancel(first)
        self.assertTrue(self.c.is_cancelled(first))
        self.assertFalse(self.c.is_cancelled(second))

    def test_a_failure_in_one_job_leaves_the_other_untouched(self):
        first, second = self.job(), self.job(task_type="code")
        one, two = self.attempt(first), self.attempt(second)
        db.set_attempt_state(self.c.conn, one, "running")
        db.set_attempt_state(self.c.conn, one, "failed", error={
            "code": "internal_error", "message": "documents failed",
            "retryable": False})
        db.set_attempt_state(self.c.conn, two, "running")
        states = self.states()
        self.assertEqual(states[one], "failed")
        self.assertEqual(states[two], "running")

    def test_artifacts_belong_to_one_attempt_only(self):
        first, second = self.job(), self.job(task_type="code")
        one, two = self.attempt(first), self.attempt(second)
        root = db.artifacts_root(self.c.state_path)
        root.mkdir(parents=True, exist_ok=True)
        (root / "note.docx").write_bytes(b"PK\x03\x04 fake")
        record = db.record_artifact(
            self.c.conn, workspace_id=self.c.workspace_id, chat_id=self.chat,
            job_id=first, attempt_id=one, workflow="inspection_report_to_approval_note",
            filename="note.docx", stored_name="note.docx",
            media_type="application/vnd.openxmlformats-officedocument."
                       "wordprocessingml.document",
            byte_size=9, sha256="b" * 64,
            validation={"readable": True, "paragraphs": 3}, citations=[])
        rows = [r["attempt_id"] for r in self.c.conn.execute(
            "SELECT attempt_id FROM artifacts WHERE job_id=?", (first,))]
        self.assertEqual(rows, [one])
        self.assertEqual([], [r["artifact_id"] for r in self.c.conn.execute(
            "SELECT artifact_id FROM artifacts WHERE job_id=?", (second,))])
        self.assertIsNotNone(record["artifact_id"])
        self.assertNotEqual(one, two)


# --------------------------------------------------------------------------
# Proof Cards
# --------------------------------------------------------------------------

class TestProofCards(Base):
    def validation(self, *, job_id, attempt_id, passed=True, observed=True,
                   pod=True, digest="c" * 64):
        result = {
            "observed": observed,
            "job_state": "succeeded" if passed else "failed",
            "passed": passed,
            "job_name": "af-validate-" + "0" * 32,
            "job_uid": "job-uid-1",
            "pod": ({"namespace": "aegisforge", "pod_name": "af-validate-x",
                     "pod_uid": "pod-uid-1", "image_digest": digest,
                     "ready": False, "restarts": 0} if pod else None),
            "result": ({"passed": passed, "exit_status": 0 if passed else 1,
                        "command": ["python3", "-m", "unittest"],
                        "tests_run": 1 if passed else 0,
                        "stdout": "OK", "stderr": "",
                        "started_at": "2026-09-05T10:00:00Z",
                        "finished_at": "2026-09-05T10:00:05Z",
                        "result_sha256": "d" * 64} if observed else None),
        }
        return db.record_validation(
            self.c.conn, workspace_id=self.c.workspace_id,
            proposal_id=str(uuid.uuid4()), job_id=job_id, attempt_id=attempt_id,
            node_id=str(uuid.uuid4()), result=result, patch_sha256="e" * 64)

    def finish(self, attempt_id):
        db.set_attempt_state(self.c.conn, attempt_id, "running")
        db.set_attempt_state(self.c.conn, attempt_id, "validating")
        db.set_attempt_state(self.c.conn, attempt_id, "completed")

    def test_a_local_attempt_carries_no_pod_evidence(self):
        job_id = self.job()
        attempt_id = self.attempt(job_id)
        self.finish(attempt_id)
        card = proof.job_card(self.c, job_id)
        entry = card["attempts"][0]
        self.assertIsNone(entry["proof"]["pod"])
        self.assertEqual(entry["where"], device.HERE)
        self.assertIn("ran on the coordinator", entry["sources"]["pod"])

    def test_a_validation_attempt_carries_no_model_evidence(self):
        """The sandbox runs no model, so naming one would describe other work."""
        job_id = self.job(task_type="code")
        worker = str(uuid.uuid4())
        attempt_id = self.attempt(
            job_id, node_id=worker,
            model={"model_id": "qwen3.5:4b-q4_K_M", "manifest_sha256": "a" * 64,
                   "runtime": "ollama", "runtime_version": "0.33.3"})
        self.finish(attempt_id)
        self.validation(job_id=job_id, attempt_id=attempt_id)
        entry = proof.job_card(self.c, job_id)["attempts"][0]
        self.assertIsNone(entry["proof"]["model"])
        self.assertIn("ran no model", entry["sources"]["model"])
        self.assertIsNotNone(entry["proof"]["pod"])
        self.assertEqual(entry["where"], device.PEER)

    def test_validation_is_unavailable_rather_than_failed_when_nothing_ran(self):
        job_id = self.job()
        attempt_id = self.attempt(job_id)
        self.finish(attempt_id)
        entry = proof.job_card(self.c, job_id)["attempts"][0]
        self.assertEqual(entry["proof"]["validation"], "unavailable")
        self.assertIsNone(entry["proof"]["validation_source"])
        self.assertNotEqual(entry["proof"]["validation"], "failed")

    def test_a_job_that_was_created_but_produced_nothing_is_not_a_pass(self):
        job_id = self.job(task_type="code")
        attempt_id = self.attempt(job_id, node_id=str(uuid.uuid4()))
        self.finish(attempt_id)
        self.validation(job_id=job_id, attempt_id=attempt_id, observed=False,
                        pod=False)
        entry = proof.job_card(self.c, job_id)["attempts"][0]
        self.assertEqual(entry["proof"]["validation"], "unavailable")
        self.assertIsNone(entry["proof"]["pod"])

    def test_a_failing_validation_is_reported_failed_with_its_source(self):
        job_id = self.job(task_type="code")
        attempt_id = self.attempt(job_id, node_id=str(uuid.uuid4()))
        self.finish(attempt_id)
        self.validation(job_id=job_id, attempt_id=attempt_id, passed=False)
        entry = proof.job_card(self.c, job_id)["attempts"][0]
        self.assertEqual(entry["proof"]["validation"], "failed")
        self.assertIn("sandbox validation result",
                      entry["proof"]["validation_source"])

    def test_an_image_digest_the_api_did_not_report_produces_no_pod_evidence(self):
        """Requesting an image is not evidence that the image ran."""
        job_id = self.job(task_type="code")
        attempt_id = self.attempt(job_id, node_id=str(uuid.uuid4()))
        self.finish(attempt_id)
        self.validation(job_id=job_id, attempt_id=attempt_id, digest="")
        entry = proof.job_card(self.c, job_id)["attempts"][0]
        self.assertIsNone(entry["proof"]["pod"])
        self.assertIn("no container status", entry["sources"]["pod"])

    def test_queue_time_that_was_never_recorded_stays_missing(self):
        job_id = self.job()
        attempt_id = self.attempt(job_id)
        self.finish(attempt_id)
        entry = proof.job_card(self.c, job_id)["attempts"][0]
        self.assertIsNone(entry["proof"]["queue_ms"])
        self.assertNotEqual(entry["proof"]["queue_ms"], 0)
        self.assertIn("unavailable", entry["sources"]["queue_ms"])

    def test_network_evidence_is_unavailable_and_never_zero_egress(self):
        job_id = self.job()
        attempt_id = self.attempt(job_id)
        self.finish(attempt_id)
        card = proof.job_card(self.c, job_id)
        network = card["attempts"][0]["proof"]["network"]
        self.assertEqual(network["public_egress_policy"], "unavailable")
        self.assertIsNone(network["public_outbound_flows"])
        self.assertIsNone(network["external_ai_calls"])
        self.assertIn("not a measurement", card["network"])

    def test_the_contract_refuses_an_attempt_whose_model_has_no_digest(self):
        """First line of defence: such a row cannot be written at all."""
        job_id = self.job()
        with self.assertRaises(Exception):
            self.attempt(job_id,
                         model={"model_id": "qwen3.5:4b-q4_K_M", "runtime": "ollama"})

    def test_a_model_without_a_manifest_digest_is_not_integrity_evidence(self):
        """Second line: a row that predates the check, or was written by hand,
        yields no model evidence rather than a name with no integrity behind it."""
        job_id = self.job()
        attempt_id = self.attempt(job_id)
        self.finish(attempt_id)
        with self.c.conn:
            self.c.conn.execute(
                "UPDATE attempts SET model_json=? WHERE attempt_id=?",
                (json.dumps({"model_id": "qwen3.5:4b-q4_K_M", "runtime": "ollama"}),
                 attempt_id))
        entry = proof.job_card(self.c, job_id)["attempts"][0]
        self.assertIsNone(entry["proof"]["model"])
        self.assertIn("unavailable", entry["sources"]["model"])

    def test_each_attempt_gets_its_own_proof_record(self):
        """A superseded attempt's proof must not describe its successor."""
        job_id = self.job(task_type="code")
        worker = str(uuid.uuid4())
        first = self.attempt(job_id, node_id=worker, reason="paired worker")
        db.set_attempt_state(self.c.conn, first, "running")
        db.set_attempt_state(self.c.conn, first, "failed", error={
            "code": "validation_failed", "message": "no", "retryable": True})
        second = self.attempt(job_id, node_id=worker, reason="paired worker retry")
        self.finish(second)
        self.validation(job_id=job_id, attempt_id=second)
        card = proof.job_card(self.c, job_id)
        self.assertEqual(len(card["attempts"]), 2)
        ids = [entry["proof"]["attempt_id"] for entry in card["attempts"]]
        self.assertEqual(ids, [first, second])
        # The failed attempt has no validation of its own.
        self.assertEqual(card["attempts"][0]["proof"]["validation"], "unavailable")
        self.assertEqual(card["attempts"][1]["proof"]["validation"], "passed")

    def test_every_proof_validates_against_the_shared_contract(self):
        job_id = self.job(task_type="code")
        attempt_id = self.attempt(job_id, node_id=str(uuid.uuid4()))
        self.finish(attempt_id)
        self.validation(job_id=job_id, attempt_id=attempt_id)
        for entry in proof.job_card(self.c, job_id)["attempts"]:
            v1.Proof(**entry["proof"])          # raises on an inconsistent record

    def test_every_displayed_value_names_where_it_came_from(self):
        job_id = self.job()
        attempt_id = self.attempt(job_id)
        self.finish(attempt_id)
        sources = proof.job_card(self.c, job_id)["attempts"][0]["sources"]
        for field in ("state", "route_reason", "queue_ms", "runtime_ms", "model",
                      "pod", "validation", "artifacts", "citations", "approval",
                      "network"):
            with self.subTest(field=field):
                self.assertTrue(sources[field], f"{field} has no stated source")

    def test_an_unknown_job_has_no_card(self):
        self.assertIsNone(proof.job_card(self.c, str(uuid.uuid4())))


if __name__ == "__main__":                                    # pragma: no cover
    unittest.main()
