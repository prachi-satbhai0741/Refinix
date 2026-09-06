"""Offline checks for the worker runtime adapter.

No server, model, network or FastAPI. FastAPI lives only inside the pinned
image, so these cover the parts testable outside it; the API surface itself is
checked at image build time (`--network=none`) and by the Ubuntu build handoff.
"""

import unittest
from unittest.mock import patch

from backend.worker import runtime


def stream(*objects):
    import json
    return [json.dumps(o).encode() + b"\n" for o in objects]


class FakeResponse:
    def __init__(self, lines): self._lines = lines
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __iter__(self): return iter(self._lines)


DONE = {"done": True, "done_reason": "stop", "eval_count": 5,
        "prompt_eval_count": 100, "total_duration": 1_000_000_000}


class TestBoundedSettings(unittest.TestCase):
    def test_truncation_and_shifting_are_disabled(self):
        """An oversized prompt must be rejected, never silently trimmed."""
        captured = {}

        def fake(path, payload=None, timeout=30):
            captured.update(payload or {})
            return FakeResponse(stream({"message": {"content": "hi"}}, DONE))

        with patch.object(runtime, "_post", fake):
            list(runtime.stream_chat([{"role": "user", "content": "x"}]))
        self.assertIs(captured["truncate"], False)
        self.assertIs(captured["shift"], False)
        self.assertIs(captured["think"], False)
        self.assertEqual(captured["options"]["num_ctx"], runtime.NUM_CTX)

    def test_worker_window_stays_4096_until_ubuntu_measures(self):
        self.assertEqual(runtime.NUM_CTX, 4096)


class TestLimitClassification(unittest.TestCase):
    def _limit(self, prompt, output):
        done = dict(DONE, done_reason="length",
                    prompt_eval_count=prompt, eval_count=output)
        with patch.object(runtime, "_post",
                          lambda *a, **k: FakeResponse(stream({"message": {"content": "x"}}, done))):
            result = list(runtime.stream_chat([{"role": "user", "content": "x"}]))
        return result[-1][1]["limit_reason"]

    # Boundaries are expressed against the worker's own configured window, so
    # a changed window cannot leave the cases silently unreachable.
    def test_output_stop_when_only_the_reply_limit_is_reached(self):
        prompt = runtime.NUM_CTX - runtime.NUM_PREDICT - 100      # total stays under
        self.assertEqual(self._limit(prompt, runtime.NUM_PREDICT), "output")

    def test_context_stop_when_only_the_window_is_reached(self):
        self.assertEqual(self._limit(runtime.NUM_CTX - 10, 10), "context")

    def test_both_bounds_reached_reports_both(self):
        """Counts establish which bounds were reached, not which fired first."""
        prompt = runtime.NUM_CTX - runtime.NUM_PREDICT
        self.assertEqual(self._limit(prompt, runtime.NUM_PREDICT), "context_and_output")

    def test_unknown_when_counts_are_missing(self):
        done = {"done": True, "done_reason": "length"}
        with patch.object(runtime, "_post",
                          lambda *a, **k: FakeResponse(stream({"message": {"content": "x"}}, done))):
            result = list(runtime.stream_chat([{"role": "user", "content": "x"}]))
        self.assertEqual(result[-1][1]["limit_reason"], "unknown")


class TestFailureHandling(unittest.TestCase):
    def test_error_object_is_raised_not_returned_as_text(self):
        with patch.object(runtime, "_post",
                          lambda *a, **k: FakeResponse(stream({"error": "model missing"}))):
            with self.assertRaises(runtime.RuntimeUnavailable):
                list(runtime.stream_chat([{"role": "user", "content": "x"}]))

    def test_stream_without_done_is_rejected(self):
        with patch.object(runtime, "_post",
                          lambda *a, **k: FakeResponse(stream({"message": {"content": "x"}}))):
            with self.assertRaises(runtime.RuntimeUnavailable):
                list(runtime.stream_chat([{"role": "user", "content": "x"}]))

    def test_cancel_stops_before_the_next_chunk(self):
        with patch.object(runtime, "_post",
                          lambda *a, **k: FakeResponse(stream({"message": {"content": "a"}}, DONE))):
            kinds = [k for k, _ in runtime.stream_chat(
                [{"role": "user", "content": "x"}], should_cancel=lambda: True)]
        self.assertEqual(kinds, ["cancelled"])


class TestProbe(unittest.TestCase):
    def test_runtime_requests_ignore_proxies_and_refuse_redirects(self):
        class Opener:
            def open(self, request, timeout):
                return FakeResponse([])

        with patch.object(runtime.urllib.request, "build_opener",
                          return_value=Opener()) as build:
            runtime._post("/api/version")
        handlers = build.call_args.args
        proxy = next(item for item in handlers
                     if isinstance(item, runtime.urllib.request.ProxyHandler))
        self.assertEqual(proxy.proxies, {})
        self.assertTrue(any(isinstance(item, runtime._NoRedirect)
                            for item in handlers))

    def test_unreachable_runtime_reports_honestly(self):
        with patch.object(runtime, "_post", side_effect=OSError("refused")):
            state = runtime.probe()
        self.assertFalse(state["reachable"])
        self.assertIsNone(state["server_version"])
        self.assertIn("OSError", state["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
