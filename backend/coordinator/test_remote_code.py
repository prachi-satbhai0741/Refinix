"""AF-010 checks from the coordinator's side: what leaves, and what comes back.

A `FakeWorker` stands in for the paired worker, so the whole remote path —
package, envelope, event stream, proposal parsing, diff, sandbox validation —
runs without a worker, a cluster or a network. What the fake records is as
important as what it returns: several checks here are about what was *sent*.

The load-bearing claim is that the canonical repository is byte-identical after
generation and after validation. Nothing in C09 writes to it; only an approved
`canonical.write` does, and that is `test_approvals.py`.

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from backend.contracts import profiles, v1
from backend.coordinator import (code_service, codeflow, db, dispatch, models,
                                 repo, runtime)
from backend.coordinator.server import Coordinator
from backend.worker import packages, validate

PROJECT = {
    "pumpcheck/__init__.py": '"""Synthetic fixture package."""\n',
    "pumpcheck/limits.py": "def over(value, limit):\n    return value > limit\n",
    "tests/__init__.py": "",
    "tests/test_limits.py": (
        "import unittest\n"
        "from pumpcheck.limits import over\n\n"
        "class T(unittest.TestCase):\n"
        "    def test_over(self):\n"
        "        self.assertTrue(over(7.9, 7.1))\n"),
}
IMPROVED = "def over(value, limit):\n    return float(value) > float(limit)\n"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FakeWorker:
    """Records every request and replays one scripted reply as SSE frames."""

    def __init__(self, reply: str):
        self.reply = reply
        self.packages: list[dict] = []
        self.envelopes: list[v1.JobEnvelope] = []
        self.order: list[str] = []
        self.fail_submit: Exception | None = None
        self.fail_upload: Exception | None = None

    def upload_package(self, body):
        if self.fail_upload:
            raise self.fail_upload
        self.order.append("upload")
        self.packages.append(body)
        return {"attempt_id": body["attempt_id"],
                "package_sha256": body["package_sha256"],
                "file_count": len(body["files"]), "total_bytes": 1,
                "stored_at": "2026-09-05T10:00:00Z", "replayed": False}

    def submit(self, envelope, key):
        if self.fail_submit:
            raise self.fail_submit
        self.order.append("submit")
        self.envelopes.append(envelope)
        return {"attempt_id": envelope.attempt_id}

    def stream(self, job_id, attempt_id, after=0):
        env = self.envelopes[-1]
        frames = [
            ("attempt.state", {"kind": "attempt.state", "previous": None,
                               "current": "queued"}),
            ("attempt.state", {"kind": "attempt.state", "previous": "queued",
                               "current": "running"}),
        ]
        for index in range(0, len(self.reply), 512):
            frames.append(("output.delta",
                           {"kind": "output.delta",
                            "text": self.reply[index:index + 512]}))
        if env.inference is not None:
            frames.append(("inference.metrics", {
                "kind": "inference.metrics",
                "requested_profile_id": env.inference.profile_id,
                "actual_profile_id": env.inference.profile_id,
                "context_window": env.inference.context_window_tokens,
                "output_token_limit": env.inference.output_allowance_tokens,
                "reasoning": env.inference.reasoning,
                "decoder": env.inference.decoder,
                "prompt_tokens": 100,
                "output_tokens": 50,
                "runtime_ms": 10,
            }))
        frames += [
            ("attempt.state", {"kind": "attempt.state", "previous": "running",
                               "current": "validating"}),
            ("attempt.state", {"kind": "attempt.state", "previous": "validating",
                               "current": "completed"}),
        ]
        for sequence, (_kind, data) in enumerate(frames, start=1):
            if sequence <= after:
                continue
            yield v1.Event(
                contract_version=v1.CONTRACT_VERSION,
                workspace_id=env.workspace_id,
                job_id=env.job_id, attempt_id=env.attempt_id,
                event_id=str(uuid.uuid4()), sequence=sequence,
                producer_node_id=env.target_node_id, producer="worker",
                occurred_at="2026-09-05T10:00:00Z", data=data
            ).model_dump_json().encode()

    def cancel(self, job_id, attempt_id):
        return True


class Base(unittest.TestCase):
    def setUp(self):
        if not repo.containment_supported():
            self.skipTest("this platform cannot contain repository access")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "project"
        for name, text in PROJECT.items():
            target = self.project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="")
        self.c = Coordinator(Path(self.tmp.name) / "state" / "refinix.sqlite3")
        self.addCleanup(self.c.conn.close)
        self.repo_id = self.c.code.connect(str(self.project))["repo_id"]
        self.worker_node = str(uuid.uuid4())
        self.relationship_id = str(uuid.uuid4())
        db.record_relationship(
            self.c.conn, relationship_id=self.relationship_id,
            workspace_id=self.c.workspace_id, node_id=self.worker_node,
            display_name="ubuntu-worker", address="192.0.2.10", port=30443,
            fingerprint="AA:BB", certificate_pem="-----BEGIN CERTIFICATE-----")

    def route(self):
        profile = next(p for p in profiles.PROFILES if p.target_profile_id == profiles.MAC_M5_16GB and p.workflow_mode == profiles.CODE and p.model.runtime_version == "0.32.14")
        return dispatch.Route(
            "remote", "paired worker ubuntu-worker: healthy, qwen3.5:4b-q4_K_M",
            node_id=self.worker_node, relationship_id=self.relationship_id,
            model=profile.model.model_dump(), profile=profile.model_dump())

    def proposal_reply(self, *, path="pumpcheck/limits.py", content=IMPROVED,
                       base=None):
        return json.dumps({
            "summary": "compare the readings as numbers",
            "edits": [{"path": path,
                       "base_sha256": base or digest(PROJECT.get(path, "")),
                       "content": content}]})

    def run_remote(self, worker, *, paths=("pumpcheck/limits.py",),
                   request="compare the readings as numbers"):
        with patch.object(Coordinator, "choose_route", return_value=self.route()), \
                patch.object(Coordinator, "worker_client", return_value=worker):
            return self.c.code.propose(self.repo_id, request, list(paths))

    def on_disk(self) -> dict:
        return {name: (self.project / name).read_text(encoding="utf-8")
                for name in PROJECT}


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------

class TestRemoteGeneration(Base):
    def test_a_remote_proposal_produces_a_diff_and_changes_nothing_on_disk(self):
        worker = FakeWorker(self.proposal_reply())
        proposal = self.run_remote(worker)
        self.assertEqual(len(proposal["edits"]), 1)
        self.assertIn("float(value)", proposal["edits"][0]["diff"])
        attempt = self.c.job_detail(proposal["job_id"])["attempts"][-1]
        self.assertEqual(
            attempt["requested_inference"]["profile_id"],
            attempt["actual_profile"]["profile_id"])
        self.assertEqual(attempt["metrics"]["route"], "remote")
        # THE claim of C09: the canonical repository is untouched.
        self.assertEqual(self.on_disk(), PROJECT)

    def test_the_package_is_uploaded_before_the_envelope_is_submitted(self):
        """The worker refuses a code envelope with no package, so an accepted
        receipt has to mean the attempt can actually run."""
        worker = FakeWorker(self.proposal_reply())
        self.run_remote(worker)
        self.assertEqual(worker.order, ["upload", "submit"])

    def test_only_the_selected_files_are_sent(self):
        worker = FakeWorker(self.proposal_reply())
        self.run_remote(worker)
        sent = {item["path"] for item in worker.packages[0]["files"]}
        self.assertEqual(sent, {"pumpcheck/limits.py"})

    def test_the_worker_never_learns_the_absolute_repository_path(self):
        worker = FakeWorker(self.proposal_reply())
        self.run_remote(worker)
        rendered = json.dumps(worker.packages[0]) + \
            worker.envelopes[0].model_dump_json()
        for leak in (str(self.project), str(self.tmp.name), "/Users", "/home"):
            with self.subTest(value=leak):
                self.assertNotIn(leak, rendered)
        self.assertNotIn(self.repo_id, rendered)

    def test_the_envelope_names_the_code_capability_and_a_patch_output(self):
        worker = FakeWorker(self.proposal_reply())
        self.run_remote(worker)
        envelope = worker.envelopes[0]
        self.assertEqual(envelope.task_type, "code")
        self.assertEqual(list(envelope.required_capabilities), ["code.generate"])
        self.assertEqual(envelope.output.kind, "patch")
        self.assertIn("patch.applies", envelope.output.validators)
        self.assertEqual(list(envelope.allowed_tools), [])
        self.assertEqual(envelope.limits.tool_network, "disabled")

    def test_every_envelope_resource_matches_the_uploaded_package(self):
        worker = FakeWorker(self.proposal_reply())
        self.run_remote(worker)
        uploaded = {item["resource_id"]: item
                    for item in worker.packages[0]["files"]}
        for reference in worker.envelopes[0].context:
            entry = uploaded[reference.resource_id]
            self.assertEqual(entry["sha256"], reference.sha256)
            self.assertEqual(entry["size_bytes"], reference.size_bytes)

    def test_the_uploaded_package_passes_the_workers_own_validation(self):
        """The two sides agree on the format and on the digest."""
        worker = FakeWorker(self.proposal_reply())
        self.run_remote(worker)
        checked = packages.validate(worker.packages[0])
        self.assertEqual(checked["package_sha256"],
                         worker.packages[0]["package_sha256"])

    def test_a_proposal_naming_an_unselected_path_is_refused(self):
        worker = FakeWorker(self.proposal_reply(path="tests/test_limits.py"))
        with self.assertRaises(code_service.CodeError) as caught:
            self.run_remote(worker)
        self.assertEqual(caught.exception.code, "unselected_path")
        self.assertEqual(self.on_disk(), PROJECT)

    def test_a_proposal_with_a_stale_base_digest_is_refused(self):
        worker = FakeWorker(self.proposal_reply(base="0" * 64))
        with self.assertRaises(code_service.CodeError) as caught:
            self.run_remote(worker)
        self.assertEqual(caught.exception.code, "base_mismatch")
        self.assertEqual(self.on_disk(), PROJECT)

    def test_a_proposal_carrying_extra_fields_is_refused(self):
        reply = json.dumps({
            "summary": "x", "edits": [], "command": ["rm", "-rf", "/"],
            "approved": True})
        worker = FakeWorker(reply)
        with self.assertRaises(code_service.CodeError) as caught:
            self.run_remote(worker)
        self.assertEqual(caught.exception.code, "unknown_fields")

    def test_the_job_and_attempt_exist_before_the_worker_is_contacted(self):
        worker = FakeWorker(self.proposal_reply())
        recorded = {}
        real = dispatch.consume

        def watch(client, envelope, **kwargs):
            recorded["jobs"] = self.c.conn.execute(
                "SELECT COUNT(*) AS n FROM jobs WHERE task_type='code'"
            ).fetchone()["n"]
            recorded["attempts"] = self.c.conn.execute(
                "SELECT COUNT(*) AS n FROM attempts").fetchone()["n"]
            return real(client, envelope, **kwargs)

        with patch.object(code_service.dispatch, "consume", watch):
            self.run_remote(worker)
        self.assertGreaterEqual(recorded["jobs"], 1)
        self.assertGreaterEqual(recorded["attempts"], 1)

    def test_an_ambiguous_receipt_never_falls_back_to_running_it_here(self):
        """The worker may be running it. A local retry would answer twice."""
        worker = FakeWorker(self.proposal_reply())
        worker.fail_submit = dispatch.ReceiptUnknown("no answer")
        asked = []
        with patch.object(runtime, "stream_chat",
                          side_effect=lambda *a, **k: asked.append(1)):
            with self.assertRaises(code_service.CodeError) as caught:
                self.run_remote(worker)
        self.assertEqual(caught.exception.code, "receipt_unknown")
        self.assertEqual(asked, [], "the coordinator must not re-run it locally")
        row = self.c.conn.execute(
            "SELECT state, error_json FROM attempts ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(row["state"], "interrupted")
        self.assertEqual(json.loads(row["error_json"])["code"], "worker_lost")

    def test_a_changed_worker_identity_is_surfaced_not_flattened(self):
        """Pinning exists to make this visible; it must not become a traceback
        or, worse, a quiet local answer."""
        from backend.coordinator import pairing

        class Mismatching(FakeWorker):
            def stream(self, job_id, attempt_id, after=0):
                raise pairing.IdentityMismatch("the worker certificate changed")
                yield  # pragma: no cover

        worker = Mismatching(self.proposal_reply())
        asked = []
        with patch.object(runtime, "stream_chat",
                          side_effect=lambda *a, **k: asked.append(1)):
            with self.assertRaises(code_service.CodeError) as caught:
                self.run_remote(worker)
        self.assertEqual(caught.exception.code, "identity")
        self.assertEqual(asked, [], "an identity mismatch must not run locally")
        row = self.c.conn.execute(
            "SELECT state, error_json FROM attempts ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(row["state"], "failed")
        self.assertEqual(json.loads(row["error_json"])["code"], "permission_denied")
        self.assertEqual(self.on_disk(), PROJECT)

    def test_the_proposal_records_the_attempt_that_produced_it(self):
        worker = FakeWorker(self.proposal_reply())
        proposal = self.run_remote(worker)
        stored = self.c.conn.execute(
            "SELECT job_id, attempt_id FROM proposals WHERE proposal_id=?",
            (proposal["proposal_id"],)).fetchone()
        self.assertIsNotNone(stored["job_id"])
        self.assertEqual(stored["attempt_id"], worker.envelopes[0].attempt_id)


# --------------------------------------------------------------------------
# Sandbox validation
# --------------------------------------------------------------------------

class TestSandboxValidation(Base):
    def result(self, *, passed=True, observed=True):
        inner = {"result_version": validate.RESULT_VERSION,
                 "command": ["python3", "-m", "unittest"],
                 "exit_status": 0 if passed else 1, "timed_out": False,
                 "stdout": "OK", "stderr": "", "stdout_truncated": False,
                 "stderr_truncated": False, "replaced": ["pumpcheck/limits.py"],
                 "started_at": "2026-09-05T10:00:00Z",
                 "finished_at": "2026-09-05T10:00:05Z", "runtime_ms": 5000,
                 "tests_run": 1,
                 "passed": passed}
        inner["result_sha256"] = validate.result_digest(inner)
        return json.dumps({
            "cancelled": False, "observed": observed,
            "job_name": "af-validate-" + "0" * 32, "job_uid": "job-uid-1",
            "job_state": "succeeded",
            "pod": {"namespace": "aegisforge", "pod_name": "af-validate-x",
                    "pod_uid": "pod-uid-1", "image_digest": "b" * 64,
                    "ready": False, "restarts": 0},
            "passed": passed, "result": inner if observed else None,
            "package_sha256": "c" * 64})

    def proposal(self):
        return self.run_remote(FakeWorker(self.proposal_reply()), paths=tuple(PROJECT))

    def validate_it(self, proposal, worker):
        with patch.object(Coordinator, "choose_route", return_value=self.route()), \
                patch.object(Coordinator, "worker_client", return_value=worker):
            return self.c.code.validate(self.repo_id, proposal["proposal_id"])

    def test_a_passing_validation_is_recorded_with_its_evidence(self):
        proposal = self.proposal()
        worker = FakeWorker(self.result())
        record = self.validate_it(proposal, worker)
        self.assertTrue(record["passed"])
        self.assertTrue(record["observed"])
        self.assertEqual(record["command"], ["python3", "-m", "unittest"])
        self.assertEqual(record["image_digest"], "b" * 64)
        self.assertEqual(record["patch_sha256"], proposal["digest"])
        self.assertEqual(self.on_disk(), PROJECT)

    def test_validation_uses_a_separate_attempt_from_generation(self):
        proposal = self.proposal()
        record = self.validate_it(proposal, FakeWorker(self.result()))
        generation = self.c.conn.execute(
            "SELECT attempt_id FROM proposals WHERE proposal_id=?",
            (proposal["proposal_id"],)).fetchone()["attempt_id"]
        self.assertNotEqual(record["attempt_id"], generation)

    def test_the_validation_package_carries_the_plan_the_command_comes_from(self):
        proposal = self.proposal()
        worker = FakeWorker(self.result())
        self.validate_it(proposal, worker)
        files = {item["path"]: item for item in worker.packages[0]["files"]}
        self.assertIn("plan.json", files)
        import base64
        plan = json.loads(base64.b64decode(files["plan.json"]["content_base64"]))
        self.assertEqual(plan["command"], ["python3", "-m", "unittest"])
        self.assertEqual(plan["minimum_tests"], 1)
        self.assertTrue(any(p.startswith("original/") for p in files))
        self.assertTrue(any(p.startswith("replacement/") for p in files))
        self.assertIn("original/tests/test_limits.py", files)

    def test_the_command_comes_from_configuration_not_from_the_model(self):
        """The plan is built here from `VALIDATION_COMMAND`; the proposal has
        no field that could carry a command, and the sandbox checks it again."""
        proposal = self.proposal()
        worker = FakeWorker(self.result())
        self.validate_it(proposal, worker)
        import base64
        files = {item["path"]: item for item in worker.packages[0]["files"]}
        plan = json.loads(base64.b64decode(files["plan.json"]["content_base64"]))
        self.assertEqual(tuple(plan["command"]), validate.ALLOWED_COMMANDS[0])
        self.assertNotIn("command", json.dumps(proposal["edits"]))

    def test_an_unobserved_result_is_not_recorded_as_passed(self):
        proposal = self.proposal()
        record = self.validate_it(proposal, FakeWorker(self.result(observed=False)))
        self.assertFalse(record["passed"])
        self.assertFalse(record["observed"])

    def test_a_failing_validation_is_recorded_as_failed(self):
        proposal = self.proposal()
        record = self.validate_it(proposal, FakeWorker(self.result(passed=False)))
        self.assertFalse(record["passed"])
        self.assertTrue(record["observed"])

    def test_a_file_changed_since_review_is_not_validated(self):
        proposal = self.proposal()
        (self.project / "pumpcheck/limits.py").write_text("# someone else\n")
        with self.assertRaises(code_service.CodeError) as caught:
            self.validate_it(proposal, FakeWorker(self.result()))
        self.assertEqual(caught.exception.code, "stale")

    def test_validation_without_a_paired_worker_is_unavailable_not_skipped(self):
        proposal = self.proposal()
        local = dispatch.Route("local", "local coordinator: no paired worker")
        with patch.object(Coordinator, "choose_route", return_value=local):
            with self.assertRaises(code_service.CodeError) as caught:
                self.c.code.validate(self.repo_id, proposal["proposal_id"])
        self.assertEqual(caught.exception.code, "no_sandbox")
        self.assertIsNone(db.latest_validation(self.c.conn,
                                               proposal["proposal_id"],
                                               self.c.workspace_id))


if __name__ == "__main__":                                    # pragma: no cover
    unittest.main()
