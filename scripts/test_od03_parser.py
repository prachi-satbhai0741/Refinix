#!/usr/bin/env python3
"""Offline checks for the OD-03 stream parsers and memory reporting.

No server, no network, no model. Runs anywhere Python does:

    python3 -m unittest scripts.test_od03_parser -v
    python3 scripts/test_od03_parser.py

These exist because a latency median is only trustworthy if a failed run is
rejected rather than quietly dropped.
"""

import json
import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from od03_runtime_comparison import (  # noqa: E402
    StreamError,
    memory_snapshot,
    parse_ollama_stream,
    parse_openai_stream,
)


def ol(*objs):
    """Timestamped NDJSON lines, 0.1 s apart."""
    return [(0.1 * (i + 1), json.dumps(o)) for i, o in enumerate(objs)]


def sse(*payloads):
    return [(0.1 * (i + 1), f"data: {p}") for i, p in enumerate(payloads)]


OLLAMA_DONE = {
    "done": True, "done_reason": "stop", "eval_count": 89,
    "eval_duration": 3_000_000_000, "load_duration": 200_000_000,
    "prompt_eval_duration": 60_000_000, "total_duration": 3_300_000_000,
}


class TestOllamaParser(unittest.TestCase):
    def test_good_stream(self):
        r = parse_ollama_stream(ol(
            {"message": {"content": "Hello"}, "done": False},
            {"message": {"content": " world"}, "done": False},
            OLLAMA_DONE,
        ))
        self.assertEqual(r["output_tokens"], 89)
        self.assertEqual(r["response_chars"], len("Hello world"))
        self.assertEqual(r["ttft_s"], 0.1)
        self.assertTrue(r["thinking_suppressed"])
        self.assertFalse(r["visible_output_empty"])
        self.assertEqual(len(r["response_sha256"]), 64)

    def test_identical_text_hashes_identically(self):
        a = parse_ollama_stream(ol({"message": {"content": "same"}}, OLLAMA_DONE))
        b = parse_ollama_stream(ol({"message": {"content": "same"}}, OLLAMA_DONE))
        c = parse_ollama_stream(ol({"message": {"content": "diff"}}, OLLAMA_DONE))
        self.assertEqual(a["response_sha256"], b["response_sha256"])
        self.assertNotEqual(a["response_sha256"], c["response_sha256"])

    def test_error_object_is_rejected(self):
        with self.assertRaisesRegex(StreamError, "server reported an error"):
            parse_ollama_stream(ol(
                {"message": {"content": "hi"}},
                {"error": "model requires more system memory"},
            ))

    def test_malformed_line_is_rejected(self):
        with self.assertRaisesRegex(StreamError, "malformed JSON"):
            parse_ollama_stream([(0.1, '{"message": {"content": "hi"'), (0.2, "{}")])

    def test_missing_done_record_is_rejected(self):
        with self.assertRaisesRegex(StreamError, "without a done record"):
            parse_ollama_stream(ol({"message": {"content": "hi"}, "done": False}))

    def test_done_without_metrics_is_rejected(self):
        with self.assertRaisesRegex(StreamError, "missing eval metrics"):
            parse_ollama_stream(ol(
                {"message": {"content": "hi"}}, {"done": True, "done_reason": "stop"}))

    def test_no_tokens_at_all_is_rejected(self):
        with self.assertRaisesRegex(StreamError, "no token was ever emitted"):
            parse_ollama_stream(ol({"message": {"content": ""}}, OLLAMA_DONE))

    def test_thinking_only_run_is_flagged_not_hidden(self):
        r = parse_ollama_stream(ol(
            {"message": {"content": "", "thinking": "reasoning..."}},
            dict(OLLAMA_DONE, done_reason="length"),
        ))
        self.assertTrue(r["visible_output_empty"])
        self.assertFalse(r["thinking_suppressed"])


class TestOpenAIParser(unittest.TestCase):
    GOOD = (
        json.dumps({"choices": [{"delta": {"content": "Hello"}}]}),
        json.dumps({"choices": [{"delta": {"content": " world"}}]}),
        json.dumps({"choices": [], "usage": {"completion_tokens": 89},
                    "timings": {"predicted_ms": 3000.0,
                                "predicted_per_second": 29.6}}),
        "[DONE]",
    )

    def test_good_stream(self):
        r = parse_openai_stream(sse(*self.GOOD))
        self.assertEqual(r["output_tokens"], 89)
        self.assertEqual(r["tokens_per_s"], 29.6)
        self.assertEqual(r["ttft_s"], 0.1)
        self.assertTrue(r["thinking_suppressed"])

    def test_missing_done_sentinel_is_rejected(self):
        with self.assertRaisesRegex(StreamError, r"\[DONE\] sentinel"):
            parse_openai_stream(sse(*self.GOOD[:-1]))

    def test_error_object_is_rejected(self):
        with self.assertRaisesRegex(StreamError, "server reported an error"):
            parse_openai_stream(sse(
                json.dumps({"choices": [{"delta": {"content": "hi"}}]}),
                json.dumps({"error": {"message": "context exceeded"}}),
            ))

    def test_malformed_payload_is_rejected(self):
        with self.assertRaisesRegex(StreamError, "malformed SSE payload"):
            parse_openai_stream(sse('{"choices": ['))

    def test_non_sse_line_is_rejected(self):
        with self.assertRaisesRegex(StreamError, "non-SSE line"):
            parse_openai_stream([(0.1, '{"choices": []}')])

    def test_missing_metrics_is_rejected(self):
        with self.assertRaisesRegex(StreamError, "neither a usage nor a timings"):
            parse_openai_stream(sse(
                json.dumps({"choices": [{"delta": {"content": "hi"}}]}), "[DONE]"))

    def test_separate_reasoning_is_counted_before_visible_output(self):
        for answer in ("answer", ""):
            with self.subTest(answer=answer):
                r = parse_openai_stream(sse(
                    json.dumps({"choices": [{"delta": {"reasoning_content": "reasoning"}}]}),
                    json.dumps({"choices": [{"delta": {"content": answer}}]}),
                    self.GOOD[2], "[DONE]",
                ))
                self.assertEqual(r["ttft_s"], 0.1)
                self.assertEqual(r["thinking_chars"], len("reasoning"))
                self.assertEqual(r["response_chars"], len(answer))
                self.assertFalse(r["thinking_suppressed"])
                self.assertEqual(r["visible_output_empty"], not answer)

    def test_usage_without_generation_timing_is_rejected(self):
        with self.assertRaisesRegex(StreamError, "generation timing"):
            parse_openai_stream(sse(
                self.GOOD[0],
                json.dumps({"usage": {"completion_tokens": 89}}), "[DONE]",
            ))

    def test_invalid_completion_token_count_is_rejected(self):
        for count in (0, -1, True, 1.5, "89"):
            with self.subTest(count=count):
                with self.assertRaisesRegex(StreamError, "completion-token count"):
                    parse_openai_stream(sse(
                        self.GOOD[0],
                        json.dumps({"usage": {"completion_tokens": count},
                                    "timings": {"predicted_ms": 400.0}}), "[DONE]",
                    ))

    def test_invalid_generation_timing_is_rejected(self):
        for field in ("predicted_ms", "predicted_per_second"):
            for value in (0, -1, True, "fast", float("nan"), float("inf")):
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(StreamError, "generation timing"):
                        parse_openai_stream(sse(
                            self.GOOD[0],
                            json.dumps({"usage": {"completion_tokens": 89},
                                        "timings": {field: value}}), "[DONE]",
                        ))

    def test_generation_speed_can_be_derived_from_duration(self):
        r = parse_openai_stream(sse(
            self.GOOD[0],
            json.dumps({"usage": {"completion_tokens": 12},
                        "timings": {"predicted_ms": 400.0}}), "[DONE]",
        ))
        self.assertEqual(r["tokens_per_s"], 30.0)

    def test_leaked_thinking_marker_is_reported(self):
        r = parse_openai_stream(sse(
            json.dumps({"choices": [{"delta": {"content": "<think>hmm</think> ok"}}]}),
            json.dumps({"choices": [], "usage": {"completion_tokens": 12},
                        "timings": {"predicted_ms": 400.0}}),
            "[DONE]",
        ))
        self.assertFalse(r["thinking_suppressed"])
        self.assertEqual(r["thinking_markers_found"], ["<think>", "</think>"])


class TestMemorySnapshot(unittest.TestCase):
    def test_ubuntu_runner_is_reported_separately_from_daemon(self):
        ps = "PID PPID RSS COMMAND\n2052 1 56004 ollama\n17155 2052 2209224 llama-server\n99 1 999999 unrelated-ollama\n"
        gpu = "17155, 2948\n99, 1000\n"
        with patch("od03_runtime_comparison.subprocess.run", side_effect=[
            subprocess.CompletedProcess([], 0, ps),
            subprocess.CompletedProcess([], 0, gpu),
        ]):
            result = memory_snapshot("ollama")
        self.assertEqual(result["processes"], [
            {"pid": 2052, "ppid": 1, "name": "ollama", "rss_mib": 54.7, "vram_mib": None},
            {"pid": 17155, "ppid": 2052, "name": "llama-server", "rss_mib": 2157.4, "vram_mib": 2948.0},
        ])
        self.assertNotIn("rss_mb", result)

    def test_macos_full_paths_and_multiple_candidates_remain_visible(self):
        ps = ("PID PPID RSS COMMAND\n1 0 50000 /usr/local/bin/ollama\n"
              "2 1 102400 /Applications/Ollama.app/Contents/Resources/llama-server\n"
              "3 4 204800 /opt/homebrew/bin/llama-server\n")
        with patch("od03_runtime_comparison.subprocess.run", side_effect=[
            subprocess.CompletedProcess([], 0, ps), FileNotFoundError(),
        ]):
            result = memory_snapshot("llama-server")
        self.assertEqual([p["pid"] for p in result["processes"]], [2, 3])
        self.assertEqual([p["rss_mib"] for p in result["processes"]], [100.0, 200.0])
        self.assertIn("not attributed", result["scope"])
        self.assertIn("no nvidia-smi", result["note"])

    def test_failed_process_queries_are_unavailable(self):
        with patch("od03_runtime_comparison.subprocess.run",
                   side_effect=subprocess.CalledProcessError(1, "probe")):
            result = memory_snapshot("ollama")
        self.assertEqual(result["processes"], [])
        self.assertIn("rss unavailable", result["note"])
        self.assertIn("vram unavailable", result["note"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
