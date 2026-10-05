"""The read-only sandbox control check. Synthetic /proc and /sys only.

    python3 -m unittest backend.coordinator.test_sandbox_probe -v
"""

from __future__ import annotations

import unittest

from backend.coordinator import sandbox_probe

UID = 1000
MANAGER = f"/sys/fs/cgroup/user.slice/user-{UID}.slice/user@{UID}.service"


def files(**overrides):
    base = {"/proc/self/status": "Name:\tpython\nSeccomp:\t0\nSeccomp_filters:\t0\n",
            f"{MANAGER}/cgroup.subtree_control": "cpu io memory pids",
            "/proc/sys/kernel/io_uring_disabled": "0"}
    base.update(overrides)
    return lambda path: base.get(path)


def probe(**kwargs):
    values = dict(platform="linux", read=files(), exists=lambda p: True,
                  systemd_version=lambda: 255, landlock_abi=lambda: 4, uid=UID,
                  environ={"XDG_RUNTIME_DIR": f"/run/user/{UID}"})
    values.update(kwargs)
    return sandbox_probe.probe(**values)


class TestProbe(unittest.TestCase):
    def test_validation_is_never_offered_while_the_storage_limit_is_missing(self):
        result = probe()
        self.assertFalse(result["available"])
        self.assertEqual(result["missing"], ["aggregate temporary-storage limit"])
        self.assertIn("aggregate temporary-storage limit", result["detail"])

    def test_each_missing_control_is_named(self):
        result = probe(read=files(**{f"{MANAGER}/cgroup.subtree_control": "cpu"}),
                       systemd_version=lambda: 252, landlock_abi=lambda: None,
                       exists=lambda p: False)
        for name in ("systemd user manager", "systemd 255 or later", "Landlock",
                     "delegated memory, process and CPU limits"):
            self.assertIn(name, result["missing"])

    def test_no_seccomp_is_reported(self):
        result = probe(read=files(**{"/proc/self/status": "Name:\tpython\n"}))
        self.assertIn("seccomp", result["missing"])

    def test_macos_and_windows_say_validation_is_not_offered(self):
        for platform in ("darwin", "win32"):
            with self.subTest(platform=platform):
                result = sandbox_probe.probe(platform=platform)
                self.assertFalse(result["available"])
                self.assertIn("Apply/Undo still work", result["detail"])

    def test_this_computer_can_be_checked_without_changing_anything(self):
        result = sandbox_probe.probe()
        self.assertFalse(result["available"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
