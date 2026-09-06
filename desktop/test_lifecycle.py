"""Offline checks for the Refinix startup and shutdown lifecycle.

No window, no model, no installer and no network: every probe, launcher and
listener is synthetic, and the only state is a temporary directory.

    python3 -m unittest desktop.test_lifecycle -v
"""

import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import db, runtime
from desktop import lifecycle


class FakeProcess:
    """Stands in for `ollama serve` without starting anything."""

    def __init__(self, exits_with=None):
        self.returncode = exits_with
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True


def probes(*states):
    """A probe function that walks a fixed script, repeating the last entry."""
    box = list(states)

    def probe():
        return box.pop(0) if len(box) > 1 else box[0]
    return probe


REACHABLE = {"reachable": True, "server_version": "0.33.3",
             "models": [runtime.MODEL], "loaded": None,
             "endpoint": lifecycle.runtime.HOST, "error": None}
DOWN = {"reachable": False, "server_version": None, "models": [],
        "loaded": None, "endpoint": lifecycle.runtime.HOST,
        "error": "URLError: connection refused"}


# --------------------------------------------------------------------------

class TestEngine(unittest.TestCase):
    def test_running_runtime_is_used_and_never_restarted(self):
        supervisor = lifecycle.EngineSupervisor(
            probe=probes(REACHABLE),
            locate=lambda: self.fail("a running runtime must not be located"),
            spawn=lambda *a, **k: self.fail("a running runtime must not be started"))
        state = supervisor.ensure()
        self.assertTrue(state["reachable"])
        self.assertFalse(state["started_by_refinix"])
        self.assertFalse(supervisor.owned)
        self.assertFalse(supervisor.stop(), "nothing we started, nothing to stop")

    def test_stopped_runtime_is_started_and_owned(self):
        process = FakeProcess()
        started = []
        supervisor = lifecycle.EngineSupervisor(
            probe=probes(DOWN, DOWN, REACHABLE),
            locate=lambda: "/opt/homebrew/bin/ollama",
            spawn=lambda argv, **k: (started.append(argv), process)[1],
            sleep=lambda _s: None)
        state = supervisor.ensure()
        self.assertEqual(started, [["/opt/homebrew/bin/ollama", "serve"]])
        self.assertTrue(state["started_by_refinix"])
        self.assertTrue(supervisor.stop())
        self.assertTrue(process.terminated)

    def test_missing_runtime_is_reported_and_nothing_is_downloaded(self):
        supervisor = lifecycle.EngineSupervisor(
            probe=probes(DOWN), locate=lambda: None,
            spawn=lambda *a, **k: self.fail("nothing may be installed"))
        with self.assertRaises(lifecycle.StartupError) as caught:
            supervisor.ensure()
        self.assertIn("not installed", str(caught.exception))
        self.assertEqual(caught.exception.action["kind"], "install")

    def test_startup_timeout_is_bounded_and_does_not_hang(self):
        clock = iter([0.0, 1.0, 2.0, 3.0, 99.0, 99.0])
        supervisor = lifecycle.EngineSupervisor(
            probe=probes(DOWN), locate=lambda: "/usr/local/bin/ollama",
            spawn=lambda *a, **k: FakeProcess(), sleep=lambda _s: None,
            clock=lambda: next(clock))
        with self.assertRaises(lifecycle.StartupError) as caught:
            supervisor.ensure(budget=5)
        self.assertIn("did not become ready", str(caught.exception))

    def test_a_runtime_that_dies_at_once_is_reported_not_retried_forever(self):
        supervisor = lifecycle.EngineSupervisor(
            probe=probes(DOWN), locate=lambda: "/usr/local/bin/ollama",
            spawn=lambda *a, **k: FakeProcess(exits_with=1), sleep=lambda _s: None)
        with self.assertRaises(lifecycle.StartupError) as caught:
            supervisor.ensure()
        self.assertIn("stopped immediately", str(caught.exception))
        self.assertFalse(supervisor.owned)

    def test_reachable_but_silent_runtime_is_not_restarted(self):
        half = dict(DOWN, reachable=True, error="tags unavailable")
        supervisor = lifecycle.EngineSupervisor(
            probe=probes(half),
            locate=lambda: self.fail("must not relocate a live service"),
            spawn=lambda *a, **k: self.fail("must not restart a live service"))
        state = supervisor.ensure()
        self.assertFalse(state["started_by_refinix"])


class TestModel(unittest.TestCase):
    def test_installed_model_is_reported_ready(self):
        self.assertEqual(lifecycle.model_status(REACHABLE)["state"], "ok")

    def test_missing_model_gives_the_exact_command_and_no_download(self):
        state = lifecycle.model_status(dict(REACHABLE, models=["other:1b"]))
        self.assertEqual(state["state"], "attention")
        self.assertEqual(state["action"]["command"], f"ollama pull {runtime.MODEL}")
        self.assertIn("does not download", state["detail"])

    def test_unreachable_runtime_leaves_the_model_unknown_not_missing(self):
        state = lifecycle.model_status(DOWN)
        self.assertEqual(state["state"], "unavailable")
        self.assertIsNone(state["installed"])

    def test_a_similar_model_name_is_not_accepted_as_the_configured_one(self):
        near = dict(REACHABLE, models=[runtime.MODEL.split(":")[0]])
        self.assertEqual(lifecycle.model_status(near)["state"], "attention")


class TestPorts(unittest.TestCase):
    def test_free_port_is_taken_directly(self):
        choice = lifecycle.choose_port(8770, free=lambda p: p == 8770,
                                       identify=lambda p, **k: None)
        self.assertEqual((choice.port, choice.reused), (8770, False))

    def test_our_own_coordinator_is_reused(self):
        choice = lifecycle.choose_port(
            8770, workspace_id="w-1", free=lambda p: False,
            identify=lambda p, **k: {"workspace_id": "w-1", "node_id": "n"})
        self.assertTrue(choice.reused)
        self.assertEqual(choice.port, 8770)

    def test_an_unrelated_service_is_never_attached_to(self):
        seen = []

        def identify(port, **_k):
            seen.append(port)
            return None                      # something else answers, or nothing

        choice = lifecycle.choose_port(
            8770, free=lambda p: p != 8770, identify=identify,
            candidates=(8770, 8771))
        self.assertEqual(choice.port, 8771)
        self.assertFalse(choice.reused)
        self.assertEqual(seen, [8770])

    def test_another_workspaces_coordinator_is_left_alone(self):
        choice = lifecycle.choose_port(
            8770, workspace_id="mine", free=lambda p: p == 8772,
            identify=lambda p, **k: {"workspace_id": "theirs", "node_id": "n"},
            candidates=(8770, 8771, 8772))
        self.assertEqual(choice.port, 8772)
        self.assertFalse(choice.reused)

    def test_every_port_taken_fails_readably_rather_than_looping(self):
        with self.assertRaises(lifecycle.StartupError) as caught:
            lifecycle.choose_port(8770, free=lambda p: False,
                                  identify=lambda p, **k: None,
                                  candidates=(8770, 8771))
        self.assertIn("No local address", str(caught.exception))
        self.assertEqual(caught.exception.action["kind"], "retry")

    def test_identify_rejects_a_listener_that_is_not_a_coordinator(self):
        """A real socket that answers nothing must not be mistaken for ours."""
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            self.assertFalse(lifecycle.port_free(port))
            self.assertIsNone(lifecycle.identify_occupant(port, timeout=0.5))


class TestSingleInstance(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "desktop.lock"

    def tearDown(self):
        self.dir.cleanup()

    def test_second_launch_finds_the_first_and_its_port(self):
        first = lifecycle.SingleInstance(self.path)
        self.assertIsNone(first.acquire())
        first.record(port=8770, mode="window")

        second = lifecycle.SingleInstance(self.path)
        existing = second.acquire()
        self.assertIsNotNone(existing, "a second launch must not take the lock")
        self.assertEqual(existing["port"], 8770)
        first.release()

    def test_the_lock_is_reusable_once_released(self):
        first = lifecycle.SingleInstance(self.path)
        first.acquire()
        first.record(port=8770)
        first.release()
        second = lifecycle.SingleInstance(self.path)
        self.assertIsNone(second.acquire())
        second.release()

    def test_a_corrupt_lock_file_does_not_crash_the_second_launch(self):
        self.path.write_text("not json at all")
        first = lifecycle.SingleInstance(self.path)
        first.acquire()
        second = lifecycle.SingleInstance(self.path)
        self.assertEqual(second.acquire(), {})
        first.release()


class TestStartupSequence(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.state = Path(self.dir.name) / "state.sqlite3"

    def tearDown(self):
        self.dir.cleanup()

    def _supervisor(self, probe):
        return lifecycle.EngineSupervisor(
            probe=probe, locate=lambda: None, spawn=lambda *a, **k: FakeProcess(),
            sleep=lambda _s: None)

    def test_ready_start_reports_every_step_and_a_loopback_address(self):
        progress = lifecycle.Progress()
        started = {}

        def start_server(state_path, port):
            started["port"] = port
            return ("server", "coordinator")

        with patch.object(lifecycle, "choose_port",
                          return_value=lifecycle.PortChoice(8770, False, "free")):
            result = lifecycle.run_startup(
                progress, state_path=self.state, start_server=start_server,
                supervisor=self._supervisor(probes(REACHABLE)))
        self.assertEqual(result.url, "http://127.0.0.1:8770/")
        self.assertEqual(started["port"], 8770)
        snapshot = progress.snapshot()
        self.assertEqual(snapshot["phase"], "ready")
        self.assertEqual({s["state"] for s in snapshot["steps"]}, {"ok"})

    def test_a_missing_engine_still_opens_the_window_with_an_action(self):
        progress = lifecycle.Progress()
        with patch.object(lifecycle, "choose_port",
                          return_value=lifecycle.PortChoice(8770, False, "free")):
            result = lifecycle.run_startup(
                progress, state_path=self.state,
                start_server=lambda *_a: ("server", "coordinator"),
                supervisor=self._supervisor(probes(DOWN)))
        snapshot = progress.snapshot()
        self.assertEqual(snapshot["phase"], "attention")
        steps = {s["key"]: s for s in snapshot["steps"]}
        self.assertEqual(steps["engine"]["state"], "attention")
        self.assertEqual(steps["engine"]["action"]["kind"], "install")
        # The window still gets an address; it never sits on a spinner.
        self.assertTrue(result.url.startswith("http://127.0.0.1:"))

    def test_reusing_our_coordinator_does_not_start_a_second_one(self):
        progress = lifecycle.Progress()
        with patch.object(lifecycle, "choose_port", return_value=lifecycle.PortChoice(
                8770, True, "reusing", {"workspace_id": "w"})):
            result = lifecycle.run_startup(
                progress, state_path=self.state,
                start_server=lambda *_a: self.fail("must not start a second coordinator"),
                supervisor=self._supervisor(probes(REACHABLE)))
        self.assertTrue(result.reused_coordinator)
        self.assertIsNone(result.server)

    def test_an_occupied_port_fails_readably_rather_than_hanging(self):
        progress = lifecycle.Progress()

        def start_server(_state, _port):
            raise OSError(48, "Address already in use")

        with patch.object(lifecycle, "choose_port",
                          return_value=lifecycle.PortChoice(8770, False, "free")):
            with self.assertRaises(lifecycle.StartupError) as caught:
                lifecycle.run_startup(
                    progress, state_path=self.state, start_server=start_server,
                    supervisor=self._supervisor(probes(REACHABLE)))
        self.assertIn("would not start", str(caught.exception))
        self.assertEqual(caught.exception.action["kind"], "retry")

    def test_existing_state_is_read_not_created_for_the_identity_check(self):
        self.assertIsNone(lifecycle.read_workspace_id(self.state))
        self.assertFalse(self.state.exists(), "the probe must not create a database")
        conn = db.connect(self.state)
        conn.execute("INSERT INTO meta(key, value) VALUES ('workspace_id', 'w-42')")
        conn.commit()
        conn.close()
        self.assertEqual(lifecycle.read_workspace_id(self.state), "w-42")


class TestProgress(unittest.TestCase):
    def test_snapshots_are_safe_to_read_while_steps_are_written(self):
        progress = lifecycle.Progress()
        stop = threading.Event()

        def writer():
            while not stop.is_set():
                progress.set("engine", "running", "still going")

        thread = threading.Thread(target=writer, daemon=True)
        thread.start()
        try:
            for _ in range(200):
                self.assertEqual(len(progress.snapshot()["steps"]),
                                 len(lifecycle.Progress.ORDER))
        finally:
            stop.set()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
