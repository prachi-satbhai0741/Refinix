"""Offline checks for AF-005 dispatch, the executor, and OD-06 pairing state.

Standard library and the shared contract only — no FastAPI, no Redis, no model,
no network — so these run on the coordinator as well as inside the image.

`FakeRedis` is a **stateful** fake, not a stub: it keeps streams, consumer
groups, a pending-entries list with idle times, and key expiry, because the
behaviours under test are exactly the ones a return-value stub would paper over
— a killed consumer leaving recoverable work, a lease that another executor can
take once it expires, an event log that was trimmed away. It is not evidence
that a real Redis behaves this way; it is evidence that this code does what it
claims *given* the documented Redis semantics.

    python -m unittest backend.worker.test_executor
"""

from __future__ import annotations

import pathlib
import time
import unittest
import uuid
from unittest.mock import patch

from backend.contracts import profiles, v1
from backend.worker import executor as executor_module
from backend.worker import pairing as pairing_module
from backend.worker import runtime
from backend.worker import dispatch as dispatch_module
from backend.worker.dispatch import DispatchError, DispatchQueue, ExecutorSession
from backend.worker.redis_client import RedisUnavailable

NODE = "22222222-2222-4222-8222-222222222222"
RELATIONSHIP = "66666666-6666-4666-8666-666666666666"
WORKSPACE = "77777777-7777-4777-8777-777777777777"
PROFILE = next(
    profile for profile in profiles.PROFILES
    if profile.target_profile_id == profiles.UBUNTU_VICTUS_RTX2050
    and profile.workflow_mode == profiles.CHAT
    and profile.model.runtime_version == "0.33.2")
INFERENCE = profiles.request(
    PROFILE, reasoning="disabled", decoder="text",
    context_window=4096, output_allowance=2048)


# --------------------------------------------------------------- the fake ---

class FakeRedis:
    """Enough Redis to be wrong in the same places a real one would be."""

    def __init__(self, *, reachable: bool = True):
        self.reachable = reachable
        self.fail_writes = False
        # Redis executes the script and the connection dies before the reply
        # arrives. The mutation happens; the client never learns it did.
        self.lose_reply_after_commit = False
        self.reads_fail = False
        self.streams: dict[str, list] = {}
        self.keys: dict[str, tuple[str, float | None]] = {}
        self.groups: dict[str, dict] = {}       # key -> {consumer: [(id, claimed_at)]}
        self.clock = time.time()
        self._counter = 0

    # -- helpers the tests drive
    def advance(self, seconds: float) -> None:
        """Move the fake clock. Lease expiry and idle time are the whole point
        of several checks, and sleeping for 30 real seconds is not a test."""
        self.clock += seconds

    def _now(self) -> float:
        return self.clock

    def _alive(self, key: str):
        record = self.keys.get(key)
        if record is None:
            return None
        value, expires = record
        if expires is not None and expires <= self._now():
            del self.keys[key]
            return None
        return value

    def _guard(self):
        if not self.reachable:
            raise RedisUnavailable("fake redis is unreachable")

    def _read_guard(self):
        self._guard()
        if self.reads_fail:
            raise RedisUnavailable("fake redis lost the connection on a read")

    def _write_guard(self):
        self._guard()
        if self.fail_writes:
            raise RedisUnavailable("fake redis refuses writes")

    # -- the client surface
    def ping(self) -> bool:
        return self.reachable

    def xadd(self, key, fields, *, maxlen=None):
        self._write_guard()
        self._counter += 1
        entry_id = f"{int(self._now() * 1000)}-{self._counter}"
        stream = self.streams.setdefault(key, [])
        stream.append((entry_id, dict(fields)))
        if maxlen is not None and len(stream) > maxlen:
            del stream[:len(stream) - maxlen]
        return entry_id

    def xgroup_create(self, key, group, *, start="0"):
        self._guard()
        self.streams.setdefault(key, [])
        created = key not in self.groups
        self.groups.setdefault(key, {"delivered": 0, "pending": {}})
        return created

    def xreadgroup(self, key, group, consumer, *, count=1, block_ms=0, last=">"):
        self._guard()
        state = self.groups.setdefault(key, {"delivered": 0, "pending": {}})
        stream = self.streams.get(key, [])
        out = []
        while state["delivered"] < len(stream) and len(out) < count:
            entry = stream[state["delivered"]]
            state["delivered"] += 1
            state["pending"][entry[0]] = (consumer, self._now())
            out.append(entry)
        return out

    def xack(self, key, group, entry_id):
        self._guard()
        state = self.groups.setdefault(key, {"delivered": 0, "pending": {}})
        return 1 if state["pending"].pop(entry_id, None) else 0

    def xautoclaim(self, key, group, consumer, min_idle_ms, *, start="0-0", count=8):
        self._guard()
        state = self.groups.setdefault(key, {"delivered": 0, "pending": {}})
        by_id = dict(self.streams.get(key, []))
        claimed = []
        for entry_id, (owner, since) in sorted(state["pending"].items()):
            if len(claimed) >= count:
                break
            if (self._now() - since) * 1000 < min_idle_ms:
                continue
            state["pending"][entry_id] = (consumer, self._now())
            claimed.append((entry_id, by_id.get(entry_id, {})))
        return claimed

    def xlen(self, key):
        self._guard()
        return len(self.streams.get(key, []))

    def xrange(self, key, start="-", end="+", *, count=None):
        self._read_guard()
        entries = list(self.streams.get(key, []))
        return entries[:count] if count else entries

    def set(self, key, value, *, nx=False, ex=None):
        self._write_guard()
        if nx and self._alive(key) is not None:
            return False
        self.keys[key] = (value, None if ex is None else self._now() + ex)
        return True

    def get(self, key):
        self._read_guard()
        return self._alive(key)

    def delete(self, *keys):
        self._guard()
        return sum(1 for key in keys if self.keys.pop(key, None) is not None)

    def expire(self, key, seconds):
        self._guard()
        record = self.keys.get(key)
        if record is None:
            return False
        self.keys[key] = (record[0], self._now() + seconds)
        return True

    def eval(self, script, keys, args):
        """Reproduce each script's effect atomically — it does not run Lua.

        Recognising the three scripts by identity rather than interpreting them
        is deliberate: a Lua interpreter here would be a second implementation
        that can drift from Redis's, and the property under test is that the
        check and the write cannot be separated, not that the Lua parses. The
        real scripts are still exercised against a real Redis at the device
        gate.
        """
        self._write_guard()
        if script is dispatch_module.COMMIT_DISPATCH:
            maxlen, envelope, attempt_id, epoch, enqueued, record, ttl = args
            entry = self.xadd(keys[0], {"envelope": envelope,
                                        "attempt_id": attempt_id,
                                        "epoch": epoch,
                                        "enqueued_at": enqueued},
                              maxlen=int(maxlen))
            self.set(keys[1], record, ex=int(ttl))
            if self.lose_reply_after_commit:
                # Committed. The caller will never hear so.
                raise RedisUnavailable("redis closed the connection")
            return entry.encode()
        if script is dispatch_module.EXTEND_LEASE:
            owner, lease_ttl, stamp, beat_ttl = args
            if self._alive(keys[0]) != owner:
                return 0
            self.expire(keys[0], int(lease_ttl))
            self.set(keys[1], stamp, ex=int(beat_ttl))
            return 1
        if script is dispatch_module.RELEASE_LEASE:
            if self._alive(keys[0]) != args[0]:
                return 0
            self.delete(keys[0], keys[1])
            return 1
        raise AssertionError("unrecognised script; teach the fake about it")


def envelope(**over) -> v1.JobEnvelope:
    nid = lambda: str(uuid.uuid4())                          # noqa: E731
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    later = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 600))
    fields = dict(
        contract_version=v1.CONTRACT_VERSION, workspace_id=WORKSPACE,
        workflow_id=nid(),
        job_id=nid(), step_id=nid(), attempt_id=nid(), chat_id=nid(),
        coordinator_node_id=nid(), target_node_id=NODE,
        relationship_id=RELATIONSHIP, original_request="say something",
        messages=[v1.InferenceMessage(role="system", content="You are Refinix."),
                  v1.InferenceMessage(role="user", content="say something")],
        task_type="chat", required_capabilities=["text.generate"], context=[],
        model=PROFILE.model, inference=INFERENCE,
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
    if "messages" not in over and fields["task_type"] == "chat":
        fields["messages"] = [
            v1.InferenceMessage(role="system", content="You are Refinix."),
            v1.InferenceMessage(role="user", content=fields["original_request"]),
        ]
    return v1.JobEnvelope(**fields)


METRICS = {
    "requested_profile_id": PROFILE.profile_id,
    "actual_profile_id": PROFILE.profile_id,
    "context_window": 4096,
    "output_token_limit": 2048,
    "reasoning": "disabled",
    "decoder": "text",
    "prompt_tokens": 10,
    "output_tokens": 5,
    "runtime_ms": 10,
}
DONE_STOP = ("done", {**METRICS, "done_reason": "stop", "limit_reason": None})
DONE_LENGTH = ("done", {**METRICS, "done_reason": "length",
                        "limit_reason": "output"})


def fake_stream(items):
    def stream(messages, should_cancel=None, timeout=None, **_options):
        for item in items:
            if isinstance(item, Exception):
                raise item
            if should_cancel is not None and should_cancel():
                yield "cancelled", {}
                return
            yield item
    return stream


class Base(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.session = ExecutorSession(self.redis, RELATIONSHIP, "consumer-a")
        self.executor = executor_module.Executor(self.session, node_id=NODE)
        self.queue = DispatchQueue(self.redis)
        self._profile = patch.object(
            runtime, "resolve_profile",
            side_effect=lambda profile_id: PROFILE
            if profile_id == PROFILE.profile_id else None)
        self._profile.start()
        self.addCleanup(self._profile.stop)

    def events(self, attempt_id) -> list:
        return self.queue.read_events(RELATIONSHIP, attempt_id)

    def admitted_events(self, attempt_id) -> list:
        return self.queue.read_events(RELATIONSHIP, attempt_id, admitted=True)

    def states(self, attempt_id) -> list:
        return [e["data"]["current"] for e in self.events(attempt_id)
                if e["data"]["kind"] == "attempt.state"]

    def run_with(self, env, items, *, claim=True):
        """Run one attempt the way `_handle` does: claim the lease first.

        Without the claim, `should_cancel` correctly sees a lease it does not
        own and stops — which is the right production behaviour and the wrong
        test setup.
        """
        if claim:
            self.session.claim(env.attempt_id, 0)
        with patch.object(runtime, "stream_chat", fake_stream(items)):
            return self.executor.execute(env, epoch=0)


class TestChatIdentity(Base):
    def test_remote_chat_keeps_the_coordinator_system_instruction(self):
        seen = {}

        def generating(messages, **_options):
            seen["messages"] = messages
            yield "delta", "hello"
            yield DONE_STOP

        env = envelope(system_instruction="You are Refinix, not the model engine.")
        self.session.claim(env.attempt_id, 0)
        with patch.object(runtime, "stream_chat", generating):
            self.assertEqual(self.executor.execute(env, epoch=0), "completed")
        self.assertEqual([message["role"] for message in seen["messages"]],
                         ["system", "user"])
        self.assertIn("Refinix", seen["messages"][0]["content"])

    def test_remote_chat_preserves_selected_history_and_inference_semantics(self):
        seen = {}
        logical = [
            v1.InferenceMessage(role="system", content="You are Refinix."),
            v1.InferenceMessage(role="user", content="Earlier question"),
            v1.InferenceMessage(role="assistant", content="Earlier answer"),
            v1.InferenceMessage(role="user", content="say something"),
        ]
        env = envelope(messages=logical)

        def generating(messages, **options):
            seen["messages"] = messages
            seen["profile"] = options["profile"]
            seen["inference"] = options["inference"]
            yield "delta", "hello"
            yield DONE_STOP

        self.session.claim(env.attempt_id, 0)
        with patch.object(runtime, "stream_chat", generating):
            self.assertEqual(self.executor.execute(env, epoch=0), "completed")
        self.assertEqual(seen["messages"], [item.model_dump() for item in logical])
        self.assertEqual(seen["profile"], PROFILE)
        self.assertEqual(seen["inference"], env.inference)


class TestExecutorProfileRevalidation(Base):
    """Admission evidence is checked again at the last boundary before use."""

    def test_a_profile_that_disappears_after_admission_never_starts_inference(self):
        env = envelope()
        self.session.claim(env.attempt_id, 0)
        with patch.object(runtime, "resolve_profile", return_value=None), \
                patch.object(runtime, "stream_chat") as inference:
            self.assertEqual(self.executor.execute(env, epoch=0), "failed")
        inference.assert_not_called()

    def test_mutated_semantics_after_admission_never_start_inference(self):
        env = envelope()
        env = env.model_copy(update={
            "inference": env.inference.model_copy(
                update={"context_window_tokens": 8192})})
        self.session.claim(env.attempt_id, 0)
        with patch.object(runtime, "stream_chat") as inference:
            self.assertEqual(self.executor.execute(env, epoch=0), "failed")
        inference.assert_not_called()


class TestPackageRetention(unittest.TestCase):
    def test_an_idle_executor_periodically_reclaims_abandoned_packages(self):
        class Store:
            def __init__(self):
                self.sweeps = 0

            def purge_expired(self):
                self.sweeps += 1

        store = Store()
        session = ExecutorSession(FakeRedis(), RELATIONSHIP, "consumer-a")
        with patch.object(executor_module.time, "monotonic", return_value=10):
            worker = executor_module.Executor(session, node_id=NODE, packages=store)
        self.assertEqual(store.sweeps, 1)
        with patch.object(executor_module.time, "monotonic", return_value=309):
            worker.run_once()
        self.assertEqual(store.sweeps, 1)
        with patch.object(executor_module.time, "monotonic", return_value=310):
            worker.run_once()
        self.assertEqual(store.sweeps, 2)


# ------------------------------------------------------------- the receipt ---

class TestDurableReceipt(Base):
    def payload(self, env):
        return {"attempt_id": env.attempt_id, "state": "queued"}

    def enqueue(self, env, key="11111111-1111-4111-8111-111111111111",
                body="digest-a"):
        return self.queue.enqueue(env, scope="scope-a", body_digest=body,
                                  idempotency_key=key, epoch=0,
                                  attempt_payload=self.payload(env))

    def test_the_envelope_is_in_the_stream_after_enqueue(self):
        env = envelope()
        self.enqueue(env)
        stream = self.redis.streams[v1.redis_key("dispatch", RELATIONSHIP)]
        self.assertEqual(len(stream), 1)
        self.assertEqual(stream[0][1]["attempt_id"], env.attempt_id)

    def test_a_write_failure_raises_rather_than_acknowledging(self):
        env = envelope()
        self.redis.fail_writes = True
        with self.assertRaises(DispatchError) as caught:
            self.enqueue(env)
        self.assertEqual(caught.exception.code, "redis_lost")
        self.assertEqual(self.redis.streams.get(
            v1.redis_key("dispatch", RELATIONSHIP), []), [])

    def test_a_replayed_key_returns_the_stored_attempt_once(self):
        env = envelope()
        first = self.enqueue(env)
        second = self.enqueue(env)
        self.assertEqual(first, second)
        self.assertEqual(len(self.redis.streams[
            v1.redis_key("dispatch", RELATIONSHIP)]), 1)

    def test_a_reused_key_with_a_different_body_is_a_conflict(self):
        env = envelope()
        self.enqueue(env)
        with self.assertRaises(DispatchError) as caught:
            self.enqueue(env, body="digest-b")
        self.assertEqual(caught.exception.code, "idempotency_conflict")

    def test_an_unfinished_reservation_is_unknown_not_a_refusal(self):
        """A reservation this request did not make belongs to an earlier
        attempt at the SAME dispatch — one key per attempt — so its outcome is
        unknown. Reporting it as `redis_lost` would let the coordinator run the
        work locally while that dispatch was on its way to an executor."""
        env = envelope()
        key = v1.redis_key("idempotency", RELATIONSHIP,
                           "11111111-1111-4111-8111-111111111111")
        self.redis.set(key, '{"scope": "scope-a", "body": "digest-a",'
                            ' "state": "reserved", "attempt": {}}')
        with self.assertRaises(DispatchError) as caught:
            self.enqueue(env)
        self.assertEqual(caught.exception.code, "internal_error")
        self.assertNotEqual(caught.exception.code, "redis_lost")


# ------------------------------------------------------------------ events ---

class TestAmbiguousCommit(Base):
    """Atomic server-side mutation does not prove the client learned of it."""

    def enqueue(self, env, key="11111111-1111-4111-8111-111111111111",
                body="digest-a"):
        return self.queue.enqueue(env, scope="scope-a", body_digest=body,
                                  idempotency_key=key, epoch=0,
                                  attempt_payload={"attempt_id": env.attempt_id})

    def dispatch_stream(self):
        return self.redis.streams.get(v1.redis_key("dispatch", RELATIONSHIP), [])

    def test_a_committed_dispatch_whose_reply_was_lost_is_not_a_refusal(self):
        """THE case this correction exists for. Redis ran COMMIT_DISPATCH, the
        entry and the receipt are both stored, and the connection died before
        the reply. The old code called that `redis_lost` — the code the
        coordinator treats as proof of non-acceptance — and the coordinator
        would have run the same request locally while the executor ran it."""
        env = envelope()
        self.redis.lose_reply_after_commit = True
        payload = self.enqueue(env)
        # The read-back found the entry, so this is an acceptance, not an error.
        self.assertEqual(payload["attempt_id"], env.attempt_id)
        self.assertEqual(len(self.dispatch_stream()), 1)

    def test_a_lost_reply_that_cannot_be_read_back_is_unknown(self):
        """Redis committed and then stopped answering entirely. Nothing can be
        proved, so nothing may be refused."""
        env = envelope()
        redis = self.redis

        original = redis.eval

        def commit_then_die(script, keys, args):
            original(script, keys, args)      # the server ran it
            redis.reachable = False           # and then the link dropped
            raise RedisUnavailable("redis closed the connection")

        redis.eval = commit_then_die
        with self.assertRaises(DispatchError) as caught:
            self.enqueue(env)
        self.assertEqual(caught.exception.code, "internal_error",
                         "an unconfirmable commit must not be `redis_lost`")
        self.assertIn("may be running", caught.exception.message)
        # The work really is queued, which is exactly why refusing is unsafe.
        redis.reachable = True
        self.assertEqual(len(self.dispatch_stream()), 1)

    def test_a_commit_that_never_ran_is_a_definite_refusal(self):
        """The receipt still reads `reserved`. COMMIT_DISPATCH writes the entry
        and that marker in one script, so an unadvanced receipt proves the
        XADD did not happen either. Only this may authorise a fallback."""
        env = envelope()
        redis = self.redis

        def refuse(script, keys, args):
            raise RedisUnavailable("the write never ran")

        redis.eval = refuse
        with self.assertRaises(DispatchError) as caught:
            self.enqueue(env)
        self.assertEqual(caught.exception.code, "redis_lost")
        self.assertEqual(self.dispatch_stream(), [])

    def test_a_reservation_failure_is_a_definite_refusal(self):
        """Nothing has been queued yet, so this one really is definite."""
        env = envelope()
        self.redis.fail_writes = True
        with self.assertRaises(DispatchError) as caught:
            self.enqueue(env)
        self.assertEqual(caught.exception.code, "redis_lost")
        self.assertEqual(self.dispatch_stream(), [])

    def test_an_unreadable_receipt_after_a_commit_failure_is_unknown(self):
        env = envelope()
        redis = self.redis

        def commit_then_break_reads(script, keys, args):
            redis.reads_fail = True
            raise RedisUnavailable("the reply was lost")

        redis.eval = commit_then_break_reads
        with self.assertRaises(DispatchError) as caught:
            self.enqueue(env)
        self.assertEqual(caught.exception.code, "internal_error")

class TestEventReplay(Base):
    def test_events_replay_in_sequence_order(self):
        env = envelope()
        self.run_with(env, [("delta", "one"), ("delta", "two"), DONE_STOP])
        sequences = [e["sequence"] for e in self.events(env.attempt_id)]
        self.assertEqual(sequences, sorted(sequences))
        self.assertEqual(sequences, list(range(1, len(sequences) + 1)))

    def test_replay_can_resume_from_a_sequence(self):
        env = envelope()
        self.run_with(env, [("delta", "one"), ("delta", "two"), DONE_STOP])
        everything = self.events(env.attempt_id)
        resumed = self.queue.read_events(RELATIONSHIP, env.attempt_id,
                                         after_sequence=2)
        self.assertEqual(len(resumed), len(everything) - 2)
        self.assertTrue(all(e["sequence"] > 2 for e in resumed))

    def test_a_missing_log_reports_expired_rather_than_empty(self):
        with self.assertRaises(DispatchError) as caught:
            self.queue.read_events(RELATIONSHIP, str(uuid.uuid4()))
        self.assertEqual(caught.exception.code, "events_expired")

    def test_retention_bounds_the_event_log(self):
        env = envelope()
        key = v1.redis_key("events", RELATIONSHIP, env.attempt_id)
        for index in range(v1.MAX_EVENT_ENTRIES + 50):
            self.redis.xadd(key, {"event": "{}", "sequence": str(index)},
                            maxlen=v1.MAX_EVENT_ENTRIES)
        self.assertLessEqual(len(self.redis.streams[key]), v1.MAX_EVENT_ENTRIES)

    def test_a_corrupt_record_is_dropped_not_forwarded(self):
        env = envelope()
        self.run_with(env, [("delta", "one"), DONE_STOP])
        key = v1.redis_key("events", RELATIONSHIP, env.attempt_id)
        self.redis.xadd(key, {"event": '{"not": "an event"}', "sequence": "99"})
        for event in self.events(env.attempt_id):
            v1.Event.model_validate(event)          # every survivor validates


# --------------------------------------------------------------- execution ---

class TestExecution(Base):
    def test_a_normal_stop_completes(self):
        env = envelope()
        self.assertEqual(self.run_with(env, [("delta", "hello"), DONE_STOP]),
                         "completed")
        self.assertEqual(self.states(env.attempt_id)[-1], "completed")

    def test_a_capped_reply_does_not_complete(self):
        """A reply cut off by the token limit is not a validated answer."""
        env = envelope()
        self.assertEqual(self.run_with(env, [("delta", "hel"), DONE_LENGTH]),
                         "failed")
        self.assertEqual(self.states(env.attempt_id)[-1], "failed")

    def test_empty_output_fails_the_nonempty_validator(self):
        env = envelope()
        self.assertEqual(self.run_with(env, [("delta", "   "), DONE_STOP]),
                         "failed")

    def test_deltas_reach_the_log_before_the_terminal_event(self):
        env = envelope()
        self.run_with(env, [("delta", "hello"), DONE_STOP])
        kinds = [e["data"]["kind"] for e in self.events(env.attempt_id)]
        self.assertIn("output.delta", kinds)
        self.assertLess(kinds.index("output.delta"), len(kinds) - 1)

    def test_output_bytes_is_enforced(self):
        env = envelope(limits=v1.Limits(
            cpu_millis=2000, memory_bytes=2_147_483_648, runtime_seconds=300,
            processes=8, workspace_bytes=1_048_576, output_bytes=16,
            tool_network="disabled"))
        self.assertEqual(
            self.run_with(env, [("delta", "x" * 64), DONE_STOP]), "failed")

    def test_a_runtime_error_fails_the_attempt(self):
        env = envelope()
        self.assertEqual(
            self.run_with(env, [("delta", "part"), RuntimeError("boom")]),
            "failed")

    def test_an_expired_deadline_never_calls_the_runtime(self):
        past = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 10))
        env = envelope(
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                     time.gmtime(time.time() - 600)),
            deadline_at=past)
        called = []

        def never(*args, **kwargs):
            called.append(1)
            yield DONE_STOP

        with patch.object(runtime, "stream_chat", never):
            self.assertEqual(self.executor.execute(env, epoch=0), "failed")
        self.assertEqual(called, [])


# ------------------------------------------------ cancellation and fencing ---

class TestCancellationAndFencing(Base):
    def test_a_cancel_flag_stops_the_attempt_before_it_runs(self):
        env = envelope()
        self.queue.request_cancel(RELATIONSHIP, env.attempt_id)
        self.assertEqual(self.run_with(env, [("delta", "x"), DONE_STOP]),
                         "cancelled")
        self.assertEqual(self.states(env.attempt_id)[-1], "cancelled")

    def test_a_cancel_during_generation_stops_it(self):
        env = envelope()
        queue = self.queue

        def cancelling(messages, should_cancel=None, timeout=None, **_options):
            yield "delta", "first"
            queue.request_cancel(RELATIONSHIP, env.attempt_id)
            # The executor polls at most once a second; move the fake clock so
            # the next check is not suppressed by that budget.
            self.executor_poll_reset()
            if should_cancel():
                yield "cancelled", {}
                return
            yield "delta", "second"

        with patch.object(runtime, "stream_chat", cancelling):
            self.assertEqual(self.executor.execute(env, epoch=0), "cancelled")

    def executor_poll_reset(self):
        time.sleep(executor_module.CANCEL_POLL_SECONDS + 0.05)

    def test_revocation_fences_an_attempt_that_has_not_started(self):
        env = envelope()
        self.queue.revoke_relationship(RELATIONSHIP)
        self.assertEqual(self.run_with(env, [("delta", "x"), DONE_STOP]),
                         "cancelled")

    def test_a_lost_lease_stops_generation(self):
        """Another executor reclaimed the attempt; producing a second copy of
        the answer would duplicate the work the lease exists to prevent."""
        env = envelope()
        self.assertTrue(self.session.claim(env.attempt_id, 0))
        self.redis.set(v1.redis_key("lease", RELATIONSHIP, env.attempt_id),
                       "consumer-b:0")

        def generating(messages, should_cancel=None, timeout=None, **_options):
            yield "delta", "first"
            time.sleep(executor_module.CANCEL_POLL_SECONDS + 0.05)
            if should_cancel():
                yield "cancelled", {}
                return
            yield "delta", "second"

        with patch.object(runtime, "stream_chat", generating):
            self.assertEqual(self.executor.execute(env, epoch=0), "cancelled")


class TestLeasesAndRecovery(Base):
    def test_two_executors_cannot_claim_the_same_attempt(self):
        env = envelope()
        other = ExecutorSession(self.redis, RELATIONSHIP, "consumer-b")
        self.assertTrue(self.session.claim(env.attempt_id, 0))
        self.assertFalse(other.claim(env.attempt_id, 0))

    def test_an_expired_lease_can_be_reclaimed(self):
        env = envelope()
        other = ExecutorSession(self.redis, RELATIONSHIP, "consumer-b")
        self.assertTrue(self.session.claim(env.attempt_id, 0))
        self.redis.advance(v1.LEASE_SECONDS + 1)
        self.assertTrue(other.claim(env.attempt_id, 0))

    def test_a_heartbeat_we_no_longer_own_is_refused(self):
        env = envelope()
        self.session.claim(env.attempt_id, 0)
        self.redis.set(v1.redis_key("lease", RELATIONSHIP, env.attempt_id),
                       "consumer-b:0")
        self.assertFalse(self.session.heartbeat(env.attempt_id, 0))

    def test_a_killed_executor_leaves_recoverable_pending_work(self):
        env = envelope()
        self.queue.enqueue(env, scope="s", body_digest="d",
                           idempotency_key="11111111-1111-4111-8111-111111111111",
                           epoch=0, attempt_payload={})
        self.session.ensure_group()
        taken = self.session.next_entries(block_ms=0)
        self.assertEqual(len(taken), 1)          # delivered, never acknowledged

        survivor = ExecutorSession(self.redis, RELATIONSHIP, "consumer-b")
        self.assertEqual(survivor.recover_pending(), [],
                         "work is not stolen before the lease expires")
        self.redis.advance(v1.LEASE_SECONDS + 1)
        recovered = survivor.recover_pending()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0][1]["attempt_id"], env.attempt_id)

    def test_a_duplicate_delivery_runs_once(self):
        env = envelope()
        fields = {"envelope": env.model_dump_json(),
                  "attempt_id": env.attempt_id, "epoch": "0",
                  "enqueued_at": "2026-09-05T00:00:00Z"}
        with patch.object(runtime, "stream_chat",
                          fake_stream([("delta", "hello"), DONE_STOP])):
            self.executor._handle("1-1", fields, recovered=False)
            second = executor_module.Executor(
                ExecutorSession(self.redis, RELATIONSHIP, "consumer-b"),
                node_id=NODE)
            # The first run released its lease, so re-claiming succeeds; what
            # must not happen is two executors running it at the same time.
            self.assertTrue(self.session.claim(env.attempt_id, 0))
            self.assertFalse(second.session.claim(env.attempt_id, 0))

    def test_an_unparsable_entry_is_acknowledged_and_dropped(self):
        """Otherwise the executor reclaims the same poison forever."""
        handled = self.executor._handle("1-1", {"envelope": "not json"},
                                        recovered=False)
        self.assertEqual(handled, 1)


class TestRedisLoss(Base):
    def test_an_unreachable_queue_is_not_a_silent_success(self):
        self.redis.reachable = False
        self.assertFalse(self.queue.is_live())
        with self.assertRaises(DispatchError) as caught:
            self.queue.enqueue(envelope(), scope="s", body_digest="d",
                               idempotency_key="11111111-1111-4111-8111-111111111111",
                               epoch=0, attempt_payload={})
        self.assertEqual(caught.exception.code, "redis_lost")

    def test_redis_loss_during_generation_stops_the_attempt(self):
        env = envelope()
        redis = self.redis

        def generating(messages, should_cancel=None, timeout=None, **_options):
            yield "delta", "first"
            redis.reachable = False
            time.sleep(executor_module.CANCEL_POLL_SECONDS + 0.05)
            if should_cancel():
                yield "cancelled", {}
                return
            yield "delta", "second"

        self.session.claim(env.attempt_id, 0)
        with patch.object(runtime, "stream_chat", generating):
            # Not "cancelled": the terminal event never reached a log, so
            # nothing may claim it was recorded. The coordinator sees
            # worker_lost, which is what actually happened.
            self.assertEqual(self.executor.execute(env, epoch=0), "interrupted")


class TestRestartRecovery(Base):
    """The API Pod restarts. Redis still holds the receipt, so the routes must.

    These exercise the dispatch layer the routes resolve through; the HTTP
    routes themselves are covered in `test_worker_app` at image build time.
    """

    def enqueue(self, env, key=None):
        return self.queue.enqueue(
            env, scope="s", body_digest="d",
            idempotency_key=key or str(uuid.uuid4()), epoch=0,
            attempt_payload={"attempt_id": env.attempt_id})

    def test_the_attempt_is_found_by_a_process_that_never_admitted_it(self):
        env = envelope()
        self.enqueue(env)
        fresh = DispatchQueue(self.redis)          # a restarted API
        found = fresh.find_attempt(RELATIONSHIP, env.attempt_id)
        self.assertIsNotNone(found, "a restarted API answered 404 for live work")
        self.assertEqual(found.job_id, env.job_id)

    def test_an_unknown_attempt_is_still_unknown(self):
        self.assertIsNone(
            DispatchQueue(self.redis).find_attempt(RELATIONSHIP, str(uuid.uuid4())))

    def test_events_replay_to_a_process_that_never_admitted_the_attempt(self):
        env = envelope()
        self.enqueue(env)
        self.run_with(env, [("delta", "hello"), DONE_STOP])
        fresh = DispatchQueue(self.redis)
        replayed = fresh.read_events(RELATIONSHIP, env.attempt_id)
        self.assertTrue(replayed)
        self.assertEqual(replayed[-1]["data"]["current"], "completed")

    def test_an_admitted_attempt_with_no_events_is_not_expired(self):
        """It has not started. Calling that expired fails work about to run."""
        env = envelope()
        self.enqueue(env)
        fresh = DispatchQueue(self.redis)
        self.assertEqual(
            fresh.read_events(RELATIONSHIP, env.attempt_id, admitted=True), [])
        with self.assertRaises(DispatchError) as caught:
            fresh.read_events(RELATIONSHIP, env.attempt_id)
        self.assertEqual(caught.exception.code, "events_expired")

    def test_cancellation_survives_a_restart(self):
        env = envelope()
        self.enqueue(env)
        DispatchQueue(self.redis).request_cancel(RELATIONSHIP, env.attempt_id)
        self.assertTrue(self.session.cancelled(env.attempt_id))

    def test_capacity_comes_from_redis_not_a_process_counter(self):
        env = envelope()
        self.enqueue(env)
        self.assertEqual(
            DispatchQueue(self.redis).active_attempts(RELATIONSHIP), 1)

    def test_a_finished_attempt_stops_holding_capacity(self):
        """A stale dictionary entry held a slot against a completed attempt for
        the life of the process."""
        env = envelope()
        self.enqueue(env)
        self.run_with(env, [("delta", "hello"), DONE_STOP])
        self.assertEqual(self.queue.active_attempts(RELATIONSHIP), 0)

    def test_more_than_two_sequential_attempts_complete(self):
        """MAX_ACTIVE is 2. With capacity derived from finished state rather
        than a counter, a third and fourth request must still be admissible."""
        for index in range(4):
            env = envelope()
            self.enqueue(env)
            self.assertLessEqual(self.queue.active_attempts(RELATIONSHIP), 1,
                                 f"attempt {index} was blocked by a stale slot")
            self.assertEqual(
                self.run_with(env, [("delta", "hi"), DONE_STOP]), "completed")
            self.assertEqual(self.queue.active_attempts(RELATIONSHIP), 0)


class TestAmbiguousDispatch(Base):
    """Failure injection around the atomic commit."""

    def enqueue(self, env, key="11111111-1111-4111-8111-111111111111"):
        return self.queue.enqueue(env, scope="s", body_digest="d",
                                  idempotency_key=key, epoch=0,
                                  attempt_payload={"attempt_id": env.attempt_id})

    def test_the_entry_and_its_receipt_land_together_or_not_at_all(self):
        """The old flow was SET reserved, XADD, SET accepted. A failure between
        the last two returned 503 to a coordinator whose work was running."""
        env = envelope()
        self.redis.fail_writes = True
        with self.assertRaises(DispatchError):
            self.enqueue(env)
        self.assertEqual(
            self.redis.streams.get(v1.redis_key("dispatch", RELATIONSHIP), []), [])
        key = v1.redis_key("idempotency", RELATIONSHIP,
                           "11111111-1111-4111-8111-111111111111")
        self.assertIsNone(self.redis.keys.get(key))

    def test_a_committed_dispatch_is_replayable_by_the_same_key(self):
        """The client never saw the answer and retries with the SAME key. It
        must get the original receipt, not a second attempt."""
        env = envelope()
        first = self.enqueue(env)
        self.assertEqual(len(self.redis.streams[
            v1.redis_key("dispatch", RELATIONSHIP)]), 1)
        second = self.enqueue(env)          # the retry after a lost response
        self.assertEqual(first, second)
        self.assertEqual(len(self.redis.streams[
            v1.redis_key("dispatch", RELATIONSHIP)]), 1,
            "a retry under the same key must not queue the work twice")

    def test_a_committed_dispatch_is_visible_even_if_the_client_never_learns(self):
        """After the server-side commit the work exists regardless of what the
        client saw. That is exactly why the coordinator must not fall back."""
        env = envelope()
        self.enqueue(env)
        self.assertIsNotNone(
            DispatchQueue(self.redis).find_attempt(RELATIONSHIP, env.attempt_id))


class TestPendingEntryRecovery(Base):
    """Real consumer-group semantics: XAUTOCLAIM transfers, XACK destroys.

    `XAUTOCLAIM` moves the ONE pending entry to another consumer. It does not
    hand out a copy, so an executor that cannot claim the custom lease has
    nothing of its own to dispose of — and `XACK` there removes the entry from
    the group's pending list for everyone. The sequence below is the one that
    lost work.
    """

    def entry(self, env, epoch=0):
        return {"envelope": env.model_dump_json(), "attempt_id": env.attempt_id,
                "epoch": str(epoch), "enqueued_at": "2026-09-05T00:00:00Z"}

    def deliver_to(self, env, consumer, entry_id="1-1"):
        key = v1.redis_key("dispatch", RELATIONSHIP)
        self.redis.streams.setdefault(key, []).append((entry_id, self.entry(env)))
        state = self.redis.groups.setdefault(key, {"delivered": 0, "pending": {}})
        state["pending"][entry_id] = (consumer, self.redis._now())

    def pending(self) -> dict:
        return self.redis.groups.get(
            v1.redis_key("dispatch", RELATIONSHIP), {}).get("pending", {})

    def test_a_recovered_entry_with_a_live_owner_stays_recoverable(self):
        """A -> heartbeat -> idle passes -> B recovers -> B cannot claim.

        B must leave the entry pending. Acknowledging it would delete the only
        record of the work while A is still running it.
        """
        env = envelope()
        alpha = ExecutorSession(self.redis, RELATIONSHIP, "consumer-a")
        beta = ExecutorSession(self.redis, RELATIONSHIP, "consumer-b")

        # 1. A owns the lease and heartbeats it.
        self.deliver_to(env, "consumer-a", "1-1")
        self.assertTrue(alpha.claim(env.attempt_id, 0))
        self.assertTrue(alpha.heartbeat(env.attempt_id, 0))

        # 2. The pending-entry idle threshold passes while A stays alive.
        #    A real executor heartbeats every HEARTBEAT_SECONDS, which is well
        #    inside LEASE_SECONDS, so its lease never lapses even though the
        #    entry's idle time crosses the recovery threshold. Advancing in one
        #    jump would expire the lease and test a different scenario.
        elapsed = 0
        while elapsed <= v1.LEASE_SECONDS:
            self.redis.advance(v1.HEARTBEAT_SECONDS)
            elapsed += v1.HEARTBEAT_SECONDS
            self.assertTrue(alpha.heartbeat(env.attempt_id, 0),
                            "a heartbeating owner must keep its lease")

        # 3. B recovers the entry through XAUTOCLAIM.
        recovered = beta.recover_pending()
        self.assertEqual(len(recovered), 1)
        entry_id, fields = recovered[0]

        # 4. B cannot acquire the live lease, and 5. must not destroy it.
        called = []

        def never(*args, **kwargs):
            called.append(1)
            yield DONE_STOP

        worker = executor_module.Executor(beta, node_id=NODE)
        with patch.object(runtime, "stream_chat", never):
            worker._handle(entry_id, fields, recovered=True)
        self.assertEqual(called, [], "B must not run work A owns")
        self.assertIn(entry_id, self.pending(),
                      "acknowledging here deletes the only record of the work")
        self.assertTrue(alpha.still_owned(env.attempt_id, 0),
                        "A's lease must survive B's attempt")

        # 6. A disappears. Its lease expires, and a later recovery runs it.
        self.redis.advance(v1.LEASE_SECONDS + 1)
        again = beta.recover_pending()
        self.assertEqual(len(again), 1, "the entry is still there to recover")
        with patch.object(runtime, "stream_chat",
                          fake_stream([("delta", "hello"), DONE_STOP])):
            worker._handle(again[0][0], again[0][1], recovered=True)
        self.assertEqual(beta.terminal_state(env.attempt_id), "completed")
        self.assertNotIn(entry_id, self.pending(),
                         "a durable outcome is finally acknowledged")

    def test_the_live_owner_can_still_acknowledge_after_a_failed_recovery(self):
        """XACK is not scoped to the current owner, so A finishing normally
        still clears the entry B briefly held."""
        env = envelope()
        alpha = ExecutorSession(self.redis, RELATIONSHIP, "consumer-a")
        beta = ExecutorSession(self.redis, RELATIONSHIP, "consumer-b")
        self.deliver_to(env, "consumer-a", "1-1")
        alpha.claim(env.attempt_id, 0)
        for _ in range(4):                     # stays alive across the window
            self.redis.advance(v1.HEARTBEAT_SECONDS)
            alpha.heartbeat(env.attempt_id, 0)
        beta.recover_pending()                 # ownership moves to B
        alpha.acknowledge("1-1")               # A finishes and acknowledges
        self.assertNotIn("1-1", self.pending())

    def test_a_declined_entry_is_not_offered_again_immediately(self):
        """Claiming resets the idle timer, so the loop does not spin on an
        entry it has just declined."""
        env = envelope()
        alpha = ExecutorSession(self.redis, RELATIONSHIP, "consumer-a")
        beta = ExecutorSession(self.redis, RELATIONSHIP, "consumer-b")
        self.deliver_to(env, "consumer-a", "1-1")
        alpha.claim(env.attempt_id, 0)
        for _ in range(4):
            self.redis.advance(v1.HEARTBEAT_SECONDS)
            alpha.heartbeat(env.attempt_id, 0)
        self.assertEqual(len(beta.recover_pending()), 1)
        self.assertEqual(beta.recover_pending(), [],
                         "a just-claimed entry must not be offered again")

    def test_only_three_paths_acknowledge(self):
        """Acknowledgement is the point of no return, so its call sites are
        worth pinning: poison, terminal duplicate, and a stored outcome."""
        source = pathlib.Path(executor_module.__file__).read_text()
        self.assertEqual(source.count("self.session.acknowledge(entry_id)"), 3)


class TestLeaseOwnership(Base):
    """Atomic, owner-checked lease operations."""

    def test_an_old_executor_cannot_extend_a_reclaimed_lease(self):
        env = envelope()
        self.session.claim(env.attempt_id, 0)
        self.redis.advance(v1.LEASE_SECONDS + 1)
        other = ExecutorSession(self.redis, RELATIONSHIP, "consumer-b")
        self.assertTrue(other.claim(env.attempt_id, 0))
        self.assertFalse(self.session.heartbeat(env.attempt_id, 0),
                         "the previous owner extended a lease it had lost")
        self.assertTrue(other.still_owned(env.attempt_id, 0))

    def test_an_old_executor_cannot_release_a_reclaimed_lease(self):
        env = envelope()
        self.session.claim(env.attempt_id, 0)
        self.redis.advance(v1.LEASE_SECONDS + 1)
        other = ExecutorSession(self.redis, RELATIONSHIP, "consumer-b")
        other.claim(env.attempt_id, 0)
        self.assertFalse(self.session.release(env.attempt_id, 0),
                         "the previous owner released someone else's lease")
        self.assertTrue(other.still_owned(env.attempt_id, 0))

    def test_an_owner_releases_its_own_lease(self):
        env = envelope()
        self.session.claim(env.attempt_id, 0)
        self.assertTrue(self.session.release(env.attempt_id, 0))
        self.assertIsNone(
            self.redis.get(v1.redis_key("lease", RELATIONSHIP, env.attempt_id)))


class TestDuplicateAndPending(Base):
    """Acknowledgement is the point of no return, so it waits for a record."""

    def entry(self, env, epoch=0):
        return {"envelope": env.model_dump_json(), "attempt_id": env.attempt_id,
                "epoch": str(epoch), "enqueued_at": "2026-09-05T00:00:00Z"}

    def deliver(self, env, entry_id="1-1"):
        key = v1.redis_key("dispatch", RELATIONSHIP)
        self.redis.streams.setdefault(key, []).append((entry_id, self.entry(env)))
        state = self.redis.groups.setdefault(key, {"delivered": 0, "pending": {}})
        state["pending"][entry_id] = (self.session.consumer, self.redis._now())

    def pending(self) -> dict:
        return self.redis.groups.get(
            v1.redis_key("dispatch", RELATIONSHIP), {}).get("pending", {})

    def test_a_duplicate_after_a_completed_run_does_not_run_again(self):
        env = envelope()
        self.deliver(env, "1-1")
        with patch.object(runtime, "stream_chat",
                          fake_stream([("delta", "hello"), DONE_STOP])):
            self.executor._handle("1-1", self.entry(env), recovered=False)
        self.assertEqual(self.executor.session.terminal_state(env.attempt_id),
                         "completed")

        called = []

        def never(*args, **kwargs):
            called.append(1)
            yield DONE_STOP

        self.deliver(env, "1-2")
        with patch.object(runtime, "stream_chat", never):
            self.executor._handle("1-2", self.entry(env), recovered=True)
        self.assertEqual(called, [], "the duplicate produced a second answer")
        self.assertNotIn("1-2", self.pending(), "the duplicate stays pending")

    def test_a_completed_attempt_is_acknowledged(self):
        env = envelope()
        self.deliver(env, "1-1")
        with patch.object(runtime, "stream_chat",
                          fake_stream([("delta", "hello"), DONE_STOP])):
            self.executor._handle("1-1", self.entry(env), recovered=False)
        self.assertNotIn("1-1", self.pending())

    def test_interrupted_work_stays_pending_for_recovery(self):
        """No terminal record means no acknowledgement: the entry must remain
        recoverable rather than be silently dropped."""
        env = envelope()
        self.deliver(env, "1-1")
        redis = self.redis

        def dying(messages, should_cancel=None, timeout=None, **_options):
            yield "delta", "partial"
            redis.reachable = False
            time.sleep(executor_module.CANCEL_POLL_SECONDS + 0.05)
            if should_cancel():
                yield "cancelled", {}
                return

        with patch.object(runtime, "stream_chat", dying):
            self.executor._handle("1-1", self.entry(env), recovered=False)
        self.redis.reachable = True
        self.assertIn("1-1", self.pending(),
                      "interrupted work was acknowledged and lost")

    def test_sigterm_leaves_partial_work_pending_without_cancelling_it(self):
        env = envelope()
        self.deliver(env, "1-1")
        checks = iter((False, True))
        worker = executor_module.Executor(
            self.session, node_id=NODE, stop_check=lambda: next(checks))

        with patch.object(runtime, "stream_chat", fake_stream([
                ("delta", "partial"), DONE_STOP])):
            with self.assertRaises(executor_module.Stopped):
                worker._handle("1-1", self.entry(env), recovered=False)

        self.assertEqual(self.states(env.attempt_id), ["queued", "running"])
        self.assertIn("1-1", self.pending(),
                      "SIGTERM acknowledged work before another executor recovered it")

    def test_redis_recovering_after_a_failed_emit_does_not_ack(self):
        """The terminal event never reached the log, so no acknowledgement.

        This is the subtle one. Redis is answering again by the time cleanup
        runs, so `release` and `acknowledge` would both succeed — but the
        outcome was never recorded, and acknowledging here would drop work no
        record exists for. The check is on the record, not on whether Redis
        happens to be up.
        """
        env = envelope()
        self.deliver(env, "1-1")
        redis = self.redis
        real_emit = self.session.emit

        def emit_then_recover(event):
            try:
                return real_emit(event)
            finally:
                # Redis comes back the instant after the failed write, which is
                # what makes the naive "is Redis up?" check wrong.
                redis.reachable = True

        def dying(messages, should_cancel=None, timeout=None, **_options):
            yield "delta", "partial"
            redis.reachable = False
            raise RuntimeError("the runtime died while redis was down")

        with patch.object(self.session, "emit", emit_then_recover), \
                patch.object(runtime, "stream_chat", dying):
            self.executor._handle("1-1", self.entry(env), recovered=False)

        self.assertTrue(self.redis.reachable, "redis is back")
        self.assertIsNone(self.executor.session.terminal_state(env.attempt_id),
                          "no terminal event was ever stored")
        self.assertIn("1-1", self.pending(),
                      "an unrecorded outcome was acknowledged and lost")

    def test_an_entry_owned_by_another_executor_is_not_run(self):
        env = envelope()
        other = ExecutorSession(self.redis, RELATIONSHIP, "consumer-b")
        other.claim(env.attempt_id, 0)
        self.deliver(env, "1-1")
        called = []

        def never(*args, **kwargs):
            called.append(1)
            yield DONE_STOP

        with patch.object(runtime, "stream_chat", never):
            self.executor._handle("1-1", self.entry(env), recovered=False)
        self.assertEqual(called, [])


# ----------------------------------------------------------------- pairing ---

class TestPairingStore(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._dir = tempfile.TemporaryDirectory()
        self.path = f"{self._dir.name}/pairing.json"
        self.store = pairing_module.PairingStore(self.path)

    def tearDown(self):
        self._dir.cleanup()

    def pair(self, relationship_id=RELATIONSHIP):
        return self.store.redeem(self.store.issue_code(),
                                 relationship_id=relationship_id,
                                 workspace_id=WORKSPACE)

    def test_a_credential_verifies_against_the_stored_hash(self):
        credential = self.pair()
        record = self.store.authorise(RELATIONSHIP, credential)
        self.assertEqual(record["workspace_id"], WORKSPACE)

    def test_no_plaintext_secret_reaches_the_state_file(self):
        credential = self.pair()
        raw = pathlib.Path(self.path).read_text(encoding="utf-8")
        self.assertNotIn(credential, raw)
        self.assertIn("credential_sha256", raw)

    def test_the_state_file_is_not_group_or_world_readable(self):
        import os
        import stat
        if os.name == "nt":
            self.skipTest("Windows protects this file with ACLs, not mode bits")
        self.pair()
        mode = stat.S_IMODE(os.stat(self.path).st_mode)
        self.assertEqual(mode & 0o077, 0, f"pairing file is mode {mode:o}")

    def test_a_code_cannot_be_used_twice(self):
        code = self.store.issue_code()
        self.store.redeem(code, relationship_id=RELATIONSHIP,
                          workspace_id=WORKSPACE)
        with self.assertRaises(pairing_module.PairingError):
            self.store.redeem(code, relationship_id=str(uuid.uuid4()),
                              workspace_id=WORKSPACE)

    def test_a_failed_redemption_still_spends_the_code(self):
        """A code that has been presented is spent; otherwise a failure becomes
        a retry oracle."""
        code = self.store.issue_code()
        self.store.redeem(code, relationship_id=RELATIONSHIP,
                          workspace_id=WORKSPACE)
        with self.assertRaises(pairing_module.PairingError):
            self.store.redeem(code, relationship_id=RELATIONSHIP,
                              workspace_id=WORKSPACE)
        self.assertEqual(self.store.open_code_count(), 0)

    def test_an_expired_code_is_refused(self):
        code = self.store.issue_code()
        with patch.object(pairing_module, "_now",
                          lambda: int(time.time()) + pairing_module.CODE_TTL_SECONDS + 1):
            with self.assertRaises(pairing_module.PairingError):
                self.store.redeem(code, relationship_id=RELATIONSHIP,
                                  workspace_id=WORKSPACE)

    def test_an_unknown_credential_is_refused(self):
        self.pair()
        with self.assertRaises(pairing_module.PairingError):
            self.store.authorise(RELATIONSHIP, "not-the-credential")

    def test_revocation_refuses_the_credential_and_bumps_the_fence(self):
        credential = self.pair()
        before = self.store.epoch()
        self.assertTrue(self.store.revoke(RELATIONSHIP))
        self.assertGreater(self.store.epoch(), before)
        with self.assertRaises(pairing_module.PairingError):
            self.store.authorise(RELATIONSHIP, credential)

    def test_relationship_metadata_carries_no_secret(self):
        self.pair()
        for record in self.store.relationships().values():
            self.assertNotIn("salt", record)
            self.assertNotIn("credential_sha256", record)

    def test_state_survives_a_reopen(self):
        credential = self.pair()
        reopened = pairing_module.PairingStore(self.path)
        self.assertIsNotNone(reopened.authorise(RELATIONSHIP, credential))

    def test_a_running_api_sees_a_code_minted_by_the_host_cli(self):
        api = pairing_module.PairingStore(self.path)
        cli = pairing_module.PairingStore(self.path)
        code = cli.issue_code()
        credential = api.redeem(code, relationship_id=RELATIONSHIP,
                                workspace_id=WORKSPACE)
        self.assertIsNotNone(api.authorise(RELATIONSHIP, credential))

    def test_the_fingerprint_matches_openssl_formatting(self):
        value = pairing_module.fingerprint(b"certificate-bytes")
        self.assertRegex(value, r"^([0-9A-F]{2}:){31}[0-9A-F]{2}$")
        self.assertEqual(pairing_module.normalise_fingerprint(
            f"sha256 Fingerprint={value.lower().replace(':', ' ')}"), value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
