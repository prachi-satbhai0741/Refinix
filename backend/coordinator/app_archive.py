"""Expanding a verified Refinix package into a folder, without trusting its layout.

The package's bytes are already authenticated by the update metadata before
anything here runs. These checks are the second line: a signed but malformed
archive still must not write outside its folder, create a device or a setuid
file, exhaust the disk, or install something other than a Refinix app.

    inspect   read the archive's listing only and decide whether every entry is
              acceptable: one top-level `Refinix.app/`, bounded counts and
              sizes, ordinary names, directories, regular files and symlinks
              only, and every symlink resolving inside the app through a
              bounded, acyclic chain. AppleDouble (`._*`, `__MACOSX`) entries
              carry Finder metadata only and are skipped.
    extract   write exactly the checked listing into a new private folder:
              directories 0755, executables 0755, other files 0644, links last.
    check_tree  walk what was written (lstat, never following a link) and
              compare it with the listing.
    verify_bundle  the app's own identity: bundle id, embedded build identity,
              the shipped trust root (this build's own, or a newer root the
              update client authenticated starting from it), the code-signature
              seal, the publisher's Team ID for a signed Beta build, and the
              shipped engine files.

Standard library plus the engine verifier already in the application.
"""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import posixpath
import shutil
import stat
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

TOP = "Refinix.app"
BUNDLE_ID = "com.refinix.desktop"
IDENTITY_NAME = "refinix-build.json"
ROOT_FILE = "refinix-update-root.json"
MAX_ENTRIES = 10_000
MAX_TOTAL_BYTES = 2 * 1024 ** 3
MAX_TOTAL_RATIO = 8                     # uncompressed total / archive size
MAX_ENTRY_RATIO = 200                   # for entries of at least RATIO_FLOOR bytes
RATIO_FLOOR = 1024 * 1024
MAX_LINK_HOPS = 8
MAX_LINK_TARGET = 1024
CHUNK = 1024 * 1024


class ArchiveError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Entry:
    name: str                           # normalised, no trailing slash
    kind: str                           # dir | file | link
    executable: bool = False
    size: int = 0
    target: str | None = None
    info: zipfile.ZipInfo | None = field(default=None, repr=False)


@dataclass
class Listing:
    entries: dict[str, Entry]
    total_bytes: int
    archive_bytes: int

    @property
    def files(self) -> list[Entry]:
        return [e for e in self.entries.values() if e.kind == "file"]


def _apple_double(name: str) -> bool:
    parts = name.rstrip("/").split("/")
    return parts[0] == "__MACOSX" or any(part.startswith("._") for part in parts)


def _clean_name(raw: str) -> str:
    if not raw or "\\" in raw or "\x00" in raw or raw.startswith("/"):
        raise ArchiveError("unsafe_name", f"The package names an unsafe path: {raw!r}.")
    name = raw[:-1] if raw.endswith("/") else raw
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ArchiveError("unsafe_name", f"The package names an unsafe path: {raw!r}.")
    if parts[0] != TOP:
        raise ArchiveError("not_refinix", "The package holds something other than "
                                          f"one {TOP}.")
    return name


def inspect(path: Path) -> Listing:
    """Decide from the listing alone whether the archive may be expanded."""
    path = Path(path)
    archive_bytes = path.stat().st_size
    entries: dict[str, Entry] = {}
    seen: set[str] = set()
    total = 0
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ArchiveError("unreadable", f"The package cannot be read: {exc}") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES * 2:
            raise ArchiveError("too_many", "The package has too many entries.")
        for info in infos:
            if _apple_double(info.filename):
                continue
            name = _clean_name(info.filename)
            folded = name.casefold()
            if folded in seen:
                raise ArchiveError("duplicate", f"The package names {name} twice.")
            seen.add(folded)
            mode = info.external_attr >> 16
            kind_bits = stat.S_IFMT(mode)
            if mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX):
                raise ArchiveError("special_mode", f"{name} asks for a privileged mode.")
            if info.is_dir():
                if kind_bits not in (0, stat.S_IFDIR):
                    raise ArchiveError("special_file", f"{name} is not a plain folder.")
                entries[name] = Entry(name, "dir", info=info)
                continue
            if kind_bits == stat.S_IFLNK:
                if info.file_size > MAX_LINK_TARGET:
                    raise ArchiveError("unsafe_link", f"{name} is not a usable link.")
                try:
                    target = archive.read(info).decode("utf-8")
                except (UnicodeDecodeError, zipfile.BadZipFile) as exc:
                    raise ArchiveError("unsafe_link", f"{name} is not a usable link.") from exc
                entries[name] = Entry(name, "link", target=target, info=info)
                continue
            if kind_bits not in (0, stat.S_IFREG):
                raise ArchiveError("special_file", f"{name} is not a regular file.")
            if info.file_size >= RATIO_FLOOR and info.compress_size and \
                    info.file_size / info.compress_size > MAX_ENTRY_RATIO:
                raise ArchiveError("ratio", f"{name} expands far more than an app file.")
            total += info.file_size
            entries[name] = Entry(name, "file", executable=bool(mode & 0o111),
                                  size=info.file_size, info=info)
    if not entries:
        raise ArchiveError("not_refinix", f"The package holds no {TOP}.")
    if len(entries) > MAX_ENTRIES:
        raise ArchiveError("too_many", f"The package has more than {MAX_ENTRIES} entries.")
    if total > MAX_TOTAL_BYTES or total > MAX_TOTAL_RATIO * max(archive_bytes, 1):
        raise ArchiveError("too_large", "The package would expand to more than an app "
                                        "of this size can.")
    listing = Listing(entries, total, archive_bytes)
    _complete_folders(listing)
    for entry in listing.entries.values():
        if entry.kind == "link":
            resolve_link(listing, entry.name)
    return listing


def _complete_folders(listing: Listing) -> None:
    """Add implied folders; refuse a path that passes through a file or a link."""
    folded = {name.casefold(): name for name in listing.entries}
    for name in list(listing.entries):
        parent = posixpath.dirname(name)
        while parent:
            existing = listing.entries.get(parent)
            if existing is None:
                if parent.casefold() in folded:
                    raise ArchiveError("duplicate", f"The package names {parent} twice.")
                listing.entries[parent] = Entry(parent, "dir")
                folded[parent.casefold()] = parent
            elif existing.kind != "dir":
                raise ArchiveError("unsafe_name", f"{name} would be written through "
                                                  f"{parent}, which is not a folder.")
            parent = posixpath.dirname(parent)
    top = listing.entries.get(TOP)
    if top is None or top.kind != "dir":
        raise ArchiveError("not_refinix", f"{TOP} is not a folder.")


def _inside(name: str) -> bool:
    return name == TOP or name.startswith(TOP + "/")


def resolve_link(listing: Listing, name: str) -> str:
    """Where a link finally points, inside the app, or ArchiveError."""
    hops = 0
    visited: set[str] = set()
    path = name
    while True:
        parts = path.split("/")
        current = ""
        for index, part in enumerate(parts):
            current = part if not current else f"{current}/{part}"
            entry = listing.entries.get(current)
            if entry is None:
                raise ArchiveError("unsafe_link", f"The link {name} points at something "
                                                  "the package does not contain.")
            if entry.kind != "link":
                continue
            if current in visited:
                raise ArchiveError("unsafe_link", f"The link {name} is part of a loop.")
            visited.add(current)
            hops += 1
            if hops > MAX_LINK_HOPS:
                raise ArchiveError("unsafe_link", f"The link {name} passes through too "
                                                  "many other links.")
            target = entry.target or ""
            if not target or target.startswith("/") or "\\" in target or "\x00" in target:
                raise ArchiveError("unsafe_link", f"The link {name} is not relative.")
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(current), target))
            if not _inside(resolved):
                raise ArchiveError("unsafe_link", f"The link {name} points outside {TOP}.")
            rest = "/".join(parts[index + 1:])
            path = f"{resolved}/{rest}" if rest else resolved
            break
        else:
            return path


def extract(path: Path, listing: Listing, destination: Path) -> Path:
    """Write the checked listing into `destination`, which must not exist yet."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ArchiveError("exists", f"{destination} already exists.")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.mkdir(mode=0o700)
    ordered = sorted(listing.entries.values(), key=lambda e: e.name.count("/"))
    for entry in ordered:
        if entry.kind == "dir":
            (destination / entry.name).mkdir(mode=0o755, exist_ok=True)
            os.chmod(destination / entry.name, 0o755)
    with zipfile.ZipFile(path) as archive:
        for entry in listing.files:
            target = destination / entry.name
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            mode = 0o755 if entry.executable else 0o644
            descriptor = os.open(target, flags, 0o600)
            written = 0
            with os.fdopen(descriptor, "wb") as out, archive.open(entry.info) as source:
                for block in iter(lambda: source.read(CHUNK), b""):
                    written += len(block)
                    if written > entry.size:
                        raise ArchiveError("size", f"{entry.name} is larger than listed.")
                    out.write(block)
            if written != entry.size:
                raise ArchiveError("size", f"{entry.name} is smaller than listed.")
            os.chmod(target, mode)
    for entry in listing.entries.values():
        if entry.kind == "link":
            os.symlink(entry.target, destination / entry.name)
    return destination / TOP


def check_tree(root: Path, listing: Listing) -> None:
    """What was written is exactly the listing: kinds, sizes, links, nothing else."""
    root = Path(root)
    found: dict[str, str] = {}
    for folder, dirs, files in os.walk(root / TOP, followlinks=False):
        for name in dirs + files:
            full = Path(folder) / name
            relative = full.relative_to(root).as_posix()
            if _apple_double(relative):
                raise ArchiveError("tree", f"{relative} was not expected.")
            info = os.lstat(full)
            if stat.S_ISLNK(info.st_mode):
                found[relative] = "link"
                entry = listing.entries.get(relative)
                if entry is None or entry.kind != "link" or os.readlink(full) != entry.target:
                    raise ArchiveError("tree", f"{relative} is not the expected link.")
            elif stat.S_ISDIR(info.st_mode):
                found[relative] = "dir"
            elif stat.S_ISREG(info.st_mode):
                found[relative] = "file"
                entry = listing.entries.get(relative)
                if entry is None or entry.kind != "file" or info.st_size != entry.size:
                    raise ArchiveError("tree", f"{relative} does not match the package.")
                if info.st_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX):
                    raise ArchiveError("tree", f"{relative} has a privileged mode.")
            else:
                raise ArchiveError("tree", f"{relative} is not a plain file.")
    expected = {name: e.kind for name, e in listing.entries.items() if name != TOP}
    if found != expected:
        missing = sorted(set(expected) - set(found))[:3]
        extra = sorted(set(found) - set(expected))[:3]
        raise ArchiveError("tree", f"The expanded app differs from the package "
                                   f"(missing {missing}, unexpected {extra}).")
    for name, entry in listing.entries.items():
        if entry.kind == "link":
            resolve_link(listing, name)


def _codesign(app: Path) -> str | None:
    """The seal check; None when intact. Integrity only, not publisher identity."""
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict",
                                 str(app)], capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"the signature check could not run: {exc}"
    if result.returncode != 0:
        return (result.stderr or result.stdout or "the seal is broken").strip()[:400]
    return None


def _team_requirement(app: Path, team_id: str) -> str | None:
    """Developer ID from this Team ID; None when the requirement is met."""
    if sys.platform != "darwin":
        return "a signed macOS app can only be checked on macOS"
    requirement = ("=anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] "
                   "and certificate leaf[field.1.2.840.113635.100.6.1.13] and "
                   f'certificate leaf[subject.OU] = "{team_id}"')
    try:
        result = subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict",
                                 f"-R{requirement}", str(app)], capture_output=True,
                                text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"the publisher check could not run: {exc}"
    if result.returncode != 0:
        return (result.stderr or result.stdout or "another publisher").strip()[:400]
    return None


def bundle_identity(app: Path) -> dict | None:
    try:
        data = json.loads((Path(app) / "Contents" / "Resources" / IDENTITY_NAME)
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def verify_bundle(app: Path, *, version: str, lane: str, channel: str,
                  trust_root: str | None = None, trust_roots=None, publisher: str | None = None,
                  codesign=_codesign, team_check=_team_requirement) -> dict:
    """The expanded app is the offered Refinix and is intact. Returns its identity.

    `trust_roots` are the roots it may ship: the running build's own and any
    newer root authenticated from it (`UpdateService.accepted_roots`). The
    older single `trust_root` form means exactly that one root.
    """
    app = Path(app)
    try:
        info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    except (OSError, ValueError, plistlib.InvalidFileException) as exc:
        raise ArchiveError("not_refinix", f"The app's Info.plist cannot be read: {exc}") from exc
    if info.get("CFBundleIdentifier") != BUNDLE_ID:
        raise ArchiveError("not_refinix", "The package is not the Refinix app.")
    executable = app / "Contents" / "MacOS" / str(info.get("CFBundleExecutable") or "")
    if not executable.is_file() or executable.is_symlink():
        raise ArchiveError("not_refinix", "The app's program is missing.")
    identity = bundle_identity(app)
    if identity is None:
        raise ArchiveError("identity", "The app carries no build identity.")
    for key, wanted in (("version", version), ("lane", lane), ("channel", channel)):
        if identity.get(key) != wanted:
            raise ArchiveError("identity", f"The app's {key.replace('_', ' ')} "
                                           f"({identity.get(key)}) is not the offered "
                                           f"one ({wanted}).")
    accepted = set(trust_roots) if trust_roots is not None else {trust_root}
    shipped = identity.get("trust_root")
    if shipped not in accepted:
        raise ArchiveError("identity", "The app trusts an update root that is neither this "
                                       "build's nor a newer one authenticated from it.")
    if shipped is not None:
        root_file = app / "Contents" / "Resources" / ROOT_FILE
        try:
            digest = hashlib.sha256(root_file.read_bytes()).hexdigest()
        except OSError as exc:
            raise ArchiveError("identity", "The app's update trust root is missing.") from exc
        if digest != shipped:
            raise ArchiveError("identity", "The app's update trust root is not the one "
                                           "its identity names.")
    problem = codesign(app)
    if problem:
        raise ArchiveError("seal", f"The app's code seal does not verify: {problem}")
    if publisher:
        problem = team_check(app, publisher)
        if problem:
            raise ArchiveError("publisher", f"The app is not signed by the expected "
                                            f"publisher: {problem}")
    from backend.coordinator import engine as engine_module
    for item in identity.get("engines") or []:
        root = app / "Contents" / "Resources" / "engine" / str(item.get("lane"))
        try:
            problems = engine_module.verify(root, engine_module.load_manifest(root))
        except engine_module.EngineError as exc:
            problems = [str(exc)]
        if problems:
            raise ArchiveError("engine", f"The app's engine failed verification: "
                                         f"{problems[:2]}")
    return identity


def remove_tree(path: Path) -> None:
    """Remove a staging folder this module created; never follows links."""
    path = Path(path)
    if path.is_symlink():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)
