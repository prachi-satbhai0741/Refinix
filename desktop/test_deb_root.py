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

OLD, NEW = "0.1.0-preview.1", "0.1.0-preview.2"


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
        return re.search(r"refinix_(\S+)_amd64\.deb", deb.read_text()).group(1)

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

    def request(self, name="request"):
        # Accounts on Ubuntu write group-writable files by default (umask 002);
        # the request must still be private to its owner.
        previous = os.umask(0o002)
        self.addCleanup(os.umask, previous)
        service = self.staged(self.service(OLD))
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
