"""Offline checks for the per-model Reasoning switch.

The runtime is a local HTTP stand-in, so the exact `/api/chat` payload and the
exact stream parsing are both observed. No model is called and no real Ollama
server is contacted.

    python3 -m unittest backend.coordinator.test_reasoning -v
"""

import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import db, models, runtime
from backend.coordinator.server import Coordinator, RequestError


class FakeOllama(BaseHTTPRequestHandler):
    """Records the request body and replays a scripted NDJSON stream."""

    protocol_version = "HTTP/1.1"
    script: list = []
    seen: list = []
    hold: threading.Event | None = None

    def log_message(self, *_a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        type(self).seen.append(json.loads(body))
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for record in type(self).script:
            if record == "__hold__":
                if type(self).hold is not None:
                    type(self).hold.wait(20)
                continue
            payload = (json.dumps(record) + "\n").encode()
            self.wfile.write(b"%x\r\n" % len(payload) + payload + b"\r\n")
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()


class RuntimeBase(unittest.TestCase):
    def setUp(self):
        FakeOllama.seen = []
        FakeOllama.script = []
        FakeOllama.hold = threading.Event()
        class Quiet(ThreadingHTTPServer):
            # A cancelled stream resets the connection on purpose; that is the
            # behaviour under test, not an error worth printing.
            def handle_error(self, request, client_address):
                pass

        self.server = Quiet(("127.0.0.1", 0), FakeOllama)
        self.server.daemon_threads = True
        self.server.block_on_close = False
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.host = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        if FakeOllama.hold:
            FakeOllama.hold.set()
        self.server.shutdown()
        self.server.server_close()

    def run_stream(self, **kwargs):
        with patch.object(runtime, "HOST", self.host):
            return list(runtime.stream_chat([{"role": "user", "content": "hi"}], **kwargs))


DONE = {"done": True, "done_reason": "stop", "eval_count": 3}


class TestRequestPayload(RuntimeBase):
    def test_off_sends_top_level_think_false(self):
        FakeOllama.script = [{"message": {"content": "hello"}}, DONE]
        self.run_stream(think=False)
        self.assertIs(FakeOllama.seen[0]["think"], False)

    def test_on_sends_top_level_think_true(self):
        FakeOllama.script = [{"message": {"content": "hello"}}, DONE]
        self.run_stream(think=True)
        self.assertIs(FakeOllama.seen[0]["think"], True)

    def test_no_qwen_prompt_switch_is_used(self):
        FakeOllama.script = [{"message": {"content": "hello"}}, DONE]
        self.run_stream(think=True)
        blob = json.dumps(FakeOllama.seen[0])
        self.assertNotIn("/think", blob)
        self.assertNotIn("/nothink", blob)

    def test_the_bounded_settings_are_unchanged_by_reasoning(self):
        FakeOllama.script = [{"message": {"content": "hello"}}, DONE]
        self.run_stream(think=True)
        sent = FakeOllama.seen[0]
        self.assertEqual(sent["options"]["num_ctx"], runtime.NUM_CTX)
        self.assertEqual(sent["options"]["num_predict"], runtime.NUM_PREDICT)
        self.assertIs(sent["truncate"], False)
        self.assertIs(sent["shift"], False)

    def test_metrics_report_the_output_limit_actually_sent(self):
        FakeOllama.script = [{"done": True, "done_reason": "length",
                              "prompt_eval_count": 100,
                              "eval_count": 3072}]
        records = self.run_stream(num_predict=3072)
        metrics = next(payload for kind, payload in records if kind == "done")
        self.assertEqual(metrics["output_token_limit"], 3072)
        self.assertEqual(metrics["limit_reason"], "output")

    def test_the_default_matches_the_accepted_execution_one_behaviour(self):
        FakeOllama.script = [{"message": {"content": "hello"}}, DONE]
        self.run_stream()
        self.assertIs(FakeOllama.seen[0]["think"], runtime.THINK)
        self.assertIs(runtime.THINK, False)


class TestStreamSeparation(RuntimeBase):
    def test_thinking_chunks_never_become_the_answer(self):
        FakeOllama.script = [
            {"message": {"thinking": "SECRET REASONING"}},
            {"message": {"thinking": "MORE REASONING"}},
            {"message": {"content": "visible answer"}},
            DONE,
        ]
        events = self.run_stream(think=True)
        kinds = [kind for kind, _ in events]
        self.assertEqual(kinds, ["thinking", "thinking", "delta", "done"])
        answer = "".join(p for k, p in events if k == "delta")
        self.assertEqual(answer, "visible answer")
        self.assertNotIn("SECRET REASONING", answer)

    def test_visible_content_still_streams_normally(self):
        FakeOllama.script = [{"message": {"content": "one "}},
                             {"message": {"content": "two"}}, DONE]
        events = self.run_stream(think=True)
        self.assertEqual("".join(p for k, p in events if k == "delta"), "one two")


class TestCancellationWithReasoning(RuntimeBase):
    def test_a_cancel_during_a_thinking_only_stream_takes_effect_quickly(self):
        FakeOllama.script = [{"message": {"thinking": "still working"}}, "__hold__",
                             {"message": {"content": "never seen"}}, DONE]
        cancel = threading.Event()
        events, finished = [], threading.Event()

        def read():
            with patch.object(runtime, "HOST", self.host):
                for item in runtime.stream_chat([{"role": "user", "content": "hi"}],
                                                think=True, should_cancel=cancel.is_set):
                    events.append(item)
            finished.set()

        threading.Thread(target=read, daemon=True).start()
        deadline = time.monotonic() + 5
        while not events and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(events[0][0], "thinking")
        started = time.monotonic()
        cancel.set()
        self.assertTrue(finished.wait(5), "cancel did not reach the quiet stream")
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(events[-1], ("cancelled", {}))

    def test_a_cancel_before_response_headers_is_reported_as_cancelled(self):
        cancel = threading.Event()
        cancel.set()
        events = self.run_stream(think=True, should_cancel=cancel.is_set)
        self.assertEqual(events, [("cancelled", {})])


class CoordinatorBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.runtime_probe = patch.object(runtime, "probe", return_value={
            "reachable": True, "server_version": "test",
            "models": [runtime.MODEL],
            "digests": {runtime.MODEL:
                        models.entry_for(runtime.MODEL).manifest_sha256},
            "loaded": None, "endpoint": runtime.HOST, "error": None})
        self.runtime_probe.start()
        self.addCleanup(self.runtime_probe.stop)
        self.c = Coordinator(Path(self.dir.name) / "state.sqlite3")
        self.chat = db.create_chat(self.c.conn, self.c.workspace_id, "check")

    def tearDown(self):
        self.c.conn.close()
        self.dir.cleanup()

    def submit(self, text="hello"):
        with patch("backend.coordinator.server.threading.Thread.start"):
            return self.c.submit(self.chat, text)


class TestPersistenceAndSnapshot(CoordinatorBase):
    def test_the_default_is_off_and_a_change_is_stored_per_model(self):
        self.assertFalse(db.get_reasoning(self.c.conn, runtime.MODEL))
        db.set_reasoning(self.c.conn, runtime.MODEL, True)
        self.assertTrue(db.get_reasoning(self.c.conn, runtime.MODEL))
        self.assertFalse(db.get_reasoning(self.c.conn, "another-model:1b"))

    def test_only_a_boolean_is_accepted(self):
        for bad in ("true", 1, None, [], {}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    db.set_reasoning(self.c.conn, runtime.MODEL, bad)

    def test_the_choice_survives_a_coordinator_restart(self):
        db.set_reasoning(self.c.conn, runtime.MODEL, True)
        path = Path(self.dir.name) / "state.sqlite3"
        self.c.conn.close()
        self.c = Coordinator(path)
        self.assertTrue(db.get_reasoning(self.c.conn, runtime.MODEL))

    def test_an_attempt_records_the_model_and_value_it_ran_with(self):
        db.set_reasoning(self.c.conn, runtime.MODEL, True)
        seen = {}

        def stream(messages, *, should_cancel=None, think=None, model=None,
                   num_predict=None):
            seen["think"] = think
            yield "delta", "answer"
            yield "done", {"done_reason": "stop"}

        job = self.submit()
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat)
        self.assertIs(seen["think"], True)
        attempt = self.c.job_detail(job)["attempts"][-1]
        recorded = json.loads(attempt["reasoning_json"])
        self.assertEqual(recorded, {"model": runtime.MODEL, "reasoning_enabled": True})

    def test_changing_the_switch_mid_request_does_not_change_that_attempt(self):
        db.set_reasoning(self.c.conn, runtime.MODEL, True)
        observed = {}
        released = threading.Event()

        def stream(messages, *, should_cancel=None, think=None, model=None,
                   num_predict=None):
            observed["think"] = think
            # The user flips the switch while this request is running.
            db.set_reasoning(self.c.conn, runtime.MODEL, False)
            released.set()
            yield "delta", "answer"
            yield "done", {"done_reason": "stop"}

        job = self.submit()
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat)
        self.assertTrue(released.is_set())
        self.assertIs(observed["think"], True)
        attempt = self.c.job_detail(job)["attempts"][-1]
        self.assertTrue(json.loads(attempt["reasoning_json"])["reasoning_enabled"])
        # The new value applies to the next request only.
        self.assertFalse(db.get_reasoning(self.c.conn, runtime.MODEL))


class TestThinkingOnlyCompletion(CoordinatorBase):
    def test_reasoning_that_eats_the_budget_fails_with_a_specific_message(self):
        db.set_reasoning(self.c.conn, runtime.MODEL, True)

        def stream(messages, *, should_cancel=None, think=None, model=None,
                   num_predict=None):
            yield "thinking", "a very long deliberation"
            yield "done", {"done_reason": "length", "limit_reason": "output"}

        job = self.submit()
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat)

        detail = self.c.job_detail(job)
        self.assertEqual(detail["job"]["state"], "failed")
        message = json.loads(detail["attempts"][-1]["error_json"])["message"]
        self.assertIn("Reasoning used the reply budget", message)
        # No blank assistant message, and no silent retry with reasoning off.
        roles = [m["role"] for m in self.c.chat_messages(self.chat)]
        self.assertEqual(roles, ["user"])
        self.assertEqual(detail["attempts"][-1]["output_text"], "")

    def test_reasoning_text_is_never_persisted_or_exported(self):
        db.set_reasoning(self.c.conn, runtime.MODEL, True)

        def stream(messages, *, should_cancel=None, think=None, model=None,
                   num_predict=None):
            yield "thinking", "PRIVATE CHAIN OF THOUGHT"
            yield "delta", "the answer"
            yield "done", {"done_reason": "stop"}

        job = self.submit()
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat)

        _name, export = db.export_chat(self.c.conn, self.chat)
        blob = json.dumps(self.c.job_detail(job)) + export + json.dumps(
            self.c.chat_messages(self.chat)) + json.dumps(
            db.search(self.c.conn, "PRIVATE"))
        self.assertNotIn("PRIVATE CHAIN OF THOUGHT", blob)
        self.assertIn("the answer", export)

    def test_an_empty_answer_without_reasoning_keeps_its_original_message(self):
        def stream(messages, *, should_cancel=None, think=None, model=None,
                   num_predict=None):
            yield "done", {"done_reason": "stop"}

        job = self.submit()
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat)
        message = json.loads(
            self.c.job_detail(job)["attempts"][-1]["error_json"])["message"]
        self.assertIn("no visible output", message)


class TestStatusSurface(CoordinatorBase):
    def test_configured_models_are_visible_before_setup(self):
        status = self.c.status()
        self.assertEqual({m["id"] for m in status["models"]},
                         {runtime.MODEL, runtime.OCR_MODEL})
        self.assertEqual(status["model_selections"]["chat"], runtime.MODEL)

    def test_the_status_reflects_the_stored_choice(self):
        db.set_reasoning(self.c.conn, runtime.MODEL, True)
        row = next(model for model in self.c.status()["models"]
                   if model["id"] == runtime.MODEL)
        self.assertTrue(row["reasoning"])

    def test_any_observed_text_model_can_be_selected_exactly(self):
        other = "another-model:1b"
        state = {"reachable": True, "server_version": "test",
                 "models": [runtime.MODEL, other],
                 "digests": {runtime.MODEL: "a" * 64, other: "b" * 64},
                 "loaded": None, "endpoint": runtime.HOST, "error": None}
        with patch.object(runtime, "probe", return_value=state):
            self.assertEqual(self.c.select_model("chat", other),
                             {"scope": "chat", "model": other})
            self.assertEqual(self.c.status()["model_selections"]["chat"], other)

    def test_only_a_confirmed_vision_model_is_selectable_for_ocr(self):
        vision = "vision-model:1b"
        state = {"reachable": True, "server_version": "test",
                 "models": [runtime.MODEL, vision],
                 "digests": {runtime.MODEL: "a" * 64, vision: "b" * 64},
                 "loaded": None, "endpoint": runtime.HOST, "error": None}
        capabilities = lambda model: (["completion", "vision"]
                                      if model == vision else ["completion"])
        with patch.object(runtime, "probe", return_value=state), \
                patch.object(runtime, "model_capabilities", side_effect=capabilities):
            inventory = {row["id"]: row for row in self.c.model_inventory()}
            self.assertNotIn("documents.ocr",
                             inventory[runtime.MODEL]["eligible_scopes"])
            self.assertIn("documents.ocr", inventory[vision]["eligible_scopes"])
            self.assertEqual(self.c.select_model("documents.ocr", vision),
                             {"scope": "documents.ocr", "model": vision})
            with self.assertRaises(RequestError):
                self.c.select_model("documents.ocr", runtime.MODEL)

    def test_auto_is_visible_as_a_future_choice_but_not_selectable(self):
        with self.assertRaises(RequestError) as caught:
            self.c.select_model("chat", "auto")
        self.assertEqual(caught.exception.status, 409)


if __name__ == "__main__":
    unittest.main(verbosity=2)
