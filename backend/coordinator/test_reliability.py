"""Bounded handoff regressions: synthetic files/state, no live models."""
import json
from unittest.mock import patch

from backend.coordinator import code_service, db, dispatch, docflow, ocr, runtime, server
from backend.coordinator.test_code_access import RepoBase
from backend.coordinator.test_documents import fake_stream
from backend.coordinator.test_execution4a import Harness


class TestReliabilitySources(Harness):
    def test_missing_transcription_source_stops_before_remote_routing(self):
        job = self.send('Complete the OCR')
        with patch.object(self.c, 'choose_route', return_value=dispatch.Route(
                'remote', 'healthy worker')) as route, \
                patch.object(self.c, '_run_remote') as remote, \
                patch.object(runtime, 'stream_chat') as stream:
            self.c._run(job, self.chat)
        route.assert_not_called()
        remote.assert_not_called()
        stream.assert_not_called()
        self.assertEqual(self.c.jobs(self.chat)[0]['state'], 'failed')
        self.assertIn('Choose the earlier source', self.last_answer())

    def test_ocr_discussion_needs_no_attachment(self):
        for text in ('OCR versus speech recognition: what is the difference?',
                     'OCR accuracy depends on what?', 'Explain OCR',
                     'Complete a document about OCR technology'):
            with self.subTest(text=text):
                self.assertFalse(docflow.requests_transcription(text))
                job = self.send(text)
                with patch.object(runtime, 'stream_chat', fake_stream('Explanation')):
                    self.c._run(job, self.chat)
                self.assertEqual(self.c.jobs(self.chat)[0]['state'], 'completed')
        for text in ('OCR', 'OCR this image', 'OCR me the contents',
                     'Please transcribe the scan', 'Complete the OCR.',
                     'Continue transcription', 'Re-read the source'):
            with self.subTest(text=text):
                self.assertTrue(docflow.requests_transcription(text))

    def test_generated_card_belongs_only_to_assistant(self):
        self.completed_answer("# Entire answer\n\nKeep every paragraph.")
        job = self.send("save that as a docx", skill_id=docflow.WRITE_SKILL)
        self.c._run(job, self.chat, docflow.WRITE_SKILL)
        for _ in range(3):
            messages = self.c.chat_messages(self.chat, with_attachments=True)
            self.assertEqual(sum(len(m['artifacts']) for m in messages), 1)
            self.assertTrue(all(not m['artifacts'] for m in messages if m['role'] == 'user'))

    def test_explicit_same_chat_reuse_reextracts_source(self):
        record = self.attach('source.txt', b'Literal source 17. [unreadable]')
        job = self.send('read the source')
        with patch.object(runtime, 'stream_chat', fake_stream('first answer')):
            self.c._run(job, self.chat)
        with patch('backend.coordinator.server.threading.Thread.start'):
            follow = self.c.submit(self.chat, 'Complete the OCR',
                                   reuse_source_ids=[record['attachment_id']])
        with patch.object(runtime, 'stream_chat', fake_stream('Literal source 17. [unreadable]')) as stream:
            self.c._run(follow, self.chat)
        self.assertIn('Literal source 17.', str(stream.messages))
        self.assertIn('Reused', self.last_answer())
        self.assertEqual(self.c.chat_messages(self.chat, True)[-2]['attachments'][0]['attachment_id'], record['attachment_id'])

    def _sent_source(self, name='source.txt'):
        record = self.attach(name, b'literal source')
        job = self.send('read it')
        with patch.object(runtime, 'stream_chat', fake_stream('read')):
            self.c._run(job, self.chat)
        return record

    def test_followup_without_explicit_source_requests_selection(self):
        self._sent_source()
        self._sent_source('second.txt')
        job = self.send('Complete the OCR')
        self.c._run(job, self.chat)
        self.assertEqual(self.c.jobs(self.chat)[0]['state'], 'failed')
        self.assertIn('Choose the earlier source', self.last_answer())

    def test_cross_chat_source_is_rejected(self):
        record = self._sent_source()
        other = db.create_chat(self.c.conn, self.c.workspace_id, 'other')
        with self.assertRaises(server.RequestError):
            self.c.submit(other, 'reuse', reuse_source_ids=[record['attachment_id']])

    def test_revoked_source_requests_reattachment(self):
        record = self._sent_source()
        with patch('backend.coordinator.server.threading.Thread.start'):
            job = self.c.submit(self.chat, 'Complete the OCR',
                                reuse_source_ids=[record['attachment_id']])
        self.c.conn.execute("UPDATE attachments SET state='received' WHERE attachment_id=?",
                            (record['attachment_id'],))
        self.c.conn.commit()
        self.c._run(job, self.chat)
        self.assertIn('re-attach', self.last_answer().lower())


class TestReliabilityOCR(RepoBase):
    def test_transcription_and_uncertainty_are_literal(self):
        self.assertEqual(ocr.parse_page_reply(json.dumps({
            'status': 'transcription', 'text': 'Valve [unreadable] 17'})), 'Valve [unreadable] 17')

    def test_refusal_is_not_page_text(self):
        with self.assertRaises(ocr.OcrError) as caught:
            ocr.parse_page_reply('{"status":"refusal","text":""}')
        self.assertEqual(caught.exception.code, 'refusal')


class TestReliabilityCode(RepoBase):
    def test_schema_and_incomplete_diagnostics(self):
        rid = self.connect()
        calls = []
        def stream(messages, **options):
            calls.append(options)
            yield 'delta', '{"summary":"partial"'
            yield 'done', {'done_reason': 'length', 'eval_count': 9,
                           'prompt_tokens': 20, 'output_token_limit': 2048}
        with patch.object(runtime, 'stream_chat', stream), self.assertRaises(code_service.CodeError):
            self.svc.propose(rid, 'change', ['src/main.py'], execution_target=code_service.TARGET_LOCAL)
        self.assertIsInstance(calls[0].get('response_format'), dict)
        attempt = dict(self.c.conn.execute('SELECT * FROM attempts').fetchone())
        metrics = json.loads(attempt['metrics_json'])
        self.assertEqual(metrics['done_reason'], 'length')
        self.assertEqual(metrics['eval_count'], 9)
        self.assertEqual(metrics['prompt_tokens'], 20)
        self.assertEqual(metrics['failure_stage'], 'generation')
        self.assertEqual(json.loads(attempt['error_json'])['code'], 'unavailable')
        self.assertIsNotNone(attempt['reasoning_json'])
