"""Build Refinix.app with py2app.

Run from the repository root, on macOS, in an environment where the pinned
desktop requirements are installed:

    python3 desktop/setup_py2app.py py2app          # release bundle
    python3 desktop/setup_py2app.py py2app -A       # alias build, for a quick check

The alias build (`-A`) symlinks back into this working tree, so it proves the
window and the launch path but NOT independence from the repository. Only the
plain `py2app` build produces a bundle that stands on its own; the acceptance
check for that is in desktop/README.md.

The bundle carries the frontend and the icon. It does not carry a model, the
model runtime, or any state: `~/.aegisforge` stays where it is, so an existing
database, identity and history are picked up unchanged.
"""

from __future__ import annotations

import os
import sys
import shutil
import zipfile
from pathlib import Path

from setuptools import setup

REPO = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
APPLICATION_PACKAGES = ("desktop", "backend/coordinator", "backend/contracts")


def stage_application_sources(destination: Path) -> Path:
    """Give modulegraph source-only packages, never the package's build/venv.

    py2app recursively copies non-Python package data. Pointing it at desktop/
    would copy its virtualenv and recursively copy the build into itself.
    The frontend is shipped separately by frontend_data_files().
    """
    for package in APPLICATION_PACKAGES:
        target = destination / package
        target.mkdir(parents=True, exist_ok=True)
        for source in (REPO / package).glob("*.py"):
            if source.name.startswith(("test_", "setup_")):
                continue
            shutil.copy2(source, target / source.name)
    # Make the existing backend namespace explicit only in the build staging
    # tree; no worker code or unrelated repository data belongs in this app.
    (destination / "backend" / "__init__.py").touch()
    return destination


def verify_application_contents(bundle: Path) -> None:
    """Check both loose packages and the ZIP, not just the staging directory."""
    allowed = {"backend/__init__.py"}
    for package in APPLICATION_PACKAGES:
        allowed.update(f"{package}/{source.name}" for source in (REPO / package).glob("*.py")
                       if not source.name.startswith(("test_", "setup_")))
    allowed |= {name + "c" for name in allowed}
    library = bundle / "Contents" / "Resources" / "lib"
    shipped = set()
    for root in library.glob("python3.*"):
        for package in ("backend", "desktop"):
            shipped.update(str(path.relative_to(root)) for path in (root / package).rglob("*")
                           if path.is_file())
    for archive in library.glob("python*.zip"):
        with zipfile.ZipFile(archive) as files:
            shipped.update(name for name in files.namelist()
                           if name.startswith(("backend/", "desktop/")) and not name.endswith("/"))
    unexpected = shipped - allowed
    required = ("backend/coordinator/server.py", "backend/contracts/v1.py", "desktop/shell.py")
    missing = [name for name in required if not {name, name + "c"} & shipped]
    if unexpected or missing:
        raise RuntimeError(f"Invalid application bundle: unexpected={sorted(unexpected)}, missing={missing}")

# Reverse-DNS identifier. Nothing is signed or distributed from this repository,
# so this is a local identifier only; a real distribution needs an owned domain
# and a Developer ID, which is a requester decision, not an implementation one.
BUNDLE_ID = "com.refinix.desktop"


def frontend_data_files() -> list[tuple[str, list[str]]]:
    """Ship frontend/app exactly as the coordinator serves it."""
    root = REPO / "frontend" / "app"
    grouped: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        # The synthetic UI fixture and its Node check are development tools.
        if path.name in ("fixture.html", "fixture.js") or path.name.endswith(".cjs"):
            continue
        parent = path.relative_to(root).parent
        destination = "frontend/app" if parent == Path(".") else \
            str(Path("frontend/app") / parent)
        grouped.setdefault(destination, []).append(str(path))
    return sorted(grouped.items())


PLIST = {
    "CFBundleName": "Refinix",
    "CFBundleDisplayName": "Refinix",
    "CFBundleIdentifier": BUNDLE_ID,
    "CFBundleShortVersionString": VERSION,
    "CFBundleVersion": VERSION,
    "CFBundleExecutable": "Refinix",
    "NSHumanReadableCopyright": "Refinix. Runs entirely on this computer.",
    "LSApplicationCategoryType": "public.app-category.productivity",
    "LSMinimumSystemVersion": "12.0",
    # One Refinix per login session; the lock file in ~/.aegisforge covers a
    # copy started from a terminal instead.
    "LSMultipleInstancesProhibited": True,
    "NSHighResolutionCapable": True,
    "NSSupportsAutomaticGraphicsSwitching": True,
    # WKWebView applies App Transport Security. The window loads
    # http://127.0.0.1:<port>/, so local networking is allowed and nothing else
    # is: no arbitrary-loads exception is granted.
    "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
}

OPTIONS = {
    "bdist_base": str(REPO / "desktop" / "build"),
    "dist_dir": str(REPO / "desktop" / "dist"),
    "iconfile": str(REPO / "desktop" / "icons" / "Refinix.icns"),
    "plist": PLIST,
    # pywebview carries JS/native resources. Python application modules are
    # followed from imports; do not force-bundle worker code or test suites.
    "packages": ["webview"],
    "includes": ["backend.contracts.v1", "backend.coordinator.server",
                 "backend.coordinator.db", "backend.coordinator.runtime",
                 "backend.coordinator.context", "desktop.lifecycle", "desktop.shell"],
    "excludes": ["tkinter", "test", "unittest", "pydoc_data", "py2app",
                 "setuptools", "pip"],
    # py2app 0.28.10's optimized mode creates a dangling legacy site.pyo
    # symlink on Python 3.12, which fails codesign resource verification.
    "optimize": 0,
    "argv_emulation": False,
    "semi_standalone": False,
    "site_packages": False,
}

if __name__ == "__main__":
    if sys.platform != "darwin":
        sys.exit("py2app builds macOS bundles only. "
                 "See desktop/README.md for the Windows and Ubuntu paths.")
    sources = REPO / "desktop" / "build" / "sources"
    if sources.exists():
        shutil.rmtree(sources)
    stage_application_sources(sources)
    sys.path.insert(0, str(sources))
    previous = Path.cwd()
    try:
        # py2app get_bootstrap() prefers a same-named directory in cwd over
        # sys.path. Build here so its __file__ recipe cannot copy repo/backend.
        os.chdir(sources)
        distribution = setup(
            name="Refinix",
            version=VERSION,
            app=[{"script": str(REPO / "desktop" / "refinix.py"),
                  "dest_base": "Refinix", "plist": PLIST}],
            data_files=frontend_data_files(),
            options={"py2app": OPTIONS},
        )
        command = distribution.get_command_obj("py2app")
        if not command.alias:
            verify_application_contents(Path(command.dist_dir) / "Refinix.app")
    finally:
        os.chdir(previous)
