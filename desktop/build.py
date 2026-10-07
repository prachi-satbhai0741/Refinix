"""Build one Refinix internal test package on this computer's native OS.

The single build driver for every lane (macOS arm64, Windows x64, Ubuntu x86_64),
used the same way on a native host and in `.github/workflows/package.yml`:

    python desktop/build.py --version 0.1.0-internal.1 --build-set bs-0001 --out out/
    python desktop/build.py ... --plan          # digests and reuse decision only

What it guarantees:

* **One application.** Sources are staged by `packaging_plan.stage_application_sources`,
  the same boundary the macOS py2app build has always used; the three lanes
  share one source snapshot digest for the application, frontend and build code.
* **Pinned inputs.** Dependencies come from hash-pinned locks; the engine from
  `desktop/engine/engine-pins.json`; AppImage tooling from `packaging-tools.json`.
  Cached downloads are re-verified by hash before use. Built packages are never
  cached or restored.
* **No relabelling.** If the input identity (snapshot, locks, engine, interpreter,
  toolchain, runner image) matches a recorded build set *and* the retained
  artifact still exists with the recorded SHA-256, the build is skipped with
  "reuse"; otherwise a new labelled build is produced (or a rebuild reason is
  required).
* **Two identity records.** `refinix-build.json` is embedded in the package and
  never contains the package's own hash. After packaging, `<artifact>.sha256`
  and `<artifact>.manifest.json` record the final bytes, and the embedded
  identity is extracted from the finished artifact and compared.

Internal packages are unsigned test evidence. Signing, notarisation and
publication are separate, user-authorised steps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform as _platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

DESKTOP = Path(__file__).resolve().parent
REPO = DESKTOP.parent
sys.path.insert(0, str(DESKTOP))
sys.path.insert(0, str(DESKTOP / "engine"))
import packaging_plan  # noqa: E402
import fetch as engine_fetch  # noqa: E402

IDENTITY_NAME = "refinix-build.json"
# Names the application looks for (backend/coordinator/updates.py).
UPDATE_ROOT_NAME = "refinix-update-root.json"
UPDATE_FEED_NAME = "refinix-update-feed.json"


def schema_version() -> int:
    """The workspace data format this source writes, read without importing it."""
    text = (REPO / "backend" / "coordinator" / "db.py").read_text(encoding="utf-8")
    match = re.search(r"^SCHEMA_VERSION\s*=\s*(\d+)", text, re.M)
    if not match:
        raise BuildError("SCHEMA_VERSION not found in backend/coordinator/db.py")
    return int(match.group(1))


def update_files(trust_root: Path | None, feed: Path | None) -> dict:
    """Validate the optional update trust root and feed; return their identities."""
    found = {}
    for label, path, name in (("trust_root", trust_root, UPDATE_ROOT_NAME),
                              ("update_feed", feed, UPDATE_FEED_NAME)):
        if path is None:
            found[label] = None
            continue
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BuildError(f"{label}: {path} is not readable JSON: {exc}") from exc
        if label == "trust_root" and (data.get("signed") or {}).get("_type") != "root":
            raise BuildError(f"{path} is not TUF root metadata")
        if label == "update_feed" and not all(
                str(data.get(k, "")).startswith("https://")
                for k in ("metadata_url", "targets_url")):
            raise BuildError(f"{path} must name HTTPS metadata_url and targets_url")
        found[label] = {"path": str(path.resolve()), "name": name,
                        "sha256": sha256_file(path)}
    return found
TOOLS = DESKTOP / "packaging-tools.json"
CHUNK = 4 * 1024 * 1024


class BuildError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def detect_lane(platform: str | None = None, machine: str | None = None) -> str:
    platform = sys.platform if platform is None else platform
    machine = (_platform.machine() if machine is None else machine).lower()
    machine = {"amd64": "x86_64", "aarch64": "arm64"}.get(machine, machine)
    for key, lane in packaging_plan.LANES.items():
        prefix, arch = lane.host
        if platform.startswith(prefix) and machine == arch:
            return key
    raise BuildError(f"no native build lane for {platform}/{machine}; PyInstaller "
                     "and py2app cannot cross-build another OS's package")


def _run_text(argv, **kwargs) -> str | None:
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=60,
                              check=False, **kwargs).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _file_identity(path) -> dict | None:
    """Where one outside binary is and what its bytes are."""
    if not path:
        return None
    real = Path(os.path.realpath(path))
    if not real.is_file():
        return None
    return {"path": str(real), "size": real.stat().st_size, "sha256": sha256_file(real)}


def interpreter_identity() -> dict:
    """The exact interpreter whose bytes the package carries, and where it came from.

    Version strings are not enough: the macOS K17 defect was two interpreters
    with the same version and different deployment targets. The executable and
    the shared Python library that py2app/PyInstaller copy are hashed.
    """
    import sysconfig
    base = Path(sys.base_prefix)
    library = None
    if sys.platform == "win32":
        library = base / f"python{sys.version_info[0]}{sys.version_info[1]}.dll"
    elif sysconfig.get_config_var("PYTHONFRAMEWORK"):
        library = base / sysconfig.get_config_var("PYTHONFRAMEWORK")
    elif sysconfig.get_config_var("INSTSONAME") and sysconfig.get_config_var("LIBDIR"):
        library = Path(sysconfig.get_config_var("LIBDIR")) / sysconfig.get_config_var("INSTSONAME")
    text = str(base).replace("\\", "/").lower()
    origin = ("python.org installer" if text.startswith("/library/frameworks/python.framework")
              else "github actions setup-python" if "hostedtoolcache" in text
              else "homebrew" if "/homebrew/" in text or "/cellar/" in text
              else "operating system" if text.startswith(("/usr", "/system"))
              else "other")
    return {"version": _platform.python_version(),
            "implementation": _platform.python_implementation(),
            "build": list(_platform.python_build()),
            "compiler": _platform.python_compiler(),
            "base": str(base), "origin": origin,
            "executable": _file_identity(sys.executable),
            "library": _file_identity(library),
            "macos_deployment_target": sysconfig.get_config_var("MACOSX_DEPLOYMENT_TARGET")}


def _folder_identity(folder: Path, suffixes: tuple[str, ...]) -> dict | None:
    """One digest over a tool's own binaries, for tools that embed them."""
    if not folder.is_dir():
        return None
    files = sorted(p for p in folder.iterdir()
                   if p.is_file() and p.suffix.lower() in suffixes)
    return {"path": str(folder),
            "digest": canonical_digest([[p.name, sha256_file(p)] for p in files]),
            "files": len(files)}


def host_identity() -> dict:
    """The build host's operating system and, in CI, the runner image."""
    identity = {"platform": _platform.platform(), "release": _platform.release(),
                "version": _platform.version(),
                "runner_image": "/".join(filter(None, (os.environ.get("ImageOS"),
                                                       os.environ.get("ImageVersion")))) or None}
    if sys.platform == "darwin":
        identity["macos_build"] = _run_text(["sw_vers", "-buildVersion"])
        identity["sdk"] = _run_text(["xcrun", "--show-sdk-version"])
        identity["developer_dir"] = _run_text(["xcode-select", "-p"])
    elif sys.platform.startswith("linux"):
        identity["glibc"] = "-".join(_platform.libc_ver())
        try:
            release = Path("/etc/os-release").read_text(encoding="utf-8")
        except OSError:
            release = ""
        identity["os_release"] = {k: v.strip('"') for k, _, v in
                                  (line.partition("=") for line in release.splitlines())
                                  if k in ("ID", "VERSION_ID")}
    return identity


def toolchain_identity(lane: str) -> dict:
    """Everything outside the repository that shapes the produced bytes."""
    identity = {"interpreter": interpreter_identity(), "host": host_identity(),
                "tools": {}}
    for module in ("PyInstaller", "py2app"):
        try:
            imported = __import__(module)
            identity["tools"][module] = getattr(imported, "__version__", "unknown")
        except ImportError:
            continue
    if lane == "linux-x64":
        identity["apt"] = {name: _run_text(["dpkg-query", "-W", "-f=${Version}", name])
                           for name in ("python3-gi", "python3-gi-cairo",
                                        "gir1.2-webkit2-4.1", "libwebkit2gtk-4.1-0")}
        identity["tools"]["dpkg-deb"] = _run_text(["dpkg-deb", "--version"])
    if lane == "windows-x64":
        iscc = find_iscc()
        # The compiler and the setup stubs it embeds in every installer.
        identity["tools"]["inno_setup"] = (
            _folder_identity(Path(iscc).parent, (".exe", ".dll", ".e32", ".e64"))
            if iscc else None)
    return identity


def input_identity(lane: str, *, toolchain: dict | None = None,
                   trust_root: str | None = None, update_feed: str | None = None) -> dict:
    snapshot, listing = packaging_plan.snapshot_digest(lane)
    pins = json.loads((DESKTOP / "engine" / "engine-pins.json").read_text(encoding="utf-8"))
    entry = packaging_plan.LANES[lane]
    components = {
        "lane": lane,
        "snapshot_digest": snapshot,
        "shared_snapshot_digest": packaging_plan.shared_snapshot_digest(),
        "locks": {path: sha256_file(REPO / path) for path in
                  entry.locks + entry.build_locks},
        "engines": {name: pins["lanes"][name]["sha256"] for name in entry.engines},
        "engine_release": pins["release"],
        "tools": json.loads(TOOLS.read_text(encoding="utf-8")),
        "toolchain": toolchain if toolchain is not None else toolchain_identity(lane),
        # The update trust root a package will accept, and where its channel's
        # feed is, are part of what it is.
        "trust_root": trust_root,
        "update_feed": update_feed,
        "schema_version": schema_version(),
    }
    return {"input_digest": canonical_digest(components), "components": components,
            "snapshot_files": len(listing)}


# The finished files each lane produces; a record missing any of them is
# not a complete build set and cannot stand in for one.
ARTIFACT_KINDS = {"macos-arm64": (".zip",), "windows-x64": (".exe",),
                  "linux-x64": (".AppImage", ".deb")}
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _artifact_problem(artifact, store: Path) -> str | None:
    if not isinstance(artifact, dict):
        return "an artifact entry is not a record"
    name, digest = artifact.get("name"), artifact.get("sha256")
    if not isinstance(name, str) or not name or Path(name).name != name \
            or name in (".", ".."):
        return f"artifact name {name!r} is not a plain file name"
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        return f"{name}: no valid recorded SHA-256"
    path = store / name
    if path.is_symlink() or not path.is_file():
        return f"{name}: retained artifact missing"
    if isinstance(artifact.get("size"), int) and path.stat().st_size != artifact["size"]:
        return f"{name}: retained artifact changed size"
    if sha256_file(path) != digest:
        return f"{name}: retained artifact changed"
    return None


def find_reuse(records: list[dict], *, lane: str, input_digest: str,
               store: Path | None) -> dict | None:
    """A previous build set this one may reuse, only if its bytes still exist.

    The record must list every artifact kind the lane produces, each with a
    plain name and a SHA-256 that the retained file still matches when read
    now. An empty or partial record never counts as a build.
    """
    for record in records:
        if record.get("lane") != lane or record.get("input_digest") != input_digest:
            continue
        if store is None:
            return {**record, "reuse": False,
                    "reason": "matching inputs, but no artifact store was given to "
                              "check the retained bytes"}
        artifacts = record.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return {**record, "reuse": False,
                    "reason": "the matching record lists no artifacts"}
        problems = [problem for problem in
                    (_artifact_problem(a, Path(store)) for a in artifacts) if problem]
        names = [a.get("name", "") for a in artifacts if isinstance(a, dict)]
        absent = [kind for kind in ARTIFACT_KINDS.get(lane, ())
                  if not any(str(n).endswith(kind) for n in names)]
        if absent:
            problems.append(f"no {', '.join(absent)} artifact recorded for {lane}")
        if len(set(names)) != len(names):
            problems.append("an artifact is listed twice")
        if problems:
            return {**record, "reuse": False,
                    "reason": "retained artifact missing or changed: "
                              + "; ".join(problems)}
        return {**record, "reuse": True, "reason": "inputs unchanged and retained "
                                                   "artifacts verified"}
    return None


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------

def trim_engine(root: Path) -> None:
    """Keep only the server, its shared libraries and links, and the licence."""
    for path in sorted(root.rglob("*"), reverse=True):
        if path.name == engine_fetch.MANIFEST_NAME:
            continue
        if path.is_dir() and not path.is_symlink():
            if not any(path.iterdir()):
                path.rmdir()
            continue
        if not packaging_plan.engine_file_is_shipped(path.name):
            path.unlink()


def prepare_engines(lane: str, work: Path, cache: Path) -> list[dict]:
    pins = engine_fetch.load_pins()
    prepared = []
    for engine_lane in packaging_plan.LANES[lane].engines:
        target = work / "engine" / engine_lane
        engine_fetch.fetch(engine_lane, destination=target, cache=cache, pins=pins)
        trim_engine(target)
        manifest = engine_fetch.describe(target, pins, engine_lane)
        (target / engine_fetch.MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        prepared.append({"lane": engine_lane, "path": target, "manifest": manifest,
                         "manifest_sha256": sha256_file(target / engine_fetch.MANIFEST_NAME)})
    return prepared


def place_engines(engines: list[dict], resources: Path) -> None:
    for item in engines:
        destination = resources / "engine" / item["lane"]
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(item["path"], destination, symlinks=True)


def verify_placed_engines(engines: list[dict], resources: Path) -> None:
    sys.path.insert(0, str(REPO))
    from backend.coordinator import engine as engine_module  # noqa: PLC0415
    for item in engines:
        root = resources / "engine" / item["lane"]
        problems = engine_module.verify(root, engine_module.load_manifest(root))
        if problems:
            raise BuildError(f"engine {item['lane']} failed verification in the "
                             f"package: {problems[:3]}")


# --------------------------------------------------------------------------
# Minimum OS
# --------------------------------------------------------------------------

_MACHO_MAGICS = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe",
                 b"\xfe\xed\xfa\xcf", b"\xfe\xed\xfa\xce"}


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def macho_minos(path: Path) -> tuple[int, ...] | None:
    output = _run_text(["/usr/bin/otool", "-l", str(path)])
    if not output:
        return None
    found = [_version(m) for m in re.findall(r"\bminos (\d+(?:\.\d+)*)", output)]
    found += [_version(m) for m in re.findall(
        r"cmd LC_VERSION_MIN_MACOSX[\s\S]*?version (\d+(?:\.\d+)*)", output)]
    return max(found) if found else None


def macho_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            try:
                with open(path, "rb") as handle:
                    if handle.read(4) in _MACHO_MAGICS:
                        yield path
            except OSError:
                continue


def bundle_floor(root: Path) -> tuple[tuple[int, ...], str]:
    """The highest minimum macOS any shipped binary declares, and which one."""
    worst, which = (0,), ""
    for path in macho_files(root):
        minos = macho_minos(path)
        if minos and minos > worst:
            worst, which = minos, str(path.relative_to(root))
    return worst, which


def expected_macos_floor(engines: list[dict]) -> tuple[int, ...]:
    """Floor from the inputs, before building: interpreter, engine, renderer."""
    candidates = [Path(sys.base_prefix) / "Python"]
    candidates += [item["path"] / item["manifest"]["executable"] for item in engines]
    try:
        import pypdfium2_raw
        candidates.append(Path(pypdfium2_raw.__file__).parent / "libpdfium.dylib")
    except ImportError:
        pass
    floors = [m for m in (macho_minos(p) for p in candidates if p.is_file()) if m]
    return max(floors) if floors else (13, 3)


# --------------------------------------------------------------------------
# Platform tools
# --------------------------------------------------------------------------

def find_iscc() -> str | None:
    for candidate in (os.environ.get("ISCC"),
                      r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
                      r"C:\Program Files\Inno Setup 6\ISCC.exe"):
        if candidate and Path(candidate).is_file():
            return candidate
    return shutil.which("iscc")


def _check(argv, **kwargs) -> None:
    result = subprocess.run(argv, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        raise BuildError(f"{Path(argv[0]).name} failed ({result.returncode}): "
                         f"{(result.stderr or result.stdout)[-1500:]}")


def obtain_tool(name: str, cache: Path) -> Path:
    tool = json.loads(TOOLS.read_text(encoding="utf-8"))[name]
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{tool['sha256']}-{Path(tool['url']).name}"
    if not (path.is_file() and sha256_file(path) == tool["sha256"]):
        engine_fetch._download(tool["url"], path)
        if path.stat().st_size != tool["size"] or sha256_file(path) != tool["sha256"]:
            path.unlink(missing_ok=True)
            raise BuildError(f"{name} did not match its pinned SHA-256")
    path.chmod(0o755)
    return path


def verify_update_files(resources: Path) -> None:
    """The trust root and feed this build was given are in the package, unchanged."""
    for variable in ("REFINIX_UPDATE_ROOT", "REFINIX_UPDATE_FEED"):
        source = os.environ.get(variable)
        if not source:
            continue
        placed = resources / Path(source).name
        if not placed.is_file() or sha256_file(placed) != sha256_file(Path(source)):
            raise BuildError(f"{Path(source).name} is missing from the package or changed")


def build_macos(args, work: Path, identity_file: Path, engines: list[dict]) -> list[Path]:
    floor = expected_macos_floor(engines)
    env = dict(os.environ, REFINIX_BUILD_IDENTITY=str(identity_file),
               REFINIX_MIN_MACOS=".".join(map(str, floor)))
    dist = work / "dist"
    _check([sys.executable, str(DESKTOP / "setup_py2app.py"), "py2app",
            "--bdist-base", str(work / "py2app"), "--dist-dir", str(dist)],
           cwd=str(DESKTOP), env=env)
    app = dist / "Refinix.app"
    resources = app / "Contents" / "Resources"
    place_engines(engines, resources)
    verify_placed_engines(engines, resources)
    verify_update_files(resources)
    actual, which = bundle_floor(app)
    if actual > floor:
        raise BuildError(f"{which} needs macOS {'.'.join(map(str, actual))}, above the "
                         f"declared minimum {'.'.join(map(str, floor))}")
    # Adding the engine changed the bundle, so the ad-hoc signature is redone.
    # This is not Developer ID signing or notarisation.
    _check(["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(app)])
    _check(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)])
    artifact = Path(args.out) / f"Refinix-{args.version}-macos-arm64.zip"
    _check(["/usr/bin/ditto", "-c", "-k", "--keepParent", str(app), str(artifact)])
    args.min_os = ".".join(map(str, floor))
    return [artifact]


def build_pyinstaller(work: Path, identity_file: Path, staged: Path,
                      engines: list[dict]) -> Path:
    env = dict(os.environ, REFINIX_STAGED_SOURCES=str(staged),
               REFINIX_BUILD_IDENTITY=str(identity_file))
    _check([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--distpath", str(work / "dist"), "--workpath", str(work / "pyi"),
            str(DESKTOP / "refinix.spec")], env=env)
    onedir = work / "dist" / "Refinix"
    resources = onedir / "_internal"
    place_engines(engines, resources)
    verify_placed_engines(engines, resources)
    shipped = [str(p.relative_to(onedir)).replace("\\", "/") for p in onedir.rglob("*")]
    forbidden = [p for p in shipped if "/worker/" in p or "/fixtures/" in p
                 or re.search(r"(^|/)(test_|fake_|check_)[^/]*\.py$", p)]
    if forbidden:
        raise BuildError(f"development files in the package: {forbidden[:5]}")
    if not (resources / IDENTITY_NAME).is_file():
        raise BuildError("the build identity is missing from the package")
    verify_update_files(resources)
    return onedir


SIGNATURE_PATH_VARIABLE = "REFINIX_SIGNATURE_PATH"
# The path reaches PowerShell through the environment. Arguments after a
# `-Command` string are joined into the command text rather than bound to
# `$args`, so passing the path that way would check nothing (review finding).
SIGNATURE_SCRIPT = (
    f"$s = Get-AuthenticodeSignature -LiteralPath $env:{SIGNATURE_PATH_VARIABLE}; "
    "$subject = if ($s.SignerCertificate) { $s.SignerCertificate.Subject } else { '' }; "
    "Write-Output ($s.Status.ToString() + '|' + $subject)")


def verify_microsoft_signature(path: Path, run=subprocess.run) -> None:
    """The bundled WebView2 installer carries a valid Microsoft Authenticode
    signature. Checked on the Windows build host, beside the pinned SHA-256."""
    env = dict(os.environ, **{SIGNATURE_PATH_VARIABLE: str(Path(path).resolve())})
    result = run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                  SIGNATURE_SCRIPT], capture_output=True, text=True, env=env)
    status, _, subject = (result.stdout or "").strip().partition("|")
    if result.returncode != 0 or status != "Valid" or "O=Microsoft Corporation" not in subject:
        raise BuildError(f"{path.name} is not validly signed by Microsoft "
                         f"({status or result.stderr.strip()[-200:]})")


def build_windows(args, work: Path, identity_file: Path, staged: Path,
                  engines: list[dict], cache: Path) -> list[Path]:
    onedir = build_pyinstaller(work, identity_file, staged, engines)
    iscc = find_iscc()
    if not iscc:
        raise BuildError("Inno Setup (ISCC.exe) was not found on this build host")
    # Shipped inside the setup, and run by it only when this computer has no
    # WebView2 Runtime: the install never needs a separate download.
    webview2 = obtain_tool("webview2_standalone_x64", cache)
    verify_microsoft_signature(webview2)
    base = f"Refinix-{args.version}-windows-x64-setup"
    _check([iscc, f"/DAppVersion={args.version}", f"/DSourceDir={onedir}",
            f"/DOutputDir={Path(args.out).resolve()}", f"/DOutputBase={base}",
            f"/DWebView2Installer={webview2}",
            str(DESKTOP / "windows" / "refinix.iss")])
    args.min_os = "Windows 11 (10.0.22000)"
    return [Path(args.out) / f"{base}.exe"]


def build_linux(args, work: Path, identity_file: Path, staged: Path,
                engines: list[dict], cache: Path) -> list[Path]:
    onedir = build_pyinstaller(work, identity_file, staged, engines)
    icon = packaging_plan.ICONS / "refinix-256.png"
    outputs = []
    # AppImage: one user-writable file; replaced atomically on update.
    appdir = work / "Refinix.AppDir"
    shutil.copytree(onedir, appdir / "usr" / "lib" / "refinix", symlinks=True)
    shutil.copy2(DESKTOP / "linux" / "AppRun", appdir / "AppRun")
    shutil.copy2(DESKTOP / "linux" / "refinix.desktop", appdir / "refinix.desktop")
    shutil.copy2(icon, appdir / "refinix.png")
    appimage = Path(args.out) / f"Refinix-{args.version}-linux-x86_64.AppImage"
    tool = obtain_tool("appimagetool", cache)
    runtime_file = obtain_tool("appimage_runtime", cache)
    _check([str(tool), "--runtime-file", str(runtime_file), str(appdir), str(appimage)],
           env=dict(os.environ, ARCH="x86_64", APPIMAGE_EXTRACT_AND_RUN="1"))
    outputs.append(appimage)
    # .deb: installed through App Center, which resolves GTK/WebKitGTK.
    tree = work / "deb"
    shutil.copytree(onedir, tree / "opt" / "refinix", symlinks=True)
    (tree / "usr" / "bin").mkdir(parents=True)
    os.symlink("/opt/refinix/Refinix", tree / "usr" / "bin" / "refinix")
    (tree / "usr" / "share" / "applications").mkdir(parents=True)
    shutil.copy2(DESKTOP / "linux" / "refinix.desktop",
                 tree / "usr" / "share" / "applications" / "refinix.desktop")
    for size in packaging_plan.LINUX_ICON_SIZES:
        folder = tree / "usr" / "share" / "icons" / "hicolor" / f"{size}x{size}" / "apps"
        folder.mkdir(parents=True)
        shutil.copy2(packaging_plan.ICONS / f"refinix-{size}.png", folder / "refinix.png")
    (tree / "DEBIAN").mkdir()
    control = (DESKTOP / "linux" / "control.in").read_text(encoding="utf-8")
    (tree / "DEBIAN" / "control").write_text(
        control.replace("@DEB_VERSION@", args.version.replace("-", "~")), encoding="utf-8")
    deb = Path(args.out) / f"refinix_{args.version.replace('-', '~')}_amd64.deb"
    _check(["dpkg-deb", "--build", "--root-owner-group", str(tree), str(deb)])
    outputs.append(deb)
    args.min_os = f"Ubuntu 24.04 or later (glibc {_platform.libc_ver()[1]} build host)"
    return outputs


# --------------------------------------------------------------------------
# Identity extraction and records
# --------------------------------------------------------------------------

# The installer's own AppId, read from refinix.iss so the two never disagree.
WINDOWS_APP_ID = re.search(r"AppId=\{\{([0-9A-Fa-f-]+)\}",
                           (DESKTOP / "windows" / "refinix.iss").read_text(encoding="utf-8")
                           ).group(1)


def _windows_registration(app_id: str = WINDOWS_APP_ID) -> list[str]:
    """Where an installation of this AppId is registered on this Windows host."""
    import winreg
    key = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{{{app_id}}}_is1"
    found = []
    for name, hive in (("HKCU", winreg.HKEY_CURRENT_USER),
                       ("HKLM", winreg.HKEY_LOCAL_MACHINE)):
        try:
            winreg.CloseKey(winreg.OpenKey(hive, key))
            found.append(f"{name}\\{key}")
        except OSError:
            continue
    return found


def extract_identity(artifact: Path, work: Path, *, disposable_host: bool = False,
                     registration=None) -> dict:
    """Read the embedded identity back out of the finished artifact.

    Archives are read without running anything. A Windows installer cannot be
    read without running it, and running it registers the Refinix AppId,
    creates its Start menu entry and may close a running Refinix, whatever
    folder it installs into. So that check runs only on a host declared
    disposable (a fresh CI runner) that has no Refinix registered.
    """
    name = artifact.name
    if name.endswith(".zip"):
        with zipfile.ZipFile(artifact) as bundle:
            return json.loads(bundle.read(f"Refinix.app/Contents/Resources/{IDENTITY_NAME}"))
    if name.endswith(".deb"):
        folder = work / "deb-check"
        _check(["dpkg-deb", "-x", str(artifact), str(folder)])
        return json.loads((folder / "opt" / "refinix" / "_internal" / IDENTITY_NAME)
                          .read_text(encoding="utf-8"))
    if name.endswith(".AppImage"):
        folder = work / "appimage-check"
        folder.mkdir(exist_ok=True)
        _check([str(artifact.resolve()), "--appimage-extract",
                f"usr/lib/refinix/_internal/{IDENTITY_NAME}"], cwd=str(folder))
        return json.loads((folder / "squashfs-root" / "usr" / "lib" / "refinix" / "_internal"
                           / IDENTITY_NAME).read_text(encoding="utf-8"))
    if name.endswith(".exe"):
        if not disposable_host:
            raise BuildError(
                f"{name}: reading a Windows installer's identity means running it, "
                "which registers Refinix on this computer. Do it only on a "
                "disposable runner, with --disposable-host.")
        registration = registration or _windows_registration
        existing = registration()
        if existing:
            raise BuildError(f"{name}: Refinix is already registered on this host "
                             f"({existing[0]}); this is not a disposable runner.")
        # Install into a private folder, read the identity, uninstall again.
        # This also proves a silent per-user install works on a clean host.
        target = work / "install-check"
        _check([str(artifact.resolve()), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                "/NORESTART", "/CURRENTUSER", "/NOCLOSEAPPLICATIONS",
                "/NORESTARTAPPLICATIONS", f"/DIR={target}"])
        try:
            return json.loads((target / "_internal" / IDENTITY_NAME).read_text(encoding="utf-8"))
        finally:
            uninstaller = target / "unins000.exe"
            if uninstaller.is_file():
                subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                                "/NORESTART"], check=False, timeout=600)
            left = registration()
            if left:
                raise BuildError(f"{name}: the check installation is still "
                                 f"registered after uninstalling ({left[0]}).")
    raise BuildError(f"unknown artifact type: {name}")


INSTALL_STEPS = {
    "macos-arm64": "1. Unzip the file and move **Refinix.app** to Applications.\n"
                   "2. Open it. Because this build is unsigned, macOS blocks the first "
                   "open: open System Settings → Privacy & Security and choose "
                   "**Open Anyway** for Refinix, then confirm.",
    "windows-x64": "1. Run the setup file. Because it is unsigned, Windows SmartScreen "
                   "may warn: choose **More info → Run anyway**.\n"
                   "2. Setup installs for your account only; no administrator password "
                   "is needed.",
    "linux-x64": "Recommended — **.deb:** double-click it to install with App Center. "
                 "It asks for your password and installs the GTK/WebKitGTK packages "
                 "Refinix needs, so nothing else has to be set up.\n"
                 "Alternative — **AppImage:** in Files, open the file's Properties, turn on "
                 "**Executable as Program** (\"Allow executing\"), then double-click it. "
                 "It needs FUSE and WebKitGTK already installed.",
}
PREREQUISITES = {
    "macos-arm64": "- A Mac with an Apple M-series chip.",
    "windows-x64": "- Windows 11 x64. The Microsoft Edge WebView2 Runtime is part of "
                   "Windows 11; if it is missing, setup installs it from the copy "
                   "included in this package, without downloading.\n"
                   "- A current graphics driver; Refinix uses the processor if no "
                   "usable graphics device is found.",
    "linux-x64": "- Ubuntu 24.04 desktop.\n- The .deb installs everything else it needs. "
                 "The AppImage needs FUSE (`fuse3`) and the WebKitGTK 4.1 packages; "
                 "Refinix explains if they are missing.\n- A current graphics driver; "
                 "otherwise the processor is used.",
}
UNINSTALL = {
    "macos-arm64": "Move Refinix.app to the Bin.",
    "windows-x64": "Settings → Apps → Installed apps → Refinix → Uninstall.",
    "linux-x64": "Remove the package with App Center, or delete the AppImage file.",
}
UPDATE_LIMITATION = ("- Updates: Check for updates works only in a build given an update trust "
                     "root and feed; installing an update from inside Refinix is not "
                     "available yet (a verified package's folder is shown instead).")
LIMITATIONS = {
    "macos-arm64": "- Code validation in a sandbox is not available on macOS in this "
                   "build; Code changes keep the \"Not sandbox tested\" label.\n"
                   "- Scan reading (OCR) is not qualified yet.",
    "windows-x64": "- Code validation in a sandbox is not available on Windows in this "
                   "build.\n- Scan reading (OCR) is not qualified yet.\n- No qualified "
                   "model preset exists for Windows hardware yet; the setup screen says so.",
    "linux-x64": "- Code sandbox validation depends on this computer's kernel and "
                 "systemd features and is shown as unavailable when they are missing.\n"
                 "- Scan reading (OCR) is not qualified yet.\n- No qualified model preset "
                 "exists for Linux hardware yet; the setup screen says so.",
}


def finalize(artifact: Path, identity: dict, *, lane: str, min_os: str,
             work: Path, disposable_host: bool = False) -> dict:
    extracted = extract_identity(artifact, work, disposable_host=disposable_host)
    if extracted != identity:
        raise BuildError(f"{artifact.name}: the embedded identity does not match the "
                         "requested build")
    digest, size = sha256_file(artifact), artifact.stat().st_size
    record = {"artifact": artifact.name, "size": size, "sha256": digest, "lane": lane,
              "minimum_os": min_os, "channel": identity["channel"],
              "signing": identity["signing"], "embedded_identity": identity,
              "embedded_identity_sha256": canonical_digest(identity),
              "finalized_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    (artifact.parent / f"{artifact.name}.sha256").write_text(
        f"{digest}  {artifact.name}\n", encoding="utf-8")
    (artifact.parent / f"{artifact.name}.manifest.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    engines = ", ".join(f"{e['release']} {e['backend']}" for e in identity["engines"])
    notes = (DESKTOP / "TESTING.md.in").read_text(encoding="utf-8")
    for key, value in {
            "@ARTIFACT@": artifact.name, "@VERSION@": identity["version"],
            "@BUILD_SET@": identity["build_set"], "@SHA256@": digest,
            "@OS_LABEL@": lane, "@MIN_OS@": min_os, "@ENGINE@": engines,
            "@SOURCE_DIGEST@": identity["shared_snapshot_digest"],
            "@INSTALL_STEPS@": INSTALL_STEPS[lane], "@PREREQUISITES@": PREREQUISITES[lane],
            "@UNINSTALL_STEPS@": UNINSTALL[lane],
            "@LIMITATIONS@": LIMITATIONS[lane] + "\n" + UPDATE_LIMITATION}.items():
        notes = notes.replace(key, value)
    (artifact.parent / f"{artifact.name}.TESTING.md").write_text(notes, encoding="utf-8")
    return record


def build_identity(args, lane: str, inputs: dict, engines: list[dict]) -> dict:
    return {
        "identity_version": 1, "product": "Refinix", "version": args.version,
        "build_set": args.build_set, "channel": "internal", "signing": "unsigned",
        "lane": lane, "input_digest": inputs["input_digest"],
        "snapshot_digest": inputs["components"]["snapshot_digest"],
        "shared_snapshot_digest": inputs["components"]["shared_snapshot_digest"],
        "source_commit": args.source_commit,
        "locks": inputs["components"]["locks"],
        "engines": [{"lane": e["lane"], "release": e["manifest"]["release"],
                     "commit": e["manifest"]["commit"], "backend": e["manifest"]["backend"],
                     "archive_sha256": e["manifest"]["archive_sha256"],
                     "manifest_sha256": e["manifest_sha256"]} for e in engines],
        "toolchain": inputs["components"]["toolchain"],
        # The same values the input digest covers: the SHA-256 of the update
        # trust root this package accepts and of its channel feed, or None.
        "trust_root": inputs["components"]["trust_root"],
        "update_feed": inputs["components"]["update_feed"],
        "schema_version": inputs["components"]["schema_version"],
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True)
    parser.add_argument("--build-set", required=True)
    parser.add_argument("--out", type=Path, default=REPO / "desktop" / "out")
    parser.add_argument("--records", type=Path, default=DESKTOP / "build-sets.json")
    parser.add_argument("--store", type=Path, help="folder holding retained artifacts")
    parser.add_argument("--cache", type=Path,
                        default=Path(tempfile.gettempdir()) / "refinix-build-cache")
    parser.add_argument("--source-commit", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--trust-root", type=Path, default=None,
                        help="TUF root metadata this package trusts for updates")
    parser.add_argument("--update-feed", type=Path, default=None,
                        help="JSON naming the channel's HTTPS metadata_url and targets_url")
    parser.add_argument("--rebuild-reason")
    parser.add_argument("--disposable-host", action="store_true",
                        help="this host is a throwaway runner: the Windows installer "
                             "may be installed and removed to read its identity")
    parser.add_argument("--plan", action="store_true",
                        help="print digests and the reuse decision without building")
    args = parser.parse_args(argv)
    try:
        lane = detect_lane()
        update = update_files(args.trust_root, args.update_feed)
        inputs = input_identity(
            lane, trust_root=(update["trust_root"] or {}).get("sha256"),
            update_feed=(update["update_feed"] or {}).get("sha256"))
        records = (json.loads(args.records.read_text(encoding="utf-8"))
                   if args.records.is_file() else [])
        reuse = find_reuse(records, lane=lane, input_digest=inputs["input_digest"],
                           store=args.store)
        plan = {"lane": lane, "input_digest": inputs["input_digest"],
                "shared_snapshot_digest": inputs["components"]["shared_snapshot_digest"],
                "snapshot_digest": inputs["components"]["snapshot_digest"],
                "reuse": reuse}
        if args.plan:
            print(json.dumps(plan, indent=2))
            return 0
        if reuse and reuse.get("reuse") and not args.rebuild_reason:
            print(json.dumps({"result": "reuse", "build_set": reuse["build_set"],
                              "reason": reuse["reason"]}, indent=2))
            return 0
        args.out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="refinix-build-") as directory:
            work = Path(directory)
            engines = prepare_engines(lane, work, args.cache)
            identity = build_identity(args, lane, inputs, engines)
            identity_file = work / IDENTITY_NAME
            identity_file.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n",
                                     encoding="utf-8")
            # The update trust root and feed travel under the names the app reads.
            for key, variable in (("trust_root", "REFINIX_UPDATE_ROOT"),
                                  ("update_feed", "REFINIX_UPDATE_FEED")):
                item = update[key]
                if item:
                    placed = work / item["name"]
                    shutil.copyfile(item["path"], placed)
                    os.environ[variable] = str(placed)
                else:
                    os.environ.pop(variable, None)
            staged = packaging_plan.stage_application_sources(work / "staged")
            started = time.monotonic()
            if lane == "macos-arm64":
                artifacts = build_macos(args, work, identity_file, engines)
            elif lane == "windows-x64":
                artifacts = build_windows(args, work, identity_file, staged, engines,
                                          args.cache)
            else:
                artifacts = build_linux(args, work, identity_file, staged, engines,
                                        args.cache)
            finals = [finalize(a, identity, lane=lane, min_os=args.min_os, work=work,
                               disposable_host=args.disposable_host)
                      for a in artifacts]
        record = {"build_set": args.build_set, "version": args.version, "lane": lane,
                  "input_digest": inputs["input_digest"],
                  "shared_snapshot_digest": inputs["components"]["shared_snapshot_digest"],
                  "rebuild_reason": args.rebuild_reason,
                  "artifacts": [{"name": f["artifact"], "sha256": f["sha256"],
                                 "size": f["size"]} for f in finals],
                  "build_seconds": round(time.monotonic() - started, 1)}
        (args.out / f"build-record-{lane}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(record, indent=2))
        return 0
    except (BuildError, engine_fetch.FetchError, FileNotFoundError) as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
