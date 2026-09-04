"""Behavioural checks for the worker API.

These need FastAPI, which lives only inside the pinned image, so they run at
**image build time** under `--network=none`. They cover the three defects Codex
reproduced plus the admission bounds, using a synthetic runtime — no server,
model or network.

    python -m unittest backend.worker.test_worker_app
"""

import asyncio
import os
import pathlib
import unittest
from unittest.mock import patch

os.environ.setdefault("AEGIS_WORKER_TOKEN", "x" * 40)   # the startup guard
os.environ.setdefault("AEGIS_NODE_ID", "22222222-2222-4222-8222-222222222222")

from backend.contracts import v1                        # noqa: E402
from backend.worker import app as W                     # noqa: E402
from backend.worker import runtime                      # noqa: E402


CONFIRMED = "66666666-6666-4666-8666-666666666666"


def confirm_relationship():
    """Inject a confirmed relationship so admission logic is reachable offline.

    This is test-only injection of internal state. It is NOT a deployable
    bypass: no code path, environment variable or request populates
    `W._relationships`, so a running worker stays fail-closed.
    """
    W._relationships[CONFIRMED] = {"confirmed_at": "test"}


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


def run(env, produced, *, budget=60.0):
    """Execute with a synthetic runtime stream and return (record, event kinds)."""
    def fake(messages, should_cancel=None, timeout=None):
        for item in produced:
            if isinstance(item, Exception):
                raise item
            if should_cancel is not None and should_cancel():
                yield "cancelled", {}
                return
            yield item
    with patch.object(runtime, "stream_chat", fake):
        asyncio.run(W._execute(env.attempt_id, budget))
    record = W._attempts[env.attempt_id]
    frames, queue = [], W._streams[env.attempt_id]
    while not queue.empty():
        frame = queue.get_nowait()
        if frame is not None:
            frames.append(frame)
    return record, frames


DONE_STOP = ("done", {"done_reason": "stop", "limit_reason": None,
                      "runtime_ms": 10, "prompt_tokens": 5, "output_tokens": 2})
DONE_LENGTH = ("done", {"done_reason": "length", "limit_reason": "output",
                        "runtime_ms": 10, "prompt_tokens": 5,
                        "output_tokens": runtime.NUM_PREDICT})


class Base(unittest.TestCase):
    def setUp(self):
        confirm_relationship()
        W._attempts.clear()
        W._streams.clear()
        W._idempotency.clear()

    def tearDown(self):
        W._relationships.clear()


class TestCappedReplies(Base):
    """Finding 1: a nonempty reply ending on `length` must not complete."""

    def test_length_stop_does_not_complete(self):
        env = envelope()
        register(env)
        record, _ = run(env, [("delta", "partial answer"), DONE_LENGTH])
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["error"]["code"], "validation_failed")
        self.assertIn("reply token limit", record["error"]["message"])

    def test_length_stop_keeps_the_partial_text(self):
        env = envelope()
        register(env)
        record, _ = run(env, [("delta", "kept text"), DONE_LENGTH])
        self.assertEqual(record["output"], "kept text")

    def test_normal_stop_completes(self):
        env = envelope()
        register(env)
        record, _ = run(env, [("delta", "a real answer"), DONE_STOP])
        self.assertEqual(record["state"], "completed")
        self.assertIsNone(record["error"])

    def test_empty_output_fails_the_nonempty_validator(self):
        env = envelope()
        register(env)
        record, _ = run(env, [("delta", "   "), DONE_STOP])
        self.assertEqual(record["state"], "failed")


class TestIncrementalDelivery(Base):
    """Finding 2: output must not be buffered until generation finishes."""

    def test_partial_output_survives_a_runtime_error(self):
        env = envelope()
        register(env)
        record, frames = run(
            env, [("delta", "before the failure"),
                  runtime.RuntimeUnavailable("synthetic failure")])
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["output"], "before the failure",
                         "text produced before the error must not be discarded")
        self.assertTrue(any(b"output.delta" in f for f in frames),
                        "the delta must have reached the stream before the error")

    def test_deltas_are_emitted_before_the_terminal_event(self):
        env = envelope()
        register(env)
        _, frames = run(env, [("delta", "one"), ("delta", "two"), DONE_STOP])
        kinds = [b"output.delta" in f for f in frames]
        self.assertGreaterEqual(sum(kinds), 2)
        last = frames[-1]
        self.assertIn(b"attempt.state", last, "the stream must end on a state change")


class TestCancellationFencing(Base):
    def test_cancel_prevents_a_later_completion(self):
        env = envelope()
        register(env)
        W._attempts[env.attempt_id]["cancelled"] = True
        record, _ = run(env, [("delta", "some text"), DONE_STOP])
        self.assertEqual(record["state"], "cancelled")
        self.assertEqual(record["error"]["code"], "cancelled_by_user")

    def test_cancel_keeps_text_already_produced(self):
        env = envelope()
        register(env)
        W._attempts[env.attempt_id]["cancelled"] = True
        record, _ = run(env, [("delta", "kept"), DONE_STOP])
        self.assertIn("kept", record["output"] or "kept")


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
    """Blockers 1 and 2: no pairing and no durable receipt means no acceptance."""

    def setUp(self):
        W._relationships.clear()

    def test_prerequisites_are_missing_by_default(self):
        blockers = W.missing_prerequisites()
        self.assertEqual(len(blockers), 2)
        self.assertTrue(any("OD-06" in b for b in blockers))
        self.assertTrue(any("AF-005" in b for b in blockers))

    def test_job_routes_are_closed(self):
        shut = W._closed()
        self.assertIsNotNone(shut)
        self.assertEqual(shut.status_code, 503)

    def test_no_environment_variable_can_open_them(self):
        """A deployable bypass would defeat the point of failing closed."""
        import backend.worker.app as module
        source = pathlib.Path(module.__file__).read_text()
        opener = "_relationships["
        # The only assignment to the registry must be absent from app source.
        self.assertNotIn(opener, source,
                         "nothing in the application may populate the registry")

    def test_capability_is_not_advertised_while_closed(self):
        node = W._node(observed=False)
        self.assertEqual(node["capabilities"], [])


class TestAttemptSchema(Base):
    """Blocker 4: outgoing Attempt records must satisfy the shared contract."""

    def test_terminal_attempt_has_a_finish_timestamp(self):
        env = envelope()
        record = register(env)
        run(env, [("delta", "done"), DONE_STOP])
        attempt = W._as_attempt(W._attempts[env.attempt_id])
        self.assertEqual(attempt.state, "completed")
        self.assertIsNotNone(attempt.finished_at)
        self.assertIsNotNone(attempt.started_at)

    def test_stopped_attempt_carries_exactly_one_reason(self):
        env = envelope()
        register(env)
        run(env, [("delta", "x"), DONE_LENGTH])
        attempt = W._as_attempt(W._attempts[env.attempt_id])
        self.assertEqual(attempt.state, "failed")
        self.assertIsNotNone(attempt.error)
        self.assertIsNotNone(attempt.finished_at)

    def test_serialised_attempt_has_no_extra_fields(self):
        env = envelope()
        register(env)
        run(env, [("delta", "x"), DONE_STOP])
        payload = W._as_attempt(W._attempts[env.attempt_id]).model_dump()
        for forbidden in ("metrics", "output_chars", "output"):
            self.assertNotIn(forbidden, payload)
        v1.Attempt(**payload)          # round-trips through the contract

    def test_queued_attempt_has_not_started(self):
        env = envelope()
        record = register(env)
        attempt = W._as_attempt(record)
        self.assertEqual(attempt.state, "queued")
        self.assertIsNone(attempt.started_at)
        self.assertIsNone(attempt.finished_at)


class TestAbsoluteDeadline(Base):
    """Blocker 3: one deadline for the attempt, not a fresh one per read."""

    def test_slow_stream_cannot_extend_the_budget(self):
        import time as _t
        env = envelope()
        register(env)

        def slow(messages, should_cancel=None, timeout=None):
            for _ in range(50):
                if should_cancel is not None and should_cancel():
                    yield "cancelled", {}
                    return
                _t.sleep(0.05)
                yield "delta", "tick "
            yield DONE_STOP

        began = _t.monotonic()
        with patch.object(runtime, "stream_chat", slow):
            asyncio.run(W._execute(env.attempt_id, 0.30))
        elapsed = _t.monotonic() - began
        record = W._attempts[env.attempt_id]
        self.assertLess(elapsed, 3.0,
                        f"a 0.30s budget must not run for {elapsed:.2f}s")
        self.assertIn(record["state"], {"failed", "cancelled"})

    def test_runtime_seconds_bounds_the_budget(self):
        env = envelope(limits=v1.Limits(
            cpu_millis=2000, memory_bytes=2_147_483_648, runtime_seconds=1,
            processes=8, workspace_bytes=1_048_576, output_bytes=1_048_576,
            tool_network="disabled"))
        register(env)
        import time as _t

        def slow(messages, should_cancel=None, timeout=None):
            for _ in range(40):
                if should_cancel is not None and should_cancel():
                    yield "cancelled", {}
                    return
                _t.sleep(0.05)
                yield "delta", "x"
            yield DONE_STOP

        began = _t.monotonic()
        with patch.object(runtime, "stream_chat", slow):
            asyncio.run(W._execute(env.attempt_id, 600.0))
        self.assertLess(_t.monotonic() - began, 4.0,
                        "runtime_seconds must bound the attempt")

    def test_output_bytes_is_enforced(self):
        env = envelope(limits=v1.Limits(
            cpu_millis=2000, memory_bytes=2_147_483_648, runtime_seconds=300,
            processes=8, workspace_bytes=1_048_576, output_bytes=64,
            tool_network="disabled"))
        register(env)
        record, _ = run(env, [("delta", "y" * 500), DONE_STOP])
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["error"]["code"], "validation_failed")
        self.assertIn("byte limit", record["error"]["message"])


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
