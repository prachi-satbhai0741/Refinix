"""The one application version, and the identity of the build that is running.

`APP_VERSION` is the single source for the UI, the stored "last writer" value,
the package metadata and update compatibility. A packaged build also carries an
embedded `refinix-build.json` written by `desktop/build.py`; it records the
build set, channel, source and input digests and the engine identity. That
embedded record deliberately never contains the SHA-256 of the package that
encloses it — the external artifact record next to the package holds that.

Standard library only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP_VERSION = "0.1.0"

BUILD_IDENTITY_NAME = "refinix-build.json"


def _resource_roots() -> list[Path]:
    roots = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)          # PyInstaller
        if meipass:
            roots.append(Path(meipass))
        roots.append(Path(sys.prefix))                     # py2app Resources
        roots.append(Path(sys.executable).resolve().parent)
    return roots


def embedded_identity() -> dict | None:
    """The build identity shipped inside this package, or None from source."""
    for root in _resource_roots():
        candidate = root / BUILD_IDENTITY_NAME
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return None


def describe() -> dict:
    """What the status surface may say about this build."""
    identity = embedded_identity() or {}
    return {
        "version": identity.get("version", APP_VERSION),
        "channel": identity.get("channel", "development"),
        "build_set": identity.get("build_set"),
        "signing": identity.get("signing"),
        "source_digest": identity.get("source_digest"),
        "packaged": bool(getattr(sys, "frozen", False)),
    }
