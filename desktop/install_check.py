"""Is an installed copy of Refinix exactly what was packaged?

`build.py` writes `_internal/refinix-files.json` into the Windows and Linux
packages: every shipped file with its size and SHA-256. After an update the
installed folder is compared with it — every listed file present and
unchanged, nothing else there except files the installer itself adds, and
the embedded identity naming the expected version. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

FILES_NAME = "refinix-files.json"
IDENTITY_NAME = "refinix-build.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_listing(root: Path) -> dict:
    """Every regular file under `root` except the listing itself."""
    root = Path(root)
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            relative = path.relative_to(root).as_posix()
            if relative == f"_internal/{FILES_NAME}":
                continue
            files[relative] = {"size": path.stat().st_size, "sha256": _sha256(path)}
    links = {path.relative_to(root).as_posix(): os.readlink(path)
             for path in sorted(root.rglob("*")) if path.is_symlink()}
    return {"files": files, "links": links}


def installed_identity(app: Path) -> dict | None:
    try:
        data = json.loads((Path(app) / "_internal" / IDENTITY_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def completeness_problem(app: Path, version: str, extras=frozenset()) -> str | None:
    """None when `app` is exactly the packaged `version`; otherwise why not."""
    app = Path(app)
    try:
        listing = json.loads((app / "_internal" / FILES_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return f"the installed file list cannot be read ({exc})"
    identity = installed_identity(app)
    if identity is None:
        return "the installed identity cannot be read"
    if identity.get("version") != version:
        return f"the installed identity names {identity.get('version')!r}, not {version!r}"
    files = listing.get("files") or {}
    links = listing.get("links") or {}
    for name, entry in files.items():
        path = app / Path(*name.split("/"))
        try:
            if path.is_symlink() or not path.is_file():
                return f"{name} is missing"
            if path.stat().st_size != entry["size"] or _sha256(path) != entry["sha256"]:
                return f"{name} is not the packaged file"
        except OSError as exc:
            return f"{name} cannot be read ({exc})"
    for name, target in links.items():
        path = app / Path(*name.split("/"))
        if not path.is_symlink() or os.readlink(path) != target:
            return f"{name} is not the packaged link"
    expected = set(files) | set(links) | {f"_internal/{FILES_NAME}"}
    for folder, dirs, names in os.walk(app, followlinks=False):
        for name in names + [d for d in dirs if (Path(folder) / d).is_symlink()]:
            relative = (Path(folder) / name).relative_to(app).as_posix()
            if relative not in expected and relative not in extras:
                return f"{relative} is not part of this version"
    return None
