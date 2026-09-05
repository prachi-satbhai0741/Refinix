"""AF-005 durable dispatch: the receipt that makes a 202 honest.

The worker API previously refused every job because "an in-memory dictionary is
not a durable receipt". This is the receipt. `POST /v1/jobs` writes the
validated envelope into a Redis Stream **before** it answers, so an API process
that dies one instruction after the 202 leaves work an executor can still find.

Every key and limit comes from `backend.contracts.v1`; none is redefined here.
`redis_key` fixes the layout:

    af:1.0:<relationship>:dispatch                  the work stream
    af:1.0:<relationship>:events:<attempt>          that attempt's event log
    af:1.0:<relationship>:lease:<attempt>           who owns it, and until when
    af:1.0:<relationship>:cancel:<attempt>          a cancellation request
    af:1.0:<relationship>:heartbeat:<attempt>       liveness of the owner
    af:1.0:<relationship>:idempotency:<key>         one answer per key

Four design points, each a failure mode rather than a preference.

**Redis is coordination, never canonical.** Every key expires; the streams are
capped by `MAX_DISPATCH_ENTRIES` and `MAX_EVENT_ENTRIES`. Losing Redis loses
queue position and replay. The coordinator's SQLite keeps the canonical history
and nothing here can delete it.

**The dispatch stream is also the attempt record.** There is no second index and
no process-local dictionary: `find_attempt` scans the stream, which is bounded
at 128 entries by the contract. That is what lets `poll`, `events` and `cancel`
answer correctly after the API Pod restarts — the receipt is in Redis, so the
routes are too.

**The receipt commits atomically.** `XADD` and the "accepted" marker land in one
`EVAL`, so there is no window in which the work is queued but the receipt says
otherwise. Before this was atomic, a failure between them returned 503 to a
coordinator whose work was already running.

**A terminal event is the done marker.** No separate key: the last
`attempt.state` in the event log is the record of completion, it expires with
the log, and the executor consults it before running anything. That is what
makes a duplicate delivery after a completed run a no-op instead of a second
answer.
"""

from __future__ import annotations

import json
import time

from backend.contracts import v1
from backend.worker.redis_client import Redis, RedisError, RedisUnavailable

# A reserved-but-unfinished receipt is retried by the client, so it need only
# outlive one dispatch round trip; a completed one is kept for the contract's
# retention window so a client retry gets the same answer.
RESERVATION_SECONDS = 60

# --------------------------------------------------------------------------
# Atomic operations. Each exists because the read-then-write version has a
# window in which two callers both believe they won.
# --------------------------------------------------------------------------

# Queue the envelope and mark the receipt accepted together. Either the work is
# dispatched and the caller is told so, or neither happened.
COMMIT_DISPATCH = """
local entry = redis.call('XADD', KEYS[1], 'MAXLEN', '~', ARGV[1], '*',
                         'envelope', ARGV[2], 'attempt_id', ARGV[3],
                         'epoch', ARGV[4], 'enqueued_at', ARGV[5])
redis.call('SET', KEYS[2], ARGV[6], 'EX', tonumber(ARGV[7]))
return entry
"""

# Extend a lease only while we still hold it. A blind EXPIRE would let a slow
# executor keep alive a lease another executor legitimately reclaimed.
EXTEND_LEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
  redis.call('SET', KEYS[2], ARGV[3], 'EX', tonumber(ARGV[4]))
  return 1
end
return 0
"""

# Release only our own lease. Deleting unconditionally would drop the lease of
# whoever reclaimed the attempt after ours expired.
RELEASE_LEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  redis.call('DEL', KEYS[1])
  redis.call('DEL', KEYS[2])
  return 1
end
return 0
"""


class DispatchError(Exception):
    """Carries the contract failure code the route should return."""

    def __init__(self, code: str, message: str, retryable: bool, status: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status = status


def _definite(detail: str) -> DispatchError:
    """No dispatch exists, and that is KNOWN.

    `redis_lost` is the code the coordinator treats as proof that nothing was
    accepted, so it authorises local fallback. Raise it only where the dispatch
    command provably never reached Redis.
    """
    return DispatchError("redis_lost", detail, True, 503)


def _unknown(detail: str) -> DispatchError:
    """A dispatch MAY exist and we could not find out.

    Deliberately not `redis_lost`. Atomic server-side mutation does not prove
    the client learned the outcome: Redis can run `COMMIT_DISPATCH` and the
    connection can die before the reply arrives, and reporting that as "nothing
    was accepted" lets the coordinator run locally while the executor is
    already running the same attempt. `internal_error` is outside the
    coordinator's `DEFINITE_REFUSALS`, so it becomes `ReceiptUnknown` there and
    no fallback follows.
    """
    return DispatchError(
        "internal_error",
        f"{detail} The dispatch state could not be confirmed; this attempt may "
        "be running. It was NOT refused.", True, 503)


class DispatchQueue:
    """The worker API's half: enqueue, cancel, replay. It never executes work."""

    def __init__(self, redis: Redis):
        self.redis = redis

    # ------------------------------------------------------------- receipt ---

    def enqueue(self, envelope: v1.JobEnvelope, *, scope: str, body_digest: str,
                idempotency_key: str, epoch: int, attempt_payload: dict) -> dict:
        """Persist the envelope, then return the attempt payload for the 202.

        Returns the *stored* payload on a replayed key, so a retried request and
        the original answer describe the same attempt rather than two.
        """
        relationship_id = envelope.relationship_id
        key = v1.redis_key("idempotency", relationship_id, idempotency_key)
        record = {"scope": scope, "body": body_digest, "state": "reserved",
                  "attempt": attempt_payload}

        # PHASE ONE — reserve. Nothing has been queued yet, so a failure here
        # is definite: the dispatch command was never sent.
        try:
            reserved = self.redis.set(key, json.dumps(record), nx=True,
                                      ex=RESERVATION_SECONDS)
        except RedisUnavailable as exc:
            raise _definite("the dispatch queue is unavailable and nothing was "
                            "sent to it.") from exc
        except RedisError as exc:
            raise _definite(f"the dispatch queue refused the reservation: {exc}") from exc

        if not reserved:
            return self._replay_receipt(key, scope, body_digest)

        # PHASE TWO — commit. From here the outcome is NOT knowable from the
        # exception alone. The command is atomic on the server, which says
        # nothing about whether its reply reached this process.
        record["state"] = "accepted"
        try:
            self.redis.eval(
                COMMIT_DISPATCH,
                [v1.redis_key("dispatch", relationship_id), key],
                [v1.MAX_DISPATCH_ENTRIES, envelope.model_dump_json(),
                 envelope.attempt_id, str(epoch), _now(),
                 json.dumps(record), v1.RETENTION_SECONDS])
            return attempt_payload
        except (RedisUnavailable, RedisError) as exc:
            return self._after_ambiguous_commit(envelope, key, record,
                                                attempt_payload, exc)

    def _after_ambiguous_commit(self, envelope: v1.JobEnvelope, key: str,
                                record: dict, attempt_payload: dict,
                                cause: Exception) -> dict:
        """Find out whether the commit landed, or say that we could not.

        Three outcomes, and only one of them may authorise a local fallback.

        * **The entry is in the dispatch stream.** It committed. The reply was
          lost, not the work; answer 202 so the coordinator streams it rather
          than running a second copy.
        * **The entry is absent AND the receipt still reads "reserved".**
          `COMMIT_DISPATCH` writes both in one script, so a receipt that never
          advanced proves the `XADD` never ran either. Only this branch is
          definite.
        * **Anything else** — the read-back also failed, the receipt is gone,
          or the two disagree — is unknown, and unknown must never become a
          refusal.
        """
        try:
            queued = self.find_attempt(envelope.relationship_id,
                                       envelope.attempt_id) is not None
        except DispatchError as exc:
            raise _unknown("the dispatch queue stopped answering while "
                           "confirming the commit.") from exc

        if queued:
            # Best effort: re-mark the receipt so a retry replays instead of
            # reserving again. Failing this changes nothing that matters — the
            # work is queued either way.
            try:
                self.redis.set(key, json.dumps(record), ex=v1.RETENTION_SECONDS)
            except (RedisUnavailable, RedisError):
                pass
            return attempt_payload

        try:
            stored = self.redis.get(key)
        except (RedisUnavailable, RedisError) as exc:
            raise _unknown("the dispatch queue stopped answering while "
                           "confirming the commit.") from exc

        if stored is not None:
            try:
                if json.loads(stored).get("state") == "reserved":
                    return self._refuse_reservation(key, cause)
            except ValueError:
                pass
        # The receipt expired, was evicted, or reads as accepted while the
        # stream does not show the entry. Neither claim can be trusted over the
        # other, so nothing here is proof.
        raise _unknown("the dispatch state could not be read back.") from cause

    def _refuse_reservation(self, key: str, cause: Exception) -> dict:
        """Release the reservation and report a definite non-acceptance."""
        try:
            self.redis.delete(key)
        except (RedisUnavailable, RedisError):
            pass          # it expires on its own; the refusal is still definite
        raise _definite("the dispatch queue rejected the commit and nothing "
                        "was queued.") from cause

    def _replay_receipt(self, key: str, scope: str, body_digest: str) -> dict:
        """Answer a request whose key was already reserved.

        A reservation this request did not make belongs to an earlier attempt
        at the SAME dispatch — the coordinator uses one key per attempt — so a
        reservation whose outcome is not yet recorded is UNKNOWN, not a
        refusal. Reporting it as definite would let the coordinator run locally
        while the earlier request's dispatch is on its way to an executor.
        """
        try:
            stored = self.redis.get(key)
        except (RedisUnavailable, RedisError) as exc:
            raise _unknown("the stored receipt could not be read.") from exc
        if stored is None:
            # Reserved a moment ago and now gone: expired, or another process
            # is mid-commit. Either way this cannot prove non-acceptance.
            raise _unknown("a request for this key is in flight and its "
                           "receipt is not readable.")
        try:
            record = json.loads(stored)
            same = (record["scope"] == scope and record["body"] == body_digest)
        except (ValueError, KeyError, TypeError) as exc:
            raise _unknown("the stored receipt is unreadable.") from exc
        if not same:
            # A definite refusal: this key names a different request, so this
            # one was never accepted under it.
            raise DispatchError("idempotency_conflict",
                                "this key was used with a different request body",
                                False, 409)
        if record.get("state") != "accepted":
            raise _unknown("a request for this key is still in flight.")
        return record["attempt"]

    # -------------------------------------------------------- cancellation ---

    def request_cancel(self, relationship_id: str, attempt_id: str) -> None:
        """Set the cancellation flag the executor polls.

        Cancellation is written to Redis rather than held in the API process,
        so it reaches an executor in another Pod — the boundary the coordinator
        must be able to cross to cancel remote work.
        """
        try:
            self.redis.set(v1.redis_key("cancel", relationship_id, attempt_id),
                           "1", ex=v1.RETENTION_SECONDS)
        except RedisUnavailable as exc:
            raise _definite("cancellation could not be recorded") from exc

    def cancelled(self, relationship_id: str, attempt_id: str) -> bool:
        """Whether a cancellation has been recorded for this attempt.

        Read by the streaming route so a cancelled attempt stops streaming
        promptly instead of waiting out its deadline.
        """
        try:
            return self.redis.get(
                v1.redis_key("cancel", relationship_id, attempt_id)) is not None
        except RedisUnavailable as exc:
            raise _definite("the cancellation flag is unavailable") from exc

    def revoke_relationship(self, relationship_id: str) -> None:
        """Fence every attempt of a revoked relationship.

        A relationship-scoped cancel key: the identifier is the relationship's
        own ID, which `redis_key` accepts because it is a valid contract `Id`.
        The executor checks it before starting an attempt and while running one,
        so revocation stops work in flight rather than only refusing new work —
        `security.md` 4.1 requires exactly that.
        """
        try:
            self.redis.set(
                v1.redis_key("cancel", relationship_id, relationship_id),
                "revoked", ex=v1.RETENTION_SECONDS)
        except (RedisUnavailable, RedisError):
            # Best effort here. The worker-side hash is already deleted, so the
            # credential is dead either way; this only shortens the fence.
            pass

    # ------------------------------------------------------ attempt lookup ---

    def find_attempt(self, relationship_id: str, attempt_id: str) -> v1.JobEnvelope | None:
        """The envelope this worker admitted, read back from Redis.

        This is what replaces the process-local dictionary that used to gate
        polling, streaming and cancellation. After an API Pod restart that
        dictionary is empty while Redis still holds the receipt, so those routes
        answered 404 for work that was running. Reading the dispatch stream
        instead makes the answer survive the restart.

        The scan is bounded by the contract: `MAX_DISPATCH_ENTRIES` is 128, and
        the stream is trimmed to it, so this is a small constant-cost read
        rather than a second index that could disagree with the first.
        """
        try:
            entries = self.redis.xrange(
                v1.redis_key("dispatch", relationship_id),
                count=v1.MAX_DISPATCH_ENTRIES)
        except RedisUnavailable as exc:
            raise _definite("the dispatch record is unavailable") from exc
        for _, fields in entries:
            if fields.get("attempt_id") != attempt_id:
                continue
            try:
                return v1.parse_message(v1.JobEnvelope,
                                        fields.get("envelope", "").encode("utf-8"))
            except Exception:                                  # noqa: BLE001
                return None
        return None

    def active_attempts(self, relationship_id: str) -> int:
        """How many admitted attempts have not reached a terminal event.

        Derived from Redis, not from a counter this process keeps: a restarted
        API had a queue depth of zero while work was running, and a stale
        dictionary entry could hold capacity against a finished attempt forever.
        """
        try:
            entries = self.redis.xrange(
                v1.redis_key("dispatch", relationship_id),
                count=v1.MAX_DISPATCH_ENTRIES)
        except RedisUnavailable:
            return 0
        active = 0
        for _, fields in entries:
            attempt_id = fields.get("attempt_id")
            if attempt_id and self.terminal_state(relationship_id, attempt_id) is None:
                active += 1
        return active

    # -------------------------------------------------------------- events ---

    def terminal_state(self, relationship_id: str, attempt_id: str) -> str | None:
        """The attempt's terminal state, or None if it has not reached one.

        The last `attempt.state` event **is** the done marker. A separate key
        would be a second source of truth that can disagree with the log and
        expire on a different schedule; this one is written by the same atomic
        `XADD` that records the outcome, and it expires with the log it is part
        of.
        """
        events = self._stored_events(relationship_id, attempt_id)
        state = None
        for event in events:
            if event.data.kind == "attempt.state":
                state = event.data.current
        return state if state in v1.TERMINAL_ATTEMPT_STATES else None

    def _stored_events(self, relationship_id: str, attempt_id: str) -> list:
        key = v1.redis_key("events", relationship_id, attempt_id)
        try:
            entries = self.redis.xrange(key, count=v1.MAX_EVENT_ENTRIES)
        except RedisUnavailable as exc:
            raise _definite("the event log is unavailable") from exc
        events = []
        for _, fields in entries:
            body = fields.get("event")
            if not body:
                continue
            try:
                events.append(v1.parse_message(v1.Event, body.encode("utf-8")))
            except Exception:                                  # noqa: BLE001
                continue        # a record that fails the contract is dropped
        events.sort(key=lambda item: item.sequence)
        return events

    def read_events(self, relationship_id: str, attempt_id: str,
                    after_sequence: int = 0, *, admitted: bool = False) -> list[dict]:
        """Replay stored worker events in sequence order.

        `events_expired` means the record is gone, which a caller must be able
        to tell from "nothing has happened yet" — an empty list would read as a
        completed attempt with no output. But an attempt the worker has
        *admitted* and not yet started legitimately has no events, and calling
        that expired would fail work that is about to run. `admitted=True` says
        the caller already confirmed the receipt exists, so an empty log is
        "not yet", not "gone".
        """
        events = self._stored_events(relationship_id, attempt_id)
        if not events and not admitted:
            raise DispatchError(
                "events_expired",
                "this attempt's events are no longer available for replay",
                False, 410)
        return [json.loads(event.model_dump_json())
                for event in events if event.sequence > after_sequence]

    def is_live(self) -> bool:
        return self.redis.ping()


class ExecutorSession:
    """The executor's half: claim, lease, heartbeat, emit, acknowledge."""

    def __init__(self, redis: Redis, relationship_id: str, consumer: str):
        self.redis = redis
        self.relationship_id = relationship_id
        self.consumer = consumer

    def _key(self, kind: str, identifier: str) -> str:
        return v1.redis_key(kind, self.relationship_id, identifier)

    def ensure_group(self) -> None:
        self.redis.xgroup_create(
            v1.redis_key("dispatch", self.relationship_id), v1.REDIS_GROUP)

    def claim(self, attempt_id: str, epoch: int) -> bool:
        """Take the lease, or report that someone else holds it.

        `SET NX` on the lease key is what makes duplicate delivery harmless and
        what fences two executors off the same attempt. The stored value carries
        the consumer name and the pairing epoch, so `still_owned` can tell "my
        lease" from "someone else re-claimed it after mine expired".
        """
        return self.redis.set(self._key("lease", attempt_id),
                              f"{self.consumer}:{epoch}", nx=True,
                              ex=v1.LEASE_SECONDS)

    def still_owned(self, attempt_id: str, epoch: int) -> bool:
        return self.redis.get(self._key("lease", attempt_id)) == f"{self.consumer}:{epoch}"

    def heartbeat(self, attempt_id: str, epoch: int) -> bool:
        """Extend the lease, atomically, and only while it is still ours.

        The check and the extension are one `EVAL`. As two commands they raced:
        an executor could confirm ownership, lose the lease to a reclaim, and
        then extend the lease it no longer held — keeping alive work another
        executor had legitimately taken over.
        """
        return bool(self.redis.eval(
            EXTEND_LEASE,
            [self._key("lease", attempt_id), self._key("heartbeat", attempt_id)],
            [f"{self.consumer}:{epoch}", v1.LEASE_SECONDS, _now(),
             v1.HEARTBEAT_TTL_SECONDS]))

    def release(self, attempt_id: str, epoch: int) -> bool:
        """Drop our own lease and nothing else.

        An unconditional delete would remove the lease of whoever reclaimed the
        attempt after ours expired, letting two executors run it at once.
        """
        return bool(self.redis.eval(
            RELEASE_LEASE,
            [self._key("lease", attempt_id), self._key("heartbeat", attempt_id)],
            [f"{self.consumer}:{epoch}"]))

    def terminal_state(self, attempt_id: str) -> str | None:
        """Whether this attempt already finished, from its own event log."""
        return DispatchQueue(self.redis).terminal_state(self.relationship_id,
                                                        attempt_id)

    def cancelled(self, attempt_id: str) -> bool:
        return self.redis.get(self._key("cancel", attempt_id)) is not None

    def revoked(self) -> bool:
        return self.redis.get(
            self._key("cancel", self.relationship_id)) is not None

    def emit(self, event: v1.Event) -> None:
        """Store one validated event for replay.

        `sse_frame` is not used: this is storage, not a stream frame. The event
        is re-validated on the way out in `read_events`, so a trimmed or
        corrupted entry cannot reach a coordinator as a plausible record.
        """
        key = self._key("events", event.attempt_id or self.relationship_id)
        self.redis.xadd(key, {"event": event.model_dump_json(),
                              "sequence": str(event.sequence)},
                        maxlen=v1.MAX_EVENT_ENTRIES)
        self.redis.expire(key, v1.RETENTION_SECONDS)

    def acknowledge(self, entry_id: str) -> None:
        self.redis.xack(v1.redis_key("dispatch", self.relationship_id),
                        v1.REDIS_GROUP, entry_id)

    def next_entries(self, *, block_ms: int, count: int = 1) -> list:
        return self.redis.xreadgroup(
            v1.redis_key("dispatch", self.relationship_id), v1.REDIS_GROUP,
            self.consumer, count=count, block_ms=block_ms)

    def recover_pending(self, *, count: int = 8) -> list:
        """Claim entries abandoned by an executor that stopped.

        Idle longer than the lease means the previous owner is not heartbeating.
        This is the "a killed executor leaves recoverable pending work" path.
        """
        return self.redis.xautoclaim(
            v1.redis_key("dispatch", self.relationship_id), v1.REDIS_GROUP,
            self.consumer, v1.LEASE_SECONDS * 1000, count=count)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
