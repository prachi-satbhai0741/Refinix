"""Offline checks for the two-device `refinix start` presentation launcher."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("refinix")
# The launcher's own default addresses, so the checks follow the script
# rather than a second copy of the network plan.
DEFAULTS = dict(re.findall(r'^(MAC_IP|WORKER_IP)="\$\{REFINIX_\w+:-([0-9.]+)\}"',
                           SCRIPT.read_text(encoding="utf-8"), re.M))
MAC_IP, WORKER_IP = DEFAULTS["MAC_IP"], DEFAULTS["WORKER_IP"]
SUBNET = WORKER_IP.rsplit(".", 1)[0]


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

    def run_launcher(self, **extra):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("REFINIX_")}
        env.update(HOME=str(self.root), PATH=f"{self.bin}:/usr/bin:/bin",
                   CALLS=str(self.log), **extra)
        return subprocess.run([str(SCRIPT), "start"], env=env, text=True,
                              capture_output=True, check=False)

    def test_mac_opens_only_on_the_expected_hotspot_address(self):
        self.command("uname", "echo Darwin")
        self.command("ipconfig", f"echo {MAC_IP}")
        self.command("nc", "exit 0")
        self.command("open", 'echo "open $*" >> "$CALLS"')
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Refinix.app", self.log.read_text(encoding="utf-8"))

        self.command("ipconfig", f"echo {SUBNET}.99")
        self.log.unlink()
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists(), "a mismatched network opened Refinix")

    def test_ubuntu_starts_the_guarded_stack_only_on_the_expected_address(self):
        self.command("uname", "echo Linux")
        self.command(
            "ip",
            'case "$*" in *"route show default"*) echo "default via ' + SUBNET + '.238 dev wlo1";; '
            '*) echo "1: wlo1 inet ' + WORKER_IP + '/24 scope global wlo1";; esac')
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

    def test_another_network_is_given_without_editing_the_launcher(self):
        self.command("uname", "echo Darwin")
        self.command("ipconfig", "echo 192.168.50.20")
        self.command("nc", "exit 0")
        self.command("open", 'echo "open $*" >> "$CALLS"')
        self.assertNotEqual(self.run_launcher().returncode, 0)
        result = self.run_launcher(REFINIX_MAC_IP="192.168.50.20",
                                   REFINIX_WORKER_IP="192.168.50.21")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("192.168.50.21", result.stdout)


if __name__ == "__main__":
    unittest.main()
