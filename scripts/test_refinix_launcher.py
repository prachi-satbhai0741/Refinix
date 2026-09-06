"""Offline checks for the two-device `refinix start` presentation launcher."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("refinix")


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls"
        (self.root / "Documents/GitHub/AegisForge/desktop/dist/Refinix.app").mkdir(
            parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def command(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        path.chmod(0o755)

    def run_launcher(self):
        env = dict(os.environ, HOME=str(self.root),
                   PATH=f"{self.bin}:/usr/bin:/bin", CALLS=str(self.log))
        return subprocess.run([str(SCRIPT), "start"], env=env, text=True,
                              capture_output=True, check=False)

    def test_mac_opens_only_on_the_expected_hotspot_address(self):
        self.command("uname", "echo Darwin")
        self.command("ipconfig", "echo 10.219.115.113")
        self.command("nc", "exit 0")
        self.command("open", 'echo "open $*" >> "$CALLS"')
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Refinix.app", self.log.read_text(encoding="utf-8"))

        self.command("ipconfig", "echo 10.219.115.99")
        self.log.unlink()
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists(), "a mismatched network opened Refinix")

    def test_ubuntu_starts_the_guarded_stack_only_on_the_expected_address(self):
        self.command("uname", "echo Linux")
        self.command(
            "ip",
            'case "$*" in *"route show default"*) echo "default via 10.219.115.238 dev wlo1";; '
            '*) echo "1: wlo1 inet 10.219.115.160/24 scope global wlo1";; esac')
        self.command("sudo", 'echo "sudo $*" >> "$CALLS"')
        self.command("systemctl", "echo active")
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.log.read_text(encoding="utf-8")
        self.assertIn("systemctl start k3s", calls)
        self.assertIn("deployment/aegisforge-executor --timeout=300s", calls)

        self.command(
            "ip",
            'case "$*" in *"route show default"*) echo "default via 10.0.0.1 dev wlo1";; '
            '*) echo "1: wlo1 inet 10.0.0.2/24 scope global wlo1";; esac')
        self.log.unlink()
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists(), "a mismatched network started services")


if __name__ == "__main__":
    unittest.main()
