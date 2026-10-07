"""What goes into a Refinix application package, on any of the three platforms.

The macOS build already knew all of this, and it knew it *inside*
`setup_py2app.py` — a file that exits on anything that is not Darwin. So the
answers to "which Python modules are the application", "which frontend files
does the coordinator actually serve", "what must never be shipped" and "which
icon belongs to this platform" existed once, in a form no Windows or Linux
build could reuse and no check could read without executing a setuptools
script.

This module is those answers, separated from the tool that consumes them.
`setup_py2app.py` now imports them; a Windows or Linux packaging step will
import the same ones, which is what makes the three packages describe the same
application instead of three hand-maintained lists that drift.

Three rules it enforces, because each has a way of going wrong quietly:

* **Only application sources ship.** Tests, fixtures, build output, the
  worker, the development UI harness and the virtual environments are
  excluded by name and the result is verified, not assumed. A `test_` module
  in a shipped package is not merely clutter: it carries fixtures and
  assumptions that have no business on a user's computer.
* **Durable data lives outside the package.** `backend.coordinator.paths`
  chooses the data root, and none of its answers is inside an application
  bundle — which is what lets a package be replaced without taking a person's
  chats with it. `runtime_data_is_external` checks that rather than trusting
  it.
* **A prerequisite is a probe, not a platform name.** `prerequisites()` asks
  the modules that actually know — the credential store, the PDF renderer,
  the document writer, the repository containment backend — and reports what
  they observed *on the computer running this*. It never states what a
  Windows or Linux machine will find; only that machine can answer.

**This module builds nothing.** It describes the boundary and can verify a
layout it is shown. Producing a Windows or Linux package needs a packaging
tool that is not pinned in this repository, and `PLATFORMS` records that
honestly rather than implying a build exists.

Standard library only.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def _read_app_version() -> str:
    """The one version, read from `backend/coordinator/build_info.py`.

    Parsed, not imported: `setup_py2app.py` runs this module as a sibling
    script where the repository root is not importable, so an import of
    `backend` would break the real macOS build.
    """
    import ast
    tree = ast.parse((REPO / "backend" / "coordinator" / "build_info.py")
                     .read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(target, "id", None) == "APP_VERSION" for target in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError("APP_VERSION is not defined in build_info.py")


# One version source for the UI, the stored "last writer" value and packages.
VERSION = _read_app_version()
PRODUCT = "Refinix"

# Reverse-DNS identifier. Nothing is signed or distributed from this
# repository, so this is a local identifier only; a real distribution needs an
# owned domain and a platform signing identity, which is a user decision.
BUNDLE_ID = "com.refinix.desktop"

# The Python packages that *are* the application. The worker is deliberately
# absent: a desktop package that carried it would ship a Kubernetes and Redis
# client to a person who needs neither.
APPLICATION_PACKAGES = ("desktop", "backend/coordinator", "backend/contracts")

# Module name prefixes that are development material rather than application
# code, checked against the file's own name so a new test module is excluded
# the day it is written. `check_` modules make live model calls for engineering
# evidence and `fake_` modules stand in for the engine in offline tests; neither
# belongs on a user's computer.
EXCLUDED_MODULE_PREFIXES = ("test_", "setup_", "check_", "fake_")
# Build tooling that sits beside the application modules but is not part of the
# application. Listed by exact name: a prefix such as "build" would also drop
# `backend/coordinator/build_info.py`, which the application needs.
EXCLUDED_MODULE_NAMES = ("build.py",)

# Frontend files the coordinator serves but that exist for development: the
# synthetic fixture page and the Node checks beside it.
DEVELOPMENT_FRONTEND = ("fixture.html", "fixture.js")
DEVELOPMENT_SUFFIXES = (".cjs",)


@dataclass(frozen=True)
class Platform:
    """One platform's packaging boundary, and what is still missing for it.

    `tool` names the packaging tool a build would use. `pinned` says whether
    this repository actually pins it — which is the difference between "a
    package can be built from this checkout" and "a package could be built once
    somebody installs a tool". Stating that difference is the point: a plan
    that reads as a capability would be the fabricated readiness the release
    contract forbids.
    """

    key: str
    label: str
    icon: str
    tool: str
    pinned: bool
    artifact: str
    checkpoint: str
    # Prerequisites the *platform* imposes on the machine, named so a package
    # step can check them rather than discovering them at a user's first run.
    native: tuple[str, ...] = ()


PLATFORMS: dict[str, Platform] = {
    "macos": Platform(
        key="macos", label="macOS", icon="Refinix.icns",
        tool="py2app", pinned=True, artifact="Refinix.app",
        checkpoint=("Builds from this checkout with the pinned desktop "
                    "requirements. Signing and notarisation are separate and "
                    "are not performed here."),
        native=("PyObjC (Quartz, AppKit) for PDF writing",
                "the login Keychain for credential storage")),
    "windows": Platform(
        key="windows", label="Windows", icon="Refinix.ico",
        tool="PyInstaller + Inno Setup", pinned=True,
        artifact="Refinix-<version>-windows-x64-setup.exe",
        checkpoint=("Built by desktop/build.py on a native Windows x64 host or "
                    "the package workflow's Windows runner, from the pinned "
                    "requirements-windows.lock and requirements-build-windows.lock. "
                    "PyInstaller cannot cross-build from another OS. A produced "
                    "package is internal test evidence until signing and release "
                    "acceptance."),
        native=("Credential Manager for credential storage",
                "a WebView2 runtime for the application window")),
    "linux": Platform(
        key="linux", label="Linux", icon="refinix-256.png",
        tool="PyInstaller + .deb (recommended) and AppImage", pinned=True,
        # The .deb is the main package: it declares GTK/WebKitGTK, so the
        # system installs them. The AppImage relies on what the host has.
        artifact="refinix_<version>_amd64.deb",
        checkpoint=("Built by desktop/build.py on a native Ubuntu 24.04 x86_64 "
                    "host or the package workflow's Ubuntu runner, from the "
                    "pinned requirements-linux.lock and requirements-build-linux.lock "
                    "plus the distribution's GTK/WebKitGTK bindings. PyInstaller "
                    "cannot cross-build from another OS. A produced package is "
                    "internal test evidence until signing and release acceptance."),
        native=("secret-tool (libsecret-tools) and an unlocked desktop keyring "
                "for credential storage",
                "a WebKitGTK runtime for the application window")),
}

ICONS = REPO / "desktop" / "icons"
# Every size a Linux desktop entry may reference. Shipped together because a
# single size looks wrong in half the places a launcher shows an icon.
LINUX_ICON_SIZES = (16, 32, 48, 64, 128, 256, 512)


# --------------------------------------------------------------------------
# Application sources
# --------------------------------------------------------------------------

def is_application_module(path: Path) -> bool:
    return (path.suffix == ".py"
            and not path.name.startswith(EXCLUDED_MODULE_PREFIXES)
            and not (path.parent.name == "desktop" and path.name in EXCLUDED_MODULE_NAMES))


def application_modules() -> dict[str, list[Path]]:
    """Every source file that is part of the application, by package."""
    return {package: sorted(source for source in (REPO / package).glob("*.py")
                            if is_application_module(source))
            for package in APPLICATION_PACKAGES}


def application_module_names() -> set[str]:
    """The paths those modules occupy inside a package, as strings."""
    names = {"backend/__init__.py"}
    for package, sources in application_modules().items():
        names.update(f"{package}/{source.name}" for source in sources)
    return names


def stage_application_sources(destination: Path) -> Path:
    """Copy the application sources, and nothing else, into `destination`.

    A packaging tool pointed straight at `desktop/` would copy its virtual
    environment and recursively copy its own build output into itself, so the
    sources are staged first. The frontend ships separately, through
    `frontend_data_files`.
    """
    destination = Path(destination)
    for package, sources in application_modules().items():
        target = destination / package
        target.mkdir(parents=True, exist_ok=True)
        for source in sources:
            shutil.copy2(source, target / source.name)
    # The existing `backend` namespace, made explicit in the staging tree only.
    (destination / "backend" / "__init__.py").touch()
    return destination


def unexpected_shipped_files(shipped) -> list[str]:
    """Anything in a built package that is not an application module.

    Compiled names count as their source, because a packaging tool may ship
    either. `__pycache__` never counts: a directory of compiled copies beside
    the modules is not part of the declared boundary.
    """
    allowed = application_module_names()
    allowed |= {name + "c" for name in allowed}
    return sorted(name for name in shipped if name not in allowed)


def missing_shipped_files(shipped, required) -> list[str]:
    return [name for name in required if not {name, name + "c"} & set(shipped)]


# --------------------------------------------------------------------------
# Frontend
# --------------------------------------------------------------------------

def is_shipped_frontend_file(path: Path) -> bool:
    return (path.is_file() and not path.name.startswith(".")
            and path.name not in DEVELOPMENT_FRONTEND
            and path.suffix not in DEVELOPMENT_SUFFIXES)


def frontend_data_files(root: Path | None = None) -> list[tuple[str, list[str]]]:
    """The frontend exactly as the coordinator serves it, grouped by folder."""
    root = Path(root) if root is not None else REPO / "frontend" / "app"
    grouped: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*")):
        if not is_shipped_frontend_file(path):
            continue
        parent = path.relative_to(root).parent
        destination = ("frontend/app" if parent == Path(".")
                       else str(Path("frontend/app") / parent))
        grouped.setdefault(destination, []).append(str(path))
    return sorted(grouped.items())


# --------------------------------------------------------------------------
# Platform assets
# --------------------------------------------------------------------------

def icon_for(platform: str) -> Path:
    """The icon file a package for `platform` uses."""
    try:
        return ICONS / PLATFORMS[platform].icon
    except KeyError:
        raise ValueError(f"{platform!r} is not a packaged platform") from None


def linux_icons() -> list[Path]:
    return [ICONS / f"refinix-{size}.png" for size in LINUX_ICON_SIZES]


def platform_assets(platform: str) -> list[Path]:
    """Every asset file a package for `platform` needs from this repository."""
    return linux_icons() if platform == "linux" else [icon_for(platform)]


# --------------------------------------------------------------------------
# What the package does not contain
# --------------------------------------------------------------------------

def runtime_data_is_external(root: Path) -> bool:
    """Whether a data root sits outside an application package.

    The rule that makes a package replaceable: durable state has to survive
    the application being deleted and reinstalled. Checked against the real
    root resolution rather than assumed from a documented layout.
    """
    parts = {part.casefold() for part in Path(root).parts}
    return not ({"refinix.app", "contents", "resources"} & parts)


def prerequisites() -> dict:
    """What this computer actually provides, asked of the modules that know.

    Only about the computer running this. A package step may use it to refuse
    to build where a prerequisite is missing; it says nothing about any other
    machine, and no entry here is evidence that a platform is qualified.
    """
    from backend.coordinator import (credentials, docgen, pdfrender, repo,
                                     device)
    return {
        "platform": device.describe(),
        "credential_store": credentials.probe(),
        "pdf_reading": pdfrender.probe(),
        "word_writing": docgen.probe(),
        "code_containment": {
            "available": repo.containment_supported(),
            "backend": repo.containment_backend(),
            "detail": (None if repo.containment_supported()
                       else repo.PLATFORM_NOTE),
        },
    }


def plan(platform: str) -> dict:
    """One platform's packaging boundary, as a report rather than a build.

    Deliberately shaped so nothing in it can be mistaken for an artifact:
    `buildable` is the tool question and is False wherever this repository
    does not pin the tool.
    """
    entry = PLATFORMS[platform]
    return {
        "platform": entry.key, "label": entry.label, "product": PRODUCT,
        "version": VERSION, "bundle_id": BUNDLE_ID,
        "tool": entry.tool, "buildable": entry.pinned,
        "artifact": entry.artifact, "checkpoint": entry.checkpoint,
        "packages": list(APPLICATION_PACKAGES),
        "modules": sorted(application_module_names()),
        "frontend": [destination for destination, _files in frontend_data_files()],
        "assets": [str(path.relative_to(REPO)) for path in platform_assets(platform)],
        "excludes": {"modules": list(EXCLUDED_MODULE_PREFIXES),
                     "frontend": list(DEVELOPMENT_FRONTEND) + list(DEVELOPMENT_SUFFIXES),
                     "packages": ["backend/worker", "backend/worker-image",
                                  "deploy", "fixtures", "scripts", "docs"]},
        "native_prerequisites": list(entry.native),
    }


# --------------------------------------------------------------------------
# Build lanes: one per OS family, built natively from one source snapshot
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Lane:
    """What `desktop/build.py` produces on one native build host."""

    key: str
    platform: str                  # PLATFORMS key
    host: tuple[str, str]          # (sys.platform prefix, normalised machine)
    locks: tuple[str, ...]         # application locks (shipped dependencies)
    build_locks: tuple[str, ...]   # build-time tools, never shipped
    engines: tuple[str, ...]       # engine lanes from desktop/engine/engine-pins.json
    outputs: tuple[str, ...]       # artifact kinds produced


LANES: dict[str, Lane] = {
    "macos-arm64": Lane(
        "macos-arm64", "macos", ("darwin", "arm64"),
        ("desktop/requirements-macos.lock", "backend/requirements-runtime.lock"),
        ("desktop/requirements-build-macos.lock",),
        ("macos-arm64",), ("app-zip",)),
    "windows-x64": Lane(
        "windows-x64", "windows", ("win32", "x86_64"),
        ("desktop/requirements-windows.lock", "backend/requirements-runtime.lock",
         "backend/requirements-render.lock"),
        ("desktop/requirements-build-windows.lock",),
        ("windows-x64-vulkan", "windows-x64-cpu"), ("setup-exe",)),
    "linux-x64": Lane(
        "linux-x64", "linux", ("linux", "x86_64"),
        ("desktop/requirements-linux.lock", "backend/requirements-runtime.lock",
         "backend/requirements-render.lock"),
        ("desktop/requirements-build-linux.lock",),
        ("linux-x64-vulkan", "linux-x64-cpu"), ("appimage", "deb")),
}

# Files that define how a package is built, beyond the application sources and
# frontend. All of them are part of the source snapshot every lane shares.
BUILD_DEFINITION = (
    "desktop/build.py", "desktop/packaging_plan.py", "desktop/setup_py2app.py",
    "desktop/refinix.py", "desktop/refinix.spec", "desktop/engine/engine-pins.json",
    "desktop/engine/fetch.py", "desktop/packaging-tools.json",
    "desktop/windows/refinix.iss", "desktop/linux/refinix.desktop",
    "desktop/linux/AppRun", "desktop/linux/control.in", "desktop/TESTING.md.in",
    ".github/workflows/package.yml",
)

# What of an upstream engine archive is shipped: the server, its shared
# libraries and their links, and the licence. The archive's other tools are
# not needed and are left out.
ENGINE_KEEP_NAMES = ("llama-server", "llama-server.exe", "LICENSE")
ENGINE_KEEP_SUFFIXES = (".dylib", ".dll", ".so")


def engine_file_is_shipped(name: str) -> bool:
    if name in ENGINE_KEEP_NAMES:
        return True
    return name.endswith(ENGINE_KEEP_SUFFIXES) or ".so." in name


def snapshot_files(lane: str) -> list[str]:
    """Every repository file whose bytes define one lane's package."""
    entry = LANES[lane]
    files = set(application_module_names()) - {"backend/__init__.py"}
    for _destination, sources in frontend_data_files():
        files.update(str(Path(source).relative_to(REPO)) for source in sources)
    files.update(str(path.relative_to(REPO)) for path in platform_assets(entry.platform))
    files.update(entry.locks)
    files.update(entry.build_locks)
    files.update(BUILD_DEFINITION)
    return sorted(f.replace("\\", "/") for f in files)


def snapshot_digest(lane: str, root: Path | None = None) -> tuple[str, list[dict]]:
    """SHA-256 over the sorted (path, SHA-256) of a lane's snapshot files.

    The application sources, frontend and build definition are the same for
    every lane, so the shared part of the snapshot is identical across the
    three packages; the lane's own locks and assets are listed explicitly.
    """
    import hashlib
    root = Path(root) if root is not None else REPO
    listing = []
    for relative in snapshot_files(lane):
        path = root / relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        listing.append({"path": relative, "sha256": digest})
    missing = [item["path"] for item in listing if item["sha256"] is None]
    if missing:
        raise FileNotFoundError(f"snapshot files missing: {missing}")
    body = "".join(f"{item['path']}\0{item['sha256']}\n" for item in listing)
    return hashlib.sha256(body.encode("utf-8")).hexdigest(), listing


def shared_snapshot_digest(root: Path | None = None) -> str:
    """The part of the snapshot every lane must agree on: sources, frontend, build code."""
    import hashlib
    root = Path(root) if root is not None else REPO
    shared = set(application_module_names()) - {"backend/__init__.py"}
    for _destination, sources in frontend_data_files():
        shared.update(str(Path(source).relative_to(REPO)) for source in sources)
    shared.update(BUILD_DEFINITION)
    shared.update(("backend/requirements-runtime.lock", "backend/requirements-render.lock"))
    body = "".join(f"{p}\0{hashlib.sha256((root / p).read_bytes()).hexdigest()}\n"
                   for p in sorted(shared))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
