"""Install and restart on Windows (setup in a job) and Ubuntu (root .deb step).

The same real workspaces, locks and data journals as `test_update_apply`; the
operating system is simulated: a fake job, setup program and uninstall
registry for Windows, and a fake `pkexec` root step for the `.deb` route.
Every crash point between "set aside" and "committed" is driven on cue.
The native pieces are exercised on the real systems separately.

    python3 -m unittest desktop.test_update_methods -v
"""

from __future__ import annotations

import hashlib
import json
import shutil
import unittest
from pathlib import Path

from backend.coordinator import recovery
from desktop import update_apply as ua
from desktop.test_update_apply import N, N1, Base, FakeSystem


class HelperKilled(BaseException):
    """The helper process disappears at this point."""


def make_folder_app(path: Path, version: str, *, complete=True) -> Path:
    (path / "_internal").mkdir(parents=True, exist_ok=True)
    (path / "Refinix.exe").write_bytes(b"MZ")
    (path / "Refinix").write_bytes(b"\x7fELF")
    (path / "_internal" / "refinix-build.json").write_text(json.dumps({"version": version}))
    if complete:
        (path / "_internal" / "complete").write_text(version)
    return path


def folder_version(path: Path) -> str | None:
    try:
        return json.loads((path / "_internal" / "refinix-build.json").read_text())["version"]
    except (OSError, ValueError):
        return None


class MethodSystem(FakeSystem):
    def __init__(self, test):
        super().__init__(test)
        self.registry = {"DisplayVersion": N}
        self.job_error = None
        self.installer = "ok"            # ok | fail | incomplete | killed | hang
        self.jobs_closed = 0
        self.root = {}                   # mode -> answer (dict or callable)
        self.root_calls = []

    # -- windows ------------------------------------------------------------
    def rename(self, source, target):
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(source).rename(target)

    def make_job(self):
        if self.job_error:
            raise OSError(self.job_error)
        system = self

        class Job:
            def close(self):
                system.jobs_closed += 1
        return Job()

    def run_installer(self, setup, app, log, job, record):
        record({"pid": 4242, "job_limits": 0x2000})
        if self.installer == "killed":
            make_folder_app(app, N1)                    # even a new identity file
            raise HelperKilled()
        if self.installer == "fail":
            make_folder_app(app, N1, complete=False)
            return 2
        if self.installer == "hang":
            return None
        make_folder_app(app, N1, complete=self.installer != "incomplete")
        self.registry = {"DisplayVersion": N1}
        return 0

    def registry_snapshot(self):
        return dict(self.registry) if self.registry is not None else None

    def registry_restore(self, snapshot):
        self.registry = dict(snapshot) if snapshot is not None else None

    def windows_problem(self, app, version):
        if folder_version(app) != version:
            return f"identity {folder_version(app)}"
        if not (app / "_internal" / "complete").exists():
            return "a packaged file is missing"
        if self.registry.get("DisplayVersion") != version:
            return "registration"
        return None

    # -- deb -----------------------------------------------------------------
    def privileged(self, mode, folder):
        self.root_calls.append(mode)
        answer = self.root.get(mode, {"error": "not expected", "code": "failed"})
        return answer() if callable(answer) else dict(answer)

    def deb_problem(self, version):
        found = folder_version(self.test.install)
        return None if found == version else f"Ubuntu records {found}"


class MethodBase(Base):
    method = "windows-setup"

    def setUp(self):
        super().setUp()
        base = Path(self.dir.name)
        shutil.rmtree(self.install)
        self.install = make_folder_app(base / "Programs" / "Refinix", N)
        self.system = MethodSystem(self)
        self.me = self.system.start(exe=str(self.install / "Refinix.exe"))
        self.system.current = self.me

    def prepared(self, update_id="u1", to=N1, **kwargs):
        attempt = ua.attempt_folder(self.db, update_id)
        attempt.mkdir(parents=True, exist_ok=True)
        if self.method == "windows-setup":
            incoming = attempt / "setup.exe"
            incoming.write_bytes(b"verified setup bytes")
            extra = {"installer_sha256": hashlib.sha256(incoming.read_bytes()).hexdigest()}
        else:
            incoming = attempt
            extra = {"admission": "abc123", "recovery_copy": str(attempt / "previous.deb")}
        owner = self.lock()
        journal = ua.plan_attempt(owner, self.db, update_id=update_id, from_version=N,
                                  to_version=to, install_path=self.install, incoming=incoming,
                                  lane="windows-x64", channel="beta", trust_root="t",
                                  environment=self.env, system=self.system,
                                  method=self.method, extra=extra)
        recovery.Recovery(owner, self.db).set_aside(
            from_version=N, to_version=to, update_id=update_id,
            data_root=str(self.db.parent))
        journal = ua.mark(owner, self.db, journal, "snapshot_taken")
        journal = ua.hand_off(owner, self.db, journal, bundle=self.install,
                              system=self.system)
        owner.release()
        self.system.stop(self.me)
        return journal

    def opens(self, *, commit=True, write=False, die=False, expect=N1):
        def run(path, environment):
            if folder_version(Path(path)) != expect:
                return
            app = self.system.start(exe=str(Path(path) / "Refinix.exe"))
            saved, self.system.current = self.system.current, app
            owner = self.lock()
            try:
                gate = ua.on_launch(owner, self.db, expect, bundle=Path(path),
                                    system=self.system)
                if gate.supervised is None:
                    self.system.stop(app)
                    return
                if write:
                    self.newer_writes()
                if commit:
                    ua.commit_if_supervised(owner, self.db, gate.supervised)
                if die:
                    self.system.stop(app)
            finally:
                owner.release()
                self.system.current = saved
        return run

    def helper(self, mode="--apply-update"):
        journal = self.journal() or {}
        spawned = journal.get("helper")
        self.system.current = spawned if self.system.same(spawned) else self.system.start(
            exe="/data/updates/install/helper/Refinix/Refinix.exe")
        helper = self.system.current
        try:
            return ua.helper_main([mode, str(self.db)], system=self.system)
        finally:
            self.system.stop(helper)


class TestWindows(MethodBase):
    method = "windows-setup"

    def test_the_setup_runs_in_the_job_and_the_new_version_commits(self):
        self.prepared()
        self.system.on_open = self.opens()
        self.assertEqual(self.helper(), 0)
        journal = self.journal()
        self.assertEqual(journal["state"], "committed")
        self.assertEqual(folder_version(self.install), N1)
        self.assertEqual(journal["installer"]["job_limits"], 0x2000)
        self.assertEqual(self.system.jobs_closed, 1)
        self.assertEqual(folder_version(Path(journal["previous_app"])), N)
        self.assertEqual(self.data()["state"], "committed")

    def test_no_job_means_nothing_is_installed(self):
        self.prepared()
        self.system.job_error = "access denied"
        self.assertEqual(self.helper(), 0)
        self.assertEqual(self.journal()["state"], "discarded")
        self.assertIn("could not be contained", self.journal()["reason"])
        self.assertEqual(folder_version(self.install), N)
        self.assertEqual(self.system.opened[-1][0], str(self.install))

    def test_a_failed_or_unfinished_setup_puts_the_app_and_registration_back(self):
        for outcome, words in (("fail", "exit code 2"), ("hang", "did not finish"),
                               ("incomplete", "not completely installed")):
            with self.subTest(outcome=outcome):
                self.setUp()
                self.prepared()
                self.system.installer = outcome
                self.assertEqual(self.helper(), 0)
                journal = self.journal()
                self.assertEqual(journal["state"], "discarded")
                self.assertIn(words, journal["reason"])
                self.assertEqual(folder_version(self.install), N)
                self.assertEqual(self.system.registry, {"DisplayVersion": N})
                self.assertEqual(self.marker(), "before update")

    def test_a_crash_during_setup_goes_back_even_with_a_new_identity_file(self):
        self.prepared()
        self.system.installer = "killed"
        with self.assertRaises(HelperKilled):
            self.helper()
        self.assertEqual(self.journal()["state"], "installer_running")
        self.assertEqual(folder_version(self.install), N1)        # partial, unproven
        self.assertEqual(self.helper("--resume"), 0)
        self.assertEqual(self.journal()["state"], "discarded")
        self.assertEqual(folder_version(self.install), N)
        self.assertEqual(self.system.registry, {"DisplayVersion": N})
        damaged = list((ua.attempt_folder(self.db, "u1") / "damaged").iterdir())
        self.assertEqual(len(damaged), 1)

    def test_a_verified_install_is_reopened_after_a_crash(self):
        self.prepared()
        original = ua._relaunch_new
        calls = []

        def crash_once(*args, **kwargs):
            if not calls:
                calls.append(1)
                raise HelperKilled()
            return original(*args, **kwargs)
        ua._relaunch_new = crash_once
        self.addCleanup(setattr, ua, "_relaunch_new", original)
        with self.assertRaises(HelperKilled):
            self.helper()
        self.assertEqual(self.journal()["state"], "swapped")
        self.system.on_open = self.opens()
        self.assertEqual(self.helper("--resume"), 0)
        self.assertEqual(self.journal()["state"], "committed")

    def test_a_new_version_that_never_commits_is_rolled_back_with_its_data(self):
        self.prepared()
        self.system.on_open = self.opens(commit=False, write=True, die=True)
        self.assertEqual(self.helper(), 0)
        journal = self.journal()
        self.assertEqual(journal["state"], "rolled_back")
        self.assertEqual(folder_version(self.install), N)
        self.assertEqual(self.system.registry, {"DisplayVersion": N})
        self.assertEqual(self.marker(), "before update")


class TestDeb(MethodBase):
    method = "deb"

    def installed_by_root(self, version):
        def step():
            (self.install / "_internal" / "refinix-build.json").write_text(
                json.dumps({"version": version}))
            return {"state": "to" if version == N1 else "from"}
        return step

    def test_root_installs_the_admitted_package_and_the_new_version_commits(self):
        self.prepared()
        self.system.root["--deb-install"] = self.installed_by_root(N1)
        self.system.on_open = self.opens()
        self.assertEqual(self.helper(), 0)
        self.assertEqual(self.journal()["state"], "committed")
        self.assertEqual(self.system.root_calls, ["--deb-install"])
        self.assertEqual(self.data()["state"], "committed")

    def test_a_refusal_before_any_change_reopens_the_old_version(self):
        self.prepared()
        self.system.root["--deb-install"] = {"error": "Another program is installing "
                                                      "software", "code": "busy"}
        self.assertEqual(self.helper(), 0)
        journal = self.journal()
        self.assertEqual(journal["state"], "discarded")
        self.assertIn("Another program", journal["reason"])
        self.assertEqual(self.system.opened[-1][0], str(self.install))

    def half_installed(self, problem="a file is missing"):
        def step():
            self.installed_by_root(N1)()             # dpkg got part of the way
            return {"state": "incomplete", "problem": problem}
        return step

    def test_an_incomplete_install_goes_back_to_the_recorded_package(self):
        self.prepared()
        self.system.root["--deb-install"] = self.half_installed()
        self.system.root["--deb-rollback"] = self.installed_by_root(N)
        self.assertEqual(self.helper(), 0)
        self.assertEqual(self.journal()["state"], "discarded")
        self.assertEqual(self.system.root_calls, ["--deb-install", "--deb-rollback"])

    def test_a_new_version_that_never_commits_is_rolled_back_with_its_data(self):
        self.prepared()
        self.system.root["--deb-install"] = self.installed_by_root(N1)
        self.system.root["--deb-rollback"] = self.installed_by_root(N)
        self.system.on_open = self.opens(commit=False, write=True, die=True)
        self.assertEqual(self.helper(), 0)
        self.assertEqual(self.journal()["state"], "rolled_back")
        self.assertEqual(folder_version(self.install), N)
        self.assertEqual(self.marker(), "before update")

    def test_an_interrupted_install_is_finished_by_root_then_committed(self):
        self.prepared()

        def killed():
            raise HelperKilled()
        self.system.root["--deb-install"] = killed
        with self.assertRaises(HelperKilled):
            self.helper()
        self.assertEqual(self.journal()["state"], "deb_installing")
        self.system.root["--deb-recover"] = self.installed_by_root(N1)
        self.system.on_open = self.opens()
        self.assertEqual(self.helper("--resume"), 0)
        self.assertEqual(self.journal()["state"], "committed")

    def test_a_dismissed_password_prompt_during_recovery_changes_nothing(self):
        self.prepared()

        def killed():
            raise HelperKilled()
        self.system.root["--deb-install"] = killed
        with self.assertRaises(HelperKilled):
            self.helper()
        self.system.root["--deb-recover"] = {"error": "no password", "code": "not_authorised"}
        self.assertEqual(self.helper("--resume"), 1)
        self.assertEqual(self.journal()["state"], "deb_installing")
        self.assertTrue(self.system.told)

    def test_a_failed_rollback_blocks_with_the_recovery_package_named(self):
        self.prepared()
        self.system.root["--deb-install"] = self.half_installed("broken")
        self.system.root["--deb-rollback"] = {
            "state": "blocked", "problem": "dpkg failed",
            "recovery_package": "/var/lib/refinix/packages/refinix_0.1.0~1.1_amd64.deb",
            "recovery_sha256": "ab" * 32}
        self.assertEqual(self.helper(), 2)
        journal = self.journal()
        self.assertEqual(journal["state"], "blocked")
        self.assertIn("refinix_0.1.0~1.1_amd64.deb", journal["reason"])
        self.assertIn("App Center", journal["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
