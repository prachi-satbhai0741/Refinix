"""Offline checks for attachment intake, capability state and cancellation.

Synthetic inputs and a temporary database only: no model is called, no file is
read from anywhere but this test's own temporary directory, and no network
request leaves the process.

    python3 -m unittest backend.coordinator.test_desktop_surface -v
"""

import base64
import json
import tempfile
import threading
import time
import unittest
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from backend.contracts import profiles
from backend.coordinator import db, models, runtime
from backend.coordinator.server import (MAX_UPLOAD_BYTES, Coordinator, Handler,
                                        RequestError)

CHAT_PROFILE = next(
    profile for profile in profiles.PROFILES
    if profile.target_profile_id == profiles.MAC_M5_16GB
    and profile.workflow_mode == profiles.CHAT
    and profile.model.runtime_version == "0.32.14")


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "state.sqlite3"
        self.c = Coordinator(self.path)
        self.c.target_profile_id = profiles.MAC_M5_16GB
        self.runtime_probe = patch.object(runtime, "probe", return_value={
            "reachable": True, "server_version": "0.32.14",
            "models": [runtime.MODEL],
            "digests": {runtime.MODEL:
                        models.entry_for(runtime.MODEL).manifest_sha256},
            "loaded": None, "error": None})
        self.runtime_probe.start()
        self.addCleanup(self.runtime_probe.stop)
        self.root = self.c.attachments_root
        self.chat = db.create_chat(self.c.conn, self.c.workspace_id, "check")

    def tearDown(self):
        self.c.conn.close()
        self.dir.cleanup()

    def stored_files(self):
        """Files actually on disk. A rejection can precede the folder existing."""
        return sorted(self.root.iterdir()) if self.root.exists() else []

    def attach(self, filename, data=b"synthetic bytes", chat=None):
        return db.add_attachment(self.c.conn, self.root,
                                 workspace_id=self.c.workspace_id,
                                 chat_id=chat or self.chat,
                                 filename=filename, data=data)


class TestAttachmentIntake(Base):
    def test_a_file_is_stored_inside_the_folder_under_an_id_not_its_name(self):
        record = self.attach("quarterly report.pdf")
        stored = self.stored_files()
        self.assertEqual(len(stored), 1)
        self.assertTrue(stored[0].name.startswith(record["attachment_id"]))
        self.assertEqual(stored[0].suffix, ".pdf")
        self.assertEqual(record["filename"], "quarterly report.pdf")
        self.assertEqual(record["state"], "received")

    def test_a_traversing_name_cannot_escape_the_attachment_folder(self):
        for name in ("../../etc/passwd.txt", "..\\..\\windows\\notes.txt",
                     "/etc/hosts.txt", "sub/dir/notes.txt"):
            record = self.attach(name)
            self.assertNotIn("/", record["filename"])
            self.assertNotIn("\\", record["filename"])
        for stored in self.root.iterdir():
            self.assertEqual(stored.resolve().parent, self.root.resolve())
        self.assertEqual(len(list(self.root.rglob("*"))), 4,
                         "no directory was created outside the flat folder")

    def test_a_name_that_is_only_unsafe_characters_is_refused(self):
        with self.assertRaises(db.AttachmentRejected):
            self.attach("../../..")

    def test_an_unsupported_type_is_refused_with_the_accepted_list(self):
        with self.assertRaises(db.AttachmentRejected) as caught:
            self.attach("payload.exe")
        self.assertIn("pdf", str(caught.exception))
        self.assertEqual(self.stored_files(), [])

    def test_an_empty_file_is_refused(self):
        with self.assertRaises(db.AttachmentRejected):
            self.attach("blank.txt", b"")

    def test_a_file_over_the_bound_is_refused_and_nothing_is_written(self):
        oversized = b"x" * (db.MAX_ATTACHMENT_BYTES + 1)
        with self.assertRaises(db.AttachmentRejected) as caught:
            self.attach("huge.pdf", oversized)
        self.assertIn("limit", str(caught.exception))
        self.assertEqual(self.stored_files(), [])

    def test_the_per_request_count_is_bounded(self):
        for i in range(db.MAX_ATTACHMENTS_PER_REQUEST):
            self.attach(f"page-{i}.png")
        with self.assertRaises(db.AttachmentRejected) as caught:
            self.attach("one-too-many.png")
        self.assertIn("Remove one", str(caught.exception))

    def test_removing_a_selection_deletes_its_stored_file(self):
        record = self.attach("draft.txt")
        self.assertEqual(len(self.stored_files()), 1)
        db.delete_attachment(self.c.conn, self.root, record["attachment_id"])
        self.assertEqual(self.stored_files(), [])
        self.assertEqual(db.list_attachments(self.c.conn, chat_id=self.chat), [])

    def test_a_sent_file_cannot_be_removed_from_the_composer(self):
        record = self.attach("sent.txt")
        message = db.add_message(self.c.conn, self.chat, "user", "here it is")
        db.bind_attachments(self.c.conn, self.chat, self.chat, message)
        with self.assertRaises(db.AttachmentRejected):
            db.delete_attachment(self.c.conn, self.root, record["attachment_id"])

    def test_a_stored_name_from_outside_the_folder_is_never_unlinked(self):
        outside = Path(self.dir.name) / "not-an-attachment.txt"
        outside.write_text("keep me")
        db._unlink_stored(self.root, "../not-an-attachment.txt")
        self.assertTrue(outside.exists())

    def test_the_listing_never_leaks_the_stored_name(self):
        self.attach("shown.txt")
        for row in db.list_attachments(self.c.conn, chat_id=self.chat):
            self.assertNotIn("stored_name", row)


class TestSelectionTravelsWithTheRequest(Base):
    def test_a_new_chat_selection_moves_onto_the_request_that_carried_it(self):
        self.attach("before-the-chat-existed.txt", chat=db.NEW_CHAT_DRAFT)
        with patch("backend.coordinator.server.threading.Thread.start"):
            self.c.submit(self.chat, "look at this", draft_id=db.NEW_CHAT_DRAFT)
        messages = self.c.chat_messages(self.chat, with_attachments=True)
        self.assertEqual(len(messages[0]["attachments"]), 1)
        self.assertEqual(messages[0]["attachments"][0]["state"], "sent")
        self.assertEqual(db.list_attachments(self.c.conn, chat_id=db.NEW_CHAT_DRAFT), [])

    def test_the_files_sent_with_the_request_are_read_and_fenced(self):
        """Execution 4A: a file sent with an ordinary Chat request is read.
        It arrives fenced as data, with the rule that an instruction inside a
        document is content and never authority."""
        self.attach("notes.txt", b"THE PUMP RAN AT 7.9 MM/S")
        seen = {}

        def fake_stream(messages, *, should_cancel=None, profile=None,
                        inference=None, response_format=None):
            seen["messages"] = messages
            yield "delta", "an answer"
            yield "done", {"done_reason": "stop"}

        with patch("backend.coordinator.server.threading.Thread.start"):
            job = self.c.submit(self.chat, "what is in the file?")
        with patch.object(runtime, "stream_chat", fake_stream):
            self.c._run(job, self.chat)
        blob = json.dumps(seen["messages"])
        self.assertIn("THE PUMP RAN AT 7.9 MM/S", blob)
        self.assertIn("untrusted data", blob)

    def test_deleting_a_chat_removes_its_files_from_disk(self):
        self.attach("gone.txt")
        db.delete_chat(self.c.conn, self.chat, self.root)
        self.assertEqual(self.stored_files(), [])

    def test_export_names_the_files_and_says_they_were_not_read(self):
        self.attach("evidence.pdf")
        message = db.add_message(self.c.conn, self.chat, "user", "review this")
        db.bind_attachments(self.c.conn, self.chat, self.chat, message)
        _name, body = db.export_chat(self.c.conn, self.chat)
        self.assertIn("evidence.pdf", body)
        self.assertIn("received but not read", body)


class TestCapabilities(Base):
    def test_runtime_free_document_search_stays_available_when_inference_is_down(self):
        rows = self.c.capabilities({"reachable": False, "models": []})
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(by_id["chat"]["state"], "blocked")
        self.assertEqual(by_id["code"]["state"], "blocked")
        self.assertEqual(by_id["read-document"]["state"], "blocked")
        self.assertEqual(by_id["write-document"]["state"], "available")
        self.assertTrue(by_id["write-document"]["conversion_only"])
        self.assertEqual(by_id["search-documents"]["state"], "available")

    def test_a_missing_model_directs_the_user_to_the_selector(self):
        rows = self.c.capabilities({"reachable": True, "models": ["other:1b"]})
        chat = next(r for r in rows if r["id"] == "chat")
        self.assertEqual(chat["state"], "blocked")
        self.assertEqual(chat["setup"],
                         "Choose an installed model in the model selector.")

    def test_execution_three_document_skills_are_available_when_ready(self):
        rows = self.c.capabilities({
            "reachable": True, "server_version": "0.32.14",
            "models": [runtime.MODEL],
            "digests": {runtime.MODEL:
                        models.entry_for(runtime.MODEL).manifest_sha256}})
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(by_id["chat"]["state"], "available")
        self.assertEqual(by_id["code"]["state"], "available")
        for skill in ("read-document", "write-document", "search-documents"):
            self.assertEqual(by_id[skill]["state"], "available")

    def test_the_code_capability_names_what_it_still_cannot_do(self):
        """Execution 2 enforces the access modes, so the old 'no enforcement'
        wording is gone. What replaces it must still be honest about the
        boundary rather than implying a general development platform."""
        rows = self.c.capabilities({
            "reachable": True, "server_version": "0.32.14",
            "models": [runtime.MODEL],
            "digests": {runtime.MODEL:
                        models.entry_for(runtime.MODEL).manifest_sha256}})
        code = next(r for r in rows if r["id"] == "code")
        self.assertEqual(code["state"], "available")
        for missing in ("Creating", "deleting", "renaming", "commands", "Git"):
            self.assertIn(missing, code["detail"])

    def test_ollama_0342_capabilities_match_the_registered_workflows(self):
        rows = self.c.capabilities({
            "reachable": True, "server_version": "0.34.2",
            "models": [runtime.MODEL],
            "digests": {runtime.MODEL:
                        models.entry_for(runtime.MODEL).manifest_sha256}})
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(by_id["chat"]["state"], "available")
        self.assertEqual(by_id["code"]["state"], "available")
        self.assertTrue(by_id["code"]["experimental"])
        self.assertIn("small reviewable", by_id["code"]["detail"])
        self.assertIn("not qualified", by_id["code"]["detail"])
        # Reading and writing run on the limited Chat-backed route: available,
        # said to be limited, and never presented as structured Documents.
        for skill in ("read-document", "write-document"):
            row = by_id[skill]
            self.assertEqual(row["state"], "available", skill)
            self.assertEqual(row["model_scope"], "chat", skill)
            self.assertNotIn("conversion_only", row, skill)
            self.assertIn("Limited", row["detail"], skill)
            self.assertIn("qualified Chat profile", row["detail"], skill)
            self.assertIn("not", row["detail"], skill)
        self.assertIn("approval note are not qualified",
                      by_id["write-document"]["detail"])
        self.assertIn("docx", by_id["read-document"]["formats"])
        # Scans stay unavailable, named; nothing claims PaddleOCR ran.
        self.assertIn("no OCR profile is qualified", by_id["read-document"]["detail"])
        scan = [item for item in by_id["read-document"]["unavailable_reasons"]
                if item["kind"] == "pdf_scan"]
        self.assertEqual(len(scan), 1)
        self.assertIn("no qualified reading profile", scan[0]["detail"])
        # The unqualified OCR model may be *named* only inside the refusal that
        # says nothing is sent to it; no text anywhere claims it read anything.
        texts = [row.get(key, "") for row in rows for key in ("summary", "detail")]
        texts += [item["detail"] for row in rows
                  for item in row.get("unavailable_reasons", [])]
        for text in texts:
            if "paddleocr" in text.lower():
                self.assertIn("will not send a page image to it", text)
        self.assertNotIn("model_scope", by_id["search-documents"])

    def test_the_chat_backed_rows_show_the_documents_models_chat_selftest(self):
        """The route runs the model selected for Documents under its Chat
        profile, so that model's Chat self-test describes it — even when a
        different model is selected for Chat."""
        state = {"reachable": True, "server_version": "0.34.2",
                 "models": [runtime.MODEL, "other:1b"],
                 "digests": {runtime.MODEL:
                             models.entry_for(runtime.MODEL).manifest_sha256,
                             "other:1b": "f" * 64}}
        db.set_model_selection(self.c.conn, "chat", "other:1b")
        digest = models.entry_for(runtime.MODEL).manifest_sha256
        db.record_selftest(conn=self.c.conn, model=runtime.MODEL, scope=models.CHAT,
                           state="passed", detail="chat ok", digest=digest,
                           runtime_version="0.34.2")
        rows = {row["id"]: row for row in self.c.capabilities(state)}
        for skill in ("read-document", "write-document"):
            self.assertEqual(rows[skill]["selftest"]["state"], "passed", skill)
            self.assertEqual(rows[skill]["selftest"]["detail"], "chat ok", skill)

    def test_an_unmeasured_runtime_leaves_reading_blocked_and_writing_conversion_only(self):
        rows = self.c.capabilities({
            "reachable": True, "server_version": "0.99.0",
            "models": [runtime.MODEL],
            "digests": {runtime.MODEL:
                        models.entry_for(runtime.MODEL).manifest_sha256}})
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(by_id["read-document"]["state"], "blocked")
        self.assertIn("no qualified Documents or Chat execution profile",
                      by_id["read-document"]["detail"])
        self.assertTrue(by_id["write-document"]["conversion_only"])
        self.assertNotIn("model_scope", by_id["read-document"])

    def test_the_structured_profile_rows_carry_no_chat_scope(self):
        rows = self.c.capabilities({
            "reachable": True, "server_version": "0.32.14",
            "models": [runtime.MODEL],
            "digests": {runtime.MODEL:
                        models.entry_for(runtime.MODEL).manifest_sha256}})
        for row in rows:
            self.assertNotIn("model_scope", row, row["id"])

    def test_code_is_blocked_rather_than_available_without_the_runtime(self):
        rows = self.c.capabilities({"reachable": False, "models": []})
        code = next(r for r in rows if r["id"] == "code")
        self.assertEqual(code["state"], "blocked")


class TestStopBehaviour(Base):
    """The Stop path, exercised end to end with a synthetic runtime."""

    def _stalling_stream(self, delivered, stalled):
        def stream(messages, *, should_cancel=None, profile=None,
                   inference=None, response_format=None):
            yield "delta", "partial answer"
            delivered.set()
            # From here the runtime produces nothing at all, the way a wedged
            # model stream behaves. Cancellation must not wait this out.
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if should_cancel and should_cancel():
                    stalled.set()
                    yield "cancelled", {}
                    return
                time.sleep(0.02)
            raise AssertionError("cancellation never reached the stalled stream")
        return stream

    def test_cancelling_a_stalled_stream_takes_effect_without_the_full_timeout(self):
        delivered, stalled = threading.Event(), threading.Event()
        with patch("backend.coordinator.server.threading.Thread.start"):
            job = self.c.submit(self.chat, "stall please")
        runner = threading.Thread(
            target=self.c._run, args=(job, self.chat), daemon=True)
        with patch.object(runtime, "stream_chat",
                          self._stalling_stream(delivered, stalled)):
            runner.start()
            self.assertTrue(delivered.wait(5), "the stream never started")
            started = time.monotonic()
            self.c.request_cancel(job)
            self.assertTrue(stalled.wait(5), "cancel did not reach the stalled read")
            runner.join(timeout=5)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(self.c.job_detail(job)["job"]["state"], "cancelled")

    def test_cancelled_work_is_never_saved_as_a_successful_reply(self):
        delivered, stalled = threading.Event(), threading.Event()
        with patch("backend.coordinator.server.threading.Thread.start"):
            job = self.c.submit(self.chat, "stop me")
        runner = threading.Thread(target=self.c._run, args=(job, self.chat), daemon=True)
        with patch.object(runtime, "stream_chat",
                          self._stalling_stream(delivered, stalled)):
            runner.start()
            delivered.wait(5)
            self.c.request_cancel(job)
            runner.join(timeout=5)
        roles = [m["role"] for m in self.c.chat_messages(self.chat)]
        self.assertEqual(roles, ["user"], "no assistant message may be saved")
        attempt = self.c.job_detail(job)["attempts"][-1]
        self.assertEqual(attempt["state"], "cancelled")
        self.assertEqual(json.loads(attempt["error_json"])["code"], "cancelled_by_user")
        # The partial text is kept truthfully on the attempt, not as an answer.
        self.assertEqual(attempt["output_text"], "partial answer")

    def test_cancelling_before_the_model_is_called_still_records_a_cancellation(self):
        with patch("backend.coordinator.server.threading.Thread.start"):
            job = self.c.submit(self.chat, "never reaches the model")
        self.c.request_cancel(job)
        with patch.object(runtime, "stream_chat",
                          lambda *a, **k: self.fail("the model must not be called")):
            self.c._run(job, self.chat)
        self.assertEqual(self.c.job_detail(job)["job"]["state"], "cancelled")
        self.assertEqual([m["role"] for m in self.c.chat_messages(self.chat)], ["user"])

    def test_a_job_that_already_stopped_reports_a_conflict(self):
        with patch("backend.coordinator.server.threading.Thread.start"):
            job = self.c.submit(self.chat, "one shot")
        with patch.object(runtime, "stream_chat", lambda *a, **k: iter(
                [("delta", "done"), ("done", {"done_reason": "stop"})])):
            self.c._run(job, self.chat)
        with self.assertRaises(RequestError) as caught:
            self.c.request_cancel(job)
        self.assertEqual(caught.exception.status, 409)


class TestRuntimeCancelWatch(unittest.TestCase):
    """The watcher that aborts a blocked socket read."""

    class FakeSocket:
        def __init__(self):
            self.shutdown_called = False

        def shutdown(self, _how):
            self.shutdown_called = True

    class FakeResponse:
        def __init__(self, sock):
            self.closed = False
            self.fp = type("fp", (), {"raw": type("raw", (), {"_sock": sock})()})()

        def close(self):
            self.closed = True

    def test_a_cancel_shuts_the_socket_down_and_closes_the_response(self):
        sock = self.FakeSocket()
        response = self.FakeResponse(sock)
        cancelled = threading.Event()
        watch = runtime._CancelWatch(response, cancelled.is_set)
        with watch:
            cancelled.set()
            for _ in range(100):
                if watch.fired:
                    break
                time.sleep(0.02)
        self.assertTrue(watch.fired)
        self.assertTrue(sock.shutdown_called)
        self.assertTrue(response.closed)

    def test_no_cancel_leaves_the_connection_untouched(self):
        sock = self.FakeSocket()
        response = self.FakeResponse(sock)
        with runtime._CancelWatch(response, lambda: False) as watch:
            time.sleep(0.5)
        self.assertFalse(watch.fired)
        self.assertFalse(sock.shutdown_called)
        self.assertFalse(response.closed)

    def test_an_aborted_read_is_reported_as_cancelled_not_as_a_fault(self):
        class Aborted:
            def __iter__(self):
                raise OSError("Bad file descriptor")

        watch = type("W", (), {"fired": True})()
        self.assertEqual(list(runtime._read_stream(Aborted(), watch, None)),
                         [("cancelled", {})])

    def test_a_genuine_read_failure_is_still_a_runtime_fault(self):
        import http.client

        for failure in (OSError("connection reset"),
                        http.client.IncompleteRead(b"", 12)):
            class Broken:
                def __iter__(self, _f=failure):
                    raise _f

            watch = type("W", (), {"fired": False})()
            with self.assertRaises(runtime.RuntimeUnavailable):
                list(runtime._read_stream(Broken(), watch, None))

    def test_a_malformed_line_is_reported_as_itself_not_as_a_read_failure(self):
        watch = type("W", (), {"fired": False})()
        with self.assertRaises(runtime.RuntimeUnavailable) as caught:
            list(runtime._read_stream(iter([b"{not json"]), watch, None))
        self.assertIn("malformed stream line", str(caught.exception))


class TestCancelAgainstARealStalledSocket(unittest.TestCase):
    """The watcher, against an actual socket rather than a stand-in.

    A local HTTP server streams two records and then produces nothing at all,
    which is what a wedged model stream looks like from the coordinator's side.
    Loopback only, no model, and the request timeout stays at its normal value
    so a pass means the cancellation really did short-circuit it.
    """

    class Stalling(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        release = None
        received = None
        before_headers = False

        def log_message(self, *_a):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            type(self).received.set()
            if type(self).before_headers:
                type(self).release.wait(10)
                self.close_connection = True
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for text in ("first ", "second "):
                line = json.dumps({"message": {"content": text}, "done": False})
                body = (line + "\n").encode()
                self.wfile.write(b"%x\r\n" % len(body) + body + b"\r\n")
                self.wfile.flush()
            # Then nothing, until the test lets go.
            type(self).release.wait(30)
            self.close_connection = True

    def setUp(self):
        type(self).Stalling.release = threading.Event()
        type(self).Stalling.received = threading.Event()
        type(self).Stalling.before_headers = False
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.Stalling)
        self.server.daemon_threads = True
        self.server.block_on_close = False
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.host = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.Stalling.release.set()
        self.server.shutdown()
        self.server.server_close()

    def test_a_stalled_socket_read_is_abandoned_as_soon_as_cancel_is_asked(self):
        cancel = threading.Event()
        collected = []
        finished = threading.Event()

        def read():
            profile = CHAT_PROFILE
            inference = profiles.request(
                profile, reasoning="disabled", decoder="text")
            with patch.object(runtime, "HOST", self.host):
                for kind, payload in runtime.stream_chat(
                        [{"role": "user", "content": "hello"}],
                        profile=profile, inference=inference,
                        should_cancel=cancel.is_set):
                    collected.append((kind, payload))
            finished.set()

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        deadline = time.monotonic() + 5
        while len(collected) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual([k for k, _ in collected], ["delta", "delta"])

        started = time.monotonic()
        cancel.set()
        self.assertTrue(finished.wait(5),
                        "the blocked read was not abandoned; it waited out the "
                        f"{runtime.__dict__.get('REQUEST_TIMEOUT', 300)}s timeout")
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 3, f"cancel took {elapsed:.1f}s")
        self.assertEqual(collected[-1], ("cancelled", {}))
        reader.join(timeout=2)

    def test_stop_before_response_headers_records_cancelled_without_a_reply(self):
        self.Stalling.before_headers = True
        with tempfile.TemporaryDirectory() as folder:
            c = Coordinator(Path(folder) / "state.sqlite3")
            c.target_profile_id = profiles.MAC_M5_16GB
            chat = db.create_chat(c.conn, c.workspace_id, "Synthetic stalled headers")
            try:
                ready = {"reachable": True, "server_version": "0.32.14",
                         "models": [runtime.MODEL],
                         "digests": {runtime.MODEL:
                                     models.entry_for(runtime.MODEL).manifest_sha256}}
                with patch.object(runtime, "HOST", self.host), \
                        patch.object(runtime, "probe", return_value=ready):
                    job = c.submit(chat, "Synthetic request")
                    self.assertTrue(self.Stalling.received.wait(2))
                    c.request_cancel(job)
                    deadline = time.monotonic() + 3
                    while c.job_detail(job)["job"]["state"] == "running" and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertEqual(c.job_detail(job)["job"]["state"], "cancelled")
                    self.assertEqual([m["role"] for m in c.chat_messages(chat)], ["user"])
            finally:
                self.Stalling.release.set()
                c.conn.close()


class TestUploadRoute(unittest.TestCase):
    """The upload bound is route-scoped; contract routes keep their own."""

    def _handler(self, headers, body=b""):
        handler = Handler.__new__(Handler)
        message = Message()
        for key, value in headers.items():
            message[key] = value
        handler.headers = message
        handler.rfile = BytesIO(body)
        handler.connection = type("c", (), {"settimeout": lambda _s, _t: None})()
        return handler

    def test_a_contract_route_keeps_the_contract_bound(self):
        handler = self._handler({"Content-Type": "application/json",
                                 "Content-Length": str(300_000)})
        with self.assertRaises(RequestError) as caught:
            handler._body()
        self.assertEqual(caught.exception.status, 413)

    def test_the_upload_route_accepts_a_whole_file_but_is_still_bounded(self):
        payload = json.dumps({"ok": True}).encode()
        handler = self._handler({"Content-Type": "application/json",
                                 "Content-Length": str(len(payload))}, payload)
        self.assertEqual(handler._body(MAX_UPLOAD_BYTES), {"ok": True})

        handler = self._handler({"Content-Type": "application/json",
                                 "Content-Length": str(MAX_UPLOAD_BYTES + 1)})
        with self.assertRaises(RequestError) as caught:
            handler._body(MAX_UPLOAD_BYTES)
        self.assertEqual(caught.exception.status, 413)


class TestUploadDecoding(Base):
    def test_data_that_is_not_base64_is_refused_before_anything_is_written(self):
        handler = Handler.__new__(Handler)
        with self.assertRaises(RequestError):
            handler._attach(self.c, {"chat_id": self.chat, "filename": "a.txt",
                                     "data": "not base64!!"})
        self.assertEqual(self.stored_files(), [])

    def test_a_valid_upload_returns_a_record_without_the_stored_name(self):
        handler = Handler.__new__(Handler)
        result = handler._attach(self.c, {
            "chat_id": self.chat, "filename": "note.md",
            "data": base64.b64encode(b"# heading").decode()})
        self.assertNotIn("stored_name", result["attachment"])
        self.assertEqual(result["attachment"]["media_type"], "text/markdown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
