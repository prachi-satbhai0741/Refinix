"""Fetch and verify the pinned app-managed inference engine for one build lane.

Used by local development, `desktop/build.py` and CI alike, so every package is
built from the same verified engine bytes:

    python desktop/engine/fetch.py --lane macos-arm64
    python desktop/engine/fetch.py --lane windows-x64-vulkan --cache .engine-cache

Only the exact URL in `engine-pins.json` is fetched. The archive must match the
pinned size and SHA-256 before anything is extracted, extraction refuses
absolute paths, `..` and links, and the result is described by a generated
`engine-manifest.json` that lists every shipped file with its size and SHA-256.
The application re-verifies those files before every engine launch.

The binaries are never committed: `desktop/engine/dist/` is ignored.

Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
PINS = HERE / "engine-pins.json"
DIST = HERE / "dist"
MANIFEST_NAME = "engine-manifest.json"
EXECUTABLES = ("llama-server", "llama-server.exe")
CHUNK = 1024 * 1024


class FetchError(RuntimeError):
    pass


def load_pins(path: Path = PINS) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(url: str, target: Path) -> None:
    if not url.startswith("https://"):
        raise FetchError(f"refusing a non-HTTPS engine URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "refinix-build"})
    with urllib.request.urlopen(request, timeout=120) as response, \
            open(target, "wb") as out:
        shutil.copyfileobj(response, out, CHUNK)


def obtain_archive(lane: dict, cache: Path, *, offline: bool = False) -> Path:
    """Return a cached archive whose bytes match the pin, downloading if needed."""
    cache.mkdir(parents=True, exist_ok=True)
    name = PurePosixPath(lane["url"]).name
    archive = cache / f"{lane['sha256']}-{name}"
    if archive.exists() and archive.stat().st_size == lane["size"] \
            and sha256_file(archive) == lane["sha256"]:
        return archive
    if offline:
        raise FetchError(f"{name} is not in the cache and --offline was given")
    partial = archive.with_suffix(archive.suffix + ".part")
    _download(lane["url"], partial)
    size, digest = partial.stat().st_size, sha256_file(partial)
    if size != lane["size"] or digest != lane["sha256"]:
        partial.unlink(missing_ok=True)
        raise FetchError(f"{name}: expected {lane['size']} bytes sha256 "
                         f"{lane['sha256']}, got {size} bytes sha256 {digest}")
    os.replace(partial, archive)
    return archive


def _safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise FetchError(f"unsafe path in engine archive: {name!r}")
    return path


def extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                member = _safe_member(info.filename)
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise FetchError(f"symbolic link in engine archive: {info.filename}")
                target = destination.joinpath(*member.parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out, CHUNK)
        return
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            _safe_member(member.name)
            if member.issym() or member.islnk():
                # Upstream macOS/Linux archives carry versioned shared-library
                # links (libfoo.dylib -> libfoo.0.dylib). They are accepted only
                # when they point at a sibling inside the same folder.
                link = PurePosixPath(member.linkname)
                if link.is_absolute() or ".." in link.parts or len(link.parts) != 1:
                    raise FetchError(f"link leaving its folder: {member.name}")
            elif not (member.isfile() or member.isdir()):
                raise FetchError(f"unsupported entry in engine archive: {member.name}")
        bundle.extractall(destination, filter="data")


def describe(root: Path, pins: dict, lane_key: str) -> dict:
    lane = pins["lanes"][lane_key]
    files, executables = [], []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            files.append({"path": path.relative_to(root).as_posix(),
                          "link": os.readlink(path)})
            continue
        if not path.is_file() or path.name == MANIFEST_NAME:
            continue
        relative = path.relative_to(root).as_posix()
        files.append({"path": relative, "size": path.stat().st_size,
                      "sha256": sha256_file(path)})
        if path.name in EXECUTABLES:
            executables.append(relative)
    if len(executables) != 1:
        raise FetchError(f"expected exactly one llama-server in the archive, found {executables}")
    return {
        "manifest_version": 1, "kind": pins["kind"], "component": pins["component"],
        "release": pins["release"], "commit": pins["commit"], "licence": pins["licence"],
        "source": pins["source"], "lane": lane_key, "backend": lane["backend"],
        "archive_sha256": lane["sha256"], "executable": executables[0],
        "pins_sha256": hashlib.sha256(PINS.read_bytes()).hexdigest(),
        "files": files,
    }


def fetch(lane_key: str, *, destination: Path | None = None, cache: Path | None = None,
          offline: bool = False, pins: dict | None = None) -> dict:
    pins = pins or load_pins()
    if lane_key not in pins["lanes"]:
        raise FetchError(f"unknown lane {lane_key!r}; known: {sorted(pins['lanes'])}")
    destination = destination or DIST / lane_key
    cache = cache or Path(tempfile.gettempdir()) / "refinix-engine-cache"
    archive = obtain_archive(pins["lanes"][lane_key], cache, offline=offline)
    staging = Path(tempfile.mkdtemp(prefix="refinix-engine-"))
    try:
        extract(archive, staging)
        # Flatten the single top-level folder upstream archives use.
        entries = [p for p in staging.iterdir()]
        root = entries[0] if len(entries) == 1 and entries[0].is_dir() else staging
        manifest = describe(root, pins, lane_key)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(root, destination, symlinks=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    (destination / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lane", required=True)
    parser.add_argument("--dest", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = fetch(args.lane, destination=args.dest, cache=args.cache,
                         offline=args.offline)
    except FetchError as exc:
        print(f"engine fetch failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"lane": manifest["lane"], "release": manifest["release"],
                      "executable": manifest["executable"],
                      "files": len(manifest["files"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
