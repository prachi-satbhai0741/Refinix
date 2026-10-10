"""Sandbox qualification must observe each operation, not just an early refusal."""

import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import qualify_sandbox as q


class TestSandboxQualification(unittest.TestCase):
    def qualify(self, results):
        sandbox = Mock()
        sandbox.status.return_value = {"available": True}
        sandbox.validate.side_effect = results
        report = q.Report()
        with patch.object(q.sandbox_local, "LocalSandbox", return_value=sandbox), \
                patch.object(q.threading, "Timer"), \
                patch.object(q, "leftovers", return_value={}), \
                contextlib.redirect_stdout(io.StringIO()):
            q.qualify(report, Path("/synthetic-sandbox"))
        return report.checks

    def test_launcher_failure_never_counts_as_cancel_deadline_or_output_success(self):
        checks = self.qualify([{"ran": False, "refused": "launcher"}] * 5)
        self.assertEqual([c["passed"] for c in checks],
                         [True, False, False, False, False, False, True])

    def test_each_check_requires_its_observed_outcome(self):
        passed = {"ran": True, "service_exit": 0, "exit_status": 0, "tests_run": 1,
                  "inputs_sha256": "reviewed", "expected_inputs_sha256": "reviewed",
                  "controls": ["no sockets", "Landlock", "no signals"]}
        results = [passed, {**passed, "tests_run": 3},
                   {"ran": False, "refused": "cancelled"},
                   {"ran": False, "refused": "deadline"},
                   {**passed, "output_truncated": True, "output": "bounded"}]
        self.assertTrue(all(c["passed"] for c in self.qualify(results)))
        for bad in ({**passed, "output_truncated": False},
                    {**passed, "output_truncated": True,
                     "output": "x" * (q.sandbox_local.OUTPUT_LIMIT + 1)}):
            with self.subTest(truncated=bad["output_truncated"]):
                self.assertFalse(self.qualify([*results[:-1], bad])[5]["passed"])
