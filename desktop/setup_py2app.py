"""Build Refinix.app with py2app.

Run from the repository root, on macOS, in an environment where the pinned
desktop requirements are installed:

    python3 desktop/setup_py2app.py py2app          # release bundle
    python3 desktop/setup_py2app.py py2app -A       # alias build, for a quick check

This file is a script, run by path — `desktop/setup-macos.command` runs exactly
the first line above. It is not imported as `desktop.setup_py2app`, and its
imports are written for the path a script gets, not the one a package gets.

The alias build (`-A`) symlinks back into this working tree, so it proves the
window and the launch path but NOT independence from the repository. Only the
plain `py2app` build produces a bundle that stands on its own; the acceptance
check for that is in desktop/README.md.

The bundle carries the frontend and the icon. It does not carry a model, the
model runtime, or any state: `backend.coordinator.paths` chooses the durable
root, which is always outside the bundle, so an existing database, identity and
history are picked up unchanged and survive the application being replaced.

The application boundary itself — which modules, which frontend files, which
icon — lives in `desktop/packaging_plan.py`, shared with the Windows and Linux
package steps so the three describe the same application.
"""

from __future__ import annotations

import os
import sys
import shutil
import zipfile
from pathlib import Path

from setuptools import setup

# `desktop/setup-macos.command` executes this file, it does not import it, so
# sys.path[0] is the directory this file is in and the repository root is not
# on the path at all: the application boundary resolves as a sibling module.
# `from desktop import packaging_plan` would fail here before the build starts.
import packaging_plan

REPO = packaging_plan.REPO
VERSION = packaging_plan.VERSION
APPLICATION_PACKAGES = packaging_plan.APPLICATION_PACKAGES
BUNDLE_ID = packaging_plan.BUNDLE_ID

# The application boundary — which modules, which frontend files, which icon —
# lives in `desktop/packaging_plan.py` so a Windows or Linux packaging step uses the
# same answers instead of a second hand-maintained list.
stage_application_sources = packaging_plan.stage_application_sources
frontend_data_files = packaging_plan.frontend_data_files


def verify_application_contents(bundle: Path) -> None:
    """Check both loose packages and the ZIP, not just the staging directory."""
    library = bundle / "Contents" / "Resources" / "lib"
    shipped = set()
    for root in library.glob("python3.*"):
        for package in ("backend", "desktop"):
            shipped.update(path.relative_to(root).as_posix()
                           for path in (root / package).rglob("*")
                           if path.is_file())
    for archive in library.glob("python*.zip"):
        with zipfile.ZipFile(archive) as files:
            shipped.update(name for name in files.namelist()
                           if name.startswith(("backend/", "desktop/")) and not name.endswith("/"))
    unexpected = packaging_plan.unexpected_shipped_files(shipped)
    missing = packaging_plan.missing_shipped_files(
        shipped, ("backend/coordinator/server.py", "backend/contracts/v1.py",
                  "desktop/shell.py"))
    if unexpected or missing:
        raise RuntimeError(f"Invalid application bundle: unexpected={unexpected}, missing={missing}")


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
    "iconfile": str(packaging_plan.icon_for("macos")),
    "plist": PLIST,
    # pywebview carries JS/native resources, and pypdfium2 ships the PDFium
    # binary as package data (`pypdfium2_raw/libpdfium.dylib`). Both must be
    # copied whole: modulegraph follows imports, not data files, so naming them
    # only in `includes` would ship an application whose Documents surface
    # reports PDF unavailable on a Mac that has the renderer installed.
    # Python application modules are followed from imports; do not force-bundle
    # worker code or test suites.
    "packages": ["webview", "pypdfium2", "pypdfium2_raw"],
    "includes": ["backend.contracts.v1", "backend.coordinator.server",
                 "backend.coordinator.db", "backend.coordinator.runtime",
                 "backend.coordinator.context", "desktop.lifecycle", "desktop.shell",
                 # C08. `pdfrender` imports both renderers lazily so the module
                 # stays importable where neither is present — which also means
                 # modulegraph cannot see either dependency and would ship an
                 # application that reports PDF unavailable on a Mac that has
                 # one. Quartz is the retained macOS fallback; the portable
                 # PDFium engine is in `packages` above because it carries a
                 # binary. Already pinned in requirements-macos.lock
                 # (pyobjc-framework-quartz 12.2.2, MIT; pypdfium2 5.13.0,
                 # BSD-3-Clause/Apache-2.0).
                 "Quartz", "objc",
                 "backend.coordinator.pdfrender", "backend.coordinator.ocr",
                 "backend.coordinator.proof"],
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
