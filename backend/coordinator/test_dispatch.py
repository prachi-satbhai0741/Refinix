"""Offline checks for AF-006 routing, pinning, and truthful fallback.

Standard library only. No worker, no TLS handshake, no Keychain, no network.

What that means for the claims below, stated plainly: `verify_presented` is
exercised against a fake connection that returns known certificate bytes, so
these prove the **pin comparison and the refusal path**, not that a real TLS
handshake behaves as expected. The live handshake, the Keychain and a real
worker are device gates and are reported as such.

    python -m unittest backend.coordinator.test_dispatch
"""

from __future__ import annotations

import json
import pathlib
import tempfile
import time
import unittest
import uuid

from backend.contracts import profiles, v1
from backend.coordinator import db, dispatch, pairing, server

NODE = "22222222-2222-4222-8222-222222222222"
OTHER_NODE = "33333333-3333-4333-8333-333333333333"
RELATIONSHIP = "66666666-6666-4666-8666-666666666666"
WORKSPACE = "77777777-7777-4777-8777-777777777777"
COORDINATOR = "88888888-8888-4888-8888-888888888888"
WORKER_PROFILE = profiles.PROFILES[-1]


def inference():
    return profiles.request(
        WORKER_PROFILE, reasoning="disabled", decoder="text",
        context_window=4096, output_allowance=2048)


def node_record(**over) -> dict:
    record = {
        "contract_version": v1.CONTRACT_VERSION, "node_id": NODE,
        "display_name": "ubuntu-worker",
        "app_version": "0.1.0", "platform": "Linux x86_64",
        "supported_contract_versions": [v1.CONTRACT_VERSION],
        "capabilities": ["text.generate"],
        "models": [WORKER_PROFILE.model.model_dump()],
        "inference_profiles": [WORKER_PROFILE.model_dump()],
        "health": "healthy", "observed_at": "2026-09-05T00:00:00Z",
        "queue_depth": 0, "available_memory_bytes": None,
        "loaded_model_id": None}
    if over.get("models") == [] and "inference_profiles" not in over:
        over["inference_profiles"] = []
    record.update(over)
    return record


def relationship(**over) -> dict:
    record = {"relationship_id": RELATIONSHIP, "workspace_id": WORKSPACE,
              "node_id": NODE, "state": "paired", "address": "192.168.68.207",
              "port": 30443, "fingerprint": "AA:" * 31 + "AA",
              "certificate_pem": "-----BEGIN CERTIFICATE-----\nx\n"
                                 "-----END CERTIFICATE-----\n",
              "paired_at": "2026-09-05T00:00:00Z"}
    record.update(over)
    return record


def envelope(**over) -> v1.JobEnvelope:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    later = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 600))
    nid = lambda: str(uuid.uuid4())                          # noqa: E731
    fields = dict(
        contract_version="1.0", workspace_id=WORKSPACE, workflow_id=nid(),
        job_id=nid(), step_id=nid(), attempt_id=nid(), chat_id=nid(),
        coordinator_node_id=COORDINATOR, target_node_id=NODE,
        relationship_id=RELATIONSHIP, original_request="say something",
        task_type="chat", required_capabilities=["text.generate"], context=[],
        attachments=[], allowed_tools=[],
        limits=v1.Limits(cpu_millis=2000, memory_bytes=2_147_483_648,
                         runtime_seconds=300, processes=8,
                         workspace_bytes=1_048_576, output_bytes=1_048_576,
                         tool_network="disabled"),
        output=v1.OutputContract(kind="text", validators=["text.nonempty"],
                                 schema_ref=None),
        approval_policy="coordinator-default-v1", created_at=now,
        deadline_at=later, cancel_requested=False)
    fields.update(over)
    return v1.JobEnvelope(**fields)


def worker_event(env, sequence, data, *, producer="worker",
                 producer_node_id=NODE, **over) -> bytes:
    fields = dict(
        contract_version="1.0", workspace_id=env.workspace_id,
        job_id=env.job_id, attempt_id=env.attempt_id, event_id=str(uuid.uuid4()),
        sequence=sequence, producer_node_id=producer_node_id, producer=producer,
        occurred_at="2026-09-05T00:00:00Z", data=data)
    fields.update(over)
    return v1.Event(**fields).model_dump_json().encode()


class FakeWorker:
    """A worker that yields a scripted stream. Records what it was asked.

    Frames are indexed by sequence, so `after` slices the same way the real
    replay does: a reconnect asking for `after=3` receives sequence 4 onward
    and never re-delivers what the coordinator already stored.
    """

    def __init__(self, frames, *, fail_at=None, fail_every=False,
                 truncate_at=None, reveal=None):
        self.frames = frames
        self.fail_at = fail_at
        self.fail_every = fail_every
        self.truncate_at = truncate_at
        # `truncate_at` is an absolute ceiling: frames at or beyond that index
        # are NEVER delivered, however many times the coordinator reconnects.
        # That models an executor that stopped without a terminal event.
        #
        # `reveal` models a log that grows while the coordinator is reading:
        # call N sees only the first `reveal[N]` frames, which is what an
        # executor that has not finished yet actually looks like.
        self.reveal = reveal
        self.calls = 0
        self.cancelled = []
        self.streamed = []

    def stream(self, job_id, attempt_id, after=0):
        self.streamed.append((job_id, attempt_id, after))
        available = self.frames
        if self.reveal is not None:
            limit = self.reveal[min(self.calls, len(self.reveal) - 1)]
            available = self.frames[:limit]
        self.calls += 1
        delivered = 0
        for index, frame in enumerate(available[after:], start=after):
            # `fail_at` is an absolute frame index, so a reconnect that
            # resumes past it does not accidentally sail through.
            if self.fail_at is not None and index == self.fail_at \
                    and (self.fail_every or self.calls == 1):
                raise dispatch.DispatchUnavailable("connection lost")
            if self.truncate_at is not None and index >= self.truncate_at:
                return          # a clean close with no terminal state
            delivered += 1
            yield frame

    def cancel(self, job_id, attempt_id):
        self.cancelled.append((job_id, attempt_id))
        return True


class FakeConnection:
    def __init__(self, der: bytes | None):
        self._der = der

    def getpeercert(self, binary_form=False):
        return self._der


# ------------------------------------------------------------------ pinning ---

class TestCertificatePinning(unittest.TestCase):
    def test_a_matching_certificate_is_accepted(self):
        der = b"the-real-worker-certificate"
        pairing.verify_presented(FakeConnection(der), pairing.fingerprint_of(der))

    def test_a_different_certificate_aborts(self):
        der = b"the-real-worker-certificate"
        with self.assertRaises(pairing.IdentityMismatch):
            pairing.verify_presented(FakeConnection(b"someone-else"),
                                     pairing.fingerprint_of(der))

    def test_no_certificate_at_all_aborts(self):
        with self.assertRaises(pairing.IdentityMismatch):
            pairing.verify_presented(FakeConnection(None),
                                     pairing.fingerprint_of(b"x"))

    def test_a_mismatch_is_not_a_generic_pairing_error_to_callers(self):
        """It must be catchable on its own, so the fallback path cannot swallow
        it by catching the base class."""
        self.assertTrue(issubclass(pairing.IdentityMismatch, pairing.PairingError))
        self.assertIsNot(pairing.IdentityMismatch, pairing.PairingError)

    def test_operator_typed_fingerprints_are_accepted(self):
        canonical = pairing.fingerprint_of(b"x")
        for typed in (canonical.lower(), canonical.replace(":", " "),
                      canonical.replace(":", ""),
                      f"sha256 Fingerprint={canonical}"):
            self.assertEqual(pairing.normalise_fingerprint(typed), canonical)

    def test_a_malformed_fingerprint_is_refused(self):
        for bad in ("", "AA:BB", "z" * 64, "AA" * 40):
            with self.assertRaises(pairing.PairingError):
                pairing.normalise_fingerprint(bad)

    def test_a_pinned_context_does_not_use_the_system_trust_store(self):
        with self.assertRaises(pairing.PairingError):
            pairing.pinned_context("not a certificate")

    def test_nothing_secret_survives_redaction(self):
        line = pairing.redacted({"credential": "s3cret", "pairing_code": "abc",
                                 "address": "192.168.68.207"})
        self.assertNotIn("s3cret", line)
        self.assertNotIn("abc", line)
        self.assertIn("192.168.68.207", line)


# ------------------------------------------------------------------ routing ---

class TestRouting(unittest.TestCase):
    def route(self, **over):
        return dispatch.choose_route(
            relationship=over.pop("relationship", relationship()),
            node=over.pop("node", node_record()),
            required=over.pop("required", ["text.generate"]),
            model_id=over.pop("model_id", "qwen3.5:4b-q4_K_M"), **over)

    def test_a_healthy_paired_worker_is_used(self):
        route = self.route()
        self.assertTrue(route.remote)
        self.assertEqual(route.node_id, NODE)
        self.assertEqual(route.relationship_id, RELATIONSHIP)
        self.assertIn("healthy", route.reason)

    def test_no_pairing_falls_back_with_a_reason(self):
        route = self.route(relationship=None)
        self.assertFalse(route.remote)
        self.assertIn("no paired worker", route.reason)

    def test_a_revoked_pairing_is_not_used(self):
        route = self.route(relationship=relationship(state="revoked"))
        self.assertFalse(route.remote)
        self.assertIn("revoked", route.reason)

    def test_a_worker_that_did_not_answer_falls_back(self):
        route = self.route(node=None)
        self.assertFalse(route.remote)
        self.assertIn("preflight", route.reason)

    def test_an_unhealthy_worker_falls_back_naming_the_health(self):
        route = self.route(node=node_record(health="degraded"))
        self.assertFalse(route.remote)
        self.assertIn("degraded", route.reason)

    def test_a_contract_mismatch_falls_back(self):
        route = self.route(node=node_record(supported_contract_versions=["2.0"]))
        self.assertFalse(route.remote)
        self.assertIn("contract", route.reason)

    def test_a_missing_capability_falls_back_naming_it(self):
        route = self.route(node=node_record(capabilities=[]))
        self.assertFalse(route.remote)
        self.assertIn("text.generate", route.reason)

    def test_a_missing_model_falls_back_naming_it(self):
        route = self.route(node=node_record(models=[]))
        self.assertFalse(route.remote)
        self.assertIn("qwen3.5:4b-q4_K_M", route.reason)

    def test_incompatible_semantics_do_not_route_to_the_worker(self):
        for requirements in (
            {"reasoning": "enabled"},
            {"context_window": 8192},
            {"decoder": "json_schema"},
            {"workflow": "code.whole_file"},
        ):
            with self.subTest(requirements=requirements):
                route = self.route(**requirements)
                self.assertFalse(route.remote)
                self.assertIsNone(route.profile)

    def test_every_refusal_carries_a_distinct_reason(self):
        """A single 'unavailable' for four different causes would need four
        different fixes and give the operator no way to tell them apart."""
        reasons = {
            self.route(relationship=None).reason,
            self.route(node=None).reason,
            self.route(node=node_record(health="degraded")).reason,
            self.route(node=node_record(capabilities=[])).reason,
            self.route(node=node_record(models=[])).reason,
        }
        self.assertEqual(len(reasons), 5)


class TestEnvelopeConstruction(unittest.TestCase):
    def job(self):
        return {"workspace_id": WORKSPACE, "workflow_id": str(uuid.uuid4()),
                "job_id": str(uuid.uuid4()), "chat_id": str(uuid.uuid4())}

    def route(self, relationship_id=RELATIONSHIP):
        return dispatch.Route(
            "remote", "ok", node_id=NODE, relationship_id=relationship_id,
            model=WORKER_PROFILE.model.model_dump(),
            profile=WORKER_PROFILE.model_dump())

    def build(self, *, relationship_id=RELATIONSHIP, **over):
        fields = dict(
            job=self.job(), attempt_id=str(uuid.uuid4()),
            step_id=str(uuid.uuid4()), route=self.route(relationship_id),
            coordinator_node_id=COORDINATOR, request_text="hello",
            messages=[{"role": "system", "content": "You are Refinix."},
                      {"role": "user", "content": "hello"}],
            inference=inference())
        fields.update(over)
        return dispatch.build_envelope(**fields)

    def test_a_remote_envelope_carries_target_and_relationship(self):
        env = self.build()
        self.assertEqual(env.target_node_id, NODE)
        self.assertEqual(env.relationship_id, RELATIONSHIP)
        self.assertEqual(env.limits.tool_network, "disabled")

    def test_the_deadline_follows_creation(self):
        env = self.build()
        self.assertGreater(env.deadline_at, env.created_at)

    def test_chat_identity_is_carried_as_a_system_instruction(self):
        env = self.build(system_instruction="You are Refinix.")
        self.assertEqual(env.system_instruction, "You are Refinix.")

    def test_a_remote_target_without_a_relationship_is_rejected(self):
        """The contract refuses it; this proves the coordinator cannot build
        one by accident."""
        with self.assertRaises(Exception):
            self.build(relationship_id=None)


# ------------------------------------------------------------------- stream ---

class TestStreamConsumption(unittest.TestCase):
    def frames(self, env, *, text=("one", "two")):
        out = [worker_event(env, 1, {"kind": "attempt.state", "previous": None,
                                     "current": "queued"}),
               worker_event(env, 2, {"kind": "attempt.state", "previous": "queued",
                                     "current": "running"})]
        sequence = 3
        for piece in text:
            out.append(worker_event(env, sequence,
                                    {"kind": "output.delta", "text": piece}))
            sequence += 1
        out.append(worker_event(env, sequence,
                                {"kind": "attempt.state", "previous": "running",
                                 "current": "validating"}))
        out.append(worker_event(env, sequence + 1,
                                {"kind": "attempt.state",
                                 "previous": "validating", "current": "completed"}))
        return out

    def test_a_completed_stream_yields_the_text_and_no_failure(self):
        env = envelope()
        outcome = dispatch.consume(FakeWorker(self.frames(env)), env)
        self.assertEqual(outcome.state, "completed")
        self.assertEqual(outcome.text, "onetwo")
        self.assertIsNone(outcome.failure)

    def test_a_record_for_another_attempt_is_dropped(self):
        env, other = envelope(), envelope()
        frames = self.frames(env)
        frames.insert(2, worker_event(other, 99,
                                      {"kind": "output.delta", "text": "poison"}))
        outcome = dispatch.consume(FakeWorker(frames), env)
        self.assertNotIn("poison", outcome.text)

    def test_a_record_from_another_node_is_dropped(self):
        env = envelope()
        frames = self.frames(env)
        frames.insert(2, worker_event(env, 98, {"kind": "output.delta",
                                                "text": "poison"},
                                      producer_node_id=OTHER_NODE))
        outcome = dispatch.consume(FakeWorker(frames), env)
        self.assertNotIn("poison", outcome.text)

    def test_a_worker_cannot_emit_a_coordinator_decision(self):
        """The contract forbids it; this proves an attempt to do so is dropped
        rather than persisted."""
        env = envelope()
        frames = self.frames(env)
        # Hand-built rather than through v1.Event, because the contract refuses
        # to construct this at all — which is the point. The coordinator must
        # also refuse it on the way in.
        forged = json.dumps({
            "contract_version": "1.0", "workspace_id": env.workspace_id,
            "job_id": env.job_id, "attempt_id": env.attempt_id,
            "event_id": str(uuid.uuid4()), "sequence": 97,
            "producer_node_id": NODE, "producer": "worker",
            "occurred_at": "2026-09-05T00:00:00Z",
            "data": {"kind": "job.state", "previous": None,
                     "current": "created"}}).encode()
        frames.insert(2, forged)
        outcome = dispatch.consume(FakeWorker(frames), env)
        for event in outcome.events:
            self.assertNotEqual(event.data.kind, "job.state")

    def test_malformed_bytes_are_dropped(self):
        env = envelope()
        frames = self.frames(env)
        frames.insert(2, b"{not json")
        frames.insert(3, b'{"contract_version": "9.9"}')
        outcome = dispatch.consume(FakeWorker(frames), env)
        self.assertEqual(outcome.state, "completed")
        self.assertEqual(outcome.text, "onetwo")

    def test_a_duplicate_sequence_is_not_counted_twice(self):
        env = envelope()
        frames = self.frames(env)
        frames.insert(4, frames[2])          # replay one delta
        outcome = dispatch.consume(FakeWorker(frames), env)
        self.assertEqual(outcome.text, "onetwo")

    def test_a_cut_stream_reconnects_and_still_completes(self):
        """The worker holds the connection until the attempt finishes, so a
        stream that ends early is a transport failure. Declaring it an outcome
        marked running work `interrupted`."""
        env = envelope()
        worker = FakeWorker(self.frames(env), fail_at=4)
        outcome = dispatch.consume(worker, env)
        self.assertEqual(outcome.state, "completed")
        self.assertEqual(outcome.text, "onetwo", "no delta delivered twice")
        self.assertGreater(len(worker.streamed), 1, "it must have reconnected")

    def test_a_reconnect_resumes_after_the_last_stored_sequence(self):
        env = envelope()
        worker = FakeWorker(self.frames(env), fail_at=4)
        dispatch.consume(worker, env)
        first, second = worker.streamed[0], worker.streamed[1]
        self.assertEqual(first[2], 0)
        self.assertGreater(second[2], 0,
                           "a reconnect that restarts at 0 duplicates output")

    def test_an_initially_empty_log_is_waited_out_not_declared_interrupted(self):
        """Immediately after submission the log is empty. That is an attempt
        that has not started, not one that failed."""
        env = envelope()
        frames = self.frames(env)
        worker = FakeWorker(frames, reveal=[0, 2, len(frames)])
        outcome = dispatch.consume(worker, env)
        self.assertEqual(outcome.state, "completed")
        self.assertEqual(outcome.text, "onetwo")

    def test_output_arriving_across_reconnects_is_not_duplicated(self):
        env = envelope()
        frames = self.frames(env, text=("one", "two", "three"))
        worker = FakeWorker(frames, fail_at=3, reveal=[4, 6, len(frames)])
        outcome = dispatch.consume(worker, env)
        self.assertEqual(outcome.state, "completed")
        self.assertEqual(outcome.text, "onetwothree")

    def test_a_worker_that_never_comes_back_is_reported_lost(self):
        """Reconnection is bounded: an executor that died must eventually be
        reported rather than reconnected to forever."""
        env = envelope()
        worker = FakeWorker(self.frames(env), fail_at=4, fail_every=True)
        outcome = dispatch.consume(worker, env, reconnects=3)
        self.assertEqual(outcome.state, "interrupted")
        self.assertEqual(outcome.failure["code"], "worker_lost")
        self.assertTrue(outcome.text, "partial output must be retained")
        self.assertEqual(len(worker.streamed), 3, "bounded, not unbounded")

    def test_a_stream_that_never_reaches_a_terminal_state_interrupts(self):
        env = envelope()
        worker = FakeWorker(self.frames(env), truncate_at=3)
        outcome = dispatch.consume(worker, env, reconnects=2)
        self.assertEqual(outcome.state, "interrupted")
        self.assertEqual(outcome.failure["code"], "worker_lost")

    def test_cancellation_reaches_the_worker(self):
        env = envelope()
        worker = FakeWorker(self.frames(env))
        outcome = dispatch.consume(worker, env, should_cancel=lambda: True)
        self.assertEqual(outcome.state, "cancelled")
        self.assertEqual(outcome.failure["code"], "cancelled_by_user")

    def test_replay_resumes_from_the_last_persisted_sequence(self):
        env = envelope()
        worker = FakeWorker(self.frames(env))
        dispatch.consume(worker, env, after=3)
        self.assertEqual(worker.streamed[0][2], 3)

    def test_one_key_per_attempt_is_reused_by_every_retry(self):
        """A fresh key on a retry creates a second remote attempt instead of
        replaying the first — the opposite of what idempotency is for."""
        env = envelope()
        self.assertEqual(dispatch.idempotency_key_for(env.attempt_id),
                         dispatch.idempotency_key_for(env.attempt_id))
        self.assertNotEqual(dispatch.idempotency_key_for(env.attempt_id),
                            dispatch.idempotency_key_for(str(uuid.uuid4())))

    def test_every_kept_event_is_a_validated_contract_record(self):
        env = envelope()
        outcome = dispatch.consume(FakeWorker(self.frames(env)), env)
        for event in outcome.events:
            self.assertIsInstance(event, v1.Event)
            self.assertEqual(event.producer, "worker")


class FakeHttpConnection:
    """An http.client.HTTPSConnection stand-in with a scriptable failure point.

    `request()` is where the transmission happens, so it is where an exception
    can leave the body already at the worker. That is the case these model.
    """

    def __init__(self, *, raise_in_request=None, status=202, payload=b"{}",
                 raise_in_getresponse=None):
        self.raise_in_request = raise_in_request
        self.raise_in_getresponse = raise_in_getresponse
        self.status = status
        self.payload = payload
        self.closed = False
        self.sock = FakePeerSocket()

    def connect(self):
        return None

    def request(self, method, path, body=None, headers=None):
        if self.raise_in_request is not None:
            raise self.raise_in_request

    def getresponse(self):
        if self.raise_in_getresponse is not None:
            raise self.raise_in_getresponse
        return FakeResponse(self.status, self.payload)

    def close(self):
        self.closed = True


class FakePeerSocket:
    def getpeercert(self, binary_form=False):
        return b"the-real-worker-certificate"


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    def read(self, limit=None):
        return self._payload


def client_with(connection) -> dispatch.WorkerClient:
    """A WorkerClient whose transport is the fake, with the pin satisfied."""
    client = dispatch.WorkerClient.__new__(dispatch.WorkerClient)
    client.address, client.port = "192.168.1.20", 30443
    client.fingerprint = pairing.fingerprint_of(b"the-real-worker-certificate")
    client.credential = "credential"
    client.timeout = 1.0
    client._context = None
    client._connect = lambda timeout=None: connection
    return client


class TestSubmitAmbiguity(unittest.TestCase):
    """What the coordinator can actually prove about a POST."""

    def test_a_failure_during_transmission_is_receipt_unknown(self):
        """`HTTPConnection.request` performs the write, so it can raise having
        already delivered the body. An earlier version set its "sent" flag only
        after `request` RETURNED, classified this as definite, and allowed the
        coordinator to run the same work locally."""
        connection = FakeHttpConnection(raise_in_request=OSError("connection reset"))
        with self.assertRaises(dispatch.ReceiptUnknown):
            client_with(connection).submit(envelope(), "key")
        self.assertTrue(connection.closed, "the socket is still released")

    def test_a_failure_awaiting_the_reply_is_receipt_unknown(self):
        connection = FakeHttpConnection(raise_in_getresponse=OSError("timed out"))
        with self.assertRaises(dispatch.ReceiptUnknown):
            client_with(connection).submit(envelope(), "key")

    def test_a_connect_failure_stays_a_definite_refusal(self):
        """Nothing was written, so local execution is safe."""
        client = client_with(FakeHttpConnection())

        def refuse(timeout=None):
            raise dispatch.DispatchUnavailable("the worker did not answer")

        client._connect = refuse
        with self.assertRaises(dispatch.DispatchUnavailable):
            client.submit(envelope(), "key")

    def test_a_typed_client_refusal_stays_definite(self):
        connection = FakeHttpConnection(
            status=422, payload=b'{"code": "invalid_request", '
                                b'"message": "bad envelope", "retryable": false}')
        with self.assertRaises(dispatch.DispatchUnavailable):
            client_with(connection).submit(envelope(), "key")

    def test_a_definite_server_side_code_stays_definite(self):
        connection = FakeHttpConnection(
            status=503, payload=b'{"code": "redis_lost", '
                                b'"message": "nothing was sent", "retryable": true}')
        with self.assertRaises(dispatch.DispatchUnavailable):
            client_with(connection).submit(envelope(), "key")

    def test_an_unconfirmable_server_code_is_receipt_unknown(self):
        """The worker could not establish whether its own commit landed."""
        connection = FakeHttpConnection(
            status=503, payload=b'{"code": "internal_error", "message": '
                                b'"the dispatch state could not be read back.", '
                                b'"retryable": true}')
        with self.assertRaises(dispatch.ReceiptUnknown):
            client_with(connection).submit(envelope(), "key")

    def test_an_unreadable_202_is_receipt_unknown_not_a_refusal(self):
        """Accepted, and we cannot tell which attempt. The work exists."""
        connection = FakeHttpConnection(status=202, payload=b"not json")
        with self.assertRaises(dispatch.ReceiptUnknown):
            client_with(connection).submit(envelope(), "key")

    def test_receipt_unknown_cannot_be_caught_as_unavailability(self):
        """A caller that means to fall back must not do so by accident."""
        self.assertFalse(issubclass(dispatch.ReceiptUnknown,
                                    dispatch.DispatchUnavailable))


class TestFallbackVersusRefusal(unittest.TestCase):
    """The distinction the whole design rests on."""

    def test_unavailability_is_recoverable_and_mismatch_is_not(self):
        self.assertTrue(issubclass(dispatch.DispatchUnavailable, Exception))
        self.assertFalse(issubclass(dispatch.DispatchUnavailable,
                                    pairing.IdentityMismatch))

    def test_consume_never_converts_a_mismatch_into_a_fallback(self):
        env = envelope()

        class Changed:
            def stream(self, *args, **kwargs):
                raise pairing.IdentityMismatch("the worker identity changed")
                yield b""                      # pragma: no cover

            def cancel(self, *args, **kwargs):
                return True

        with self.assertRaises(pairing.IdentityMismatch):
            dispatch.consume(Changed(), env)


class TestRelationshipRecords(unittest.TestCase):
    """The canonical half of pairing: a real database, no worker, no Keychain."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.conn = db.connect(pathlib.Path(self._dir.name) / "t.db")
        self.workspace = db.new_id()

    def tearDown(self):
        self.conn.close()
        self._dir.cleanup()

    def pair(self) -> str:
        relationship_id = db.new_id()
        db.record_relationship(
            self.conn, relationship_id=relationship_id,
            workspace_id=self.workspace, node_id=db.new_id(),
            display_name="ubuntu-worker", address="192.168.1.20", port=30443,
            fingerprint="AB:CD", certificate_pem="-----BEGIN CERTIFICATE-----")
        return relationship_id

    def running_attempt(self, relationship_id: str) -> tuple[str, str]:
        chat = db.create_chat(self.conn, self.workspace, "t")
        job = db.create_job(self.conn, workspace_id=self.workspace,
                            chat_id=chat, request="hi")
        for following in ("context_preparing", "queued", "routing", "running"):
            db.set_job_state(self.conn, job, following)
        attempt = db.create_attempt(
            self.conn, job_id=job, node_id=db.new_id(),
            route_reason="paired worker: healthy")
        db.set_attempt_relationship(self.conn, attempt, relationship_id)
        db.set_attempt_state(self.conn, attempt, "running")
        return job, attempt

    def test_the_stored_row_keeps_the_id_the_worker_was_given(self):
        """The worker minted its credential against the ID the coordinator
        sent. A locally generated second ID would not match it."""
        relationship_id = self.pair()
        self.assertEqual(
            db.active_relationship(self.conn, self.workspace)["relationship_id"],
            relationship_id)

    def test_no_credential_column_exists_to_write_one_into(self):
        columns = {row["name"] for row in
                   self.conn.execute("PRAGMA table_info(relationships)")}
        self.assertEqual(columns & {"credential", "token", "secret", "password"},
                         set())

    def test_the_public_view_carries_what_the_ui_renders_and_nothing_secret(self):
        self.pair()
        shown = pairing.describe(db.active_relationship(self.conn, self.workspace))
        for field in ("display_name", "address", "port", "fingerprint", "state"):
            self.assertIsNotNone(shown[field], f"the card renders {field}")
        self.assertNotIn("certificate_pem", shown)

    def test_revocation_fences_a_running_attempt_and_its_job(self):
        relationship_id = self.pair()
        job, attempt = self.running_attempt(relationship_id)
        self.assertEqual(
            db.fence_relationship_attempts(self.conn, relationship_id, db.new_id()),
            [attempt])
        row = self.conn.execute(
            "SELECT state, error_json FROM attempts WHERE attempt_id=?",
            (attempt,)).fetchone()
        self.assertEqual(row["state"], "interrupted")
        self.assertIn("revoked", row["error_json"])
        self.assertEqual(self.conn.execute(
            "SELECT state FROM jobs WHERE job_id=?", (job,)).fetchone()["state"],
            "interrupted")

    def test_a_revoked_relationship_is_kept_as_history_not_deleted(self):
        """Attempts reference it; deleting it would make a finished job look as
        if it had run nowhere."""
        relationship_id = self.pair()
        self.assertTrue(db.revoke_relationship(self.conn, relationship_id,
                                               self.workspace))
        self.assertIsNone(db.active_relationship(self.conn, self.workspace))
        self.assertEqual(
            db.get_relationship(self.conn, relationship_id,
                                self.workspace)["state"], "revoked")

    def test_a_revoked_relationship_is_never_routed_to(self):
        relationship_id = self.pair()
        db.revoke_relationship(self.conn, relationship_id, self.workspace)
        route = dispatch.choose_route(
            relationship=db.get_relationship(self.conn, relationship_id,
                                             self.workspace),
            node=node_record(), required=["text.generate"], model_id=None)
        self.assertFalse(route.remote)
        self.assertIn("revoked", route.reason)

    def test_another_workspace_cannot_read_the_relationship(self):
        relationship_id = self.pair()
        self.assertIsNone(db.get_relationship(self.conn, relationship_id,
                                              db.new_id()))


class TestDistributedSelftestVerdict(unittest.TestCase):
    """A distributed pass has to mean distributed execution passed.

    Uses a real coordinator over a temporary database, so the verdict is read
    from the attempt records the ordinary path writes rather than from a
    hand-made dictionary.
    """

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.coordinator = server.Coordinator(
            pathlib.Path(self._dir.name) / "state.db")

    def tearDown(self):
        self.coordinator.conn.close()
        self._dir.cleanup()

    def job_with(self, attempts: list, *, job_state: str = "completed") -> str:
        """Build one job and its attempts through the ordinary db helpers."""
        conn = self.coordinator.conn
        workspace = self.coordinator.workspace_id
        chat = db.create_chat(conn, workspace, "Connection self-test")
        job = db.create_job(conn, workspace_id=workspace, chat_id=chat,
                            request="self test")
        for following in ("context_preparing", "queued", "routing", "running"):
            db.set_job_state(conn, job, following)
        for where, state in attempts:
            # An explicit comparison: `"local"` is a truthy string, so testing
            # the tag for truthiness marked every attempt remote.
            relationship_id = db.new_id() if where == "remote" else None
            attempt = db.create_attempt(
                conn, job_id=job, node_id=db.new_id(),
                route_reason=("paired worker ubuntu-worker: healthy"
                              if where == "remote"
                              else "local coordinator: the paired worker was "
                                   "unavailable"))
            if relationship_id:
                db.set_attempt_relationship(conn, attempt, relationship_id)
            db.set_attempt_state(conn, attempt, "running")
            if state == "completed":
                db.set_attempt_state(conn, attempt, "validating")
                db.set_attempt_state(conn, attempt, "completed")
            elif state == "interrupted":
                db.set_attempt_state(conn, attempt, "interrupted", error={
                    "code": "worker_lost", "message": "the worker stopped",
                    "retryable": True})
        if job_state == "completed":
            db.set_job_state(conn, job, "validating")
            db.set_job_state(conn, job, "completed")
        else:
            db.set_job_state(conn, job, job_state)
        return job

    def test_a_remote_interruption_rescued_locally_does_not_pass(self):
        """THE false positive. The job completes because the local fallback
        answered, which proves the fallback works and says nothing about
        distributed execution."""
        job = self.job_with([("remote", "interrupted"), ("local", "completed")])
        result = self.coordinator.selftest_result(job)
        self.assertEqual(result["state"], "completed")
        self.assertFalse(result["passed"],
                         "a local rescue is not a distributed pass")
        self.assertTrue(result["fell_back"])

    def test_a_completed_remote_attempt_passes(self):
        job = self.job_with([("remote", "completed")])
        result = self.coordinator.selftest_result(job)
        self.assertTrue(result["passed"])
        self.assertFalse(result["fell_back"])

    def test_a_completed_remote_attempt_does_not_hide_a_failed_job(self):
        job = self.job_with([("remote", "completed")], job_state="failed")
        result = self.coordinator.selftest_result(job)
        self.assertTrue(result["finished"])
        self.assertFalse(result["passed"])

    def test_a_purely_local_run_does_not_pass(self):
        job = self.job_with([("local", "completed")])
        self.assertFalse(self.coordinator.selftest_result(job)["passed"])

    def test_every_attempt_is_reported_with_its_route_reason(self):
        """The UI's useful display survives the stricter verdict."""
        job = self.job_with([("remote", "interrupted"), ("local", "completed")])
        result = self.coordinator.selftest_result(job)
        self.assertEqual(len(result["attempts"]), 2)
        self.assertTrue(result["attempts"][0]["ran_remotely"])
        self.assertFalse(result["attempts"][1]["ran_remotely"])
        for attempt in result["attempts"]:
            self.assertTrue(attempt["route_reason"])
        self.assertIsNotNone(result["attempts"][0]["error"])

    def test_pod_readiness_stays_unobserved(self):
        """Refinix has no Kubernetes credential and must not acquire one to
        fill in a row."""
        job = self.job_with([("remote", "completed")])
        result = self.coordinator.selftest_result(job)
        self.assertIsNone(result["pod_readiness"])
        self.assertIn("Kubernetes", result["pod_readiness_note"])

    def test_the_self_test_uses_the_ordinary_submit_path(self):
        """A bypass would pass while the path it claims to test was broken."""
        source = pathlib.Path(server.__file__).read_text()
        body = source[source.index("def run_selftest"):
                      source.index("def selftest_result")]
        self.assertIn("self.submit(chat_id", body)
        for bypass in ("WorkerClient(", "build_envelope(", "consume("):
            self.assertNotIn(bypass, body,
                             "the self-test must not build its own path")


class TestAmbiguityNeverRunsLocally(unittest.TestCase):
    """End to end on a real coordinator: what an ambiguous send actually does.

    Classifying the exception correctly is only half of it; the handler that
    receives it has to refuse the fallback. These drive `_run_remote` on a
    temporary database and count the attempts left behind.
    """

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.coordinator = server.Coordinator(
            pathlib.Path(self._dir.name) / "state.db")
        conn, workspace = self.coordinator.conn, self.coordinator.workspace_id
        self.relationship = db.new_id()
        db.record_relationship(
            conn, relationship_id=self.relationship, workspace_id=workspace,
            node_id=NODE, display_name="ubuntu-worker", address="192.168.1.20",
            port=30443, fingerprint="AB:CD", certificate_pem="pem")
        self.chat = db.create_chat(conn, workspace, "t")
        self.job = db.create_job(conn, workspace_id=workspace,
                                 chat_id=self.chat, request="say something")
        for following in ("context_preparing", "queued", "routing", "running"):
            db.set_job_state(conn, self.job, following)
        self.attempt = db.create_attempt(
            conn, job_id=self.job, node_id=NODE,
            route_reason="paired worker ubuntu-worker: healthy")
        db.set_attempt_relationship(conn, self.attempt, self.relationship)
        db.set_attempt_state(conn, self.attempt, "running")
        self.route = dispatch.Route("remote", "paired worker: healthy",
                                    node_id=NODE,
                                    relationship_id=self.relationship,
                                    model=WORKER_PROFILE.model.model_dump(),
                                    profile=WORKER_PROFILE.model_dump())
        self.inference = inference()
        self.messages = [
            {"role": "system", "content": "You are Refinix."},
            {"role": "user", "content": "say something"},
        ]
        local_profile = profiles.PROFILES[0]
        self.coordinator.local_profile = lambda **_kwargs: local_profile

    def tearDown(self):
        self.coordinator.conn.close()
        self._dir.cleanup()

    def drive(self, error):
        class Client:
            def submit(self, envelope, key):
                raise error

        self.coordinator.worker_client = lambda relationship: Client()
        return self.coordinator._run_remote(
            self.job, self.chat, self.attempt, self.route, text="say something",
            messages=self.messages, inference=self.inference)

    def attempts(self):
        return [dict(row) for row in self.coordinator.conn.execute(
            "SELECT state, relationship_id, error_json FROM attempts"
            " WHERE job_id=? ORDER BY created_at", (self.job,))]

    def test_receipt_unknown_does_not_open_a_local_attempt(self):
        handled, *_ = self.drive(dispatch.ReceiptUnknown("no answer"))
        self.assertTrue(handled, "the job is finished, not continued locally")
        rows = self.attempts()
        self.assertEqual(len(rows), 1, "a second attempt would duplicate work")
        self.assertEqual(rows[0]["state"], "interrupted")
        self.assertEqual(json.loads(rows[0]["error_json"])["code"], "worker_lost")
        self.assertIn("may be", json.loads(rows[0]["error_json"])["message"])

    def test_a_definite_refusal_does_open_a_local_attempt(self):
        """Truthful fallback is preserved where non-acceptance is proven."""
        handled, replacement, *_ = self.drive(
            dispatch.DispatchUnavailable("the request never reached the worker"))
        self.assertFalse(handled, "the caller continues locally")
        rows = self.attempts()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["state"], "interrupted")
        self.assertIsNotNone(rows[0]["relationship_id"])
        self.assertIsNone(rows[1]["relationship_id"], "the retry runs here")
        self.assertEqual(replacement, [r for r in self.coordinator.conn.execute(
            "SELECT attempt_id FROM attempts WHERE job_id=? ORDER BY created_at",
            (self.job,))][1]["attempt_id"])

    def test_an_identity_mismatch_does_not_open_a_local_attempt(self):
        handled, *_ = self.drive(pairing.IdentityMismatch("identity changed"))
        self.assertTrue(handled)
        rows = self.attempts()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["state"], "failed")
        self.assertEqual(json.loads(rows[0]["error_json"])["code"],
                         "permission_denied")

    def test_receipt_unknown_is_handled_before_the_fallback_clause(self):
        """Source order matters here: `except DispatchUnavailable` earlier in
        the chain would swallow it if the classes were ever related."""
        source = pathlib.Path(server.__file__).read_text()
        body = source[source.index("def _run_remote"):
                      source.index("def _fallback")]
        self.assertLess(body.index("except dispatch.ReceiptUnknown"),
                        body.index("except (dispatch.DispatchUnavailable"))


class TestImageBuildRunsTheExecutorSuite(unittest.TestCase):
    """The operational runbook and image build retain the required suites."""

    def dockerfile(self) -> str:
        return (pathlib.Path(server.__file__).parents[2]
                / "backend/worker-image/Dockerfile").read_text()

    def test_the_build_runs_the_executor_suite(self):
        self.assertIn("backend.worker.test_executor", self.dockerfile())

    def test_the_build_runs_the_worker_application_suite(self):
        self.assertIn("backend.worker.test_worker_app", self.dockerfile())

    def test_the_test_stage_is_still_offline(self):
        """Adding a suite must not relax the network restriction."""
        for line in self.dockerfile().splitlines():
            if "python -m unittest" in line:
                self.assertIn("--network=none", self.dockerfile())

    def test_the_runbook_and_the_dockerfile_name_the_same_suites(self):
        runbook = (pathlib.Path(server.__file__).parents[2]
                   / "docs/worker-operations.md").read_text()
        for suite in ("backend.worker.test_worker_app",
                      "backend.worker.test_executor"):
            self.assertIn(suite, runbook)
            self.assertIn(suite, self.dockerfile())


if __name__ == "__main__":
    unittest.main(verbosity=2)
