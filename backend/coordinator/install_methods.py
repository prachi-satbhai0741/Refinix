"""How this copy of Refinix was installed, and how an update is prepared for it.

One method per install format, chosen from the build's lane and how the
running copy was installed — never from what an offer says:

    mac-app        macOS `Refinix.app` in Applications: the verified ZIP is
                   expanded beside it and checked (`app_archive`); the helper
                   swaps it in atomically.
    windows-setup  Windows per-user install in `%LOCALAPPDATA%\\Programs\\Refinix`:
                   the verified setup program is copied into the attempt
                   folder; the helper runs it silently inside a kill-on-close
                   job (`desktop/update_windows.py`).
    deb            Ubuntu `.deb` in `/opt/refinix`: "Download and prepare" ends
                   with one administrator prompt in which root copies the
                   package, its recovery package and the signed metadata into
                   root-owned storage and authenticates the copies, including
                   expiry (`desktop/deb_root.py`). Installing, resuming and
                   going back each ask again.

Anything else (an AppImage, a source checkout, an unknown layout) is
`unsupported`, and Settings says why.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Where each method's program lives once installed.
DEB_PREFIX = Path("/opt/refinix")
DEB_PROGRAM = DEB_PREFIX / "Refinix"
POLKIT_POLICY = Path("/usr/share/polkit-1/actions/com.refinix.desktop.policy")
PKEXEC = Path("/usr/bin/pkexec")
# pkexec: 126 = the person dismissed or failed the prompt; 127 = not authorised.
PKEXEC_REFUSED = (126, 127)
ADMISSION_SECONDS = 600


class MethodError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def detect_format(lane: str | None, *, environ=None, executable=None,
                  dpkg_version=None) -> str | None:
    """The install format of the running copy, from how it was installed."""
    environ = os.environ if environ is None else environ
    if lane == "macos-arm64":
        return "zip"
    if lane == "windows-x64":
        return "exe"
    if lane == "linux-x64":
        if environ.get("APPIMAGE"):
            return "appimage"
        program = Path(executable or sys.executable)
        try:
            program = program.resolve()
        except OSError:
            return None
        if program == DEB_PROGRAM and (dpkg_version or installed_deb_version)() is not None:
            return "deb"
    return None


def installed_deb_version(run=subprocess.run) -> str | None:
    """dpkg's record of the installed `refinix` package, or None."""
    try:
        result = run(["dpkg-query", "-W", "-f=${Status}|${Version}", "refinix"],
                     capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    status, _, version = (result.stdout or "").partition("|")
    if result.returncode != 0 or status.strip() != "install ok installed":
        return None
    return version.strip() or None


class Method:
    name = "unsupported"

    def __init__(self, service):
        self.service = service

    def location(self) -> tuple[Path | None, str | None]:
        return None, "Installing updates from inside Refinix is not available for " \
                     "this kind of installation; install the newer version yourself."

    def prepare(self, verified: dict, update_id: str, destination: Path) -> dict:
        raise MethodError("install_unavailable", self.location()[1] or "unavailable")

    def recheck(self, ready: dict, verified: dict) -> None:
        raise MethodError("install_unavailable", self.location()[1] or "unavailable")


class MacApp(Method):
    name = "mac-app"

    def location(self):
        service = self.service
        bundle = service._bundle
        if bundle is None:
            return None, "Refinix is not running from an installed app."
        text = str(bundle)
        if "/AppTranslocation/" in text:
            return None, ("macOS is running Refinix from a temporary copy. Move Refinix "
                          "to Applications, open it from there and try again.")
        allowed = [Path("/Applications/Refinix.app"),
                   Path.home() / "Applications" / "Refinix.app"]
        test_root = service._environ.get(service.TEST_INSTALL_ROOT)
        if test_root and (service.identity or {}).get("channel") == "internal":
            allowed.append(Path(test_root) / "Refinix.app")
        if Path(os.path.realpath(bundle)) not in {Path(os.path.realpath(p)) for p in allowed}:
            return None, ("Refinix can update itself only when it is in Applications. "
                          f"This copy is at {bundle}.")
        if not os.access(bundle.parent, os.W_OK):
            return None, f"Refinix cannot write to {bundle.parent}."
        try:
            if os.stat(bundle.parent).st_dev != os.stat(service.data_root).st_dev:
                return None, ("Refinix's data and the app are on different disks, so the "
                              "app cannot be replaced safely in one step.")
        except OSError as exc:
            return None, f"The install location cannot be checked: {exc}"
        return bundle, None

    def _verify(self, app: Path, verified: dict) -> dict:
        from backend.coordinator import app_archive
        service = self.service
        kwargs = {} if service._codesign is None else {"codesign": service._codesign}
        try:
            return app_archive.verify_bundle(
                app, version=verified["version"], lane=service.lane,
                channel=(service.identity or {}).get("channel"),
                trust_roots=service.accepted_roots(verified),
                publisher=service.expected_publisher(), **kwargs)
        except app_archive.ArchiveError as exc:
            raise MethodError(exc.code, str(exc)) from exc

    def prepare(self, verified, update_id, destination):
        from backend.coordinator import app_archive
        from backend.coordinator.updates import (INSTALL_MARGIN, _database_bytes,
                                                 _tree_bytes)
        install_path, _ = self.location()
        package = Path(verified["package"])
        try:
            listing = app_archive.inspect(package)
        except app_archive.ArchiveError as exc:
            raise MethodError(exc.code, str(exc)) from exc
        needed = listing.total_bytes + _tree_bytes(install_path) + _database_bytes(
            self.service.data_root) + INSTALL_MARGIN
        free = shutil.disk_usage(self.service.home).free
        if free < needed:
            raise MethodError("disk", f"Installing needs about {needed // 1024 ** 2} MB "
                                      f"free; {free // 1024 ** 2} MB is available.")
        try:
            app = app_archive.extract(package, listing, destination)
            app_archive.check_tree(destination, listing)
        except app_archive.ArchiveError as exc:
            raise MethodError(exc.code, str(exc)) from exc
        identity = self._verify(app, verified)
        if int(identity.get("schema_version") or 0) != int(verified["schema_version"] or 0):
            raise MethodError("mismatch", "The app inside the package disagrees with "
                                          "the signed offer about its data format.")
        return {"incoming": str(app), "build_set": identity.get("build_set"),
                "trust_root": identity.get("trust_root")}

    def recheck(self, ready, verified):
        self._verify(Path(ready["incoming"]), verified)


def windows_install_root(environ=None) -> Path | None:
    environ = os.environ if environ is None else environ
    local = environ.get("LOCALAPPDATA")
    return Path(local) / "Programs" / "Refinix" if local else None


class WindowsSetup(Method):
    name = "windows-setup"

    def location(self):
        service = self.service
        expected = windows_install_root(service._environ)
        running = service._program.parent if service._program else None
        if expected is None or running is None:
            return None, "Refinix is not running from its per-user installation."
        if os.path.normcase(os.path.realpath(running)) != \
                os.path.normcase(os.path.realpath(expected)):
            return None, ("Refinix can update itself only when it was installed for this "
                          f"account by its setup program, in {expected}. This copy runs "
                          f"from {running}.")
        if not os.access(expected.parent, os.W_OK):
            return None, f"Refinix cannot write to {expected.parent}."
        try:
            if os.path.splitdrive(os.path.realpath(expected))[0].lower() != \
                    os.path.splitdrive(os.path.realpath(service.data_root))[0].lower():
                return None, ("Refinix's data and the app are on different drives, so the "
                              "app cannot be set aside safely in one step.")
        except OSError as exc:
            return None, f"The install location cannot be checked: {exc}"
        return expected, None

    def prepare(self, verified, update_id, destination):
        destination.mkdir(parents=True, exist_ok=False, mode=0o700)
        setup = destination / "setup.exe"
        shutil.copyfile(verified["package"], setup)
        if _sha256(setup) != verified["sha256"]:
            raise MethodError("changed", "The setup program changed while it was copied.")
        publisher = self.service.expected_publisher()
        if publisher:
            problem = self.service._authenticode(setup, publisher)
            if problem:
                raise MethodError("signature", f"The setup program's signature does not "
                                               f"verify: {problem}")
        return {"incoming": str(setup), "build_set": None,
                "trust_root": None, "installer_sha256": verified["sha256"]}

    def recheck(self, ready, verified):
        incoming = Path(ready["incoming"])
        if not incoming.is_file() or _sha256(incoming) != verified["sha256"]:
            raise MethodError("changed", "The prepared setup program changed; cancel and "
                                         "prepare the update again.")


def authenticode(path: Path, publisher: str, run=subprocess.run) -> str | None:
    """Why `path` is not validly Authenticode-signed by `publisher`; None when it is."""
    script = ("$s = Get-AuthenticodeSignature -LiteralPath $env:REFINIX_SIGNATURE_PATH; "
              "$subject = if ($s.SignerCertificate) { $s.SignerCertificate.Subject } "
              "else { '' }; Write-Output ($s.Status.ToString() + '|' + $subject)")
    env = dict(os.environ, REFINIX_SIGNATURE_PATH=str(Path(path).resolve()))
    try:
        result = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                     capture_output=True, text=True, env=env, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"the signature check could not run: {exc}"
    status, _, subject = (result.stdout or "").strip().partition("|")
    if result.returncode != 0 or status != "Valid":
        return status or (result.stderr or "").strip()[-200:] or "not signed"
    if subject != publisher:
        return f"signed by {subject!r}, not {publisher!r}"
    return None


# --------------------------------------------------------------------------
# Ubuntu .deb: the person's side of the privileged admission
# --------------------------------------------------------------------------

# The fixed names root reads from an admission request folder; nothing else in
# it is ever opened. Metadata keeps the feed's own versioned names.
REQUEST_FILE = "request.json"
PACKAGE_FILE = "package.deb"
RECOVERY_FILE = "recovery.deb"


def _private_dir(path: Path, parents: bool = False) -> None:
    """A folder only its owner can write, whatever the umask (Ubuntu gives
    accounts 002); root refuses a request folder anyone else could change."""
    if parents:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)


def write_admission_request(folder: Path, verified: dict, evidence: Path) -> Path:
    """The folder root copies from: the signed metadata as the feed names it,
    the offer pointer, the package and the installed version's package."""
    folder = Path(folder)
    _private_dir(folder, parents=True)
    metadata = folder / "metadata"
    _private_dir(metadata)
    for path in sorted((evidence / "root").glob("*.root.json")):
        shutil.copyfile(path, metadata / path.name)
    roles = {}
    for role in ("timestamp", "snapshot", "targets"):
        data = (evidence / f"{role}.json").read_bytes()
        version = json.loads(data)["signed"]["version"]
        roles[role] = version
        name = "timestamp.json" if role == "timestamp" else f"{version}.{role}.json"
        (metadata / name).write_bytes(data)
    record = json.loads((evidence / "record.json").read_text(encoding="utf-8"))
    pointer = record["latest_target"]
    latest = (evidence / "latest.json").read_bytes()
    target_dir = folder
    for part in ("targets", *Path(pointer).parent.parts):
        target_dir = target_dir / part
        _private_dir(target_dir)
    (target_dir / f"{hashlib.sha256(latest).hexdigest()}.{Path(pointer).name}") \
        .write_bytes(latest)
    shutil.copyfile(verified["package"], folder / PACKAGE_FILE)
    recovery = verified.get("recovery")
    if recovery:
        shutil.copyfile(recovery["package"], folder / RECOVERY_FILE)
    request = {"pointer": pointer, "target": verified["target"],
               "recovery_target": recovery["target"] if recovery else None,
               "versions": roles}
    (folder / REQUEST_FILE).write_text(json.dumps(request, indent=2, sort_keys=True),
                                       encoding="utf-8")
    return folder


def run_privileged(mode: str, folder: Path, run=subprocess.run) -> dict:
    """One administrator prompt: `pkexec /opt/refinix/Refinix <mode> <folder>`."""
    if mode not in ("--deb-admit", "--deb-install", "--deb-recover", "--deb-rollback"):
        raise MethodError("mode", f"unknown privileged step {mode}")
    try:
        result = run([str(PKEXEC), str(DEB_PROGRAM), mode, str(folder)],
                     capture_output=True, text=True, timeout=ADMISSION_SECONDS,
                     check=False, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        raise MethodError("privileged", f"The administrator step could not start: {exc}") \
            from exc
    if result.returncode in PKEXEC_REFUSED:
        raise MethodError("not_authorised", "The administrator password was not given, "
                                            "so nothing was changed.")
    try:
        answer = json.loads((result.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        answer = None
    if not isinstance(answer, dict):
        raise MethodError("privileged", "The administrator step did not finish: "
                          + ((result.stderr or "").strip()[-400:] or f"exit {result.returncode}"))
    if result.returncode != 0 or answer.get("error"):
        raise MethodError(answer.get("code") or "privileged",
                          answer.get("error") or f"exit {result.returncode}")
    return answer


class DebPackage(Method):
    name = "deb"

    def location(self):
        service = self.service
        if service._program is None or Path(os.path.realpath(service._program)) != DEB_PROGRAM:
            return None, "Refinix is not running from its installed package in /opt/refinix."
        installed = service._dpkg_version()
        expected = service.debian_version()
        if installed is None or installed != expected:
            return None, ("Ubuntu's package records do not match this copy of Refinix "
                          f"({installed or 'not installed'} vs {expected}); reinstall it "
                          "from the website, then update.")
        for path, what in ((PKEXEC, "pkexec"), (POLKIT_POLICY, "Refinix's polkit policy")):
            if not path.is_file():
                return None, f"{what} is missing ({path}); reinstall Refinix's package."
        return DEB_PREFIX, None

    def prepare(self, verified, update_id, destination):
        if not verified.get("recovery"):
            raise MethodError("no_recovery", "This update can't be installed safely without "
                                             "your current version's package. Connect once "
                                             "and download again, or use a bundle that "
                                             "includes it.")
        evidence = Path(verified["package"]).parent / "evidence"
        folder = write_admission_request(destination, verified, evidence)
        answer = self.service._privileged("--deb-admit", folder)
        admitted = answer.get("admission")
        if not isinstance(admitted, str) or not admitted.isalnum():
            raise MethodError("privileged", "The administrator step returned no admission.")
        # The unprivileged side keeps the manual recovery copy; root never
        # writes the person's data.
        keep = self.service.data_root / "updates" / "recovery-packages"
        keep.mkdir(parents=True, exist_ok=True, mode=0o700)
        recovery = verified["recovery"]
        copy = keep / Path(recovery["target"]).name
        if not copy.is_file() or _sha256(copy) != recovery["sha256"]:
            shutil.copyfile(recovery["package"], copy)
        (keep / f"{copy.name}.sha256").write_text(f"{recovery['sha256']}  {copy.name}\n",
                                                  encoding="utf-8")
        return {"incoming": str(folder), "admission": admitted, "build_set": None,
                "trust_root": None, "recovery_copy": str(copy)}

    def recheck(self, ready, verified):
        if not Path(ready["incoming"]).is_dir() or not ready.get("admission"):
            raise MethodError("changed", "The prepared update is incomplete; cancel and "
                                         "prepare it again.")


METHODS = {"zip": MacApp, "exe": WindowsSetup, "deb": DebPackage}


def for_service(service) -> Method:
    cls = METHODS.get(service.install_format() or "")
    return cls(service) if cls else Method(service)
