"""The qualification control stays off in every publishable package.

    python3 -m unittest desktop.test_qualify_control -v
"""

from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from desktop import qualify_control as control

TOKEN = "t" * 40
SCRATCH = {"channel": "beta", "publishable": False, "version": "0.1.0-beta.902"}


class TestGate(unittest.TestCase):
    def test_only_a_private_beta_build_with_a_long_token_enables_it(self):
        env = {control.TOKEN_VARIABLE: TOKEN}
        self.assertTrue(control.enabled(SCRATCH, env))
        for identity in ({**SCRATCH, "publishable": True},       # a release package
                         {**SCRATCH, "publishable": None},       # an older identity
                         {**SCRATCH, "channel": "internal"}, None, {}):
            with self.subTest(identity=identity):
                self.assertFalse(control.enabled(identity, env))
        self.assertFalse(control.enabled(SCRATCH, {control.TOKEN_VARIABLE: "short"}))
        self.assertFalse(control.enabled(SCRATCH, {}))

    def test_fail_start_names_one_version_and_obeys_the_gate(self):
        env = {control.TOKEN_VARIABLE: TOKEN, control.FAIL_START_VARIABLE: "0.1.0-beta.902"}
        self.assertTrue(control.should_fail_start(SCRATCH, env))
        self.assertFalse(control.should_fail_start({**SCRATCH, "version": "0.1.0-beta.901"},
                                                   env))
        self.assertFalse(control.should_fail_start({**SCRATCH, "publishable": True}, env))


class TestRequests(unittest.TestCase):
    def serve(self, folder, actions):
        stop = threading.Event()
        thread = threading.Thread(target=control.serve, args=(folder, actions, stop),
                                  kwargs={"environ": {control.TOKEN_VARIABLE: TOKEN},
                                          "interval": 0.05}, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(stop.set)

    def ask(self, folder, request, seconds=3.0):
        (folder / control.RESULT).unlink(missing_ok=True)
        (folder / control.REQUEST).write_text(json.dumps(request))
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if (folder / control.RESULT).is_file():
                return json.loads((folder / control.RESULT).read_text())
            time.sleep(0.05)
        return None

    def test_a_signed_request_runs_and_a_wrong_token_is_ignored(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            calls = []
            self.serve(folder, {"install": lambda request: calls.append(request) or
                                {"installing": True}})
            self.assertIsNone(self.ask(folder, {"token": "x" * 40, "id": 1,
                                                "action": "install"}, seconds=0.6))
            self.assertEqual(calls, [])
            answer = self.ask(folder, {"token": TOKEN, "id": 2, "action": "install"})
            self.assertEqual(answer, {"id": 2, "result": {"installing": True}})
            answer = self.ask(folder, {"token": TOKEN, "id": 3, "action": "erase"})
            self.assertEqual(answer["result"], {"error": "unknown action"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
