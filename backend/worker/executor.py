"""AF-005 executor: the consumer that turns a queued envelope into events.

One process, one consumer group. It runs from the same image as the worker API
with a different command, so C06 adds no second image and no second build.

The loop is deliberately boring:

    recover abandoned entries -> read new ones -> claim -> run -> acknowledge

Each stage has one failure it exists to prevent.

* **recover** — `XAUTOCLAIM` past the lease deadline. A killed executor's entries
  stay in the group's pending list; without this they stay there forever and the
  work is lost while looking delivered.
* **claim** — `SET NX` on the lease. Redis Streams give at-least-once delivery,
  so the same envelope can arrive twice; the lease is what makes the second copy
  a no-op instead of a second run.
* **acknowledge** — only after a terminal state is emitted. Acknowledging first
  would drop work that then failed to run.

Cancellation and revocation are polled, not pushed. The executor has no inbound
socket by design — its NetworkPolicy allows Redis and the runtime bridge and
nothing else — so a coordinator's cancel reaches it through the Redis key the
worker API sets.

Run it with:

    python -m backend.worker.executor
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
import uuid

from backend.contracts import v1
from backend.worker import codegen, jobspec, packages as packages_module, runtime
from backend.worker.dispatch import ExecutorSession
from backend.worker.redis_client import Redis, RedisError, RedisUnavailable

BLOCK_MS = 5_000
IDLE_SLEEP = 1.0
RECONNECT_SLEEP = 3.0
CANCEL_POLL_SECONDS = 1.0
PACKAGE_PURGE_INTERVAL_SECONDS = 300.0

# One JSON proposal or one JSON validation result, delivered as bounded output
# deltas so the coordinator reconstructs it from validated events exactly as it
# does a chat answer. No second transport.
DELTA_CHARS = 2048


class Stopped(Exception):
    """SIGTERM arrived. Unwinding leaves the current entry unacknowledged and
    therefore recoverable, which is the behaviour a rolling restart needs."""


class Executor:
    def __init__(self, session: ExecutorSession, *, node_id: str,
                 stop_check=None, packages=None, validator=None):
        self.session = session
        self.node_id = node_id
        self._stop_check = stop_check or (lambda: False)
        # AF-010: the job package volume. Separate from pairing state, which
        # this process is never given.
        self.packages = packages if packages is not None else packages_module.PackageStore()
        self._next_package_purge = 0.0
        self._purge_expired_packages()
        # AF-011: the Kubernetes validation runner. Injected so the offline
        # checks drive every failure path without a cluster.
        self.validator = validator if validator is not None else jobspec.JobValidator()

    # ---------------------------------------------------------------- loop ---

    def run_once(self) -> int:
        """One pass. Returns how many entries were handled, for the caller's
        sleep decision and for the offline checks."""
        self._purge_expired_packages()
        handled = 0
        for entry_id, fields in self.session.recover_pending():
            handled += self._handle(entry_id, fields, recovered=True)
        if handled:
            return handled
        for entry_id, fields in self.session.next_entries(block_ms=BLOCK_MS):
            handled += self._handle(entry_id, fields, recovered=False)
        return handled

    def _purge_expired_packages(self) -> None:
        now = time.monotonic()
        if now < self._next_package_purge:
            return
        self._next_package_purge = now + PACKAGE_PURGE_INTERVAL_SECONDS
        try:
            self.packages.purge_expired()
        except OSError:
            pass

    def _handle(self, entry_id: str, fields: dict, *, recovered: bool) -> int:
        """Run one delivered entry, and acknowledge it only when it is safe to.

        Acknowledgement removes the entry from the group's pending list for
        every consumer, so it is the point of no return: after it, no executor
        will ever see this entry again. There are exactly three cases where
        that is correct, and they are the only three `XACK` calls below:

        * the entry cannot be parsed, so no executor will ever make progress
          on it and leaving it pending means reclaiming the same poison
          forever;
        * the attempt already has a terminal event, so this is a duplicate
          delivery of finished work;
        * this executor ran it and its outcome is durably stored.

        Every other path leaves the entry pending, which is what makes it
        recoverable.
        """
        envelope, epoch = self._parse(fields)
        if envelope is None:
            # Unparsable entries are acknowledged and dropped: leaving them
            # pending would make the executor reclaim the same poison forever.
            self.session.acknowledge(entry_id)
            return 1

        # A duplicate delivered after the first run finished must not run again.
        # The terminal event in the log is the record that it did; without this
        # check, at-least-once delivery produces a second answer to one request.
        if self.session.terminal_state(envelope.attempt_id) is not None:
            self.session.acknowledge(entry_id)
            self._purge_package(envelope)
            return 1

        if not self.session.claim(envelope.attempt_id, epoch):
            # Someone else holds the lease and is running this attempt.
            #
            # DO NOT ACKNOWLEDGE. `XAUTOCLAIM` transfers the one pending entry
            # to this consumer rather than handing out a copy, so there is no
            # "our copy" to dispose of: `XACK` here removes the entry from the
            # group's pending list for everyone. If the live owner then died
            # before storing a terminal event, nothing would remain to recover
            # and the attempt would be lost while looking delivered.
            #
            # Leaving it pending is what keeps it recoverable. Claiming it
            # already reset its idle timer, so the next `XAUTOCLAIM` waits a
            # full lease before offering it again — by which time the owner has
            # either acknowledged it or let its lease expire, and a later
            # recovery can run it.
            return 1

        outcome = "interrupted"
        try:
            outcome = self.execute(envelope, epoch, recovered=recovered)
        finally:
            try:
                self.session.release(envelope.attempt_id, epoch)
                # Acknowledge ONLY against a durably stored terminal event. An
                # interrupted attempt, or one whose Redis vanished mid-run, has
                # no record of its outcome; leaving the entry pending is what
                # makes it recoverable rather than silently lost.
                if outcome != "interrupted" and \
                        self.session.terminal_state(envelope.attempt_id) is not None:
                    self.session.acknowledge(entry_id)
                    self._purge_package(envelope)
            except (RedisUnavailable, RedisError):
                # Nothing to release or acknowledge against. The entry stays
                # pending, which is the correct recoverable state.
                pass
        return 1

    def _purge_package(self, envelope: v1.JobEnvelope) -> None:
        if envelope.task_type != "code":
            return
        try:
            self.packages.purge(
                relationship_id=envelope.relationship_id,
                workspace_id=envelope.workspace_id,
                attempt_id=envelope.attempt_id)
        except OSError:
            pass

    @staticmethod
    def _parse(fields: dict):
        body = fields.get("envelope")
        if not body:
            return None, 0
        try:
            envelope = v1.parse_message(v1.JobEnvelope, body.encode("utf-8"))
        except Exception:                                      # noqa: BLE001
            return None, 0
        try:
            epoch = int(fields.get("epoch", "0"))
        except (TypeError, ValueError):
            epoch = 0
        return envelope, epoch

    # ------------------------------------------------------------ execution ---

    def execute(self, envelope: v1.JobEnvelope, epoch: int, *,
                recovered: bool = False) -> str:
        """Run one attempt to a terminal state and return that state."""
        state = {"sequence": 0, "lost": False}

        def emit(data: dict) -> None:
            """Record one event, or note that the log is gone and stop trying.

            A vanished Redis must not raise out of `execute`. There is nowhere
            left to write, so further emits are pointless; the attempt ends as
            `interrupted` and the coordinator sees `worker_lost`, which is the
            truth. Raising here would abandon the lease release below.
            """
            if state["lost"]:
                return
            state["sequence"] += 1
            try:
                self.session.emit(v1.Event(
                    contract_version=v1.CONTRACT_VERSION,
                    workspace_id=envelope.workspace_id, job_id=envelope.job_id,
                    attempt_id=envelope.attempt_id, event_id=str(uuid.uuid4()),
                    sequence=state["sequence"], producer_node_id=self.node_id,
                    producer="worker", occurred_at=_now(), data=data))
            except (RedisUnavailable, RedisError):
                state["lost"] = True

        emit({"kind": "attempt.state", "previous": None, "current": "queued"})

        if self.session.revoked():
            # Fenced before a single token is produced.
            emit({"kind": "attempt.state", "previous": "queued",
                  "current": "cancelled"})
            return "cancelled"
        if self.session.cancelled(envelope.attempt_id):
            emit({"kind": "attempt.state", "previous": "queued",
                  "current": "cancelled"})
            return "cancelled"

        budget = _seconds_until(envelope.deadline_at)
        if budget <= 0:
            emit({"kind": "attempt.state", "previous": "queued",
                  "current": "failed"})
            return "failed"

        emit({"kind": "attempt.state", "previous": "queued", "current": "running"})
        deadline = time.monotonic() + min(budget, float(envelope.limits.runtime_seconds))
        checked = {"at": 0.0}

        def should_cancel() -> bool:
            """Poll Redis at most once a second: cancellation must be prompt,
            but a per-token round trip would dominate generation time."""
            if self._stop_check():
                return True
            if time.monotonic() >= deadline:
                return True
            now = time.monotonic()
            if now - checked["at"] < CANCEL_POLL_SECONDS:
                return False
            checked["at"] = now
            try:
                if self.session.revoked() or self.session.cancelled(envelope.attempt_id):
                    return True
                # A lost lease means another executor took over; stop rather
                # than produce a second copy of the same answer.
                # An atomic owner-checked heartbeat: False means the lease is
                # no longer ours, so another executor took over and a second
                # copy of this answer must not be produced.
                return not self.session.heartbeat(envelope.attempt_id, epoch)
            except (RedisUnavailable, RedisError):
                # Redis is gone. Stop: continuing would produce output no one
                # can read and no lease protects.
                return True

        if envelope.task_type == "code" and \
                "code.validate" in envelope.required_capabilities:
            # A validation attempt runs no model at all: it creates one
            # restricted Job and reports exactly what that Job returned.
            produced, failed = self._validate(envelope, emit, should_cancel,
                                              deadline)
            if failed == "cancelled":
                emit({"kind": "attempt.state", "previous": "running",
                      "current": "cancelled"})
                return "interrupted" if state["lost"] else "cancelled"
        else:
            produced, failed = self._generate(envelope, emit, should_cancel,
                                              deadline, state)
            if failed == "cancelled":
                emit({"kind": "attempt.state", "previous": "running",
                      "current": "cancelled"})
                return "interrupted" if state["lost"] else "cancelled"
        if failed is not None:
            emit({"kind": "attempt.state", "previous": "running", "current": "failed"})
            return "interrupted" if state["lost"] else "failed"

        emit({"kind": "attempt.state", "previous": "running", "current": "validating"})
        emit({"kind": "attempt.state", "previous": "validating", "current": "completed"})
        # An attempt whose terminal event never reached the log is not
        # "completed" as far as anyone else can tell, and saying so would be a
        # claim about a record that does not exist.
        return "interrupted" if state["lost"] else "completed"


    # -------------------------------------------------------- production ---

    def _emit_output(self, emit, text: str, limit: int) -> str | None:
        """Send one bounded reply as deltas. Returns a failure reason or None."""
        if len(text.encode("utf-8")) > limit:
            return "output limit reached"
        for index in range(0, len(text), DELTA_CHARS):
            emit({"kind": "output.delta", "text": text[index:index + DELTA_CHARS]})
        return None

    def _generate(self, envelope, emit, should_cancel, deadline, state):
        """Run the model. Chat sends the request text; Code sends its package.

        Returns `(produced, failure)`, where a failure of `"cancelled"` is the
        caller's signal to emit a cancellation rather than a failure.
        """
        if envelope.task_type == "code":
            try:
                selection = codegen.resolve_selection(self.packages, envelope)
            except (LookupError, UnicodeDecodeError, OSError):
                # The package is gone, incomplete, or no longer matches the
                # envelope. Prompting the model with a partial selection would
                # produce a proposal against files nobody chose.
                return "", "this attempt's file package could not be resolved"
            messages = codegen.build_messages(envelope.original_request, selection)
        else:
            messages = [{"role": "user", "content": envelope.original_request}]

        produced, metrics, failed = [], {}, None
        try:
            options = {"should_cancel": should_cancel,
                       "timeout": max(0.5, deadline - time.monotonic())}
            if envelope.model:
                options["model"] = envelope.model.model_id
            for kind, payload in runtime.stream_chat(messages, **options):
                if kind == "delta":
                    produced.append(payload)
                    if len("".join(produced).encode("utf-8")) > envelope.limits.output_bytes:
                        failed = "output limit reached"
                        break
                    for index in range(0, len(payload), DELTA_CHARS):
                        emit({"kind": "output.delta",
                              "text": payload[index:index + DELTA_CHARS]})
                elif kind == "cancelled":
                    return "".join(produced), "cancelled"
                elif kind == "done":
                    metrics = payload
        except Exception:                                      # noqa: BLE001
            failed = "the local model runtime failed"

        text = "".join(produced)
        if failed is None and metrics.get("done_reason") != "stop":
            failed = "the reply was incomplete"
        if failed is None and "text.nonempty" in envelope.output.validators \
                and not text.strip():
            failed = "the runtime returned no visible output"
        if failed is None and envelope.task_type == "code" and not text.strip():
            failed = "the runtime returned no proposal"
        return text, failed

    def _validate(self, envelope, emit, should_cancel, deadline):
        """Run one restricted Kubernetes Job and report only what it returned.

        No model, no network and no repository. Every failure here — an
        unreachable API, a refused ServiceAccount, a deadline, a deleted Job,
        an unreadable result — becomes a failed attempt. There is no path from
        any of them to a passed validation.
        """
        budget = max(1.0, deadline - time.monotonic())
        try:
            result = self.validator.run(
                envelope, package_root=self.packages,
                deadline_seconds=budget, should_cancel=should_cancel)
        except jobspec.ValidationUnavailable as exc:
            return "", f"sandbox validation is unavailable: {exc}"
        except Exception:                                      # noqa: BLE001
            return "", "sandbox validation could not be run"
        if result.get("cancelled"):
            return "", "cancelled"
        body = json.dumps(result, sort_keys=True, separators=(",", ":"))
        if (reason := self._emit_output(emit, body, envelope.limits.output_bytes)):
            return body, reason
        # A Job that ran and failed is still a COMPLETED attempt carrying a
        # failed result: the coordinator needs the output to show why. Only an
        # attempt that could not produce a result at all fails here.
        if not result.get("observed"):
            return body, "the validation Job produced no readable result"
        return body, None


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _seconds_until(stamp: str) -> float:
    from datetime import datetime, timezone
    deadline = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (deadline - datetime.now(timezone.utc)).total_seconds()


def main(argv: list[str] | None = None) -> int:
    """Long-running entry point. Requires the relationship it serves.

    The relationship is configuration, not discovery: an executor that scanned
    Redis for whatever relationships exist would serve a revoked one.
    """
    relationship_id = os.environ.get("AEGIS_RELATIONSHIP_ID", "").strip()
    if not relationship_id:
        sys.stderr.write("AEGIS_RELATIONSHIP_ID is required\n")
        return 2
    host = os.environ.get("AEGIS_REDIS_HOST", "redis")
    port = int(os.environ.get("AEGIS_REDIS_PORT", "6379"))
    password = os.environ.get("AEGIS_REDIS_PASSWORD") or None
    node_id = os.environ.get("AEGIS_NODE_ID", "").strip() or str(uuid.uuid4())
    consumer = os.environ.get("HOSTNAME") or f"executor-{uuid.uuid4().hex[:8]}"

    stopping = {"now": False}

    def stop(_signal, _frame):
        stopping["now"] = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    redis = Redis(host, port, password=password)
    session = ExecutorSession(redis, relationship_id, consumer)
    executor = Executor(session, node_id=node_id,
                        stop_check=lambda: stopping["now"])

    sys.stderr.write(f"executor {consumer} serving {relationship_id}\n")
    while not stopping["now"]:
        try:
            session.ensure_group()
            if executor.run_once() == 0:
                time.sleep(IDLE_SLEEP)
        except (RedisUnavailable, RedisError) as exc:
            # Redis loss is expected and survivable: nothing canonical lives
            # here. Report it once per attempt and keep trying.
            sys.stderr.write(f"redis unavailable: {type(exc).__name__}\n")
            time.sleep(RECONNECT_SLEEP)
        except Stopped:
            break
    redis.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
