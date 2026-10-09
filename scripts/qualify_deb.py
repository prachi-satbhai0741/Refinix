#!/usr/bin/env python3
"""Native qualification of the Ubuntu `.deb` update rules, with the real dpkg and APT.

Runs only as root on a throwaway Ubuntu 24.04 machine (a container, a VM or a
hosted runner) and refuses anywhere else (REFINIX_QUALIFY_DISPOSABLE=1 must be
set). It builds small stand-in `refinix` packages that carry what the real
one carries for updates (the program path, the build identity, the update
trust root, the shipped file list, a desktop entry that sets off a trigger),
signs them into a throwaway Beta feed (throwaway keys), stages them through
the real update client as a test account, and drives `desktop/deb_root.py`
exactly as pkexec would start it — with the real dpkg, APT and lock.

Checked (plan v4.3 B3 and B4):

    plan        an update's unpack + configure plan (Inst + Conf refinix) is
                accepted; a same-version `--reinstall` simulation is accepted;
                a plan needing another package is refused before any change
    install     admitted package installs; the tree checks out
    lock        a held dpkg front-end lock changes nothing
    audit       unfinished work in an unrelated package refuses an install
    recover     dpkg killed while unpacking -> same-copy repair completes;
                unpacked-only -> `dpkg --configure refinix` completes;
                the same recovery is refused while an unrelated package is
                half-configured
    rollback    the recorded previous package is reinstalled exactly
    real        (with --real) the built package's control fields, files,
                polkit policy, that its root entry refuses without pkexec, and
                that the installed app starts as an ordinary account on
                scratch data only (scripts/qualify_package_launch.py, xvfb)

    sudo REFINIX_QUALIFY_DISPOSABLE=1 python3 scripts/qualify_deb.py \\
        [--real out/refinix_0.1.0-beta.1_amd64.deb] --report report.json

With --real the report is a release-bytes record bound to that exact package
(scripts/qualification_record.py): its name, size, SHA-256 and embedded
build identity. Without --real it is a fixture report, which the release
tooling never accepts for publication. Exit status 0 only when all passed.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import platform
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.coordinator import release  # noqa: E402

QA_USER = "refinixqa"
PREFIX = Path("/opt/refinix")
STATE = Path("/var/lib/refinix")
PASSPHRASES = {role: f"qualification {role} key" for role in
               ("root", "targets", "snapshot", "timestamp")}
SITE = "https://qualify.invalid/updates/beta/"
RELEASES = "https://qualify.invalid/releases/"
OLD, NEW, NEWER = "0.1.0-preview.1", "0.1.0-preview.2", "0.1.0-preview.3"


def run(argv, **kwargs):
    return subprocess.run(argv, capture_output=True, text=True, check=False, **kwargs)


class Report:
    def __init__(self):
        self.checks = []

    def record(self, name, passed, observed):
        self.checks.append({"check": name, "passed": bool(passed), "observed": observed})
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {observed}", flush=True)

    @property
    def ok(self):
        return all(c["passed"] for c in self.checks)


# --------------------------------------------------------------------------
# Stand-in packages
# --------------------------------------------------------------------------

def make_deb(out: Path, version: str, root_bytes: bytes, *, big_mb: int = 0,
             depends: str | None = None, name: str = "refinix",
             postinst: str | None = None) -> Path:
    from desktop import install_check
    label = release.parse(version) if name == "refinix" else None
    tree = out / f"tree-{name}-{version}"
    shutil.rmtree(tree, ignore_errors=True)
    if name == "refinix":
        opt = tree / "opt" / "refinix"
        internal = opt / "_internal"
        internal.mkdir(parents=True)
        (opt / "Refinix").write_text("#!/bin/sh\necho stand-in Refinix\n")
        (opt / "Refinix").chmod(0o755)
        (internal / "refinix-build.json").write_text(json.dumps({
            "version": version, "channel": "beta", "maturity": label.maturity,
            "lane": "linux-x64"}))
        (internal / "refinix-update-root.json").write_bytes(root_bytes)
        if big_mb:
            with open(internal / "payload.bin", "wb") as handle:
                for _ in range(big_mb):
                    handle.write(os.urandom(1024 * 1024))
        (internal / "refinix-files.json").write_text(json.dumps(
            install_check.file_listing(opt)))
        apps = tree / "usr" / "share" / "applications"
        apps.mkdir(parents=True)
        (apps / "refinix.desktop").write_text("[Desktop Entry]\nType=Application\n"
                                              "Name=Refinix\nExec=refinix\n")
        version_text = label.debian()
    else:
        (tree / "usr" / "share" / "doc" / name).mkdir(parents=True)
        (tree / "usr" / "share" / "doc" / name / "README").write_text("qualification\n")
        version_text = version
    (tree / "DEBIAN").mkdir()
    control = [f"Package: {name}", f"Version: {version_text}", "Architecture: amd64",
               "Maintainer: Refinix qualification", "Description: stand-in package"]
    if depends:
        control.insert(4, f"Depends: {depends}")
    (tree / "DEBIAN" / "control").write_text("\n".join(control) + "\n")
    if postinst:
        (tree / "DEBIAN" / "postinst").write_text(postinst)
        (tree / "DEBIAN" / "postinst").chmod(0o755)
    path = out / (release.asset_name(version, "linux-x64", "deb") if name == "refinix"
                  else f"{name}_{version}_amd64.deb")
    result = run(["dpkg-deb", "-Znone", "--build", "--root-owner-group", str(tree), str(path)])
    if result.returncode:
        raise SystemExit(result.stderr)
    return path


# --------------------------------------------------------------------------
# A throwaway feed and the real client, as the test account
# --------------------------------------------------------------------------

class LocalNetwork:
    def __init__(self, feed: Path, assets: Path):
        self.feed, self.assets = feed, assets

    def request(self, method, url, preload_content=False, redirect=False):
        class Response:
            def __init__(self, status, body=b""):
                self.status, self.body, self.headers = status, body, {}

            def stream(self, size):
                for start in range(0, len(self.body), size):
                    yield self.body[start:start + size]

            def release_conn(self):
                pass
        for prefix, folder in ((SITE, self.feed), (RELEASES, self.assets)):
            if url.startswith(prefix):
                path = folder / url[len(prefix):]
                if not path.is_file():
                    path = folder / Path(url[len(prefix):]).name
                return Response(200, path.read_bytes()) if path.is_file() else Response(404)
        return Response(404)


class Feed:
    def __init__(self, work: Path):
        from scripts import update_repository as repository
        self.repository = repository
        self.keys, self.dir, self.assets = work / "keys", work / "feed", work / "assets"
        self.assets.mkdir(parents=True)
        repository.beta_init(self.keys, self.dir, passphrases=PASSPHRASES,
                             check_location=False)
        self.root = (self.dir / "metadata" / "1.root.json").read_bytes()
        self.build = 0

    def publish(self, path: Path, version: str):
        import hashlib
        self.build += 1
        target = self.assets / path.name
        if path != target:
            shutil.copyfile(path, target)
        package = {"path": str(target), "lane": "linux-x64", "version": version,
                   "channel": "beta", "maturity": "preview", "build_set": "qa",
                   "min_os": "24.04", "schema_version": 1, "engine_release": "qa",
                   "public_build": self.build, "signing": "unsigned",
                   "install_capability": "preview-test",
                   "trust_root": hashlib.sha256(self.root).hexdigest(),
                   "shared_snapshot_digest": "qa"}
        self.repository.stage(self.keys, self.dir, maturity="preview", packages=[package],
                              passphrases=PASSPHRASES)
        self.repository.advance(self.keys, self.dir, passphrases=PASSPHRASES)


def qa_account(name: str = QA_USER) -> pwd.struct_passwd:
    try:
        return pwd.getpwnam(name)
    except KeyError:
        result = run(["useradd", "--create-home", "--shell", "/bin/sh", name])
        if result.returncode:
            raise SystemExit(f"could not create the test account: {result.stderr}")
        return pwd.getpwnam(name)


def stage_request(feed: Feed, account, installed: str, name: str) -> Path:
    """The real client stages the newest offer and writes the root request."""
    import hashlib
    from backend.coordinator import install_methods, updates
    home = Path(account.pw_dir)
    data = home / f"data-{name}"
    shutil.rmtree(data, ignore_errors=True)
    identity = {"version": installed, "channel": "beta", "maturity": "preview",
                "lane": "linux-x64", "install_capability": "preview-test",
                "trust_root": hashlib.sha256(feed.root).hexdigest()}
    service = updates.UpdateService(
        data, identity=identity, trust_root=feed.root,
        feed={"metadata_url": SITE + "metadata/", "targets_url": SITE + "targets/",
              "packages_url": RELEASES, "package_hosts": []},
        schema_version=1, os_version="24.04", pool=LocalNetwork(feed.dir, feed.assets),
        install_format="deb", platform="linux")
    service.check()
    service.start_download()
    service.wait(120)
    verified = service.admit_staged()
    folder = home / name
    shutil.rmtree(folder, ignore_errors=True)
    install_methods.write_admission_request(folder, verified,
                                            Path(verified["package"]).parent / "evidence")
    run(["chown", "-R", f"{account.pw_uid}:{account.pw_gid}", str(home)])
    for path in [home, *home.rglob("*")]:
        if path.is_dir():
            path.chmod(0o700)
    return folder


def step(account, mode: str, folder: Path) -> dict:
    from desktop import deb_root
    ctx = deb_root.Context(environ={"PKEXEC_UID": str(account.pw_uid)},
                           executable=PREFIX / "Refinix", lock_seconds=5)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        deb_root.main([mode, str(folder)], ctx)
    return json.loads(out.getvalue().strip().splitlines()[-1])


def status(package="refinix") -> str:
    return run(["dpkg-query", "-W", "-f=${Status}|${Version}", package]).stdout.strip()


def reset(old_deb: Path):
    run(["dpkg", "--purge", "refinix", "refinix-qa-unrelated"])
    shutil.rmtree(STATE, ignore_errors=True)
    result = run(["dpkg", "-i", str(old_deb)])
    if result.returncode:
        raise SystemExit(f"could not install the starting package: {result.stderr}")


# --------------------------------------------------------------------------
# The checks
# --------------------------------------------------------------------------

def qualify(report: Report, work: Path):
    from desktop import deb_root
    account = qa_account()
    feed = Feed(work)
    debs = work / "debs"
    debs.mkdir()
    old = make_deb(debs, OLD, feed.root)
    new = make_deb(debs, NEW, feed.root, big_mb=256)
    feed.publish(old, OLD)
    feed.publish(new, NEW)
    reset(old)
    ctx = deb_root.Context(lock_seconds=5)
    report.record("trigger packages found from dpkg's index",
                  True, deb_root.trigger_packages(ctx, new))

    # plan: Inst + Conf accepted; --reinstall accepted; a needed download refused
    try:
        deb_root.simulate(ctx, new, NEW)
        report.record("update plan is exactly Inst+Conf refinix", True, "accepted")
    except deb_root.RootError as exc:
        report.record("update plan is exactly Inst+Conf refinix", False, str(exc))
    try:
        deb_root.simulate(ctx, old, OLD, reinstall=True)
        report.record("same-version --reinstall plan accepted", True, "accepted")
    except deb_root.RootError as exc:
        report.record("same-version --reinstall plan accepted", False, str(exc))
    (work / "other").mkdir()
    needing = make_deb(work / "other", NEWER, feed.root, depends="refinix-qa-not-installed")
    try:
        deb_root.simulate(ctx, needing, NEWER)
        report.record("plan needing another package is refused", False, "accepted")
    except deb_root.RootError as exc:
        report.record("plan needing another package is refused", exc.code in (
            "prerequisites", "plan"), f"{exc.code}: {str(exc)[:160]}")

    # install, then rollback to the recorded previous package
    folder = stage_request(feed, account, OLD, "request-install")
    admitted = step(account, "--deb-admit", folder)
    report.record("admission authenticates root's copies", "admission" in admitted, admitted)
    installed = step(account, "--deb-install", folder)
    report.record("admitted package installs and checks out",
                  installed.get("state") == "to", {"answer": installed, "dpkg": status()})
    back = step(account, "--deb-rollback", folder)
    report.record("rollback reinstalls the recorded previous package",
                  back.get("state") == "from", {"answer": back, "dpkg": status()})

    # lock held by another program
    reset(old)
    folder = stage_request(feed, account, OLD, "request-lock")
    step(account, "--deb-admit", folder)
    holder = subprocess.Popen([sys.executable, "-c",
                               "import fcntl, os, time; fd = os.open('/var/lib/dpkg/"
                               "lock-frontend', os.O_RDWR); fcntl.lockf(fd, fcntl.LOCK_EX);"
                               " print('held', flush=True); time.sleep(60)"],
                              stdout=subprocess.PIPE, text=True)
    holder.stdout.readline()
    busy = step(account, "--deb-install", folder)
    holder.kill()
    holder.wait()
    report.record("held dpkg lock changes nothing", busy.get("code") == "busy"
                  and status().endswith(release.parse(OLD).debian()), busy)

    # unfinished unrelated work refuses an install
    unrelated = make_deb(work / "other", "1.0", b"", name="refinix-qa-unrelated",
                         postinst="#!/bin/sh\nexit 1\n")
    run(["dpkg", "-i", str(unrelated)])
    report.record("unrelated package left half-configured", "half-configured" in
                  status("refinix-qa-unrelated"), status("refinix-qa-unrelated"))
    refused = step(account, "--deb-install", folder)
    report.record("install refused while unrelated work is unfinished",
                  refused.get("code") == "unfinished", refused)
    run(["dpkg", "--purge", "refinix-qa-unrelated"])

    # dpkg killed while unpacking -> same-copy repair
    reset(old)
    folder = stage_request(feed, account, OLD, "request-kill")
    admission = step(account, "--deb-admit", folder)
    record_dir = STATE / "update" / admission["admission"]
    record = json.loads((record_dir / "record.json").read_text())
    record["state"] = "installing"
    (record_dir / "record.json").write_text(json.dumps(record))
    process = subprocess.Popen(["dpkg", "-i", str(record_dir / "package.deb")],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        if "Unpacking" in line or "Preparing to unpack" in line:
            time.sleep(0.15)
            os.kill(process.pid, signal.SIGKILL)
            break
    process.wait()
    interrupted = status()
    words = interrupted.split("|")[0].split()
    report.record("dpkg killed while unpacking leaves unfinished work",
                  bool(words) and (words[-1] != "installed" or "reinstreq" in words),
                  interrupted)
    recovered = step(account, "--deb-recover", folder)
    report.record("recovery after a killed unpack completes",
                  recovered.get("state") in ("to", "from"), {"answer": recovered,
                                                             "dpkg": status()})

    # unpacked only -> configure; refused while unrelated is half-configured
    reset(old)
    folder = stage_request(feed, account, OLD, "request-unpacked")
    admission = step(account, "--deb-admit", folder)
    record_dir = STATE / "update" / admission["admission"]
    record = json.loads((record_dir / "record.json").read_text())
    record["state"] = "installing"
    (record_dir / "record.json").write_text(json.dumps(record))
    run(["dpkg", "--unpack", str(record_dir / "package.deb")])
    run(["dpkg", "-i", str(unrelated)])
    blocked = step(account, "--deb-recover", folder)
    report.record("recovery refused while an unrelated package is half-configured",
                  blocked.get("code") == "unfinished", blocked)
    run(["dpkg", "--purge", "refinix-qa-unrelated"])
    configured = step(account, "--deb-recover", folder)
    report.record("unpacked package is configured by recovery",
                  configured.get("state") == "to", {"answer": configured, "dpkg": status()})
    run(["dpkg", "--purge", "refinix"])
    qualify_attempts(report, work, feed, old, new, account)


def kill_during_unpack(deb: Path) -> str:
    """Start `dpkg -i deb` and kill it while it unpacks; dpkg's status after."""
    process = subprocess.Popen(["dpkg", "-i", str(deb)], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        if "Unpacking" in line or "Preparing to unpack" in line:
            time.sleep(0.15)
            os.kill(process.pid, signal.SIGKILL)
            break
    process.wait()
    return status()


def set_record(admission: dict, **fields) -> Path:
    record_dir = STATE / "update" / admission["admission"]
    record = json.loads((record_dir / "record.json").read_text())
    record.update(fields)
    (record_dir / "record.json").write_text(json.dumps(record))
    return record_dir


def unfinished(state: str) -> bool:
    words = state.split("|")[0].split()
    return bool(words) and (words[-1] != "installed" or "reinstreq" in words)


def qualify_attempts(report: Report, work: Path, feed: "Feed", old: Path, new: Path,
                     account):
    """One current attempt for the whole installation (review F3/F4), real dpkg."""
    debs = work / "debs-attempts"
    debs.mkdir()
    # A -> B -> C, then the old A -> B request changes nothing.
    reset(old)
    first = stage_request(feed, account, OLD, "request-a-b")
    step(account, "--deb-admit", first)
    installed_b = step(account, "--deb-install", first)
    # Large, so a kill lands while dpkg is still unpacking it.
    newer = make_deb(debs, NEWER, feed.root, big_mb=256)
    feed.publish(newer, NEWER)
    second = stage_request(feed, account, NEW, "request-b-c")
    step(account, "--deb-admit", second)
    installed_c = step(account, "--deb-install", second)
    before = status()
    stale = {mode: step(account, mode, first)
             for mode in ("--deb-rollback", "--deb-recover", "--deb-install")}
    report.record("an old request after two updates changes nothing",
                  installed_b.get("state") == "to" and installed_c.get("state") == "to"
                  and all(a.get("code") == "superseded" for a in stale.values())
                  and status() == before and before.endswith(release.parse(NEWER).debian()),
                  {"answers": stale, "dpkg": status()})
    current = step(account, "--deb-rollback", second)
    report.record("the current attempt still rolls back with its exact copy",
                  current.get("state") == "from"
                  and status().endswith(release.parse(NEW).debian()),
                  {"answer": current, "dpkg": status()})

    # A rollback killed while unpacking finishes going back, never forward.
    # Starting from NEW (large), so the package being put back is large too.
    reset(new)
    third = stage_request(feed, account, NEW, "request-rollback")
    admitted = step(account, "--deb-admit", third)
    step(account, "--deb-install", third)
    record_dir = set_record(admitted, state="rolling_back", direction="rollback")
    interrupted = kill_during_unpack(record_dir / "recovery.deb")
    recovered = step(account, "--deb-recover", third)
    from desktop import install_check
    problem = install_check.completeness_problem(PREFIX, NEW)
    report.record("a rollback killed while unpacking finishes going back",
                  unfinished(interrupted) and recovered.get("state") == "from"
                  and problem is None and status().endswith(release.parse(NEW).debian()),
                  {"interrupted": interrupted, "answer": recovered, "dpkg": status(),
                   "tree": problem})

    # An unfinished attempt blocks every other account's preparation.
    reset(old)
    other = qa_account(QA_USER + "2")
    fourth = stage_request(feed, account, OLD, "request-unfinished")
    admitted = step(account, "--deb-admit", fourth)
    record_dir = set_record(admitted, state="installing", direction="install")
    interrupted = kill_during_unpack(record_dir / "package.deb")
    elsewhere = stage_request(feed, other, OLD, "request-other-account")
    refused = step(other, "--deb-admit", elsewhere)
    report.record("an unfinished attempt blocks another account's preparation",
                  unfinished(interrupted) and refused.get("code") == "busy_other_update"
                  and status() == interrupted,
                  {"answer": refused, "dpkg": status()})
    recovered = step(account, "--deb-recover", fourth)
    lifted = step(other, "--deb-admit", elsewhere)
    report.record("its own account recovers it, and the block lifts",
                  recovered.get("state") in ("to", "from")
                  and lifted.get("code") != "busy_other_update",
                  {"recovered": recovered, "other_account_then": lifted})
    run(["dpkg", "--purge", "refinix"])


def qualify_real(report: Report, deb: Path):
    from desktop import deb_root
    from scripts import qualify_package_launch
    fields = run(["dpkg-deb", "-f", str(deb)]).stdout
    names = {line.split(":", 1)[0] for line in fields.splitlines()
             if line and not line.startswith(" ")}
    report.record("real package carries only supported control fields",
                  names <= set(deb_root.ALLOWED_FIELDS), sorted(names))
    listing = run(["dpkg-deb", "-c", str(deb)]).stdout
    for path in ("./opt/refinix/Refinix", "./opt/refinix/_internal/refinix-build.json",
                 "./opt/refinix/_internal/refinix-files.json",
                 "./usr/share/polkit-1/actions/com.refinix.desktop.policy",
                 "./usr/share/applications/refinix.desktop"):
        report.record(f"real package ships {path}", path in listing, path in listing)
    installed = run(["apt-get", "install", "-y", "--no-install-recommends", str(deb.resolve())])
    report.record("real package installs with its dependencies", installed.returncode == 0,
                  installed.stdout[-400:] + installed.stderr[-400:])
    if installed.returncode == 0:
        from desktop import install_check
        identity = install_check.installed_identity(PREFIX) or {}
        problem = install_check.completeness_problem(PREFIX, identity.get("version", "?"))
        report.record("installed tree matches its file list", problem is None, problem)
        refused = run([str(PREFIX / "Refinix"), "--deb-admit", "/tmp/nothing"],
                      env={"PATH": "/usr/bin:/bin"})
        answer = (refused.stdout.strip().splitlines() or ["{}"])[-1]
        report.record("root entry refuses without pkexec",
                      refused.returncode != 0 and "pkexec" in answer, answer)
        account = qa_account()
        scratch = Path(account.pw_dir) / "launch-scratch"
        shutil.rmtree(scratch, ignore_errors=True)
        prefix = ["runuser", "-u", QA_USER, "--", "env", f"REFINIX_DATA_ROOT={scratch}",
                  f"HOME={account.pw_dir}", "xvfb-run", "-a", "dbus-run-session", "--"]
        launched = qualify_package_launch.launch_check(
            PREFIX / "Refinix", scratch, prefix=prefix,
            owner=(account.pw_uid, account.pw_gid),
            expect_version=identity.get("version"))
        report.record(launched["check"], launched["passed"], launched["observed"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--real", type=Path, help="the built refinix .deb to inspect too")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--commit-tested", default=os.environ.get("GITHUB_SHA"),
                        help="the source commit this qualification ran from")
    args = parser.parse_args(argv)
    if os.environ.get("REFINIX_QUALIFY_DISPOSABLE") != "1" or os.geteuid() != 0:
        print("refused: run as root on a throwaway machine with "
              "REFINIX_QUALIFY_DISPOSABLE=1", file=sys.stderr)
        return 2
    if platform.machine() not in ("x86_64", "AMD64"):
        print("refused: the Refinix package is amd64", file=sys.stderr)
        return 2
    report = Report()
    host = {"os_release": Path("/etc/os-release").read_text(errors="replace"),
            "kernel": platform.release(), "dpkg": run(["dpkg", "--version"]).stdout
            .splitlines()[0], "apt": run(["apt-get", "--version"]).stdout.splitlines()[0]}
    with tempfile.TemporaryDirectory(prefix="refinix-qualify-") as directory:
        try:
            qualify(report, Path(directory))
        except Exception as exc:                           # noqa: BLE001
            report.record("qualification ran to the end", False,
                          f"{type(exc).__name__}: {exc}")
        if args.real:
            qualify_real(report, args.real)
    from scripts import qualification_record
    if args.real:
        record = qualification_record.build(
            lane="linux-x64", host=host,
            packages=[qualification_record.package_entry(args.real)],
            checks=report.checks, commit_tested=args.commit_tested)
        ok = record["passed"]
    else:
        # Stand-in packages only: evidence about the update rules, never about
        # a package that could be published.
        record = {"kind": "fixture", "host": host, "checks": report.checks,
                  "commit_tested": args.commit_tested, "passed": report.ok}
        ok = report.ok
    args.report.write_text(json.dumps(record, indent=2) + "\n")
    print(f"{'all passed' if ok else 'FAILED'} — {args.report}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
