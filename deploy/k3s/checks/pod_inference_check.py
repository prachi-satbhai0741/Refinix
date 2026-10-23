"""Bounded inference through the worker's runtime adapter, run inside the Pod.

Exercises AF-003's model path without opening dispatch: it imports the adapter
directly, so the public job routes stay closed at 503 throughout.

The deadline uses SIGALRM via signal.setitimer, which interrupts a blocked
socket read. A timer thread that only sets a flag cannot — the read would sit
there until the socket timeout, long past the deadline. The initial runtime
probe is inside the deadline too.

Reads stdin-free; exits 0 only on a genuine, complete, expected answer.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time

EXPECTED = os.environ.get("AEGIS_EXPECTED_ANSWER", "POD").strip().upper()
DEADLINE = float(os.environ.get("AEGIS_CHECK_DEADLINE", "90"))

EXIT_OK = 0
EXIT_FAILED_CHECKS = 1
EXIT_UNREACHABLE = 2
EXIT_DEADLINE = 3


class Deadline(BaseException):
    """Raised from SIGALRM so a blocked read is actually interrupted.

    BaseException, not Exception, and that is the whole point: the raise lands
    inside the adapter, whose `except Exception` handlers (runtime.py:50, 61,
    68) would otherwise catch it and return a normal error. The deadline would
    then be reported as an ordinary failure, or not enforced at all. Deriving
    from BaseException makes it pass through, exactly as KeyboardInterrupt
    does, while `except Deadline` below still catches it by name.

    This is fixed at the check boundary on purpose: the C04 worker image is
    frozen and must not be rebuilt to make a check work.
    """


def _arm(seconds: float) -> None:
    signal.signal(signal.SIGALRM,
                  lambda signum, frame: (_ for _ in ()).throw(
                      Deadline(f"deadline of {seconds}s reached")))
    signal.setitimer(signal.ITIMER_REAL, seconds)


def _disarm() -> None:
    signal.setitimer(signal.ITIMER_REAL, 0)
    try:
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
    except ValueError:
        pass


def main() -> int:
    from backend.contracts import profiles as inference_profiles
    from backend.worker import runtime          # imported after the env is read

    started = time.monotonic()
    failures: list[str] = []
    first: float | None = None
    text: list[str] = []
    metrics: dict = {}

    try:
        _arm(DEADLINE)
        probe = runtime.probe()                 # inside the deadline
        print(json.dumps({
            "endpoint": probe.get("endpoint"), "reachable": probe.get("reachable"),
            "server_version": probe.get("server_version"),
            "models": probe.get("models"), "error": probe.get("error")}))
        if not probe.get("reachable"):
            print("FAIL: runtime unreachable from the Pod — check the proxy unit, "
                  "its host restrictions, and 30-runtime-egress.yaml")
            return EXIT_UNREACHABLE

        # The same qualified semantics the executor uses. A check that sent
        # raw settings would prove the Pod can reach a runtime while proving
        # nothing about whether this Pod may run this model for this workflow,
        # which is the question C05 is actually asking.
        qualified = runtime.qualified_profiles(probe)
        profile = next((item for item in qualified
                        if item.workflow_mode == inference_profiles.CHAT), None)
        if profile is None:
            print("FAIL: this Pod has no qualified chat profile for the "
                  "observed model, runtime version and target profile")
            return EXIT_FAILED_CHECKS
        inference = inference_profiles.request(
            profile, reasoning="disabled", decoder="text")
        for kind, payload in runtime.stream_chat(
                [{"role": "user", "content": f"Reply with the single word {EXPECTED}."}],
                profile=profile, inference=inference,
                timeout=DEADLINE):
            if kind == "delta":
                if first is None:
                    first = round(time.monotonic() - started, 3)
                text.append(payload)
            elif kind == "cancelled":
                failures.append("the adapter reported cancellation")
            elif kind == "done":
                metrics = payload
    except Deadline as exc:
        print(json.dumps({"elapsed_seconds": round(time.monotonic() - started, 3)}))
        print(f"FAIL: {exc}")
        return EXIT_DEADLINE
    except Exception as exc:                                   # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return EXIT_FAILED_CHECKS
    finally:
        _disarm()                               # always, even on the failure paths

    answer = "".join(text).strip()
    elapsed = round(time.monotonic() - started, 3)

    if not answer:
        failures.append("empty answer")
    elif EXPECTED not in answer.upper():
        failures.append(f"answer does not contain {EXPECTED!r}: {answer[:80]!r}")
    if metrics.get("done_reason") != "stop":
        failures.append(
            f"did not stop normally: done_reason={metrics.get('done_reason')!r} "
            f"limit_reason={metrics.get('limit_reason')!r}")
    for field in ("prompt_tokens", "output_tokens"):
        value = metrics.get(field)
        if not isinstance(value, int) or value <= 0:
            failures.append(f"{field} missing or not positive: {value!r}")
    # Measurements the C05 evidence needs.
    for field in ("context_window", "runtime_ms"):
        if metrics.get(field) is None:
            failures.append(f"{field} not reported")
    if first is None:
        failures.append("no first-token time observed")
    if elapsed > DEADLINE:
        failures.append(f"took {elapsed}s against a {DEADLINE}s deadline")

    print(json.dumps({
        "answer": answer[:80], "first_token_seconds": first,
        "elapsed_seconds": elapsed,
        "done_reason": metrics.get("done_reason"),
        "limit_reason": metrics.get("limit_reason"),
        "prompt_tokens": metrics.get("prompt_tokens"),
        "output_tokens": metrics.get("output_tokens"),
        "context_window": metrics.get("context_window"),
        "runtime_ms": metrics.get("runtime_ms")}, indent=1))

    if failures:
        for message in failures:
            print(f"FAIL: {message}")
        return EXIT_FAILED_CHECKS
    print("PASS: bounded inference completed normally through the runtime adapter")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
