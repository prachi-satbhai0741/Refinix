"""Durable writes keep working under Windows' rule for flushing files.

Windows refuses FlushFileBuffers (os.fsync) on a handle opened read-only,
with EBADF. The update's data copy and every managed model download used to
flush such a handle; on the native Windows runner that failed every update
(2026-10-09). These checks apply the same rule on any operating system.

    python3 -m unittest backend.coordinator.test_windows_durability -v
"""

from __future__ import annotations

import errno
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import provisioning, recovery

REAL_FSYNC = os.fsync


def windows_fsync(descriptor: int) -> None:
    import fcntl
    if fcntl.fcntl(descriptor, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY \
            and not os.path.isdir(f"/dev/fd/{descriptor}"):
        raise OSError(errno.EBADF, "Bad file descriptor")
    REAL_FSYNC(descriptor)


@unittest.skipIf(sys.platform == "win32", "Windows applies the rule itself")
class TestWindowsFlushRule(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.base = Path(self.dir.name)
        self.source = self.base / "source.bin"
        self.source.write_bytes(b"workspace bytes" * 1000)

    def test_the_rule_is_applied(self):
        with open(self.source, "rb") as handle, patch.object(os, "fsync", windows_fsync):
            with self.assertRaises(OSError):
                os.fsync(handle.fileno())

    def test_the_update_data_copy_is_durable_under_it(self):
        target = self.base / "copy.bin"
        with patch.object(recovery.os, "fsync", windows_fsync):
            recovery._copy_durably(self.source, target)
        self.assertEqual(target.read_bytes(), self.source.read_bytes())

    def test_a_model_file_is_put_in_place_under_it(self):
        target = self.base / "model.gguf"
        with patch.object(provisioning.os, "fsync", windows_fsync):
            provisioning._durable_replace(self.source, target)
        self.assertEqual(target.read_bytes(), b"workspace bytes" * 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
