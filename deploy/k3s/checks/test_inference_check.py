"""Behavioural checks for the C05 inference check and its wrapper.

The real script and the real shell wrapper are executed as subprocesses against
a stubbed adapter, rather than a copied fragment: a check that exercises a
different copy of the code proves nothing about what ships.

    python3 -m unittest deploy.k3s.checks.test_inference_check
"""

import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE / "pod_inference_check.py"
WRAPPER = HERE / "inference-in-pod.sh"

EXIT_OK, EXIT_FAILED, EXIT_UNREACHABLE, EXIT_DEADLINE = 0, 1, 2, 3

GOOD_DONE = ('("done", {"done_reason": "stop", "limit_reason": None, '
             '"prompt_tokens": 12, "output_tokens": 3, '
             '"context_window": 4096, "runtime_ms": 120})')


def run_script(stream_body: str, *, reachable=True, deadline="20", expected="POD"):
    """Run the real script with a stubbed backend.worker.runtime."""
    with tempfile.TemporaryDirectory() as tmp:
        pkg = pathlib.Path(tmp) / "backend" / "worker"
        pkg.mkdir(parents=True)
        (pathlib.Path(tmp) / "backend" / "__init__.py").write_text("")
        (pkg / "__init__.py").write_text("")
        (pkg / "runtime.py").write_text(textwrap.dedent(f"""
            import time

            def probe():
                return {{"endpoint": "http://stub:11434",
                         "reachable": {reachable},
                         "server_version": "0.0.0-stub",
                         "models": ["stub"], "error": None}}

            def stream_chat(messages, should_cancel=None, timeout=None):
            {textwrap.indent(textwrap.dedent(stream_body), " " * 16)}
            """))
        env = {**os.environ, "PYTHONPATH": tmp,
               "AEGIS_CHECK_DEADLINE": deadline,
               "AEGIS_EXPECTED_ANSWER": expected,
               "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.run([sys.executable, str(SCRIPT)], env=env,
                              capture_output=True, text=True, timeout=120)


class TestInferenceCheck(unittest.TestCase):
    def test_valid_completion_passes(self):
        result = run_script(f'''
            yield "delta", "POD"
            yield {GOOD_DONE}
        ''')
        self.assertEqual(result.returncode, EXIT_OK, result.stdout)
        self.assertIn("PASS:", result.stdout)

    def test_empty_output_fails(self):
        result = run_script(f'''
            yield "delta", "   "
            yield {GOOD_DONE}
        ''')
        self.assertEqual(result.returncode, EXIT_FAILED)
        self.assertIn("empty answer", result.stdout)

    def test_wrong_output_fails(self):
        result = run_script(f'''
            yield "delta", "SOMETHING ELSE"
            yield {GOOD_DONE}
        ''')
        self.assertEqual(result.returncode, EXIT_FAILED)
        self.assertIn("does not contain", result.stdout)

    def test_truncated_completion_fails(self):
        """A length stop is not a normal completion, even with the right text."""
        result = run_script('''
            yield "delta", "POD"
            yield ("done", {"done_reason": "length", "limit_reason": "output",
                            "prompt_tokens": 12, "output_tokens": 2048,
                            "context_window": 4096, "runtime_ms": 900})
        ''')
        self.assertEqual(result.returncode, EXIT_FAILED)
        self.assertIn("did not stop normally", result.stdout)

    def test_missing_metrics_fails(self):
        result = run_script('''
            yield "delta", "POD"
            yield ("done", {"done_reason": "stop"})
        ''')
        self.assertEqual(result.returncode, EXIT_FAILED)
        self.assertIn("prompt_tokens missing", result.stdout)

    def test_zero_token_counts_fail(self):
        result = run_script('''
            yield "delta", "POD"
            yield ("done", {"done_reason": "stop", "prompt_tokens": 0,
                            "output_tokens": 0, "context_window": 4096,
                            "runtime_ms": 10})
        ''')
        self.assertEqual(result.returncode, EXIT_FAILED)
        self.assertIn("not positive", result.stdout)

    def test_unreachable_runtime_fails_distinctly(self):
        result = run_script("yield 'delta', 'POD'", reachable=False)
        self.assertEqual(result.returncode, EXIT_UNREACHABLE)
        self.assertIn("runtime unreachable", result.stdout)

    def test_blocked_read_is_interrupted_by_the_deadline(self):
        """A blocking read must be cut off. A flag-setting timer cannot do this."""
        import time as _t
        began = _t.monotonic()
        result = run_script('''
            import time
            time.sleep(600)          # a read that never returns
            yield "delta", "POD"
        ''', deadline="3")
        elapsed = _t.monotonic() - began
        self.assertEqual(result.returncode, EXIT_DEADLINE, result.stdout)
        self.assertIn("deadline of 3", result.stdout)
        self.assertLess(elapsed, 30, f"the deadline did not interrupt: {elapsed:.1f}s")

    def test_deadline_covers_the_initial_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = pathlib.Path(tmp) / "backend" / "worker"
            pkg.mkdir(parents=True)
            (pathlib.Path(tmp) / "backend" / "__init__.py").write_text("")
            (pkg / "__init__.py").write_text("")
            (pkg / "runtime.py").write_text(
                "import time\n"
                "def probe():\n    time.sleep(600)\n    return {}\n"
                "def stream_chat(*a, **k):\n    yield 'done', {}\n")
            env = {**os.environ, "PYTHONPATH": tmp, "AEGIS_CHECK_DEADLINE": "3"}
            import time as _t
            began = _t.monotonic()
            result = subprocess.run([sys.executable, str(SCRIPT)], env=env,
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, EXIT_DEADLINE, result.stdout)
            self.assertLess(_t.monotonic() - began, 30)


class TestWrapper(unittest.TestCase):
    """The shell wrapper, not a paraphrase of it."""

    def run_wrapper(self, fake_kubectl: str, **env_extra):
        with tempfile.TemporaryDirectory() as tmp:
            fake = pathlib.Path(tmp) / "kubectl"
            fake.write_text(fake_kubectl)
            fake.chmod(0o755)
            env = {**os.environ, "KUBECTL": str(fake),
                   "AEGIS_CHECK_DEADLINE": "5", "AEGIS_OUTER_TIMEOUT": "10",
                   **env_extra}
            return subprocess.run(["sh", str(WRAPPER)], env=env,
                                  capture_output=True, text=True, timeout=60)

    def test_stdin_is_forwarded_to_the_container(self):
        """The script must arrive on the exec's stdin, not be assumed present."""
        result = self.run_wrapper(
            '#!/bin/sh\n'
            'case "$*" in *jsonpath*) echo worker-pod-1; exit 0;; esac\n'
            'bytes=$(cat | wc -c)\n'
            'echo "received $bytes bytes on stdin"\n'
            'exit 0\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"received\s+\d{3,}\s+bytes on stdin")

    def test_failure_is_propagated_not_masked(self):
        result = self.run_wrapper(
            '#!/bin/sh\n'
            'case "$*" in *jsonpath*) echo worker-pod-1; exit 0;; esac\n'
            'cat >/dev/null; echo "FAIL: synthetic"; exit 1\n')
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL: synthetic", result.stdout)

    def test_missing_pod_fails(self):
        result = self.run_wrapper(
            '#!/bin/sh\ncase "$*" in *jsonpath*) echo ""; exit 0;; esac\nexit 0\n')
        self.assertEqual(result.returncode, 4)
        self.assertIn("no worker Pod", result.stdout)

    def test_stuck_exec_is_bounded(self):
        import time as _t
        began = _t.monotonic()
        result = self.run_wrapper(
            '#!/bin/sh\n'
            'case "$*" in *jsonpath*) echo worker-pod-1; exit 0;; esac\n'
            'sleep 600\n', AEGIS_OUTER_TIMEOUT="3")
        self.assertEqual(result.returncode, 124)
        self.assertIn("exceeded", result.stdout)
        self.assertLess(_t.monotonic() - began, 30)

    def test_container_is_explicit(self):
        result = self.run_wrapper(
            '#!/bin/sh\n'
            'case "$*" in *jsonpath*) echo worker-pod-1; exit 0;; esac\n'
            'echo "args: $*"; cat >/dev/null; exit 0\n')
        self.assertIn("--container worker", result.stdout)
        self.assertNotIn(" -t ", result.stdout, "a TTY would mangle the piped script")


if __name__ == "__main__":
    unittest.main(verbosity=2)
