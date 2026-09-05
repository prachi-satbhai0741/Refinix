"""Behavioural checks for the worker API.

These need FastAPI, which lives only inside the pinned image, so the
authoritative run is at **image build time** under `--network=none`. No server,
model or network.

They can also be run on a machine without FastAPI by calling the route
coroutines directly against a minimal stand-in for `fastapi` — enough to import
the module and invoke the routes. That checks route logic only: no HTTP, no
request validation, no serialisation. A pass there is not evidence the service
works, and the image build remains the run that counts.

Execution moved to `backend.worker.executor` at C06 — the API enqueues and the
executor Pod runs the work — so the streaming, budget and cancellation checks
that used to live here now exercise the code that actually runs, in
`backend/worker/test_executor.py`. What remains here is the API's own job:
authority, admission, the durable receipt, and the contract shape of what it
returns.

    python -m unittest backend.worker.test_worker_app
"""

import asyncio
import os
import pathlib
import tempfile
import unittest

os.environ.setdefault("AEGIS_WORKER_TOKEN", "x" * 40)   # the startup guard
os.environ.setdefault("AEGIS_NODE_ID", "22222222-2222-4222-8222-222222222222")

from backend.contracts import v1                        # noqa: E402
from backend.worker import app as W                     # noqa: E402
from backend.worker import pairing as pairing_module    # noqa: E402
from backend.worker import runtime                      # noqa: E402
from backend.worker.test_executor import FakeRedis      # noqa: E402
from backend.worker.dispatch import DispatchQueue       # noqa: E402


CONFIRMED = "66666666-6666-4666-8666-666666666666"
WORKSPACE = "77777777-7777-4777-8777-777777777777"
CREDENTIAL = "test-relationship-credential-not-a-real-secret"


def confirm_relationship(store):
    """Insert a relationship the way pairing does: code, then redemption.

    Deliberately not a direct write into a registry. Going through
    `issue_code`/`redeem` means these tests cannot pass while the real pairing
    path is broken, and it keeps the credential a hash on disk here too.
    """
    code = store.issue_code()
    return store.redeem(code, relationship_id=CONFIRMED, workspace_id=WORKSPACE)


def envelope(**over):
    import time
    import uuid
    nid = lambda: str(uuid.uuid4())                      # noqa: E731
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    later = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 600))
    fields = dict(
        contract_version="1.0", workspace_id=nid(), workflow_id=nid(), job_id=nid(),
        step_id=nid(), attempt_id=nid(), chat_id=nid(),
        # A remote dispatch must carry a relationship: the contract enforces it.
        coordinator_node_id=nid(), target_node_id=W.NODE_ID,
        relationship_id=CONFIRMED,
        original_request="say something", task_type="chat",
        required_capabilities=["text.generate"], context=[], attachments=[],
        allowed_tools=[],
        limits=v1.Limits(cpu_millis=2000, memory_bytes=2_147_483_648,
                         runtime_seconds=300, processes=8, workspace_bytes=1_048_576,
                         output_bytes=1_048_576, tool_network="disabled"),
        output=v1.OutputContract(kind="text", validators=["text.nonempty"],
                                 schema_ref=None),
        approval_policy="coordinator-default-v1", created_at=now,
        deadline_at=later, cancel_requested=False)
    fields.update(over)
    return v1.JobEnvelope(**fields)


def register(env):
    """Uses the application's own registration so tests cannot drift from it."""
    return W.register(env)

class Base(unittest.TestCase):
    """Each test gets its own pairing file and its own fake Redis, so nothing
    leaks between them and no test can pass because another one paired."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.store = pairing_module.PairingStore(
            pathlib.Path(self._dir.name) / "pairing.json")
        self.credential = confirm_relationship(self.store)
        self.redis = FakeRedis()
        W._pairing = self.store
        W._receipt_backend = DispatchQueue(self.redis)

    def tearDown(self):
        W._pairing = pairing_module.PairingStore(
            pathlib.Path(self._dir.name) / "empty.json")
        W._receipt_backend = None
        self._dir.cleanup()


class TestAdmission(Base):
    """Finding 3: refuse what cannot be executed, rather than ignoring it."""

    def test_unsupported_task_type(self):
        self.assertIsNotNone(W._unsupported(envelope(task_type="documents")))

    def test_unsupported_capability(self):
        self.assertIsNotNone(
            W._unsupported(envelope(required_capabilities=["document.extract"])))

    def test_unsupported_output_kind(self):
        self.assertIsNotNone(W._unsupported(envelope(
            output=v1.OutputContract(kind="docx",
                                     validators=["document.readable"],
                                     schema_ref=None))))

    def test_context_package_is_refused(self):
        ref = v1.ResourceRef(resource_id="33333333-3333-4333-8333-333333333333",
                             sha256="a" * 64, size_bytes=10, media_type="text/plain")
        self.assertIsNotNone(W._unsupported(envelope(context=[ref])))

    def test_envelope_for_another_node_is_refused(self):
        self.assertIsNotNone(W._unsupported(
            envelope(target_node_id="44444444-4444-4444-8444-444444444444")))

    def test_relationship_is_required_on_a_remote_dispatch(self):
        """The worker cannot verify a relationship until OD-06, but an absent
        one is refused rather than treated as trusted."""
        # model_copy skips validation while keeping nested records intact, so
        # the worker's own check is what gets exercised.
        env = envelope().model_copy(update={"relationship_id": None})
        self.assertIsNotNone(W._unsupported(env))

    def test_supported_envelope_is_accepted(self):
        self.assertIsNone(W._unsupported(envelope()))


class TestIdentityAndGuards(Base):
    def test_node_identity_is_not_the_shared_placeholder(self):
        self.assertNotEqual(W.NODE_ID, "00000000-0000-4000-8000-000000000000")

    def test_unknown_health_carries_no_measurements(self):
        node = W._node(observed=False)
        self.assertEqual(node["health"], "unknown")
        self.assertIsNone(node["observed_at"])
        self.assertIsNone(node["queue_depth"])
        self.assertEqual(node["models"], [])

    def test_missing_credential_is_rejected(self):
        self.assertIsNotNone(W._guard(None, "1.0"))
        self.assertIsNotNone(W._guard("Bearer wrong", "1.0"))

    def test_contract_header_is_required_and_checked(self):
        good = "Bearer " + os.environ["AEGIS_WORKER_TOKEN"]
        self.assertIsNotNone(W._guard(good, None))
        self.assertIsNotNone(W._guard(good, "9.9"))
        self.assertIsNone(W._guard(good, v1.CONTRACT_VERSION))


if __name__ == "__main__":
    unittest.main(verbosity=2)



class TestFailClosed(unittest.TestCase):
    """No pairing and no reachable receipt backend means no acceptance."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        W._pairing = pairing_module.PairingStore(
            pathlib.Path(self._dir.name) / "pairing.json")
        W._receipt_backend = None

    def tearDown(self):
        self._dir.cleanup()

    def test_prerequisites_are_missing_by_default(self):
        blockers = W.missing_prerequisites()
        self.assertEqual(len(blockers), 2)
        self.assertTrue(any("OD-06" in b for b in blockers))
        self.assertTrue(any("AF-005" in b for b in blockers))

    def test_job_routes_are_closed(self):
        shut = W._closed()
        self.assertIsNotNone(shut)
        self.assertEqual(shut.status_code, 503)

    def test_an_unreachable_queue_closes_them_again(self):
        """A Redis that answered at startup and is gone now must close the
        routes, not queue into nothing."""
        W._pairing.redeem(W._pairing.issue_code(), relationship_id=CONFIRMED,
                          workspace_id=WORKSPACE)
        W._receipt_backend = DispatchQueue(FakeRedis(reachable=False))
        blockers = W.missing_prerequisites()
        self.assertEqual(len(blockers), 1)
        self.assertIn("reachable", blockers[0])
        self.assertIsNotNone(W._closed())

    def test_the_registry_cannot_be_populated_from_application_source(self):
        """Pairing state must come from a redeemed code, never from a literal
        or an environment variable in the application."""
        import backend.worker.app as module
        source = pathlib.Path(module.__file__).read_text()
        self.assertNotIn("_pairing._state", source)
        self.assertNotIn("relationships[", source)

    def test_capability_is_not_advertised_while_closed(self):
        node = W._node(observed=False)
        self.assertEqual(node["capabilities"], [])


class TestPairingRoutes(Base):
    """OD-06 over HTTP: a code buys one credential, and only its owner revokes."""

    def test_a_credential_authorises_only_its_own_relationship(self):
        record = W._identify(self.credential)
        self.assertIsNotNone(record)
        self.assertEqual(record["relationship_id"], CONFIRMED)
        self.assertEqual(record["workspace_id"], WORKSPACE)

    def test_the_bootstrap_token_cannot_dispatch(self):
        """It is mounted for kubelet probes and is visible to anything that can
        read the Secret reference; letting it submit work would make pairing
        decorative."""
        record, refusal = W._job_guard(f"Bearer {W._CREDENTIAL}", "1.0")
        self.assertIsNone(record)
        self.assertEqual(refusal.status_code, 401)

    def test_the_bootstrap_token_still_answers_preflight(self):
        self.assertIsNone(W._guard(f"Bearer {W._CREDENTIAL}", "1.0"))

    def test_an_unknown_credential_is_refused_on_both_surfaces(self):
        self.assertIsNotNone(W._guard("Bearer nope", "1.0"))
        self.assertIsNotNone(W._job_guard("Bearer nope", "1.0")[1])

    def test_a_revoked_credential_stops_working_immediately(self):
        self.store.revoke(CONFIRMED)
        self.assertIsNone(W._identify(self.credential))
        self.assertIsNotNone(W._job_guard(f"Bearer {self.credential}", "1.0")[1])



class TestDurableReceipt(Base):
    """AF-005: nothing returns 202 unless the envelope is in the stream."""

    def submit(self, env, key=None, credential=None):
        import json as _json
        body = env.model_dump_json().encode()

        class Request:
            async def stream(self):
                yield body

        return asyncio.run(W.submit(
            Request(), authorization=f"Bearer {credential or self.credential}",
            x_aegisforge_contract="1.0",
            idempotency_key=key or "11111111-1111-4111-8111-111111111111",
            content_type="application/json", content_encoding=None))

    def test_the_envelope_is_enqueued_before_the_202(self):
        env = envelope(relationship_id=CONFIRMED, workspace_id=WORKSPACE)
        response = self.submit(env)
        self.assertEqual(response.status_code, 202)
        stream = self.redis.streams[v1.redis_key("dispatch", CONFIRMED)]
        self.assertEqual(len(stream), 1)
        self.assertEqual(stream[0][1]["attempt_id"], env.attempt_id)

    def test_a_failed_enqueue_does_not_return_202(self):
        self.redis.fail_writes = True
        env = envelope(relationship_id=CONFIRMED, workspace_id=WORKSPACE)
        response = self.submit(env)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            self.redis.streams.get(v1.redis_key("dispatch", CONFIRMED), []), [],
            "a failed enqueue must leave nothing queued")

    def test_a_replayed_key_returns_the_same_attempt(self):
        """The retry after a lost response. It must replay the original
        receipt, not be refused as a duplicate."""
        env = envelope(relationship_id=CONFIRMED, workspace_id=WORKSPACE)
        first = self.submit(env)
        second = self.submit(env)
        self.assertEqual(second.status_code, 202)
        self.assertEqual(first.body, second.body)
        self.assertEqual(len(self.redis.streams[v1.redis_key("dispatch", CONFIRMED)]), 1)

    def test_a_reused_key_with_a_different_body_conflicts(self):
        key = "22222222-2222-4222-8222-222222222222"
        self.submit(envelope(relationship_id=CONFIRMED, workspace_id=WORKSPACE), key)
        response = self.submit(
            envelope(relationship_id=CONFIRMED, workspace_id=WORKSPACE,
                     original_request="different"), key)
        self.assertEqual(response.status_code, 409)

    def test_an_envelope_for_another_relationship_is_refused(self):
        other = "88888888-8888-4888-8888-888888888888"
        code = self.store.issue_code()
        second = self.store.redeem(code, relationship_id=other,
                                   workspace_id=WORKSPACE)
        env = envelope(relationship_id=CONFIRMED, workspace_id=WORKSPACE)
        response = self.submit(env, credential=second)
        self.assertEqual(response.status_code, 403)

    def test_an_envelope_for_another_workspace_is_refused(self):
        env = envelope(relationship_id=CONFIRMED,
                       workspace_id="99999999-9999-4999-8999-999999999999")
        self.assertEqual(self.submit(env).status_code, 403)


class TestAttemptSchema(Base):
    """Outgoing Attempt records must satisfy the shared contract.

    Reconstructed from the envelope plus the observed state rather than
    remembered, which is what lets a restarted API answer for work it never
    admitted.
    """

    def test_a_queued_attempt_has_not_started(self):
        attempt = W._attempt_record(envelope(), "queued")
        self.assertEqual(attempt.state, "queued")
        self.assertIsNone(attempt.started_at)
        self.assertIsNone(attempt.finished_at)

    def test_a_terminal_attempt_carries_a_finish_and_one_reason(self):
        for state in ("completed", "failed", "cancelled", "interrupted"):
            with self.subTest(state=state):
                attempt = W._attempt_record(envelope(), state)
                self.assertIsNotNone(attempt.finished_at)
                if state == "completed":
                    self.assertIsNone(attempt.error)
                else:
                    self.assertIsNotNone(attempt.error)

    def test_a_failure_never_claims_the_user_cancelled_it(self):
        """The contract forbids that pairing outright."""
        self.assertNotEqual(W._attempt_record(envelope(), "failed").error.code,
                            "cancelled_by_user")

    def test_the_record_has_no_extra_fields(self):
        payload = W._attempt_record(envelope(), "completed").model_dump()
        for forbidden in ("metrics", "output_chars", "output", "envelope"):
            self.assertNotIn(forbidden, payload)
        v1.Attempt(**payload)          # round-trips through the contract


class TestRestartRecovery(Base):
    """Redis holds the receipt, so the routes answer after the Pod restarts.

    The dictionary these routes used to consult is empty in a fresh process
    while the work is still running, and every job route answered 404 for it.
    """

    def submit(self, env, key=None):
        import json as _json
        body = env.model_dump_json().encode()

        class Request:
            async def stream(self):
                yield body

        return asyncio.run(W.submit(
            Request(), authorization=f"Bearer {self.credential}",
            x_aegisforge_contract="1.0",
            idempotency_key=key or env.attempt_id,
            content_type="application/json", content_encoding=None))

    def restart(self):
        """Everything a Pod restart destroys: the process, not Redis."""
        W._receipt_backend = DispatchQueue(self.redis)

    def call(self, coroutine):
        return asyncio.run(coroutine)

    def test_poll_answers_after_a_restart(self):
        env = envelope(relationship_id=CONFIRMED, workspace_id=WORKSPACE)
        self.assertEqual(self.submit(env).status_code, 202)
        self.restart()
        response = self.call(W.poll(
            env.job_id, attempt_id=env.attempt_id,
            authorization=f"Bearer {self.credential}",
            x_aegisforge_contract="1.0"))
        self.assertEqual(response.status_code, 200)

    def test_cancel_reaches_redis_after_a_restart(self):
        env = envelope(relationship_id=CONFIRMED, workspace_id=WORKSPACE)
        self.submit(env)
        self.restart()
        response = self.call(W.cancel(
            env.job_id, attempt_id=env.attempt_id,
            authorization=f"Bearer {self.credential}",
            x_aegisforge_contract="1.0"))
        self.assertEqual(response.status_code, 202)
        self.assertIsNotNone(self.redis.get(
            v1.redis_key("cancel", CONFIRMED, env.attempt_id)))

    def test_an_attempt_that_was_never_admitted_is_still_unknown(self):
        env = envelope(relationship_id=CONFIRMED, workspace_id=WORKSPACE)
        self.restart()
        response = self.call(W.poll(
            env.job_id, attempt_id=env.attempt_id,
            authorization=f"Bearer {self.credential}",
            x_aegisforge_contract="1.0"))
        self.assertEqual(response.status_code, 404)

    def test_another_relationship_cannot_read_this_attempt(self):
        env = envelope(relationship_id=CONFIRMED, workspace_id=WORKSPACE)
        self.submit(env)
        other = "88888888-8888-4888-8888-888888888888"
        second = self.store.redeem(self.store.issue_code(),
                                   relationship_id=other,
                                   workspace_id=WORKSPACE)
        self.restart()
        response = self.call(W.poll(
            env.job_id, attempt_id=env.attempt_id,
            authorization=f"Bearer {second}", x_aegisforge_contract="1.0"))
        self.assertEqual(response.status_code, 404)

    def test_more_than_two_sequential_attempts_are_admitted(self):
        """MAX_ACTIVE is 2. Capacity is derived from Redis, so a completed
        attempt must stop holding a slot."""
        from backend.worker.test_executor import DONE_STOP, fake_stream
        from backend.worker import executor as executor_module
        from backend.worker.dispatch import ExecutorSession
        from backend.worker import runtime as worker_runtime
        from unittest.mock import patch

        session = ExecutorSession(self.redis, CONFIRMED, "consumer-a")
        worker = executor_module.Executor(session, node_id=W.NODE_ID)
        for index in range(4):
            env = envelope(relationship_id=CONFIRMED, workspace_id=WORKSPACE,
                           target_node_id=W.NODE_ID)
            self.assertEqual(self.submit(env).status_code, 202,
                             f"attempt {index} was refused for capacity")
            session.claim(env.attempt_id, 0)
            with patch.object(worker_runtime, "stream_chat",
                              fake_stream([("delta", "hi"), DONE_STOP])):
                worker.execute(env, 0)
            session.release(env.attempt_id, 0)


class TestIdempotencyKeys(Base):
    """Blocker 5: keys are UUIDv4 and scoped to the relationship."""

    def test_arbitrary_strings_are_rejected(self):
        env = envelope()
        for bad in (None, "", "short", "x" * 40, "not-a-uuid-at-all"):
            with self.assertRaises(Exception, msg=f"{bad!r} must be rejected"):
                W.idempotency_scope(bad, env)

    def test_uuid4_is_accepted(self):
        import uuid as _u
        self.assertEqual(len(W.idempotency_scope(str(_u.uuid4()), envelope())), 64)

    def test_scope_includes_the_relationship(self):
        import uuid as _u
        key = str(_u.uuid4())
        a = envelope()
        b = a.model_copy(update={"relationship_id": str(_u.uuid4())})
        self.assertNotEqual(W.idempotency_scope(key, a),
                            W.idempotency_scope(key, b),
                            "the same key under a different relationship must not collide")

    def test_scope_includes_the_resource(self):
        import uuid as _u
        key = str(_u.uuid4())
        self.assertNotEqual(W.idempotency_scope(key, envelope()),
                            W.idempotency_scope(key, envelope()))
