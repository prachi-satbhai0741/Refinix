"""Install and restart: the helper, the launch gate and every crash in between.

Real SQLite workspaces, real workspace locks, real recovery journals and real
app folders on disk. Processes, the clock and opening an app are simulated by
`FakeSystem`, so a "new version" can start, commit, hang or die on cue.

    python3 -m unittest desktop.test_update_apply -v
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import db, ownership, recovery
from desktop import update_apply as ua

N, N1, N2 = "0.1.0-internal.1", "0.1.0-internal.2", "0.1.0-internal.3"


def make_app(path: Path, version: str) -> Path:
    resources = path / "Contents" / "Resources"
    resources.mkdir(parents=True)
    (path / "Contents" / "MacOS").mkdir()
    (path / "Contents" / "MacOS" / "Refinix").write_bytes(b"#!/bin/sh\n")
    (resources / "refinix-build.json").write_text(json.dumps({"version": version}))
    return path


class FakeSystem(ua.System):
    """Processes are records in `alive`; time moves only when the helper sleeps."""

    def __init__(self, test):
        self.test = test
        self.now = 0.0
        self.alive: dict[int, dict] = {}
        self.next_pid = 1000
        self.opened: list[tuple[str, dict]] = []
        self.spawned: list[list[str]] = []
        self.foreign: list[dict] = []
        self.on_open = None              # (path, env) -> None: what the opened app does
        self.terminated: list[int] = []
        self.on_terminate = None
        self.current = None              # whoever is running code right now
        self.verify_error = None
        self.told: list[str] = []
        self.reaped: list[Path] = []

    def start(self, exe="/Applications/Refinix.app/Contents/MacOS/Refinix") -> dict:
        self.next_pid += 1
        record = {"pid": self.next_pid, "create_time": 100.0 + self.next_pid, "exe": exe}
        self.alive[record["pid"]] = record
        return record

    def stop(self, record):
        if record:
            self.alive.pop(record["pid"], None)

    # -- ua.System ---------------------------------------------------------
    def sleep(self, seconds):
        self.now += seconds

    def monotonic(self):
        return self.now

    def identity(self, pid=None):
        if pid is None:
            return dict(self.current) if self.current else None
        return dict(self.alive[pid]) if pid in self.alive else None

    def same(self, record):
        if not record or record.get("pid") not in self.alive:
            return False
        live = self.alive[record["pid"]]
        return (abs(live["create_time"] - float(record.get("create_time") or 0)) < 0.01
                and live["exe"] == record.get("exe"))

    def processes_in(self, bundle):
        return list(self.foreign)

    def terminate(self, record, grace):
        self.terminated.append(record["pid"])
        if self.on_terminate:
            self.on_terminate(record)
        self.stop(record)
        return True

    def reap_engine(self, record_path):
        self.reaped.append(record_path)

    def swap(self, first, second):
        temporary = Path(str(first) + ".swap")
        os.replace(first, temporary)
        os.replace(second, first)
        os.replace(temporary, second)

    def clone(self, source, target):
        import shutil
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, symlinks=True)

    def spawn(self, argv, environment, log):
        self.spawned.append(list(argv))
        return self.start(exe=argv[0])

    def open_app(self, path, environment):
        self.opened.append((str(path), dict(environment)))
        if self.on_open:
            self.on_open(Path(path), environment)

    def verify_incoming(self, app, journal):
        if self.verify_error:
            raise RuntimeError(self.verify_error)
        if ua.installed_version(app) != journal["to_version"]:
            raise RuntimeError("not the offered version")

    def tell(self, title, text):
        self.told.append(text)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        self.db = ownership.canonical_database(base / "data" / "coordinator.sqlite3")
        conn = db.connect(self.db)
        conn.execute("INSERT INTO meta(key, value) VALUES ('marker', 'before update')")
        conn.commit()
        conn.close()
        self.install = make_app(base / "Applications" / "Refinix.app", N)
        self.system = FakeSystem(self)
        self.me = self.system.start()               # the running old app (N)
        self.system.current = self.me
        self.env = {"REFINIX_DATA_ROOT": str(self.db.parent)}

    # -- the running app's side -------------------------------------------
    def lock(self):
        lock = ownership.WorkspaceLock.for_database(self.db)
        self.assertIsNone(lock.acquire())
        return lock

    def prepared(self, update_id="u1", to=N1, *, snapshot=True, hand_off=True,
                 from_version=N):
        incoming = make_app(ua.attempt_folder(self.db, update_id) / "Refinix.app", to)
        owner = self.lock()
        journal = ua.plan_attempt(owner, self.db, update_id=update_id,
                                  from_version=from_version, to_version=to,
                                  install_path=self.install, incoming=incoming,
                                  lane="macos-arm64", channel="internal", trust_root="t",
                                  environment=self.env, system=self.system)
        if snapshot:
            recovery.Recovery(owner, self.db).set_aside(
                from_version=from_version, to_version=to, update_id=update_id,
                data_root=str(self.db.parent))
            journal = ua.mark(owner, self.db, journal, "snapshot_taken")
        if hand_off:
            journal = ua.hand_off(owner, self.db, journal, bundle=self.install,
                                  system=self.system)
        owner.release()
        self.system.stop(self.me)                     # the old app exits
        return journal

    def new_version(self, *, commit=True, write=False, die=False, crash_committing=False,
                    expect=N1):
        """What the opened app does: start under the gate, maybe write, commit or die.

        Only the expected new version acts; reopening the old one does nothing,
        so its one-time notice is left for the test to read.
        """
        def run(path, environment):
            version = ua.installed_version(path)
            if version != expect:
                return
            app = self.system.start(exe=str(path / "Contents" / "MacOS" / "Refinix"))
            saved, self.system.current = self.system.current, app
            owner = self.lock()
            try:
                gate = ua.on_launch(owner, self.db, version, bundle=path,
                                    system=self.system)
                if gate.supervised is None:
                    self.system.stop(app)
                    return
                if write:
                    self.newer_writes()
                if crash_committing:
                    ua.write_journal(owner, self.db, ua.read_journal(self.db),
                                     state="committing")
                    self.system.stop(app)
                    return
                if commit:
                    self.assertEqual(ua.read_journal(self.db)["state"], "relaunching")
                    ua.commit_if_supervised(owner, self.db, gate.supervised)
                if die:
                    self.system.stop(app)
            finally:
                owner.release()
                self.system.current = saved
        return run

    def newer_writes(self):
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE meta SET value='after update' WHERE key='marker'")
        conn.commit()
        conn.close()

    def marker(self):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute("SELECT value FROM meta WHERE key='marker'").fetchone()[0]
        finally:
            conn.close()

    def helper(self, mode="--apply-update"):
        journal = self.journal() or {}
        spawned = journal.get("helper")
        self.system.current = spawned if self.system.same(spawned) else self.system.start(
            exe="/data/updates/install/helper/Refinix.app/Contents/MacOS/Refinix")
        helper = self.system.current
        try:
            return ua.helper_main([mode, str(self.db)], system=self.system)
        finally:
            self.system.stop(helper)                 # a returned helper has exited

    def data(self):
        return ua._data_journal(self.db)

    def journal(self):
        return ua.read_journal(self.db)


class TestInstall(Base):
    def test_retention_finishes_under_the_lock_before_another_attempt_is_allowed(self):
        self.prepared()
        self.system.on_open = self.new_version()
        cleanup = ua._succeeded
        states = []
        def checked(owner, database, journal):
            ownership.require(owner, database)
            states.append(self.journal()["state"])
            self.system.stop(journal.get("helper"))  # even if the helper already exits
            with self.assertRaises(ua.InstallError):
                ua.plan_attempt(owner, database, update_id="u2", from_version=N1,
                                to_version=N2, install_path=self.install,
                                incoming=ua.attempt_folder(database, "u2") / "Refinix.app",
                                lane="macos-arm64", channel="internal", trust_root="t",
                                environment=self.env, system=self.system)
            cleanup(owner, database, journal)
        with patch.object(ua, "_succeeded", side_effect=checked):
            self.assertEqual(self.helper(), 0)
        self.assertEqual(states, ["committing"])
        self.assertEqual(self.journal()["state"], "committed")

    def test_a_crash_during_retention_is_finished_on_resume(self):
        self.prepared()
        self.system.on_open = self.new_version()
        with patch.object(ua, "_succeeded", side_effect=OSError("power lost")):
            with self.assertRaises(OSError):
                self.helper()
        self.assertEqual(self.journal()["state"], "committing")
        self.assertEqual(self.data()["state"], "committed")
        previous = Path(self.journal()["previous_app"])
        self.assertEqual(ua.installed_version(previous), N)
        for process in list(self.system.alive.values()):
            self.system.stop(process)                    # the interrupted app exits
        self.system.on_open = None
        self.assertEqual(self.helper("--resume"), 0)
        self.assertEqual(self.journal()["state"], "committed")
        self.assertEqual(ua.installed_version(previous), N)
        self.assertEqual(self.marker(), "before update")

    def test_the_new_version_replaces_the_app_reopens_and_commits(self):
        self.prepared()
        self.system.on_open = self.new_version()
        self.assertEqual(self.helper(), 0)
        self.assertEqual(ua.installed_version(self.install), N1)
        self.assertEqual(self.journal()["state"], "committed")
        self.assertEqual(self.data()["state"], "committed")
        self.assertEqual(ua.installed_version(self.journal()["previous_app"]), N)
        self.assertEqual(self.system.opened, [(str(self.install), self.env)])
        self.assertFalse((self.db.parent / "updates" / "staging" / N1).exists())

    def test_relaunching_is_recorded_before_the_new_version_opens(self):
        self.prepared()
        states = []
        inner = self.new_version()
        self.system.on_open = lambda p, e: (states.append(self.journal()["state"]),
                                            inner(p, e))
        self.helper()
        self.assertEqual(states, ["relaunching"])

    def test_the_recorded_install_path_and_environment_are_used(self):
        home_apps = Path(self.dir.name) / "home" / "Applications" / "Refinix.app"
        home_apps.parent.mkdir(parents=True)
        os.replace(self.install, home_apps)
        self.install = home_apps
        self.env = {"REFINIX_DATA_ROOT": str(self.db.parent),
                    "REFINIX_TEST_INSTALL_ROOT": str(home_apps.parent)}
        self.prepared()
        self.system.on_open = self.new_version()
        self.helper()
        self.assertEqual(self.system.opened, [(str(home_apps), self.env)])

    def test_waiting_too_long_for_the_old_app_touches_nothing(self):
        self.prepared()
        self.system.alive[self.me["pid"]] = self.me      # the old app never exits
        before = (self.journal(), self.data())
        self.assertEqual(self.helper(), 1)
        self.assertEqual((self.journal(), self.data()), before)
        status = json.loads((ua.attempt_folder(self.db, "u1") / "helper.json").read_text())
        self.assertEqual(status["state"], "old_owner_timeout")
        self.assertEqual(ua.installed_version(self.install), N)

    def test_another_program_running_from_the_app_blocks_and_is_never_signalled(self):
        journal = self.prepared()
        self.system.foreign = [{"pid": 4242, "exe": str(self.install), "create_time": 1}]
        self.assertEqual(self.helper(), 0)
        self.assertFalse(Path(journal["incoming"]).exists(),
                         "the expanded app of an attempt not installed was left behind")
        self.assertEqual(self.journal()["state"], "discarded")
        self.assertIn("another program", self.journal()["reason"])
        self.assertEqual(self.system.terminated, [])
        self.assertEqual(ua.installed_version(self.install), N)
        self.assertEqual(self.data()["state"], "discarded")

    def test_an_incoming_app_that_fails_verification_is_not_installed(self):
        self.prepared()
        self.system.verify_error = "the seal is broken"
        self.helper()
        self.assertEqual(self.journal()["state"], "discarded")
        self.assertEqual(ua.installed_version(self.install), N)
        self.assertEqual(self.system.opened, [(str(self.install), self.env)])


class TestRollback(Base):
    def test_a_new_version_that_never_commits_is_rolled_back_keeping_its_data(self):
        self.prepared()
        self.system.on_open = self.new_version(commit=False, write=True)
        self.assertEqual(self.helper(), 0)
        self.assertEqual(self.journal()["state"], "rolled_back")
        self.assertEqual(ua.installed_version(self.install), N)
        self.assertEqual(self.marker(), "before update")
        attempted = Path(self.data()["attempted"])
        self.assertTrue(any(attempted.iterdir()), "the newer data was not kept")
        self.assertEqual([p for p, _ in self.system.opened], [str(self.install)] * 2)
        self.assertTrue(self.system.terminated, "the supervised app was not stopped")
        self.assertTrue(self.system.reaped)

    def test_a_new_version_that_exits_without_committing_is_rolled_back(self):
        self.prepared()
        self.system.on_open = self.new_version(commit=False, die=True)
        self.helper()
        self.assertEqual(self.journal()["state"], "rolled_back")
        self.assertEqual(ua.installed_version(self.install), N)

    def test_a_late_commit_after_the_abort_marker_is_refused(self):
        journal = self.prepared()
        owner = self.lock()
        journal = ua.write_journal(owner, self.db, journal, state="relaunching")
        (ua.attempt_folder(self.db, "u1") / "abort").write_text("x")
        self.assertIsNone(ua.commit_if_supervised(owner, self.db, journal))
        owner.release()
        self.assertEqual(self.data()["state"], "set_aside")

    def test_a_commit_interrupted_after_committing_is_finished_not_rolled_back(self):
        self.prepared()
        self.system.on_open = self.new_version(crash_committing=True)
        self.assertEqual(self.helper(), 0)
        self.assertEqual(self.journal()["state"], "committed")
        self.assertEqual(self.data()["state"], "committed")
        self.assertEqual(ua.installed_version(self.install), N1)

    def test_a_commit_just_before_the_stop_wins(self):
        self.prepared()
        self.system.on_open = self.new_version(commit=False)
        def commit_first(record):
            owner = self.lock()
            try:
                journal = self.journal()
                ua.write_journal(owner, self.db, journal, state="committing")
                recovery.Recovery(owner, self.db).commit("u1")
            finally:
                owner.release()
        self.system.on_terminate = commit_first
        self.helper()
        self.assertEqual(self.journal()["state"], "committed")
        self.assertEqual(ua.installed_version(self.install), N1)

    def test_an_unrelated_process_after_a_failed_start_blocks_safely(self):
        self.prepared()
        self.system.on_open = self.new_version(commit=False)
        self.system.on_terminate = lambda record: setattr(
            self.system, "foreign", [{"pid": 7, "exe": "x", "create_time": 1}])
        self.assertEqual(self.helper(), 2)
        self.assertEqual(self.journal()["state"], "blocked")
        self.assertEqual(ua.installed_version(self.install), N1, "nothing more moved")
        self.assertTrue(self.system.told)


class TestResume(Base):
    """A helper that stopped is resumed by the next launch, before any database opens."""

    def successful_update_first(self):
        """N -> N1 committed; returns its set-aside folder (the previous recovery material)."""
        self.prepared()
        self.system.on_open = self.new_version()
        self.helper()
        self.system.on_open = None
        self.system.opened.clear()
        self.assertEqual(self.data()["state"], "committed")
        self.me = self.system.start()
        self.system.current = self.me
        return Path(self.data()["set_aside"])

    def test_a_second_attempt_waits_for_the_previous_helper_to_exit(self):
        self.successful_update_first()
        before = self.journal()
        self.system.alive[before["helper"]["pid"]] = before["helper"]
        owner = self.lock()
        try:
            with self.assertRaises(ua.InstallError):
                ua.plan_attempt(owner, self.db, update_id="u2", from_version=N1,
                                to_version=N2, install_path=self.install,
                                incoming=ua.attempt_folder(self.db, "u2") / "Refinix.app",
                                lane="macos-arm64", channel="internal", trust_root="t",
                                environment=self.env, system=self.system)
            self.assertEqual(self.journal(), before)
        finally:
            owner.release()

    def test_a_late_old_helper_cannot_prune_the_next_updates_rollback_copy(self):
        self.successful_update_first()
        earlier = self.journal()
        journal = self.prepared(update_id="u2", from_version=N1, to=N2,
                                hand_off=False)
        owner = self.lock()
        try:
            self.system.swap(Path(journal["incoming"]), self.install)
            previous = ua._previous_path(self.db, journal)
            previous.parent.mkdir(parents=True)
            os.replace(Path(journal["incoming"]), previous)
            recovery.Recovery(owner, self.db).commit("u2")
            journal = ua.write_journal(owner, self.db, journal, state="committed",
                                       previous_app=str(previous))
        finally:
            owner.release()
        data = self.data()
        self.assertFalse(ua._committed(self.db, earlier))
        self.assertEqual(ua._supervise(self.db, earlier, self.system), 0)
        self.assertEqual(ua._give_up(self.db, earlier, None, self.system, "late"), 0)
        with self.assertRaises(ua.InstallError):
            ua._take_lock(self.db, self.system, expected=earlier)
        self.assertEqual(ua.installed_version(previous), N1)
        self.assertTrue(Path(data["set_aside"]).is_dir())
        self.assertEqual((self.journal(), self.data()), (journal, data))
        self.assertEqual(self.system.terminated, [])
        self.assertEqual(self.system.reaped, [])
        owner = self.lock()
        try:
            ua._succeeded(owner, self.db, earlier)         # stale cleanup is inert too
            self.assertEqual(ua.installed_version(previous), N1)
            self.assertTrue(Path(data["set_aside"]).is_dir())
        finally:
            owner.release()

    def test_a_crash_before_the_snapshot_cancels_and_keeps_the_earlier_update(self):
        kept = self.successful_update_first()
        before = self.data()
        self.prepared(update_id="u2", from_version=N1, to=N2, snapshot=False,
                      hand_off=False)
        self.assertEqual(self.helper("--resume"), 0)
        self.assertEqual(self.journal()["state"], "cancelled")
        self.assertEqual(self.data(), before, "the earlier update's record was changed")
        self.assertTrue((kept / self.db.name).is_file(), "earlier snapshot not kept")
        self.assertEqual(ua.installed_version(self.install), N1)
        self.assertEqual(self.system.opened, [(str(self.install), self.env)])

    def test_a_crash_while_copying_is_finished_then_discarded(self):
        self.successful_update_first()
        incoming = make_app(ua.attempt_folder(self.db, "u2") / "Refinix.app", N2)
        owner = self.lock()
        journal = ua.plan_attempt(owner, self.db, update_id="u2", from_version=N1,
                                  to_version=N2, install_path=self.install,
                                  incoming=incoming, lane="macos-arm64",
                                  channel="internal", trust_root="t",
                                  environment=self.env, system=self.system)
        real = recovery._copy_durably

        def crash_on_the_database(source, target):
            if Path(target).name == self.db.name:
                raise OSError("power lost")
            real(source, target)

        with patch.object(recovery, "_copy_durably", side_effect=crash_on_the_database):
            with self.assertRaises(OSError):
                recovery.Recovery(owner, self.db).set_aside(
                    from_version=N1, to_version=N2, update_id="u2",
                    data_root=str(self.db.parent))
        owner.release()
        self.assertEqual(self.data()["state"], "setting_aside")
        self.assertEqual(self.helper("--resume"), 0)
        self.assertEqual(self.journal()["state"], "discarded")
        self.assertEqual(self.data()["state"], "discarded")
        self.assertEqual(ua.installed_version(self.install), N1)

    def test_a_crash_between_the_snapshot_and_its_marker_discards_the_unchanged_copy(self):
        self.successful_update_first()
        incoming = make_app(ua.attempt_folder(self.db, "u2") / "Refinix.app", N2)
        owner = self.lock()
        ua.plan_attempt(owner, self.db, update_id="u2", from_version=N1, to_version=N2,
                        install_path=self.install, incoming=incoming,
                        lane="macos-arm64", channel="internal", trust_root="t",
                        environment=self.env, system=self.system)
        recovery.Recovery(owner, self.db).set_aside(
            from_version=N1, to_version=N2, update_id="u2", data_root=str(self.db.parent))
        owner.release()                         # crash: "snapshot_taken" never written
        self.assertEqual(self.journal()["state"], "quiescing")
        self.helper("--resume")
        self.assertEqual(self.journal()["state"], "discarded")
        self.assertEqual(self.data()["state"], "discarded")

    def test_after_the_swap_mismatched_evidence_blocks_and_moves_nothing(self):
        journal = self.prepared(hand_off=False)
        owner = self.lock()
        record = recovery.Recovery(owner, self.db).read()
        record["update_id"] = "someone-else"
        (self.db.parent / "recovery" / recovery.JOURNAL).write_text(json.dumps(record))
        ua.write_journal(owner, self.db, journal, state="swapped")
        self.system.swap(Path(journal["incoming"]), self.install)
        owner.release()
        self.assertEqual(self.helper("--resume"), 2)
        self.assertEqual(self.journal()["state"], "blocked")
        self.assertEqual(ua.installed_version(self.install), N1)
        self.assertEqual(self.system.opened, [])

    def test_after_the_swap_with_matching_evidence_the_new_version_is_tried_again(self):
        journal = self.prepared(hand_off=False)
        owner = self.lock()
        ua.write_journal(owner, self.db, journal, state="swapping")
        self.system.swap(Path(journal["incoming"]), self.install)
        owner.release()
        self.system.on_open = self.new_version()
        self.assertEqual(self.helper("--resume"), 0)
        self.assertEqual(self.journal()["state"], "committed")
        self.assertEqual(ua.installed_version(self.install), N1)
        self.assertEqual(self.journal()["resume_round"], 1)

    def test_a_swap_that_had_not_happened_is_treated_as_before_the_swap(self):
        journal = self.prepared(hand_off=False)
        owner = self.lock()
        ua.write_journal(owner, self.db, journal, state="swapping")
        owner.release()
        self.helper("--resume")
        self.assertEqual(self.journal()["state"], "discarded")
        self.assertEqual(ua.installed_version(self.install), N)

    def test_an_interrupted_rollback_is_continued_before_anything_else(self):
        journal = self.prepared(hand_off=False)
        owner = self.lock()
        ua.write_journal(owner, self.db, journal, state="swapped")
        self.system.swap(Path(journal["incoming"]), self.install)
        journal = ua._previous_path(self.db, journal)
        journal.parent.mkdir(parents=True)
        os.replace(Path(self.journal()["incoming"]), journal)
        self.newer_writes()
        ua.write_journal(owner, self.db, self.journal(), state="rolling_back",
                         previous_app=str(journal), reason="it did not start")
        owner.release()
        self.assertEqual(self.helper("--resume"), 0)
        self.assertEqual(self.journal()["state"], "rolled_back")
        self.assertEqual(ua.installed_version(self.install), N)
        self.assertEqual(self.marker(), "before update")

    def test_a_missing_installed_app_is_restored_from_the_kept_previous_one(self):
        journal = self.prepared(hand_off=False)
        owner = self.lock()
        previous = ua._previous_path(self.db, journal)
        previous.parent.mkdir(parents=True)
        os.replace(self.install, previous)
        ua.write_journal(owner, self.db, journal, state="swapped",
                         previous_app=str(previous))
        owner.release()
        self.helper("--resume")
        self.assertEqual(self.journal()["state"], "rolled_back")
        self.assertEqual(ua.installed_version(self.install), N)


class TestLaunchGate(Base):
    def test_unreadable_or_malformed_install_journals_block_without_changes(self):
        journal = self.prepared(hand_off=False)
        path = ua.journal_file(self.db)
        original = path.read_bytes()
        owner = self.lock()
        try:
            for content in (b"{broken", b"[]", b"{}", b'{"state":"committed"}'):
                with self.subTest(content=content):
                    path.write_bytes(content)
                    with self.assertRaises(ua.InstallError):
                        ua.on_launch(owner, self.db, N, system=self.system)
                    with self.assertRaises(ua.InstallError):
                        ua.plan_attempt(owner, self.db, update_id="u2", from_version=N1,
                                        to_version=N2, install_path=self.install,
                                        incoming=Path(journal["incoming"]),
                                        lane="macos-arm64", channel="internal",
                                        trust_root="t", environment=self.env,
                                        system=self.system)
                    self.assertEqual(path.read_bytes(), content)
            path.write_bytes(original)
            read_text = Path.read_text
            def unreadable(target, *args, **kwargs):
                if target == path:
                    raise PermissionError("unreadable journal")
                return read_text(target, *args, **kwargs)
            with patch.object(Path, "read_text", unreadable):
                with self.assertRaises(ua.InstallError):
                    ua.on_launch(owner, self.db, N, system=self.system)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(self.marker(), "before update")
            self.assertEqual(self.system.opened, [])
        finally:
            owner.release()

    def test_missing_install_journal_with_unfinished_data_blocks_after_swap(self):
        journal = self.prepared(hand_off=False)
        self.system.swap(Path(journal["incoming"]), self.install)
        ua.journal_file(self.db).unlink()
        before = self.data()
        owner = self.lock()
        try:
            with self.assertRaises(ua.InstallError):
                ua.on_launch(owner, self.db, N1, system=self.system)
            with self.assertRaises(ua.InstallError):
                ua.helper_main(["--resume", str(self.db)], system=self.system)
            self.assertFalse(ua.journal_file(self.db).exists())
            self.assertEqual(self.data(), before)
            self.assertEqual(ua.installed_version(self.install), N1)
            self.assertEqual(self.marker(), "before update")
        finally:
            owner.release()

    def test_a_dead_helper_is_resumed_before_the_database_opens_twice_at_most(self):
        self.prepared()
        self.system.stop(self.journal()["helper"])        # the helper died
        for expected in (1, 2):
            owner = self.lock()
            gate = ua.on_launch(owner, self.db, N, bundle=self.install, system=self.system)
            owner.release()
            self.assertFalse(gate.proceed)
            self.assertEqual(self.journal()["resume_count"], expected)
            self.assertEqual(self.system.spawned[-1][1], "--resume")
            self.system.stop(self.journal()["helper"])
        owner = self.lock()
        gate = ua.on_launch(owner, self.db, N, bundle=self.install, system=self.system)
        owner.release()
        self.assertFalse(gate.proceed)
        self.assertEqual(self.journal()["state"], "blocked")
        self.assertIn("stopped safely", gate.message)
        owner = self.lock()
        self.assertFalse(ua.on_launch(owner, self.db, N, system=self.system).proceed)
        owner.release()

    def test_only_the_supervised_version_on_the_same_data_proceeds(self):
        journal = self.prepared()
        owner = self.lock()
        ua.write_journal(owner, self.db, journal, state="relaunching")
        self.assertFalse(ua.on_launch(owner, self.db, N, system=self.system).proceed)
        gate = ua.on_launch(owner, self.db, N1, bundle=self.install, system=self.system)
        self.assertEqual(gate.supervised["update_id"], "u1")
        app = json.loads((ua.attempt_folder(self.db, "u1") / "app.json").read_text())
        self.assertEqual((app["version"], app["bundle"]), (N1, str(self.install)))
        ua.write_journal(owner, self.db, self.journal(), data_root="/somewhere/else")
        self.assertFalse(ua.on_launch(owner, self.db, N1, system=self.system).proceed)
        owner.release()

    def test_a_launch_after_a_finished_attempt_sweeps_its_working_copies(self):
        journal = self.prepared()
        owner = self.lock()
        ua.write_journal(owner, self.db, journal, state="discarded")
        stale = ua.attempt_folder(self.db, "older-attempt") / "Refinix.app"
        stale.mkdir(parents=True)
        (ua.attempt_folder(self.db, "u1") / "helper.log").write_text("kept")
        self.system.stop(journal["helper"])
        ua.on_launch(owner, self.db, N, system=self.system)
        owner.release()
        self.assertFalse(stale.parent.exists())
        self.assertFalse(Path(journal["incoming"]).exists())
        self.assertFalse((ua.attempt_folder(self.db, "u1") / "helper").exists())
        self.assertTrue((ua.attempt_folder(self.db, "u1") / "helper.log").exists())

    def test_a_finished_update_is_reported_once(self):
        self.prepared()
        self.system.on_open = self.new_version(commit=False)
        self.helper()                                      # rolled back
        owner = self.lock()
        gate = ua.on_launch(owner, self.db, N, system=self.system)
        self.assertEqual(gate.notice["kind"], "rolled_back")
        self.assertIsNone(ua.on_launch(owner, self.db, N, system=self.system).notice)
        owner.release()


class TestProcesses(unittest.TestCase):
    def test_the_workspace_lock_is_not_inherited_by_a_started_helper(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "c.sqlite3"
            lock = ownership.WorkspaceLock.for_database(database)
            self.assertIsNone(lock.acquire())
            system = ua.System()
            child = system.spawn([sys.executable, "-c", "import time; time.sleep(5)"], {},
                                 Path(folder) / "helper.log")
            try:
                lock.release()
                again = ownership.WorkspaceLock.for_database(database)
                self.assertIsNone(again.acquire(), "the child kept the lock")
                again.release()
            finally:
                os.kill(child["pid"], 9)
                try:
                    os.waitpid(child["pid"], 0)
                except ChildProcessError:
                    pass

    def test_a_reused_pid_or_other_start_time_is_never_signalled(self):
        system = ua.System()
        me = system.identity()
        self.assertTrue(system.same(me))
        for changed in ({"create_time": me["create_time"] + 5}, {"exe": "/bin/other"},
                        {"pid": 999999}):
            record = {**me, **changed}
            self.assertFalse(system.same(record))
            with patch("psutil.Process.send_signal") as sent:
                self.assertTrue(system.terminate(record, 0.1))
                sent.assert_not_called()

    @unittest.skipUnless(sys.platform == "darwin", "renamex_np is macOS")
    def test_the_swap_exchanges_two_apps_in_one_step(self):
        with tempfile.TemporaryDirectory() as folder:
            a = make_app(Path(folder) / "a" / "Refinix.app", N)
            b = make_app(Path(folder) / "b" / "Refinix.app", N1)
            ua.System().swap(a, b)
            self.assertEqual((ua.installed_version(a), ua.installed_version(b)), (N1, N))


if __name__ == "__main__":
    unittest.main(verbosity=2)
