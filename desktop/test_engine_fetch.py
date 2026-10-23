"""Engine and tool downloads retry an upstream server error, never a 4xx.

    python3 -m unittest desktop.test_engine_fetch -v
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine"))
import fetch  # noqa: E402


def answers(*codes):
    calls = []

    def urlopen(request, timeout):
        calls.append(request.full_url)
        code = codes[len(calls) - 1]
        if code != 200:
            raise urllib.error.HTTPError(request.full_url, code, "error", {}, io.BytesIO())
        return io.BytesIO(b"archive bytes")
    return urlopen, calls


class TestRetries(unittest.TestCase):
    def test_a_server_error_is_retried_then_succeeds(self):
        urlopen, calls = answers(500, 502, 200)
        waits = []
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(fetch.urllib.request, "urlopen", urlopen):
            target = Path(folder) / "a.zip"
            fetch._download("https://example.invalid/a.zip", target, wait=waits.append)
            self.assertEqual(target.read_bytes(), b"archive bytes")
        self.assertEqual(len(calls), 3)
        self.assertEqual(waits, [fetch.RETRY_SECONDS, 2 * fetch.RETRY_SECONDS])

    def test_a_client_error_or_endless_server_errors_fail(self):
        for codes in ((404,), (500, 500, 500)):
            urlopen, calls = answers(*codes)
            with self.subTest(codes=codes), tempfile.TemporaryDirectory() as folder, \
                    patch.object(fetch.urllib.request, "urlopen", urlopen), \
                    self.assertRaises(urllib.error.HTTPError):
                fetch._download("https://example.invalid/a.zip", Path(folder) / "a",
                                wait=lambda s: None)
            self.assertEqual(len(calls), len(codes))

    def test_only_https(self):
        with self.assertRaises(fetch.FetchError):
            fetch._download("http://example.invalid/a.zip", Path("/nonexistent"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
