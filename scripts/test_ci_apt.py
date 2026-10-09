"""Exercise CI APT failure/retry flow with fake commands; never touch host APT."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / ".github/actions/refinix-apt/install.sh"
FAKE = r'''
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
with open(os.environ["APT_TEST_LOG"], "a") as out:
    out.write(json.dumps([name, *sys.argv[1:]]) + "\n")
if name == "timeout":
    os.execvp(sys.argv[3], sys.argv[3:])
if name == "sudo":
    if sys.argv[1] == "python3":
        sys.stdin.read()  # The mirror rewrite is simulated, never run as root.
        sys.exit(0)
    os.execvp(sys.argv[1], sys.argv[1:])
if name == "apt-get":
    if "update" in sys.argv:
        path = pathlib.Path(os.environ["APT_TEST_COUNT"])
        index = int(path.read_text()) if path.exists() else 0
        path.write_text(str(index + 1))
        sys.exit(json.loads(os.environ["APT_TEST_UPDATES"])[index])
    sys.exit(int(os.environ["APT_TEST_INSTALL"]))
'''


class TestAptSetup(unittest.TestCase):
    def test_bounded_retry_and_fail_closed_installation(self):
        for updates, install, success in (([0], 0, True), ([100, 0], 0, True),
                                          ([124, 0], 0, True), ([100, 100], 0, False),
                                          ([0], 100, False)):
            with self.subTest(updates=updates, install=install), \
                    tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                for name in ("sudo", "timeout", "apt-get"):
                    target = root / name
                    target.write_text(f"#!{sys.executable}\n" + FAKE)
                    target.chmod(0o755)
                log = root / "commands.jsonl"
                result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True,
                                        env={**os.environ, "PATH": f"{root}:{os.environ['PATH']}",
                                             "PACKAGES": "python3-venv xvfb",
                                             "APT_TEST_LOG": str(log),
                                             "APT_TEST_COUNT": str(root / "count"),
                                             "APT_TEST_UPDATES": json.dumps(updates),
                                             "APT_TEST_INSTALL": str(install)})
                self.assertEqual(result.returncode == 0, success, result.stderr)
                calls = [json.loads(line) for line in log.read_text().splitlines()]
                apt = [c for c in calls if c[0] == "apt-get"]
                self.assertEqual(sum("update" in c for c in apt), len(updates))
                self.assertEqual(sum("install" in c for c in apt), int(updates[-1] == 0))
                for call in apt:
                    self.assertIn("Acquire::http::Timeout=30", call)
                    self.assertIn("Acquire::Retries=2", call)
                    self.assertIn("APT::Update::Error-Mode=any", call)
                    self.assertNotIn("--allow-unauthenticated", call)
                for call in calls:
                    if call[0] == "timeout":
                        self.assertIn(call[2], ("180s", "600s"))
                self.assertEqual(any(c[:2] == ["sudo", "python3"] for c in calls),
                                 len(updates) == 2)
