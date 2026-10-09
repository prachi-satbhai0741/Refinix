"""The root `.deb` step: request validation, TUF admission, dpkg/apt rules.

A real Beta feed and a real staged download (the publisher and client from
`backend.coordinator.test_updates_beta`) feed a real admission request
(`install_methods.write_admission_request`). `deb_root` then runs in-process
with a test Context: not as root, with `/opt/refinix` and `/var/lib/refinix`
in a temporary folder and dpkg, dpkg-query, dpkg-deb and apt-get answered by a
small simulation of their documented output. The same steps run natively on
Ubuntu with the real tools (Docker/VM qualification).

    python3 -m unittest desktop.test_deb_root -v
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.coordinator import install_methods, release
from backend.coordinator.test_updates_beta import PASS, Base as FeedBase
from desktop import deb_root, install_check
from scripts import update_repository as repository

OLD, NEW, NEWER = "0.1.0-preview.1", "0.1.0-preview.2", "0.1.0-preview.3"


class FakeDpkg:
    """dpkg's database for a few packages, and the tools' documented output."""

    def __init__(self, prefix: Path):
        self.prefix = prefix
        self.status = {"refinix": ["install ok installed", release.parse(OLD).debian()],
                       "desktop-file-utils": ["install ok installed", "0.27"],
                       "unrelated": ["install ok installed", "1.0"]}
        self.audit = ""
        self.extra_plan = []
        self.fields = {}
        self.fail_install = False
        self.calls = []

    def version_of(self, deb: Path) -> str:
        """The Debian version a stand-in package carries (its name, from its bytes)."""
        found = re.search(r"refinix_(\S+)_amd64\.deb", deb.read_text()).group(1)
        return found if "~" in found else release.parse(found).debian()

    def label_of(self, debian: str) -> str:
        core, _, rest = debian.partition("~")
        rank, _, number = rest.partition(".")
        return f"{core}-{ {'1': 'preview', '2': 'beta'}[rank] }.{number}"

    def install(self, deb: Path) -> int:
        version = self.version_of(deb)
        if self.fail_install:
            self.status["refinix"] = ["install reinstreq half-installed", version]
            return 1
        write_install(self.prefix, self.label_of(version))
        self.status["refinix"] = ["install ok installed", version]
        return 0

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        out, code = "", 0
        if argv[0] == "dpkg-query":
            if argv[-1] == "refinix":
                state, version = self.status["refinix"]
                out = f"{state}\t{version}"
            else:
                out = "".join(f"{name}\t{state}\n" for name, (state, _v) in self.status.items())
        elif argv[:2] == ["dpkg-deb", "-f"]:
            fields = {"Package": "refinix", "Version": self.version_of(Path(argv[2])),
                      "Architecture": "amd64", "Maintainer": "Refinix",
                      "Depends": "libgtk-3-0t64 | libgtk-3-0", **self.fields}
            out = "".join(f"{k}: {v}\n" for k, v in fields.items())
        elif argv[:2] == ["dpkg-deb", "-c"]:
            out = ("drwxr-xr-x root/root 0 2026-10-08 00:00 ./usr/share/applications/\n"
                   "-rw-r--r-- root/root 1 2026-10-08 00:00 "
                   "./usr/share/applications/refinix.desktop\n")
        elif argv[0] == "apt-get":
            version = self.version_of(Path(argv[-1]))
            lines = [f"Inst refinix [{self.status['refinix'][1]}] ({version} "
                     f"local-deb [amd64])", f"Conf refinix ({version} local-deb [amd64])"]
            out = "\n".join(self.extra_plan + lines) + "\n"
        elif argv[:2] == ["dpkg", "--audit"]:
            out = self.audit
        elif argv[:2] == ["dpkg", "-i"]:
            assert kwargs["env"].get("DPKG_FRONTEND_LOCKED") == "1"
            code = self.install(Path(argv[2]))
        elif argv[:2] == ["dpkg", "--configure"]:
            self.status["refinix"][0] = "install ok installed"
        elif argv[:2] == ["dpkg", "--triggers-only"]:
            for name in argv[2:]:
                self.status[name][0] = "install ok installed"
        else:
            raise AssertionError(f"unexpected command {argv}")
        return subprocess.CompletedProcess(argv, code, out, "")


def write_install(prefix: Path, version: str, root: bytes | None = None) -> None:
    internal = prefix / "_internal"
    internal.mkdir(parents=True, exist_ok=True)
    label = release.parse(version)
    (prefix / "Refinix").write_bytes(b"program " + version.encode())
    (internal / "refinix-build.json").write_text(json.dumps({
        "version": version, "channel": "beta", "maturity": label.maturity,
        "lane": "linux-x64"}))
    if root is not None:
        (internal / "refinix-update-root.json").write_bytes(root)
    (internal / "refinix-files.json").unlink(missing_ok=True)
    (internal / "refinix-files.json").write_text(json.dumps(
        install_check.file_listing(prefix)))


class Base(FeedBase):
    def setUp(self):
        super().setUp()
        base = Path(os.path.realpath(self.dir.name))
        self.home = base / "home"
        self.home.mkdir()
        self.prefix = base / "opt" / "refinix"
        write_install(self.prefix, OLD, root=self.root)
        self.dpkg = FakeDpkg(self.prefix)
        self.ctx = deb_root.Context(
            prefix=self.prefix, state=base / "var" / "lib" / "refinix",
            dpkg_lock=base / "lock-frontend", triggers_index=base / "triggers-File",
            environ={"PKEXEC_UID": str(os.getuid())}, geteuid=lambda: 0,
            home_of=lambda uid: self.home, run=self.dpkg, executable=self.prefix / "Refinix",
            lock_seconds=1)
        (base / "triggers-File").write_text("/usr/share/applications desktop-file-utils\n"
                                            "/usr/share/icons/hicolor hicolor-icon-theme\n")
        # Debian package bytes the fake tools can read their version from.
        self.release(OLD)
        self.release(NEW)

    def package(self, version, lane="linux-x64", fmt="deb", *, content=None, build=None,
                **overrides):
        content = content or f"{release.asset_name(version, lane, fmt)}".encode()
        return super().package(version, lane, fmt, content=content, build=build, **overrides)

    def request(self, name="request", installed=OLD):
        # Accounts on Ubuntu write group-writable files by default (umask 002);
        # the request must still be private to its owner.
        previous = os.umask(0o002)
        self.addCleanup(os.umask, previous)
        service = self.staged(self.service(installed))
        verified = service.admit_staged()
        folder = self.home / name
        evidence = Path(verified["package"]).parent / "evidence"
        install_methods.write_admission_request(folder, verified, evidence)
        return folder

    def step(self, mode, folder):
        return self.run_step(mode, str(folder))

    def run_step(self, mode, folder_text):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = deb_root.main([mode, folder_text], self.ctx)
        answer = json.loads(out.getvalue().strip().splitlines()[-1])
        return code, answer


class TestAdmitAndInstall(Base):
    def test_an_admitted_package_installs_with_one_plan_and_checks_out(self):
        folder = self.request()
        code, answer = self.step("--deb-admit", folder)
        self.assertEqual((code, answer["to_version"]), (0, NEW), answer)
        record_folder = self.ctx.updates / answer["admission"]
        self.assertEqual(stat.S_IMODE(record_folder.stat().st_mode), 0o700)
        kept = sorted(p.name for p in self.ctx.packages.iterdir())
        self.assertEqual(kept, sorted(release.asset_name(v, "linux-x64", "deb")
                                      for v in (OLD, NEW)))
        for path in self.ctx.packages.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
        code, answer = self.step("--deb-install", folder)
        self.assertEqual((code, answer["state"]), (0, "to"), answer)
        self.assertEqual(install_check.installed_identity(self.prefix)["version"], NEW)
        record = json.loads((record_folder / "record.json").read_text())
        self.assertEqual(record["triggers"], ["desktop-file-utils"])
        self.assertEqual(record["state"], "installed")
        # The same admission is never installed twice.
        self.assertEqual(self.step("--deb-install", folder)[1]["code"], "state")

    def test_only_root_through_pkexec_from_the_installed_program(self):
        folder = self.request()
        for change in ({"geteuid": lambda: 501}, {"environ": {}},
                       {"environ": {"PKEXEC_UID": "0"}},
                       {"executable": self.prefix.parent / "elsewhere"}):
            with self.subTest(change=list(change)):
                saved = {k: getattr(self.ctx, k) for k in change}
                for key, value in change.items():
                    setattr(self.ctx, key, value)
                try:
                    code, answer = self.step("--deb-admit", folder)
                finally:
                    for key, value in saved.items():
                        setattr(self.ctx, key, value)
                self.assertEqual(code, 3)
                self.assertIn(answer["code"], ("not_root", "not_pkexec", "not_installed"))

    def test_unsafe_request_folders_are_refused(self):
        folder = self.request()
        link = self.home / "link"
        link.symlink_to(folder)
        outside = Path(os.path.realpath(self.dir.name)) / "outside"
        outside.mkdir()
        for text in (str(link), str(outside), "relative/path", str(folder) + "/../request",
                     str(self.home)):
            with self.subTest(text=text):
                code, answer = self.run_step("--deb-admit", text)
                self.assertEqual((code, answer["code"]), (3, "bad_request"))
        folder.chmod(0o770)
        self.assertEqual(self.step("--deb-admit", folder)[1]["code"], "bad_request")
        folder.chmod(0o700)
        (folder / "package.deb").unlink()
        (folder / "package.deb").symlink_to(folder / "recovery.deb")
        self.assertEqual(self.step("--deb-admit", folder)[1]["code"], "bad_request")

    def test_a_swapped_package_never_authenticates(self):
        folder = self.request()
        (folder / "package.deb").write_bytes(b"refinix_0.1.0~1.2_amd64.deb evil")
        code, answer = self.step("--deb-admit", folder)
        self.assertEqual((code, answer["code"]), (3, "evidence"))
        self.assertEqual(list(self.ctx.updates.iterdir()), [])

    def test_root_copies_are_rechecked_before_installing(self):
        folder = self.request()
        _code, answer = self.step("--deb-admit", folder)
        copy = self.ctx.updates / answer["admission"] / "package.deb"
        copy.write_bytes(copy.read_bytes() + b" changed")
        self.assertEqual(self.step("--deb-install", folder)[1]["code"], "evidence")
        self.assertEqual(install_check.installed_identity(self.prefix)["version"], OLD)

    def test_an_admitted_update_installs_later_without_judging_expiry(self):
        folder = self.request()
        _code, answer = self.step("--deb-admit", folder)
        self.assertNotIn("error", answer)
        # Installing re-checks root's copies offline: the TUF client (and its
        # clock) is not used again, so an expired timestamp cannot strand it.
        import tuf.ngclient

        class NoClient:
            def __init__(self, *args, **kwargs):
                raise AssertionError("the full client must not run after admission")
        original = tuf.ngclient.Updater
        tuf.ngclient.Updater = NoClient
        self.addCleanup(setattr, tuf.ngclient, "Updater", original)
        self.assertEqual(self.step("--deb-install", folder)[1]["state"], "to")

    def test_a_new_request_with_expired_metadata_is_refused(self):
        folder = self.request()
        repository.stage(self.keys, self.feed, maturity="preview",
                         packages=[self.package("0.1.0-preview.3", build=40)],
                         passphrases=PASS)
        repository.advance(self.keys, self.feed, passphrases=PASS,
                           now=datetime.now(timezone.utc) - timedelta(days=30))
        for path in (self.feed / "metadata").glob("*.json"):
            (folder / "metadata" / path.name).write_bytes(path.read_bytes())
        code, answer = self.step("--deb-admit", folder)
        self.assertEqual((code, answer["code"]), (3, "expired"), answer)
        self.assertEqual(list(self.ctx.updates.iterdir()), [])

    def test_unsupported_control_fields_are_refused(self):
        folder = self.request()
        self.dpkg.fields = {"Pre-Depends": "something"}
        code, answer = self.step("--deb-admit", folder)
        self.assertEqual((code, answer["code"]), (3, "package"))

    def test_a_plan_touching_another_package_installs_nothing(self):
        folder = self.request()
        self.step("--deb-admit", folder)
        self.dpkg.extra_plan = ["Remv unrelated [1.0]"]
        code, answer = self.step("--deb-install", folder)
        self.assertEqual((code, answer["code"]), (3, "plan"))
        self.assertFalse(any(c[:2] == ["dpkg", "-i"] for c in self.dpkg.calls))

    def test_unfinished_package_work_is_refused_before_installing(self):
        folder = self.request()
        self.step("--deb-admit", folder)
        self.dpkg.audit = "The following packages are only half configured: unrelated\n"
        self.assertEqual(self.step("--deb-install", folder)[1]["code"], "unfinished")
        self.dpkg.audit = ""
        self.dpkg.status["desktop-file-utils"][0] = "install ok triggers-pending"
        self.assertEqual(self.step("--deb-install", folder)[1]["code"], "unfinished")

    def test_a_held_package_lock_changes_nothing(self):
        import sys
        folder = self.request()
        self.step("--deb-admit", folder)
        # Record locks belong to a process, so another process holds it.
        holder = subprocess.Popen(
            [sys.executable, "-c", "import fcntl, os, sys, time; "
             "fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o640); "
             "fcntl.lockf(fd, fcntl.LOCK_EX); print('held', flush=True); time.sleep(60)",
             str(self.ctx.dpkg_lock)], stdout=subprocess.PIPE, text=True)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        self.assertEqual(self.step("--deb-install", folder)[1]["code"], "busy")
        self.assertFalse(any(c[:2] == ["dpkg", "-i"] for c in self.dpkg.calls))


class TestRecovery(Base):
    def admitted(self):
        folder = self.request()
        self.step("--deb-admit", folder)
        return folder

    def test_a_half_installed_package_is_repaired_with_the_same_copy(self):
        folder = self.admitted()
        self.dpkg.fail_install = True
        self.assertEqual(self.step("--deb-install", folder)[1]["state"], "incomplete")
        self.dpkg.fail_install = False
        code, answer = self.step("--deb-recover", folder)
        self.assertEqual((code, answer["state"]), (0, "to"), answer)

    def test_recovery_refuses_when_an_unrelated_package_is_unfinished(self):
        folder = self.admitted()
        self.dpkg.fail_install = True
        self.step("--deb-install", folder)
        self.dpkg.status["unrelated"][0] = "install ok half-configured"
        code, answer = self.step("--deb-recover", folder)
        self.assertEqual((code, answer["code"]), (3, "unfinished"))
        self.assertIn("unrelated", answer["error"])

    def test_recorded_triggers_are_processed_then_checked(self):
        folder = self.admitted()
        self.step("--deb-install", folder)
        self.dpkg.status["desktop-file-utils"][0] = "install ok triggers-pending"
        code, answer = self.step("--deb-recover", folder)
        self.assertEqual(answer["state"], "to")
        self.assertIn(["dpkg", "--triggers-only", "desktop-file-utils"], self.dpkg.calls)

    def test_rollback_reinstalls_exactly_the_recorded_previous_package(self):
        folder = self.admitted()
        self.step("--deb-install", folder)
        code, answer = self.step("--deb-rollback", folder)
        self.assertEqual((code, answer["state"]), (0, "from"), answer)
        self.assertEqual(install_check.installed_identity(self.prefix)["version"], OLD)

    def test_nothing_to_recover_without_an_install_attempt(self):
        folder = self.admitted()
        self.assertEqual(self.step("--deb-rollback", folder)[1]["code"], "state")
        other = self.home / "other"
        other.mkdir(mode=0o700)
        self.assertEqual(self.step("--deb-recover", other)[1]["code"], "not_admitted")


def dpkg_installs(calls, name: str) -> list:
    return [c for c in calls if c[:2] == ["dpkg", "-i"] and c[2].endswith(name)]


class TestCurrentAttempt(Base):
    """One current attempt for the whole installation; stale requests change nothing."""

    def install(self, name, installed=OLD):
        folder = self.request(name, installed=installed)
        code, answer = self.step("--deb-admit", folder)
        self.assertEqual(code, 0, answer)
        code, answer = self.step("--deb-install", folder)
        self.assertEqual((code, answer["state"]), (0, "to"), answer)
        return folder

    def test_an_old_request_after_two_updates_changes_nothing(self):
        first = self.install("a-to-b")
        self.release(NEWER)
        self.install("b-to-c", installed=NEW)
        self.assertEqual(install_check.installed_identity(self.prefix)["version"], NEWER)
        self.dpkg.calls.clear()
        for mode in ("--deb-rollback", "--deb-recover", "--deb-install"):
            with self.subTest(mode=mode):
                code, answer = self.step(mode, first)
                self.assertEqual((code, answer["code"]), (3, "superseded"), answer)
        self.assertEqual(dpkg_installs(self.dpkg.calls, ".deb"), [])
        self.assertEqual(install_check.installed_identity(self.prefix)["version"], NEWER)
        first_record = deb_root.find_record(self.ctx, str(first), os.getuid())[1]
        self.assertEqual(first_record["state"], "concluded")

    def test_the_current_attempt_still_rolls_back_with_its_exact_copy(self):
        self.install("a-to-b")
        self.release(NEWER)
        second = self.install("b-to-c", installed=NEW)
        code, answer = self.step("--deb-rollback", second)
        self.assertEqual((code, answer["state"]), (0, "from"), answer)
        self.assertEqual(install_check.installed_identity(self.prefix)["version"], NEW)
        self.assertTrue(dpkg_installs(self.dpkg.calls, "recovery.deb"))

    def test_an_old_request_never_configures_a_version_it_did_not_know(self):
        first = self.install("a-to-b")
        # An unrelated, newer Refinix left unpacked by something else.
        self.dpkg.status["refinix"] = ["install ok unpacked",
                                       release.parse(NEWER).debian()]
        self.dpkg.calls.clear()
        code, answer = self.step("--deb-recover", first)
        self.assertEqual((code, answer["code"]), (3, "superseded"), answer)
        self.assertFalse(any(c[:2] == ["dpkg", "--configure"] for c in self.dpkg.calls))
        self.assertEqual(dpkg_installs(self.dpkg.calls, ".deb"), [])

    def test_going_back_outside_refinix_never_revives_the_old_approval(self):
        first = self.install("a-to-b")
        # The person reinstalls the earlier version with App Center.
        write_install(self.prefix, OLD, root=self.root)
        self.dpkg.status["refinix"] = ["install ok installed", release.parse(OLD).debian()]
        self.release(NEWER)
        fresh = self.request("a-to-c", installed=OLD)
        code, answer = self.step("--deb-admit", fresh)
        self.assertEqual((code, answer["to_version"]), (0, NEWER), answer)
        self.dpkg.calls.clear()
        for mode in ("--deb-install", "--deb-recover", "--deb-rollback"):
            with self.subTest(mode=mode):
                self.assertEqual(self.step(mode, first)[1]["code"], "superseded")
        self.assertEqual(dpkg_installs(self.dpkg.calls, ".deb"), [])
        self.assertEqual(self.step("--deb-install", fresh)[1]["state"], "to")

    def test_an_unfinished_attempt_blocks_every_other_preparation(self):
        folder = self.request("a-to-b")
        self.step("--deb-admit", folder)
        self.dpkg.fail_install = True
        self.assertEqual(self.step("--deb-install", folder)[1]["state"], "incomplete")
        self.dpkg.fail_install = False
        self.dpkg.calls.clear()
        # Another account asks: refused before its request is even read.
        other_home = Path(os.path.realpath(self.dir.name)) / "other-home"
        other_home.mkdir()
        self.ctx.environ = {"PKEXEC_UID": str(os.getuid() + 1)}
        self.ctx.home_of = lambda uid: other_home
        code, answer = self.run_step("--deb-admit", str(other_home / "request"))
        self.assertEqual((code, answer["code"]), (3, "busy_other_update"), answer)
        self.assertIn("the account that started it", answer["error"])
        # Nor can it act on the first account's attempt.
        self.assertEqual(self.step("--deb-rollback", folder)[1]["code"], "not_admitted")
        self.assertEqual(dpkg_installs(self.dpkg.calls, ".deb"), [])
        # The same account preparing again is refused too, and its recovery
        # copies are still there for the unfinished attempt.
        self.ctx.environ = {"PKEXEC_UID": str(os.getuid())}
        self.ctx.home_of = lambda uid: self.home
        again = self.request("again")
        self.assertEqual(self.step("--deb-admit", again)[1]["code"], "busy_other_update")
        kept = sorted(p.name for p in self.ctx.packages.iterdir())
        self.assertEqual(kept, sorted(release.asset_name(v, "linux-x64", "deb")
                                      for v in (OLD, NEW)))
        # Its owner recovers it, and then a new preparation is possible.
        self.assertEqual(self.step("--deb-recover", folder)[1]["state"], "to")

    def test_an_interrupted_admission_is_never_used_and_is_cleared(self):
        self.ctx.updates.mkdir(parents=True, mode=0o700)
        leftover = self.ctx.updates / "00aa00aa00aa00aa"
        leftover.mkdir(mode=0o700)
        (leftover / "package.deb").write_bytes(b"half copied")
        folder = self.request("a-to-b")
        code, answer = self.step("--deb-admit", folder)
        self.assertEqual(code, 0, answer)
        self.assertFalse(leftover.exists())
        current = json.loads((self.ctx.state / "current.json").read_text())
        self.assertEqual(current["admission"], answer["admission"])

    def test_root_steps_wait_for_each_other(self):
        folder = self.request("a-to-b")
        with deb_root.RootLock(self.ctx):
            import sys
            holder = subprocess.Popen(
                [sys.executable, "-c", "import fcntl, os, sys, time; "
                 "fd = os.open(sys.argv[1], os.O_RDWR); fcntl.flock(fd, fcntl.LOCK_EX); "
                 "print('held', flush=True); time.sleep(60)",
                 str(self.ctx.state / "root.lock")], stdout=subprocess.PIPE, text=True)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        code, answer = self.step("--deb-admit", folder)
        self.assertEqual((code, answer["code"]), (3, "busy"), answer)
        self.assertFalse((self.ctx.state / "current.json").exists())


class TestRollbackDirection(Base):
    """An interrupted rollback is finished as a rollback, never towards the new version."""

    def installed_then_rolling_back(self, status_word: str):
        folder = self.request()
        self.step("--deb-admit", folder)
        self.assertEqual(self.step("--deb-install", folder)[1]["state"], "to")
        record_folder, record = deb_root.find_record(self.ctx, str(folder), os.getuid())
        deb_root._write_record(record_folder, {**record, "state": "rolling_back",
                                               "direction": "rollback"})
        # The rollback was stopped part way through putting OLD back.
        if status_word == "unpacked":
            write_install(self.prefix, OLD, root=self.root)
            self.dpkg.status["refinix"] = ["install ok unpacked",
                                           release.parse(OLD).debian()]
        else:
            self.dpkg.status["refinix"] = ["install reinstreq half-installed",
                                           release.parse(OLD).debian()]
        self.dpkg.calls.clear()
        return folder

    def test_a_rollback_killed_while_unpacking_finishes_going_back(self):
        folder = self.installed_then_rolling_back("half-installed")
        code, answer = self.step("--deb-recover", folder)
        self.assertEqual((code, answer["state"]), (0, "from"), answer)
        self.assertTrue(dpkg_installs(self.dpkg.calls, "recovery.deb"))
        self.assertFalse(dpkg_installs(self.dpkg.calls, "package.deb"))
        self.assertEqual(install_check.installed_identity(self.prefix)["version"], OLD)
        record = deb_root.find_record(self.ctx, str(folder), os.getuid())[1]
        self.assertEqual((record["state"], record["direction"]), ("rolled_back", "rollback"))

    def test_a_rollback_stopped_before_configuring_is_configured(self):
        folder = self.installed_then_rolling_back("unpacked")
        code, answer = self.step("--deb-recover", folder)
        self.assertEqual((code, answer["state"]), (0, "from"), answer)
        self.assertIn(["dpkg", "--configure", "refinix"], self.dpkg.calls)
        self.assertFalse(dpkg_installs(self.dpkg.calls, "package.deb"))

    def test_a_legacy_record_without_a_direction_keeps_going_back(self):
        folder = self.installed_then_rolling_back("half-installed")
        record_folder, record = deb_root.find_record(self.ctx, str(folder), os.getuid())
        record.pop("direction")
        deb_root._write_record(record_folder, record)
        self.assertEqual(self.step("--deb-recover", folder)[1]["state"], "from")
        self.assertFalse(dpkg_installs(self.dpkg.calls, "package.deb"))


class TestTrustContinuity(Base):
    """Root's offline re-check reaches the newest trusted root or refuses."""

    def admitted_then_rotated(self, replace=()):
        folder = self.request()
        self.assertEqual(self.step("--deb-admit", folder)[0], 0)
        new_keys = Path(os.path.realpath(self.dir.name)) / "new-keys"
        for _ in range(2):
            repository.rotate_root(self.keys, self.feed, passphrases=PASS,
                                   new_keys_dir=new_keys if replace else None,
                                   replace=replace, new_passphrases=PASS,
                                   check_location=False)
            replace = ()
        history = self.ctx.trust / "root_history"
        history.mkdir(parents=True, exist_ok=True)
        (history / "2.root.json").unlink(missing_ok=True)
        (history / "3.root.json").write_bytes(
            (self.feed / "metadata" / "3.root.json").read_bytes())
        (self.ctx.trust / "root.json").unlink()
        (self.ctx.trust / "root.json").write_bytes(
            (self.feed / "metadata" / "3.root.json").read_bytes())
        self.dpkg.calls.clear()
        return folder

    def test_a_missing_link_refuses_before_any_package_change(self):
        folder = self.admitted_then_rotated()
        code, answer = self.step("--deb-install", folder)
        self.assertEqual((code, answer["code"]), (3, "evidence"), answer)
        self.assertIn("root 2", answer["error"])
        self.assertEqual(dpkg_installs(self.dpkg.calls, ".deb"), [])

    def test_a_complete_chain_installs(self):
        folder = self.admitted_then_rotated()
        (self.ctx.trust / "root_history" / "2.root.json").write_bytes(
            (self.feed / "metadata" / "2.root.json").read_bytes())
        self.assertEqual(self.step("--deb-install", folder)[1]["state"], "to")

    def test_signatures_of_a_revoked_key_fail(self):
        folder = self.admitted_then_rotated(replace=("targets",))
        (self.ctx.trust / "root_history" / "2.root.json").write_bytes(
            (self.feed / "metadata" / "2.root.json").read_bytes())
        code, answer = self.step("--deb-install", folder)
        self.assertEqual((code, answer["code"]), (3, "evidence"), answer)
        self.assertEqual(dpkg_installs(self.dpkg.calls, ".deb"), [])

    def test_a_damaged_trust_record_refuses(self):
        folder = self.request()
        self.step("--deb-admit", folder)
        (self.ctx.trust / "root.json").unlink()
        code, answer = self.step("--deb-install", folder)
        self.assertEqual((code, answer["code"]), (3, "evidence"), answer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
