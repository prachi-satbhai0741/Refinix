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

VERSION = "0.1.0"
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
# the day it is written.
EXCLUDED_MODULE_PREFIXES = ("test_", "setup_")

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
        tool="PyInstaller", pinned=False, artifact="Refinix.exe",
        checkpoint=("No Windows packaging tool is pinned in this repository, "
                    "so no Windows package can be built from this checkout. "
                    "The application boundary below is complete; pinning the "
                    "tool and running it on a Windows machine is the remaining "
                    "step."),
        native=("Credential Manager for credential storage",
                "a WebView2 runtime for the application window")),
    "linux": Platform(
        key="linux", label="Linux", icon="refinix-256.png",
        tool="PyInstaller", pinned=False, artifact="refinix",
        checkpoint=("No Linux packaging tool is pinned in this repository, so "
                    "no Linux package can be built from this checkout. The "
                    "application boundary below is complete; pinning the tool "
                    "and running it on the selected distribution is the "
                    "remaining step."),
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
            and not path.name.startswith(EXCLUDED_MODULE_PREFIXES))


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
