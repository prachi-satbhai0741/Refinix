"""Offline checks for coordinator state and restart reconciliation.

No server, no model, no network: a temporary SQLite file only. These cover the
logic that would otherwise fail silently — an illegal state transition reaching
the database, or a restart leaving a job claiming to be running.

    python3 -m unittest backend.coordinator.test_coordinator -v
"""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from email.message import Message
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from threading import Event
from urllib.error import HTTPError
from urllib.parse import quote

from backend.contracts import v1
from backend.coordinator import db
from backend.coordinator.server import Coordinator, Handler, RequestError
from backend.coordinator import runtime


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self.dir.name) / "state.sqlite3")
        self.workspace = db.new_id()
        self.node = db.new_id()
        self.chat = db.create_chat(self.conn, self.workspace, "check")

    def tearDown(self):
        self.conn.close()
        self.dir.cleanup()

    def a_running_job(self):
        job = db.create_job(self.conn, workspace_id=self.workspace,
                            chat_id=self.chat, request="hello")
        for following in ("context_preparing", "queued"):
            db.set_job_state(self.conn, job, following)
        attempt = db.create_attempt(self.conn, job_id=job, node_id=self.node,
                                    route_reason="local")
        db.set_job_state(self.conn, job, "routing")
        db.set_job_state(self.conn, job, "running")
        db.set_attempt_state(self.conn, attempt, "running")
        return job, attempt


class TestStateMachine(Base):
    def test_happy_path_reaches_completed(self):
        job, attempt = self.a_running_job()
        db.set_attempt_state(self.conn, attempt, "validating")
        db.set_attempt_state(self.conn, attempt, "completed")
        db.set_job_state(self.conn, job, "validating")
        db.set_job_state(self.conn, job, "completed")
        row = self.conn.execute("SELECT state FROM jobs WHERE job_id=?", (job,)).fetchone()
        self.assertEqual(row["state"], "completed")

    def test_illegal_job_transition_is_rejected(self):
        job = db.create_job(self.conn, workspace_id=self.workspace,
                            chat_id=self.chat, request="hello")
        with self.assertRaisesRegex(ValueError, "illegal job transition"):
            db.set_job_state(self.conn, job, "completed")   # created -> completed
        row = self.conn.execute("SELECT state FROM jobs WHERE job_id=?", (job,)).fetchone()
        self.assertEqual(row["state"], "created", "a rejected transition must not persist")

    def test_illegal_attempt_transition_is_rejected(self):
        _, attempt = self.a_running_job()
        with self.assertRaisesRegex(ValueError, "illegal attempt transition"):
            db.set_attempt_state(self.conn, attempt, "queued")   # running -> queued

    def test_stopped_attempt_requires_a_typed_reason(self):
        _, attempt = self.a_running_job()
        # The contract says a stopped attempt records exactly one typed reason.
        with self.assertRaises(Exception):
            db.set_attempt_state(self.conn, attempt, "failed", error=None)

    def test_cancelled_by_user_cannot_explain_a_failure(self):
        _, attempt = self.a_running_job()
        with self.assertRaises(Exception):
            db.set_attempt_state(self.conn, attempt, "failed", error={
                "code": "cancelled_by_user", "message": "no", "retryable": True})


class TestEvents(Base):
    def test_concurrent_writers_keep_every_event(self):
        job, attempt = self.a_running_job()
        def write(i):
            return db.append_event(self.conn, job_id=job, attempt_id=attempt,
                                   node_id=self.node,
                                   data={"kind": "output.delta", "text": str(i)})
        with ThreadPoolExecutor(max_workers=8) as pool:
            events = list(pool.map(write, range(64)))
        self.assertEqual(sorted(e["sequence"] for e in events), list(range(1, 65)))
        self.assertEqual(self.conn.execute("SELECT count(*) FROM events").fetchone()[0], 64)

    def test_sequence_is_per_job_and_starts_at_one(self):
        job, attempt = self.a_running_job()
        first = db.append_event(self.conn, job_id=job, attempt_id=None,
                                node_id=self.node,
                                data={"kind": "job.state", "previous": None,
                                      "current": "created"})
        second = db.append_event(self.conn, job_id=job, attempt_id=attempt,
                                 node_id=self.node,
                                 data={"kind": "output.delta", "text": "hi"})
        self.assertEqual((first["sequence"], second["sequence"]), (1, 2))

    def test_output_delta_without_an_attempt_is_rejected(self):
        job, _ = self.a_running_job()
        # Contract: attempt output and decisions require an attempt ID.
        with self.assertRaises(Exception):
            db.append_event(self.conn, job_id=job, attempt_id=None,
                            node_id=self.node,
                            data={"kind": "output.delta", "text": "orphan"})


class TestReconciliation(Base):
    def test_crash_before_attempt_creation_repairs_job(self):
        for state in ("created", "context_preparing", "queued"):
            with self.subTest(state=state):
                job = db.create_job(self.conn, workspace_id=self.workspace,
                                    chat_id=self.chat, request="hello")
                for following in ("context_preparing", "queued"):
                    current = self.conn.execute("SELECT state FROM jobs WHERE job_id=?",
                                                (job,)).fetchone()[0]
                    if current == state:
                        break
                    db.set_job_state(self.conn, job, following)
                self.assertEqual(db.reconcile_on_start(self.conn, self.node), [job])
                self.assertEqual(self.conn.execute("SELECT state FROM jobs WHERE job_id=?",
                                                   (job,)).fetchone()[0], "failed")

    def test_crash_after_attempt_completed_repairs_job(self):
        job, attempt = self.a_running_job()
        db.set_job_state(self.conn, job, "validating")
        db.set_attempt_state(self.conn, attempt, "validating")
        db.set_attempt_state(self.conn, attempt, "completed")
        self.assertEqual(db.reconcile_on_start(self.conn, self.node), [job])
        self.assertEqual(self.conn.execute("SELECT state FROM jobs WHERE job_id=?",
                                           (job,)).fetchone()[0], "interrupted")

    def test_restart_interrupts_an_executing_attempt(self):
        job, attempt = self.a_running_job()
        db.append_output(self.conn, attempt, "partial answer")

        repaired = db.reconcile_on_start(self.conn, self.node)

        self.assertEqual(repaired, [job])
        row = self.conn.execute("SELECT * FROM attempts WHERE attempt_id=?",
                                (attempt,)).fetchone()
        self.assertEqual(row["state"], "interrupted")
        self.assertIn("coordinator restarted", row["error_json"])
        self.assertEqual(row["output_text"], "partial answer",
                         "partial output survives the restart")
        self.assertEqual(
            self.conn.execute("SELECT state FROM jobs WHERE job_id=?",
                              (job,)).fetchone()["state"], "interrupted")

    def test_completed_work_is_left_alone(self):
        job, attempt = self.a_running_job()
        db.set_attempt_state(self.conn, attempt, "validating")
        db.set_attempt_state(self.conn, attempt, "completed")
        db.set_job_state(self.conn, job, "validating")
        db.set_job_state(self.conn, job, "completed")

        self.assertEqual(db.reconcile_on_start(self.conn, self.node), [])
        self.assertEqual(
            self.conn.execute("SELECT state FROM jobs WHERE job_id=?",
                              (job,)).fetchone()["state"], "completed")

    def test_reconciliation_is_idempotent(self):
        self.a_running_job()
        first = db.reconcile_on_start(self.conn, self.node)
        second = db.reconcile_on_start(self.conn, self.node)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [], "a second restart repairs nothing new")

    def test_history_survives(self):
        job, _ = self.a_running_job()
        db.add_message(self.conn, self.chat, "user", "hello", job_id=job)
        db.reconcile_on_start(self.conn, self.node)
        rows = self.conn.execute("SELECT * FROM messages WHERE chat_id=?",
                                 (self.chat,)).fetchall()
        self.assertEqual(len(rows), 1)


class TestContractBinding(unittest.TestCase):
    def test_lifecycle_matches_the_shared_contract(self):
        # The UI renders this order; it must come from the contract, not a copy.
        self.assertLessEqual(
            {"created", "context_preparing", "queued", "routing", "running",
             "validating", "completed"},
            set(v1.JOB_TRANSITIONS) | v1.TERMINAL_JOB_STATES)


class TestLocalBoundary(unittest.TestCase):
    def handler(self, body=b'{}', **headers):
        h = Handler.__new__(Handler)
        h.headers = Message()
        values = {"Host": "127.0.0.1:8770", "Content-Type": "application/json",
                  "Content-Length": str(len(body)), **headers}
        for key, value in values.items():
            h.headers[key] = value
        h.server = SimpleNamespace(server_port=8770)
        h.connection = SimpleNamespace(settimeout=lambda seconds: None)
        h.rfile = BytesIO(body)
        return h

    def test_busy_delete_is_http_409_and_preserves_every_record(self):
        with tempfile.TemporaryDirectory() as directory:
            c = Coordinator(Path(directory) / 'state.sqlite3')
            chat = db.create_chat(c.conn, c.workspace_id, 'keep')
            with patch('backend.coordinator.server.threading.Thread.start'):
                job = c.submit(chat, 'unfinished')
            db.set_draft(c.conn, chat, 'unsent')
            h = self.handler(json.dumps({'chat_id': chat}).encode())
            h.path, h.coordinator = '/v1/chat/delete', c
            for state in ['created', 'context_preparing', 'queued', 'routing',
                          'running', 'validating', 'awaiting_approval']:
                if state != 'created':
                    db.set_job_state(c.conn, job, state)
                with patch.object(h, '_body', return_value={'chat_id': chat}), patch.object(h, '_json') as reply:
                    h.do_POST()
                self.assertEqual(reply.call_args.args[1], 409, state)
                self.assertEqual(c.chat_messages(chat)[0]['text'], 'unfinished')
                self.assertEqual(db.get_draft(c.conn, chat), 'unsent')
            db.set_job_state(c.conn, job, 'cancelled')
            db.delete_chat(c.conn, chat)
            c.conn.close()

    def test_submit_and_delete_share_one_critical_section(self):
        with tempfile.TemporaryDirectory() as directory:
            c = Coordinator(Path(directory) / 'state.sqlite3')
            chat = db.create_chat(c.conn, c.workspace_id, 'race')
            entered, release, deleting = Event(), Event(), Event()
            create = db.create_job
            def paused_create(*args, **kwargs):
                entered.set()
                if not release.wait(3):
                    raise AssertionError('delete did not start')
                return create(*args, **kwargs)
            def remove():
                deleting.set()
                db.delete_chat(c.conn, chat)
            with patch.object(db, 'create_job', paused_create), patch.object(c, '_run'), ThreadPoolExecutor(2) as pool:
                submitted = pool.submit(c.submit, chat, 'keep')
                self.assertTrue(entered.wait(3))
                removed = pool.submit(remove)
                self.assertTrue(deleting.wait(3))
                release.set()
                job = submitted.result(3)
                with self.assertRaises(db.ChatBusyError):
                    removed.result(3)
            self.assertEqual(c.jobs(chat)[0]['job_id'], job)
            c.conn.close()

    def test_export_serializes_unicode_filename_as_an_ascii_header(self):
        h = self.handler()
        h.request_version = 'HTTP/1.1'
        h.wfile = BytesIO()
        name = 'मराठी तपासणी.md'
        c = SimpleNamespace(export=lambda *args: (name, 'saved text'))
        with patch.object(h, 'log_request'):
            h._export(c, {'chat_id': ['synthetic'], 'format': ['md']})
        headers, body = h.wfile.getvalue().split(b'\r\n\r\n', 1)
        self.assertIn("filename*=UTF-8''" + quote(name, safe=''), headers.decode('ascii'))
        self.assertEqual(body, b'saved text')

    def test_submit_clears_the_exact_draft_including_new_chat_and_whitespace(self):
        with tempfile.TemporaryDirectory() as directory:
            c = Coordinator(Path(directory) / 'state.sqlite3')
            chat = db.create_chat(c.conn, c.workspace_id, 'draft')
            for draft_id in (chat, db.NEW_CHAT_DRAFT):
                for saved in ('  send this\n', 'newer typing'):
                    db.set_draft(c.conn, draft_id, saved)
                    body = {'chat_id': chat, 'text': 'send this', 'draft_id': draft_id,
                            'draft_text': '  send this\n'}
                    h = self.handler(json.dumps(body).encode())
                    h.path, h.coordinator = '/v1/messages', c
                    with patch.object(c, 'submit', return_value=db.new_id()), patch.object(h, '_json') as reply:
                        h.do_POST()
                    self.assertEqual(reply.call_args.args[1], 202)
                    self.assertEqual(db.get_draft(c.conn, draft_id),
                                     '' if saved.strip() == 'send this' else saved)
            c.conn.close()

    def test_disconnects_close_the_connection_without_masking_other_errors(self):
        h = self.handler()
        for error in (ConnectionResetError(), BrokenPipeError()):
            with self.subTest(error=type(error).__name__), patch.object(
                    h, 'handle_one_request', side_effect=error):
                h.handle()
                self.assertTrue(h.close_connection)
        with patch.object(h, 'handle_one_request', side_effect=ValueError('real bug')):
            with self.assertRaisesRegex(ValueError, 'real bug'):
                h.handle()

        h.path = '/v1/chats'
        h.coordinator = SimpleNamespace(chats=lambda: [])
        with patch.object(h, '_json', side_effect=BrokenPipeError()), patch(
                'backend.coordinator.server.traceback.print_exc') as logged:
            with patch.object(h, 'handle_one_request', side_effect=h.do_GET):
                h.handle()
            h.coordinator.request_cancel = lambda job: None
            h.path = '/v1/cancel'
            with patch.object(h, '_body', return_value={'job_id': db.new_id()}), patch.object(
                    h, 'handle_one_request', side_effect=h.do_POST):
                h.handle()
            logged.assert_not_called()

    def test_sse_disconnect_during_headers_releases_subscription(self):
        from backend.coordinator.server import Hub
        h = self.handler()
        h.coordinator = SimpleNamespace(hub=Hub(), stopping=None)
        with patch.object(h, 'send_response', side_effect=ConnectionResetError()):
            with patch.object(h, 'handle_one_request', side_effect=h._sse):
                h.handle()
        self.assertEqual(h.coordinator.hub._subscribers, {})

    def test_browser_origin_and_host_are_checked(self):
        self.handler(Origin="http://127.0.0.1:8770")._local_request()
        self.handler()._local_request()  # local non-browser client
        for headers in ({"Host": "attacker.example:8770"},
                        {"Origin": "https://attacker.example"},
                        {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers), self.assertRaises(RequestError):
                self.handler(**headers)._local_request()

    def test_request_limits_and_malformed_bodies(self):
        self.assertEqual(self.handler(b'{"title":"hello"}')._body(), {"title": "hello"})
        for body, headers in ((b'[]', {}), (b'{', {}), (b'{}', {"Content-Length": "-1"}),
                              (b'{}', {"Content-Length": str(v1.MAX_REQUEST_BYTES + 1)}),
                              (b'{}', {"Content-Type": "text/plain"}),
                              (b'{}', {"Transfer-Encoding": "chunked"})):
            with self.subTest(headers=headers, body=body), self.assertRaises(RequestError):
                self.handler(body, **headers)._body()

    def test_static_files_cannot_escape_to_prefix_sibling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app').mkdir()
            (root / 'app-private').mkdir()
            (root / 'app-private' / 'data.txt').write_text('private fixture')
            h = self.handler()
            with patch('backend.coordinator.server.STATIC', root / 'app'), patch.object(h, '_json') as reply:
                h._static('/../app-private/data.txt')
                reply.assert_called_once_with({"error": "not found"}, 404)

    def test_runtime_cannot_redirect_a_local_request(self):
        with self.assertRaises(runtime.RuntimeUnavailable):
            runtime._NoRedirect().redirect_request(None, None, 307, '', {},
                                                   'https://example.com')

    def test_identity_survives_restart_and_chat_rejects_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.sqlite3'
            c = Coordinator(path)
            node, workspace = c.node_id, c.workspace_id
            chat = db.create_chat(c.conn, workspace, 'check')
            with patch('backend.coordinator.server.threading.Thread.start'):
                c.submit(chat, 'first')
                with self.assertRaises(RequestError):
                    c.submit(chat, 'second')
                with self.assertRaises(RequestError):
                    c.submit(db.new_id(), 'missing conversation')
            self.assertEqual(len(c.chat_messages(chat)), 1)
            c.conn.close()
            reopened = Coordinator(path)
            self.assertEqual((reopened.node_id, reopened.workspace_id), (node, workspace))
            self.assertEqual(reopened.jobs(chat)[0]['state'], 'failed')
            reopened.conn.close()

    def test_cancel_at_last_output_does_not_save_an_assistant_message(self):
        with tempfile.TemporaryDirectory() as directory:
            c = Coordinator(Path(directory) / 'state.sqlite3')
            chat = db.create_chat(c.conn, c.workspace_id, 'check')
            with patch('backend.coordinator.server.threading.Thread.start'):
                job = c.submit(chat, 'hello')
            def result(*args, **kwargs):
                yield 'delta', 'partial'
                c.request_cancel(job)
                yield 'done', {}
            with patch.object(runtime, 'stream_chat', result):
                c._run(job, chat)
            self.assertEqual(c.job_detail(job)['job']['state'], 'cancelled')
            self.assertEqual([m['role'] for m in c.chat_messages(chat)], ['user'])
            c.conn.close()


class TestCompletion(unittest.TestCase):
    def test_real_input_overflow_error_is_actionable(self):
        error = HTTPError(runtime.HOST, 400, 'Bad Request', {},
                          BytesIO(b'{"error":"exceed_context_size_error"}'))
        with patch.object(runtime, '_request', side_effect=error):
            with self.assertRaisesRegex(runtime.RuntimeUnavailable, 'Shorten your message'):
                list(runtime.stream_chat([{'role': 'user', 'content': 'dense input'}]))

    def test_context_and_output_limits_keep_partial_answers_with_distinct_notices(self):
        for prompt, output, limit in [(8042, 150, 'context'), (40, 2048, 'output'),
                                      (6144, 2048, 'context_and_output'),
                                      (None, 2048, 'output'), (None, 100, 'unknown')]:
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as directory:
                c = Coordinator(Path(directory) / 'state.sqlite3')
                chat = db.create_chat(c.conn, c.workspace_id, 'limit test')
                with patch('backend.coordinator.server.threading.Thread.start'):
                    job = c.submit(chat, 'Count')
                final = {'message': {'content': 'saved partial answer'}, 'done': True,
                         'done_reason': 'length', 'prompt_eval_count': prompt, 'eval_count': output}
                with patch.object(runtime, '_request', return_value=BytesIO((json.dumps(final) + '\n').encode())):
                    c._run(job, chat)
                detail = c.job_detail(job)
                self.assertEqual(detail['job']['state'], 'failed')
                metrics = json.loads(detail['attempts'][0]['metrics_json'])
                self.assertEqual(metrics['limit_reason'], limit)
                message = c.chat_messages(chat)[-1]
                self.assertEqual(message['text'], 'saved partial answer')
                explanation = json.loads(message['error_json'])['message']
                self.assertIn({'context': 'context window', 'output': 'output limit',
                               'context_and_output': 'output limit also reached',
                               'unknown': 'which limit was not reported'}[limit], explanation)
                export = c.export(chat, 'md')[1]
                self.assertIn('saved partial answer', export)
                if limit == 'context_and_output':
                    self.assertIn('context window', explanation)
                    self.assertIn('start a new chat', explanation)
                    self.assertIn('context window and output token limits both reached', export)
                c.conn.close()

    def test_runtime_stopping_reason_controls_status_and_survives_restart(self):
        for reason in ('stop', 'length', None, 'unexpected'):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'state.sqlite3'
                c = Coordinator(path)
                chat = db.create_chat(c.conn, c.workspace_id, 'synthetic check')
                with patch('backend.coordinator.server.threading.Thread.start'):
                    job = c.submit(chat, 'Give a detailed answer.')
                reply = 'A retained synthetic reply.'
                stream = BytesIO((json.dumps({'message': {'content': reply}}) + '\n' +
                    json.dumps({'done': True, 'done_reason': reason, 'eval_count': 700,
                                'total_duration': 1000000}) + '\n').encode())
                with patch.object(runtime, '_request', return_value=stream) as request:
                    c._run(job, chat)
                options = request.call_args.args[1]['options']
                self.assertIs(request.call_args.args[1]['truncate'], False)
                self.assertIs(request.call_args.args[1]['shift'], False)
                # Assert the configured values are passed through, rather than
                # a literal needing an edit whenever a measured window changes.
                self.assertEqual(options, {'num_ctx': runtime.NUM_CTX,
                                           'num_predict': runtime.NUM_PREDICT})
                c.conn.close()
                c = Coordinator(path)
                detail = c.job_detail(job)
                expected = 'completed' if reason == 'stop' else 'failed'
                self.assertEqual(detail['job']['state'], expected)
                attempt = detail['attempts'][0]
                self.assertEqual(attempt['state'], expected)
                self.assertEqual(attempt['output_text'], reply)
                metrics = json.loads(attempt['metrics_json'])
                self.assertEqual((metrics['done_reason'], metrics['eval_count'],
                                  metrics['output_token_limit']), (reason, 700, 2048))
                if reason != 'stop':
                    self.assertEqual(json.loads(attempt['error_json'])['code'], 'validation_failed')
                messages = c.chat_messages(chat)
                if reason in ('stop', 'length'):
                    self.assertEqual(messages[-1]['text'], reply)
                if reason == 'length':
                    self.assertIn('Incomplete reply', json.loads(messages[-1]['error_json'])['message'])
                    # A new request keeps the saved partial answer in model context.
                    with patch('backend.coordinator.server.threading.Thread.start'):
                        next_job = c.submit(chat, 'Continue from the last sentence.')
                    stream = BytesIO(b'{"message":{"content":"Continuation."},"done":true,"done_reason":"stop"}\n')
                    with patch.object(runtime, '_request', return_value=stream) as request:
                        c._run(next_job, chat)
                    self.assertIn({'role': 'assistant', 'content': reply},
                                  request.call_args.args[1]['messages'])
                    self.assertEqual(c.job_detail(next_job)['job']['state'], 'completed')
                c.conn.close()

    def test_version_one_upgrade_retains_history_without_inventing_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.sqlite3'
            c = Coordinator(path)
            node = c.node_id
            chat = db.create_chat(c.conn, c.workspace_id, 'legacy check')
            with patch('backend.coordinator.server.threading.Thread.start'):
                job = c.submit(chat, 'retained legacy message')
            with patch.object(runtime, 'stream_chat', return_value=iter([
                    ('delta', 'retained legacy answer'), ('done', {'done_reason': 'stop'})])):
                c._run(job, chat)
            # Recreate the old on-disk shape in this disposable database only.
            c.conn.execute('ALTER TABLE attempts DROP COLUMN metrics_json')
            c.conn.execute("UPDATE meta SET value='1' WHERE key='schema_version'")
            c.conn.commit()
            c.conn.close()
            for _ in range(2):
                c = Coordinator(path)
                self.assertEqual(c.node_id, node)
                self.assertEqual(c.chat_messages(chat)[0]['text'], 'retained legacy message')
                self.assertEqual(c.chat_messages(chat)[1]['text'], 'retained legacy answer')
                self.assertIsNone(c.job_detail(job)['attempts'][0]['metrics_json'])
                self.assertEqual(c.job_detail(job)['job']['state'], 'completed')
                self.assertEqual(c.conn.execute(
                    "SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],
                    str(db.SCHEMA_VERSION))
                self.assertIn('metrics_json', {r['name'] for r in c.conn.execute('PRAGMA table_info(attempts)')})
                c.conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
