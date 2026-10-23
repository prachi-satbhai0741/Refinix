"""Explicit, bounded local-model check; never part of the offline test suite.

Run from the repository: PYTHONPATH=. ./.venv/bin/python -m backend.coordinator.check_runtime_context
Uses the installed model and request-local settings with disposable SQLite state.
"""
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import db, runtime
from backend.coordinator.server import Coordinator


def main():
    with runtime._request('/api/version') as response:
        version = json.load(response)['version']
    print(json.dumps({'runtime_version': version, 'model': runtime.MODEL,
                      'context_window': runtime.NUM_CTX, 'reply_limit': runtime.NUM_PREDICT}), flush=True)
    cases = [
        ('retained-fact', 'The synthetic access label is ALPHA17. Ignore the padding: '
         + '界' * 5000 + '\nReply with only the access label.', 'completed'),
        ('input-overflow', '界' * 12000, 'failed'),
        ('generation-overflow', 'Ignore this padding: ' + '界' * 8000
         + '\nPrint consecutive integers from 1 to 1000, one per line. Do not explain or stop early.', 'failed'),
    ]
    with tempfile.TemporaryDirectory(prefix='aegis-context-check-') as directory:
        coordinator = Coordinator(Path(directory) / 'synthetic.sqlite3')
        try:
            for label, prompt, expected in cases:
                chat = db.create_chat(coordinator.conn, coordinator.workspace_id, label)
                with patch('backend.coordinator.server.threading.Thread.start'):
                    job = coordinator.submit(chat, prompt)
                start = time.monotonic()
                coordinator._run(job, chat)
                detail = coordinator.job_detail(job)
                attempt = detail['attempts'][0]
                metrics = json.loads(attempt['metrics_json'] or '{}')
                error = json.loads(attempt['error_json'] or '{}')
                messages = coordinator.chat_messages(chat)
                assert detail['job']['state'] == expected, detail
                if label == 'retained-fact':
                    assert 'ALPHA17' in messages[-1]['text'], messages[-1]
                    assert metrics['prompt_tokens'] >= 5000, metrics
                elif label == 'input-overflow':
                    assert 'Context window exceeded' in error['message'], error
                    assert len(messages) == 1 and not attempt['output_text'], messages
                else:
                    assert metrics['limit_reason'] == 'context', metrics
                    assert metrics['prompt_tokens'] + metrics['eval_count'] == runtime.NUM_CTX, metrics
                    assert len(messages) == 2 and messages[-1]['text'], messages
                    assert 'context window' in error['message'], error
                print(json.dumps({'case': label, 'state': detail['job']['state'],
                                  'elapsed_seconds': round(time.monotonic() - start, 3),
                                  'metrics': metrics, 'error': error}), flush=True)
            with runtime._request('/api/ps') as response:
                running = json.load(response)['models']
            print(json.dumps({'loaded_models': running}), flush=True)
        finally:
            coordinator.conn.close()


if __name__ == '__main__':
    main()
