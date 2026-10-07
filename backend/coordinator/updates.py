"""Settings → Updates: checked only when asked, verified before anything runs.

The update metadata is TUF (python-tuf's client). A package carries the
publisher's trust root (`refinix-update-root.json`) and, for a channel that
has one, where its updates come from (`refinix-update-feed.json`): an HTTPS
feed, or — on the internal test channel only — a local update folder. Both are
placed in the package at build time beside `refinix-build.json`; a source
checkout or a package built without them reports that it cannot check for
updates rather than pretending to be up to date.

Per channel and lane the repository signs one small target,
`<channel>/<lane>/latest.json`, naming the offered version and its package
target. The client:

1. **Checks** only when the person presses Check for updates. Online it fetches
   TUF metadata and that one target; nothing about this computer, its work or
   its models is sent. The internal update folder is read in place: the
   metadata inside each bundle is verified without unpacking it.
2. **Offers** an update only when its lane and channel match this build, its
   version is newer, and its data format can be opened by it.
3. **Downloads** (or, for a bundle, copies) the package into a staging folder
   with TUF verifying length and SHA-256; a partial or mismatched file is
   discarded and never offered. Beside it the signed metadata that
   authenticated it is kept as evidence.
4. **Imports** an offline bundle (metadata plus package, for example from a
   USB drive) through the same client, trust root and checks.
5. **Prepares an install** without the network: the kept signed evidence is
   verified again from the installed trust root (signatures, root rotation,
   version links, lengths and hashes — not the clock, because the download was
   already verified while its metadata was current), the staged bytes are
   hashed again, and the package is expanded and checked by `app_archive`.
   Replacing the app and restarting is the desktop shell's and the update
   helper's job (`desktop/update_apply.py`).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from backend.coordinator import build_info

TRUST_ROOT_NAME = "refinix-update-root.json"
FEED_NAME = "refinix-update-feed.json"
LATEST = "latest.json"
BUNDLE_SCHEME = "refinix-bundle"
EVIDENCE = "evidence"
RECORD = "record.json"
CHUNK = 256 * 1024

# The internal update folder and the bundles in it.
BUNDLE_FILE = re.compile(r"Refinix-[A-Za-z0-9.+-]+-update\.zip")
MAX_FOLDER_FILES = 32
MAX_BUNDLE_BYTES = 2 * 1024 ** 3 + 8 * 1024 ** 2
MAX_BUNDLE_MEMBERS = 64
MAX_JSON_MEMBER = 1024 ** 2
BUNDLE_SLACK = 8 * 1024 ** 2
MEMBER = re.compile(r"metadata/(?:\d+\.root|root|timestamp|snapshot|targets)\.json"
                    r"|targets/[a-z]+/[a-z0-9-]+/[A-Za-z0-9._+-]+")

# Installing: which lanes have a helper in this application, and the test-only
# install root an internal build may also use.
CAPABILITIES = ("qualified", "internal-test", "unavailable")
HELPER_PLATFORMS = {"macos-arm64": "darwin"}
TEST_INSTALL_ROOT = "REFINIX_TEST_INSTALL_ROOT"
INSTALL_MARGIN = 256 * 1024 ** 2

INSTALL_NOTE = ("Install and restart closes Refinix, replaces the app with the verified "
                "version and opens it again. Your conversations, documents and models "
                "are kept, and the previous version is kept for going back.")


class UpdateError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def version_key(text: str) -> tuple:
    """Order `1.2.3`, `1.2.3-internal.4`, `1.2.3-beta.2`; a release sorts last."""
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-([a-z]+)\.(\d+))?", str(text or ""))
    if not match:
        raise ValueError(f"not a Refinix version: {text!r}")
    major, minor, patch, tag, number = match.groups()
    pre = (0, tag, int(number)) if tag else (1, "", 0)
    return (int(major), int(minor), int(patch), pre)


def bundled(name: str) -> Path | None:
    for root in build_info._resource_roots():
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def _sha256_file(path: Path, limit: int | None = None) -> str:
    digest, seen = hashlib.sha256(), 0
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            seen += len(block)
            if limit is not None and seen > limit:
                raise UpdateError("bad_bundle", "The file is larger than an update can be.")
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@dataclass
class Download:
    version: str
    target: str
    state: str = "running"                     # running | verified | failed | cancelled
    bytes_done: int = 0
    bytes_total: int = 0
    path: str | None = None
    error: str | None = None
    source: str = "https"
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def as_dict(self) -> dict:
        return {"version": self.version, "state": self.state, "bytes_done": self.bytes_done,
                "bytes_total": self.bytes_total, "path": self.path, "error": self.error,
                "source": self.source}


def _fetcher_classes():
    from tuf.api import exceptions
    from tuf.ngclient import FetcherInterface

    class Watched(FetcherInterface):
        progress = None                            # (bytes) -> None
        cancelled = None                           # () -> bool

        def _watch(self, blocks):
            for block in blocks:
                if self.cancelled is not None and self.cancelled():
                    raise exceptions.DownloadError("cancelled")
                if self.progress is not None:
                    self.progress(len(block))
                yield block

    class HttpsFetcher(Watched):
        """HTTPS only, OS-backed certificate verification, progress and Stop."""

        def __init__(self, pool=None):
            self._pool = pool

        def _fetch(self, url: str):
            if urlsplit(url).scheme != "https":
                raise exceptions.DownloadError(f"refusing a non-HTTPS update URL: {url}")
            if self._pool is None:
                from backend.coordinator import provisioning
                self._pool = provisioning._pool()
            response = self._pool.request("GET", url, preload_content=False,
                                          redirect=False)
            if response.status in (301, 302, 303, 307, 308):
                response.release_conn()
                raise exceptions.DownloadHTTPError(
                    f"the update server redirected the request (answer "
                    f"{response.status}); a sign-in page or proxy may be in the way",
                    response.status)
            if response.status >= 400:
                response.release_conn()
                raise exceptions.DownloadHTTPError(
                    f"the update server answered {response.status}", response.status)
            return self._watch(self._chunks(response))

        @staticmethod
        def _chunks(response):
            try:
                yield from response.stream(CHUNK)
            finally:
                response.release_conn()

    class BundleFetcher(Watched):
        """Serves `refinix-bundle:///<member>` from an open bundle, in chunks."""

        def __init__(self, archive: zipfile.ZipFile):
            self.archive = archive

        def _fetch(self, url: str):
            parts = urlsplit(url)
            if parts.scheme != BUNDLE_SCHEME:
                raise exceptions.DownloadError(f"not a bundle URL: {url}")
            name = parts.path.lstrip("/")
            try:
                info = self.archive.getinfo(name)
            except KeyError:
                raise exceptions.DownloadHTTPError(
                    "this bundle has no update for this kind of computer or channel",
                    404) from None
            return self._watch(self._chunks(info))

        def _chunks(self, info):
            with self.archive.open(info) as handle:
                yield from iter(lambda: handle.read(CHUNK), b"")

    return HttpsFetcher, BundleFetcher


def bundle_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """The outer bundle's listing, refused unless it is a plain small update bundle."""
    infos = archive.infolist()
    if len(infos) > MAX_BUNDLE_MEMBERS:
        raise UpdateError("bad_bundle", "The bundle holds more files than an update does.")
    members, total = {}, 0
    for info in infos:
        name = info.filename
        mode = info.external_attr >> 16
        if (info.is_dir() or not MEMBER.fullmatch(name) or ".." in name
                or (mode and (mode & 0o170000) not in (0, 0o100000))):
            raise UpdateError("bad_bundle", f"The bundle contains an unsafe or unexpected "
                                            f"path: {name!r}.")
        if name in members:
            raise UpdateError("bad_bundle", f"The bundle names {name} twice.")
        if name.endswith(".json") and info.file_size > MAX_JSON_MEMBER:
            raise UpdateError("bad_bundle", f"{name} is larger than update information is.")
        total += info.file_size
        members[name] = info
    if total > MAX_BUNDLE_BYTES:
        raise UpdateError("bad_bundle", "The bundle is larger than an update can be.")
    return members


def _plain(exc: Exception) -> str:
    """A TUF or network failure, in words a person can act on."""
    name = type(exc).__name__
    text = str(exc) or name
    if "Expired" in name:
        return "The update information has expired, so it was not trusted."
    if "RepositoryError" in name or "BadVersionNumber" in name or "Unsigned" in name:
        return f"The update information failed verification: {text}"
    if "non-HTTPS" in text:
        return "The update source is not an HTTPS address, so it was not used."
    if "LengthOrHash" in name:
        return "The downloaded package did not match its signed size or SHA-256."
    return text


def unreachable(exc: Exception) -> str | None:
    """Why the update server could not be reached, or None for other failures.

    A verification failure (expired, unsigned, rolled back, wrong length or
    hash) is never a connectivity problem. tuf wraps a network error as
    `DownloadError("Failed to download …")` with the cause chained, so the
    whole chain is read.
    """
    chain, seen, current = [], set(), exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    names = {type(item).__name__ for item in chain}
    if names & {"RepositoryError", "ExpiredMetadataError", "BadVersionNumberError",
                "EqualVersionNumberError", "UnsignedMetadataError",
                "LengthOrHashMismatchError", "DownloadLengthMismatchError",
                "UpdateError"}:
        return None
    lowered = " | ".join(f"{type(item).__name__}: {item}" for item in chain).lower()
    if "non-https" in lowered:
        return None
    if "redirected" in lowered:
        return next(str(item) for item in chain if "redirected" in str(item))
    if "sslerror" in lowered or "certificate" in lowered or "ssl:" in lowered:
        return ("the secure connection failed — a Wi-Fi sign-in page, proxy or "
                "firewall may be intercepting it")
    if ("nameresolution" in lowered or "nodename nor servname" in lowered
            or "name or service not known" in lowered
            or "temporary failure in name resolution" in lowered
            or "getaddrinfo" in lowered):
        return "the update server's name could not be looked up (no internet?)"
    if "timed out" in lowered or "timeouterror" in lowered or "readtimeout" in lowered \
            or "connecttimeout" in lowered:
        return "the update server did not answer in time"
    if ("network is unreachable" in lowered or "no route to host" in lowered
            or "connection refused" in lowered or "newconnectionerror" in lowered
            or "maxretryerror" in lowered or "connectionerror" in lowered
            or "connection reset" in lowered or "protocolerror" in lowered):
        return "this computer could not connect to the update server"
    for item in chain:
        if type(item).__name__ == "DownloadHTTPError":
            return str(item)
    return None


# --------------------------------------------------------------------------
# The kept evidence, verified again without the network
# --------------------------------------------------------------------------

def _metadata(data: bytes, role: str):
    from tuf.api.metadata import Metadata
    try:
        item = Metadata.from_bytes(data)
    except Exception as exc:                               # noqa: BLE001
        raise UpdateError("evidence", f"Kept {role} metadata cannot be read: {exc}") from exc
    if item.signed.type != role:
        raise UpdateError("evidence", f"Kept {role} metadata is of another kind.")
    return item


def _next_root(current, data: bytes):
    """One step of root rotation: exactly the next version, both thresholds met."""
    item = _metadata(data, "root")
    if item.signed.version != current.signed.version + 1:
        raise UpdateError("evidence", "The kept root versions are not consecutive.")
    try:
        current.signed.verify_delegate("root", item.signed_bytes, item.signatures)
        item.signed.verify_delegate("root", item.signed_bytes, item.signatures)
    except Exception as exc:                               # noqa: BLE001
        raise UpdateError("evidence", f"A kept root is not properly signed: {exc}") from exc
    return item


def verify_evidence(staged: Path, *, anchor: bytes, local_metadata: Path | None = None) -> dict:
    """Authenticate a staged package from its kept signed metadata, offline.

    Verifies, from the installed trust anchor: each kept root version in turn
    (consecutive, old and new thresholds), continuing through any newer root
    this client has trusted since; timestamp, snapshot and targets signatures
    under that newest root; the version links timestamp → snapshot → targets
    and any declared lengths and hashes; the kept `latest.json` bytes against
    their signed target entry before reading them; and the staged package
    bytes against the package's signed target entry. Metadata expiry is not
    judged here: it was judged when the package was downloaded or imported.
    """
    staged = Path(staged)
    evidence = staged / EVIDENCE
    try:
        record = json.loads((evidence / RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UpdateError("evidence", "The kept verification record is missing.") from exc
    if not isinstance(record, dict):
        raise UpdateError("evidence", "The kept verification record is not readable.")
    if record.get("trust_root") != hashlib.sha256(anchor).hexdigest():
        raise UpdateError("evidence", "The update was verified with another trust root.")
    root = _metadata(anchor, "root")
    kept = sorted((evidence / "root").glob("*.root.json"),
                  key=lambda p: int(p.name.split(".")[0])) if (evidence / "root").is_dir() \
        else []
    for path in kept:
        root = _next_root(root, path.read_bytes())
    # Keys this client has trusted since: continue the chain to them.
    if local_metadata is not None:
        history = Path(local_metadata) / "root_history"
        try:
            trusted = _metadata((Path(local_metadata) / "root.json").read_bytes(), "root")
            while root.signed.version < trusted.signed.version:
                version = root.signed.version + 1
                try:
                    data = (history / f"{version}.root.json").read_bytes()
                except OSError as exc:
                    raise UpdateError("evidence", f"Locally trusted root {version} is "
                                                  "missing or unreadable.") from exc
                root = _next_root(root, data)
            if root.signed.version == trusted.signed.version \
                    and root.signed_bytes != trusted.signed_bytes:
                raise UpdateError("evidence", "The authenticated root disagrees with "
                                              "the newest locally trusted root.")
        except OSError as exc:
            raise UpdateError("evidence", "The newest locally trusted root is missing "
                                          "or unreadable.") from exc
    signed: dict = {}
    for role in ("timestamp", "snapshot", "targets"):
        try:
            data = (evidence / f"{role}.json").read_bytes()
        except OSError as exc:
            raise UpdateError("evidence", f"The kept {role} metadata is missing.") from exc
        item = _metadata(data, role)
        try:
            root.signed.verify_delegate(role, item.signed_bytes, item.signatures)
        except Exception as exc:                           # noqa: BLE001
            raise UpdateError("evidence", f"The kept {role} metadata is not signed by "
                                          f"the trusted keys: {exc}") from exc
        signed[role] = (item, data)
    timestamp, (snapshot, snapshot_bytes), (targets, targets_bytes) = (
        signed["timestamp"][0], signed["snapshot"], signed["targets"])
    try:
        link = timestamp.signed.snapshot_meta
        if link.version != snapshot.signed.version:
            raise UpdateError("evidence", "The kept snapshot is not the one its "
                                          "timestamp names.")
        if link.length is not None or link.hashes:
            link.verify_length_and_hashes(snapshot_bytes)
        link = snapshot.signed.meta.get("targets.json")
        if link is None or link.version != targets.signed.version:
            raise UpdateError("evidence", "The kept targets metadata is not the one its "
                                          "snapshot names.")
        if link.length is not None or link.hashes:
            link.verify_length_and_hashes(targets_bytes)
    except UpdateError:
        raise
    except Exception as exc:                               # noqa: BLE001
        raise UpdateError("evidence", f"The kept metadata does not link up: {exc}") from exc
    entries = targets.signed.targets
    latest_name = record.get("latest_target")
    latest_entry = entries.get(latest_name)
    if latest_entry is None:
        raise UpdateError("evidence", "The kept offer is not in the signed targets.")
    try:
        latest_bytes = (evidence / LATEST).read_bytes()
        latest_entry.verify_length_and_hashes(latest_bytes)
    except Exception as exc:                               # noqa: BLE001
        raise UpdateError("evidence", "The kept offer does not match its signed "
                                      "entry.") from exc
    latest = json.loads(latest_bytes)
    package_entry = entries.get(latest.get("artifact"))
    if package_entry is None:
        raise UpdateError("evidence", "The kept offer names a package that is not signed.")
    custom = package_entry.custom or {}
    for key in ("version", "lane", "channel"):
        values = {latest.get(key), record.get(key)}
        if key in ("version", "lane"):
            values.add(custom.get(key))
        if len(values) != 1:
            raise UpdateError("evidence", f"The kept details disagree about the {key}.")
    if record.get("target") != latest.get("artifact"):
        raise UpdateError("evidence", "The kept record names another package.")
    package = staged / Path(latest["artifact"]).name
    try:
        with open(package, "rb") as handle:
            package_entry.verify_length_and_hashes(handle)
    except Exception as exc:                               # noqa: BLE001
        raise UpdateError("evidence", "The staged package no longer matches its "
                                      "signed size and SHA-256.") from exc
    if (record.get("size"), record.get("sha256")) != (package_entry.length,
                                                      package_entry.hashes.get("sha256")):
        raise UpdateError("evidence", "The kept record disagrees with the signed package.")
    return {"version": latest["version"], "lane": latest.get("lane"),
            "channel": latest.get("channel"), "schema_version": latest.get("schema_version"),
            "qualified_migrations": latest.get("qualified_migrations") or [],
            "package": str(package), "size": package_entry.length,
            "sha256": package_entry.hashes.get("sha256"),
            "verified_at": record.get("verified_at")}


def compatible_schema(current: int, target: int, migrations) -> str | None:
    """Why `target` may not open data at `current`, or None when it may."""
    if target == current:
        return None
    if target < current:
        return ("This update reads an older data format than this computer's "
                "workspace, so it cannot open it.")
    if [current, target] in [list(m) for m in migrations or []]:
        return None
    return ("This update changes the data format and needs a qualified migration, "
            "which this update does not declare.")


def running_bundle() -> Path | None:
    """The .app this process runs from, when it is a packaged macOS app."""
    if not getattr(sys, "frozen", False):
        return None
    for parent in Path(sys.executable).resolve().parents:
        if parent.suffix == ".app":
            return parent
    return None


# --------------------------------------------------------------------------
# The service
# --------------------------------------------------------------------------

class UpdateService:
    """Check, download, import and install preparation for this installation."""

    def __init__(self, data_root: Path, *, identity: dict | None = None,
                 trust_root: bytes | None = None, feed: dict | None = None,
                 schema_version: int, os_version=None, pool=None,
                 bundle: Path | None = None, platform: str | None = None,
                 environ=None, codesign=None):
        self.data_root = Path(data_root)
        self.home = self.data_root / "updates"
        self.identity = identity if identity is not None else build_info.embedded_identity()
        if trust_root is None:
            path = bundled(TRUST_ROOT_NAME)
            trust_root = path.read_bytes() if path else None
        if feed is None:
            path = bundled(FEED_NAME)
            try:
                feed = json.loads(path.read_text(encoding="utf-8")) if path else None
            except (OSError, ValueError):
                feed = None
        self.trust_root = trust_root
        feed = feed if isinstance(feed, dict) else {}
        self.feed = ({"metadata_url": feed["metadata_url"], "targets_url": feed["targets_url"]}
                     if feed.get("metadata_url") and feed.get("targets_url") else None)
        folder = feed.get("local_folder")
        self.folder = (Path(os.path.expanduser(folder))
                       if folder and (self.identity or {}).get("channel") == "internal"
                       else None)
        self.schema_version = schema_version
        self.os_version = os_version
        self._pool = pool
        self._bundle = bundle if bundle is not None else running_bundle()
        self._platform = platform or sys.platform
        self._environ = os.environ if environ is None else environ
        self._codesign = codesign
        self._lock = threading.Lock()
        self._busy = threading.Lock()              # one metadata operation at a time
        self.last_check: dict | None = None
        self.offer: dict | None = None
        self.download: Download | None = None
        self.install: dict = {"state": "idle"}
        self.notice: dict | None = None
        self._negative: dict = {}
        self._thread: threading.Thread | None = None
        self._install_thread: threading.Thread | None = None
        self._rediscover_staged()

    # -- what the interface reads -----------------------------------------
    @property
    def version(self) -> str:
        return (self.identity or {}).get("version") or build_info.APP_VERSION

    @property
    def lane(self) -> str | None:
        return (self.identity or {}).get("lane")

    def unavailable_reason(self) -> str | None:
        if not self.identity:
            return ("This is a source checkout, not an installed package, so it does "
                    "not check for updates.")
        if not self.trust_root:
            return ("This package was built without an update trust root, so it cannot "
                    "verify updates. Install a newer package yourself when you have one.")
        return None

    def source(self) -> str | None:
        if self.feed:
            return "https"
        if self.folder is not None:
            return "folder"
        return None

    def capability(self) -> str:
        value = (self.identity or {}).get("install_capability")
        return value if value in CAPABILITIES else "unavailable"

    def helper_present(self) -> bool:
        return HELPER_PLATFORMS.get(self.lane or "") == self._platform

    def header_eligible(self) -> bool:
        """The header control may appear (the page adds the online hint)."""
        return (self.unavailable_reason() is None and self.source() is not None
                and self.capability() != "unavailable" and self.helper_present())

    def install_location(self) -> tuple[Path | None, str | None]:
        """Where the running app is installed, or why it cannot be replaced there."""
        if self.capability() == "unavailable":
            return None, "Installing updates from inside Refinix is not available for " \
                         "this build on this kind of computer yet."
        if not self.helper_present():
            return None, "Installing updates from inside Refinix is not available on " \
                         "this kind of computer yet."
        bundle = self._bundle
        if bundle is None:
            return None, "Refinix is not running from an installed app."
        text = str(bundle)
        if "/AppTranslocation/" in text:
            return None, ("macOS is running Refinix from a temporary copy. Move Refinix "
                          "to Applications, open it from there and try again.")
        allowed = [Path("/Applications/Refinix.app"),
                   Path.home() / "Applications" / "Refinix.app"]
        test_root = self._environ.get(TEST_INSTALL_ROOT)
        if test_root and (self.identity or {}).get("channel") == "internal":
            allowed.append(Path(test_root) / "Refinix.app")
        if Path(os.path.realpath(bundle)) not in {Path(os.path.realpath(p)) for p in allowed}:
            return None, ("Refinix can update itself only when it is in Applications. "
                          f"This copy is at {bundle}.")
        if not os.access(bundle.parent, os.W_OK):
            return None, f"Refinix cannot write to {bundle.parent}."
        try:
            if os.stat(bundle.parent).st_dev != os.stat(self.data_root).st_dev:
                return None, ("Refinix's data and the app are on different disks, so the "
                              "app cannot be replaced safely in one step.")
        except OSError as exc:
            return None, f"The install location cannot be checked: {exc}"
        return bundle, None

    def describe(self) -> dict:
        with self._lock:
            source = self.source()
            install_path, install_reason = self.install_location()
            unavailable = self.unavailable_reason() or (
                None if source else "No update source is set for this build's channel. "
                                    "You can still import a verified update bundle.")
            return {
                "version": self.version,
                "channel": (self.identity or {}).get("channel", "development"),
                "lane": self.lane,
                "source": source,
                "folder": str(self.folder) if self.folder is not None else None,
                "can_check": self.unavailable_reason() is None and source is not None,
                "can_import": self.unavailable_reason() is None,
                "header_eligible": self.header_eligible(),
                "unavailable": unavailable,
                "last_check": self.last_check, "offer": self.offer,
                "download": self.download.as_dict() if self.download else None,
                "install_capability": self.capability(),
                "install_supported": install_reason is None,
                "install_reason": install_reason,
                "install_path": str(install_path) if install_path else None,
                "install": dict(self.install),
                "install_note": INSTALL_NOTE,
                "notice": self.notice,
                "kept": self._kept(),
            }

    def _kept(self) -> dict | None:
        """The previous app and data copy kept for going back, read without changing them."""
        try:
            journal = json.loads((self.home / "install-journal.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(journal, dict) or journal.get("state") != "committed":
            return None
        app = journal.get("previous_app")
        try:
            data = json.loads((self.data_root / "recovery" / "update-journal.json")
                              .read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        copy = data.get("set_aside") if data.get("update_id") == journal.get("update_id") \
            else None
        return {"previous_version": journal.get("from_version"),
                "previous_app": app if app and Path(app).is_dir() else None,
                "previous_app_bytes": self._size(app),
                "data_copy": copy if copy and Path(copy).is_dir() else None,
                "data_copy_bytes": self._size(copy)}

    def _size(self, path) -> int | None:
        """A folder's size, measured once per folder (they never change once kept)."""
        if not path or not Path(path).is_dir():
            return None
        cache = self.__dict__.setdefault("_sizes", {})
        if path not in cache:
            cache[path] = _tree_bytes(Path(path))
        return cache[path]

    # -- checking ----------------------------------------------------------
    def _updater(self, fetcher, metadata_url: str, targets_url: str):
        from tuf.ngclient import Updater
        metadata = self.home / "metadata"
        metadata.mkdir(parents=True, exist_ok=True, mode=0o700)
        return Updater(str(metadata), metadata_url, str(self.home / "targets"),
                       targets_url, fetcher=fetcher, bootstrap=self.trust_root)

    def _online(self):
        reason = self.unavailable_reason()
        if reason or not self.feed:
            raise UpdateError("unavailable", reason or "No online update source is set.")
        HttpsFetcher, _ = _fetcher_classes()
        fetcher = HttpsFetcher(self._pool)
        return fetcher, self._updater(fetcher, self.feed["metadata_url"],
                                      self.feed["targets_url"])

    def _claim(self):
        if not self._busy.acquire(blocking=False):
            raise UpdateError("busy", "Another update step is running; try again when "
                                      "it finishes.")

    def check(self) -> dict:
        """User-initiated: the HTTPS feed, or the internal update folder."""
        reason = self.unavailable_reason()
        if reason:
            self._record_check("failed", reason)
            raise UpdateError("unavailable", reason)
        if not self.feed and self.folder is not None:
            return self.check_folder()
        if not self.feed:
            raise UpdateError("unavailable", "No online update source is set.")
        self._claim()
        try:
            _fetcher, updater = self._online()
            offer = self._decide(updater)
        except UpdateError as exc:
            self._record_check("failed", str(exc))
            raise
        except Exception as exc:                           # noqa: BLE001
            why = unreachable(exc)
            if why:
                self._record_check("unreachable", f"Couldn't reach the update server: {why}.")
                raise UpdateError("unreachable", f"Couldn't reach the update server: "
                                                 f"{why}.") from exc
            self._record_check("failed", _plain(exc))
            raise UpdateError("check_failed", _plain(exc)) from exc
        finally:
            self._busy.release()
        if offer:
            offer["source"] = {"kind": "https"}
        with self._lock:
            self.offer = offer
        self._record_check("update_available" if offer else "up_to_date",
                           f"Version {offer['version']} is available." if offer else
                           f"Version {self.version} is the newest for this channel.")
        return self.describe()

    def _record_check(self, result: str, detail: str) -> None:
        with self._lock:
            previous = self.last_check
            self.last_check = {"at": _stamp(), "result": result, "detail": detail}
            if result in ("update_available", "up_to_date", "imported"):
                self.last_check["last_success"] = self.last_check["at"]
            elif previous:
                self.last_check["last_success"] = previous.get("last_success")
            if result in ("failed", "unreachable"):
                self.offer = None

    def _decide(self, updater) -> dict | None:
        """The verified offer for this lane and channel, or None when up to date."""
        updater.refresh()
        identity = self.identity
        channel, lane = identity.get("channel"), identity.get("lane")
        latest_path = f"{channel}/{lane}/{LATEST}"
        info = updater.get_targetinfo(latest_path)
        if info is None:
            return None
        with tempfile.TemporaryDirectory() as folder:
            local = updater.download_target(info, str(Path(folder) / LATEST))
            latest = json.loads(Path(local).read_text(encoding="utf-8"))
        if (latest.get("channel"), latest.get("lane")) != (channel, lane):
            raise UpdateError("mismatch", "The signed offer names another channel or "
                                          "platform, so it was refused.")
        try:
            newer = version_key(latest["version"]) > version_key(self.version)
        except (KeyError, ValueError) as exc:
            raise UpdateError("mismatch", f"The signed offer is malformed: {exc}") from exc
        if not newer:
            return None
        target_schema = int(latest.get("schema_version", 0))
        if target_schema < self.schema_version:
            raise UpdateError("incompatible", "The offered version reads an older data "
                              "format than this one has written, so it was refused.")
        why = compatible_schema(self.schema_version, target_schema,
                                latest.get("qualified_migrations"))
        if why:
            raise UpdateError("incompatible", why)
        package = updater.get_targetinfo(latest["artifact"])
        if package is None:
            raise UpdateError("mismatch", "The offered package is not in the signed "
                                          "metadata, so it was refused.")
        custom = package.custom or {}
        if custom.get("version") != latest["version"] or custom.get("lane") != lane:
            raise UpdateError("mismatch", "The package's signed details do not match "
                                          "the offer, so it was refused.")
        minimum = latest.get("min_os")
        # Only a plain version number is compared; descriptive text is shown.
        if minimum and self.os_version is not None \
                and re.fullmatch(r"\d+(\.\d+)*", str(minimum)):
            try:
                if version_tuple(self.os_version) < version_tuple(minimum):
                    raise UpdateError("incompatible",
                                      f"Version {latest['version']} needs {minimum} or "
                                      "later on this computer.")
            except ValueError:
                pass
        return {"version": latest["version"], "build_set": latest.get("build_set"),
                "target": latest["artifact"], "latest_target": latest_path,
                "size": package.length,
                "sha256": package.hashes.get("sha256"),
                "notes": str(latest.get("notes") or "")[:4000],
                "prerequisites": list(latest.get("prerequisites") or [])[:16],
                "engine_release": latest.get("engine_release"),
                "schema_version": latest.get("schema_version"),
                "min_os": minimum}

    # -- the internal update folder ------------------------------------------
    def _trust_state(self) -> tuple:
        """The versions of the metadata this client trusts now."""
        state = []
        for role in ("root", "timestamp", "snapshot", "targets"):
            try:
                data = json.loads((self.home / "metadata" / f"{role}.json")
                                  .read_text(encoding="utf-8"))
                state.append(int(data["signed"]["version"]))
            except (OSError, ValueError, KeyError, TypeError):
                state.append(None)
        return tuple(state)

    def _bundle_offer(self, path: Path) -> dict | None:
        """Verify one bundle's metadata in place; its offer, or None when not newer."""
        _, BundleFetcher = _fetcher_classes()
        try:
            archive = zipfile.ZipFile(path)
        except (OSError, zipfile.BadZipFile) as exc:
            raise UpdateError("bad_bundle", f"The bundle cannot be read: {exc}") from exc
        with archive:
            members = bundle_members(archive)
            updater = self._updater(BundleFetcher(archive), f"{BUNDLE_SCHEME}:///metadata/",
                                    f"{BUNDLE_SCHEME}:///targets/")
            try:
                offer = self._decide(updater)
            except UpdateError:
                raise
            except Exception as exc:                       # noqa: BLE001
                text = _plain(exc)
                code = "expired" if "expired" in text else (
                    "older" if "BadVersionNumber" in type(exc).__name__ else "bad_bundle")
                raise UpdateError(code, text) from exc
            if offer is None:
                return None
            info = members.get(f"targets/{offer['target']}")
            total = sum(i.file_size for i in members.values())
            if info is None or info.file_size != offer["size"] \
                    or total > offer["size"] + BUNDLE_SLACK:
                raise UpdateError("bad_bundle", "The bundle's package is not the signed size.")
            return offer

    def check_folder(self) -> dict:
        """User-initiated: verify bundles in the internal update folder, in place."""
        reason = self.unavailable_reason()
        if reason or self.folder is None:
            raise UpdateError("unavailable", reason or "This build has no update folder.")
        self._claim()
        try:
            return self._check_folder()
        finally:
            self._busy.release()

    def _check_folder(self) -> dict:
        folder = self.folder
        if not folder.is_dir():
            self._record_check("failed", f"The update folder {folder} does not exist yet.")
            raise UpdateError("no_folder", f"The update folder {folder} does not exist yet.")
        found = []
        with os.scandir(folder) as entries:
            for entry in entries:
                if not BUNDLE_FILE.fullmatch(entry.name) or entry.is_symlink() \
                        or not entry.is_file(follow_symlinks=False):
                    continue
                info = entry.stat(follow_symlinks=False)
                if info.st_size <= MAX_BUNDLE_BYTES:
                    found.append((Path(entry.path), info))
        found.sort(key=lambda item: item[1].st_mtime_ns, reverse=True)
        incomplete = len(found) > MAX_FOLDER_FILES
        found = found[:MAX_FOLDER_FILES]

        def claimed(item):
            match = re.match(r"Refinix-(\d+\.\d+\.\d+(?:-[a-z]+\.\d+)?)-", item[0].name)
            try:
                return (1, version_key(match.group(1))) if match else (0, ())
            except ValueError:
                return (0, ())

        found.sort(key=claimed, reverse=True)
        offer, outcomes = None, []
        for path, info in found:
            key = (str(path), info.st_size, info.st_mtime_ns)
            cached = self._negative.get(key)
            if cached is not None and cached["trust"] == self._trust_state():
                outcomes.append(cached["why"])
                continue
            try:
                candidate = self._bundle_offer(path)
            except UpdateError as exc:
                self._negative[key] = {"trust": self._trust_state(),
                                       "why": f"{path.name}: {exc}"}
                outcomes.append(f"{path.name}: {exc}")
                continue
            if candidate is None:
                self._negative[key] = {"trust": self._trust_state(),
                                       "why": f"{path.name}: not newer"}
                outcomes.append(f"{path.name}: not newer")
                continue
            digest = _sha256_file(path, MAX_BUNDLE_BYTES)
            candidate["source"] = {"kind": "bundle", "path": str(path),
                                   "size": info.st_size, "mtime_ns": info.st_mtime_ns,
                                   "sha256": digest}
            offer = candidate
            break
        with self._lock:
            self.offer = offer
        if offer:
            self._record_check("update_available",
                               f"Version {offer['version']} is in the update folder.")
        elif incomplete:
            self._record_check("incomplete", "Not every bundle in the update folder was "
                                             f"checked (more than {MAX_FOLDER_FILES}); "
                                             "remove older bundles and check again.")
        else:
            detail = f"No newer verified update in {folder}."
            if outcomes:
                detail += " " + "; ".join(outcomes[:3])
            self._record_check("up_to_date", detail)
        return self.describe()

    # -- downloading -------------------------------------------------------
    def start_download(self) -> dict:
        self._claim()
        started = False
        try:
            with self._lock:
                offer, cached = self.offer, self.download
            if offer is None:
                raise UpdateError("no_offer", "Check for updates first.")
            if cached and cached.state == "verified" \
                    and (cached.version, cached.target) == (offer["version"], offer["target"]):
                try:
                    verified = self.admit_staged()
                    if (verified["size"], verified["sha256"]) != (offer["size"], offer["sha256"]):
                        raise UpdateError("changed", "The offer disagrees with the verified package.")
                except UpdateError as exc:
                    cached.state, cached.error = "failed", str(exc)
                    raise
                return cached.as_dict()
            source = offer.get("source") or {"kind": "https"}
            if source.get("kind") == "bundle":
                result = self._start_bundle_copy(offer, source)
                started = True
                return result
            fetcher, updater = self._online()
            operation = Download(offer["version"], offer["target"], bytes_total=offer["size"])
            self._run_stage(fetcher, updater, operation, offer)
            started = True
            return operation.as_dict()
        finally:
            if not started:
                self._busy.release()

    def _start_bundle_copy(self, offer: dict, source: dict) -> dict:
        path = Path(source["path"])
        info = path.stat()
        if (info.st_size, info.st_mtime_ns) != (source["size"], source["mtime_ns"]) \
                or _sha256_file(path, MAX_BUNDLE_BYTES) != source["sha256"]:
            raise UpdateError("changed", "The bundle changed after it was checked; check again.")
        _, BundleFetcher = _fetcher_classes()
        archive = zipfile.ZipFile(path)
        try:
            fetcher = BundleFetcher(archive)
            updater = self._updater(fetcher, f"{BUNDLE_SCHEME}:///metadata/",
                                    f"{BUNDLE_SCHEME}:///targets/")
            operation = Download(offer["version"], offer["target"], bytes_total=offer["size"],
                                 source="bundle")
            self._run_stage(fetcher, updater, operation, offer, archive=archive)
        except BaseException:
            archive.close()
            raise
        return operation.as_dict()

    def _run_stage(self, fetcher, updater, operation, offer, archive=None):
        fetcher.cancelled = operation.cancel.is_set
        fetcher.progress = lambda n: setattr(operation, "bytes_done",
                                             operation.bytes_done + n)

        def work():
            try:
                self._stage(updater, operation, offer)
            finally:
                if archive is not None:
                    archive.close()
                self._busy.release()

        with self._lock:
            self.download = operation
            self._thread = threading.Thread(target=work, daemon=True,
                                            name="refinix-update-download")
            self._thread.start()

    def _stage(self, updater, operation: Download, offer: dict) -> None:
        staging = self.home / "staging" / operation.version
        partial = staging.with_name(staging.name + ".partial")
        shutil.rmtree(partial, ignore_errors=True)
        partial.mkdir(parents=True, mode=0o700)
        try:
            # Refreshes the signed metadata first when this client has not yet.
            info = updater.get_targetinfo(operation.target)
            if info is None:
                raise UpdateError("mismatch", "The package is no longer offered.")
            name = Path(operation.target).name
            updater.download_target(info, str(partial / name))
            self._keep_evidence(updater, partial, offer, info)
            shutil.rmtree(staging, ignore_errors=True)
            partial.rename(staging)
            operation.path, operation.state = str(staging / name), "verified"
            operation.bytes_done = info.length
        except Exception as exc:                           # noqa: BLE001
            shutil.rmtree(partial, ignore_errors=True)
            operation.state = "cancelled" if operation.cancel.is_set() else "failed"
            why = None if operation.cancel.is_set() else unreachable(exc)
            operation.error = (None if operation.cancel.is_set() else
                               f"Couldn't reach the update server: {why}." if why
                               else _plain(exc))

    def _keep_evidence(self, updater, folder: Path, offer: dict, info) -> None:
        """Keep the exact signed metadata this client trusted, beside the package."""
        evidence = folder / EVIDENCE
        (evidence / "root").mkdir(parents=True, mode=0o700)
        metadata = self.home / "metadata"
        anchor = _metadata(self.trust_root, "root")
        current = json.loads((metadata / "root.json").read_text(encoding="utf-8"))
        for version in range(anchor.signed.version + 1, current["signed"]["version"] + 1):
            source = metadata / "root_history" / f"{version}.root.json"
            if not source.is_file():
                raise UpdateError("evidence", f"Root version {version} was not kept by "
                                              "the update client.")
            shutil.copyfile(source, evidence / "root" / source.name)
        for role in ("timestamp", "snapshot", "targets"):
            shutil.copyfile(metadata / f"{role}.json", evidence / f"{role}.json")
        latest_info = updater.get_targetinfo(offer["latest_target"])
        if latest_info is None:
            raise UpdateError("mismatch", "The offer is no longer signed.")
        updater.download_target(latest_info, str(evidence / LATEST))
        _write_json(evidence / RECORD, {
            "version": offer["version"], "target": offer["target"],
            "latest_target": offer["latest_target"], "lane": self.lane,
            "channel": (self.identity or {}).get("channel"),
            "size": info.length, "sha256": info.hashes.get("sha256"),
            "schema_version": offer.get("schema_version"),
            "trust_root": hashlib.sha256(self.trust_root).hexdigest(),
            "verified_at": _stamp(), "source": (offer.get("source") or {}).get("kind")})

    def cancel(self) -> dict:
        with self._lock:
            operation = self.download
        if operation is None or operation.state != "running":
            return {"cancelled": False}
        operation.cancel.set()
        return {"cancelled": True}

    def wait(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    # -- offline -------------------------------------------------------------
    def import_bundle(self, path: Path) -> dict:
        """Verify an offline bundle with the same trust root and checks, then stage it."""
        reason = self.unavailable_reason()
        if reason:
            raise UpdateError("unavailable", reason)
        path = Path(path)
        try:
            if path.stat().st_size > MAX_BUNDLE_BYTES:
                raise UpdateError("bad_bundle", "The bundle is larger than an update can be.")
        except OSError as exc:
            raise UpdateError("bad_bundle", f"The bundle cannot be read: {exc}") from exc
        self._claim()
        try:
            _, BundleFetcher = _fetcher_classes()
            try:
                archive = zipfile.ZipFile(path)
            except (OSError, zipfile.BadZipFile) as exc:
                raise UpdateError("bad_bundle", f"The bundle cannot be read: {exc}") from exc
            with archive:
                members = bundle_members(archive)
                updater = self._updater(BundleFetcher(archive),
                                        f"{BUNDLE_SCHEME}:///metadata/",
                                        f"{BUNDLE_SCHEME}:///targets/")
                try:
                    offer = self._decide(updater)
                except UpdateError:
                    raise
                except Exception as exc:                   # noqa: BLE001
                    raise UpdateError("bad_bundle", _plain(exc)) from exc
                if offer is None:
                    raise UpdateError("not_newer", "That bundle is not newer than this "
                                                   "version, so nothing was imported.")
                info = members.get(f"targets/{offer['target']}")
                if info is None or info.file_size != offer["size"] or \
                        sum(i.file_size for i in members.values()) > offer["size"] + BUNDLE_SLACK:
                    raise UpdateError("bad_bundle", "The bundle's package is not the "
                                                    "signed size.")
                offer["source"] = {"kind": "import"}
                operation = Download(offer["version"], offer["target"],
                                     bytes_total=offer["size"], source="import")
                self._stage(updater, operation, offer)
        finally:
            self._busy.release()
        with self._lock:
            self.offer, self.download = offer, operation
        if operation.state != "verified":
            raise UpdateError("bad_bundle", operation.error or "The package failed "
                                                               "verification.")
        self._record_check("imported", f"Version {offer['version']} was imported "
                                       "from a bundle.")
        return self.describe()

    # -- install preparation (no network) ----------------------------------
    def _rediscover_staged(self) -> None:
        """A package verified in an earlier session is still offered for install."""
        staging = self.home / "staging"
        try:
            folders = [p for p in staging.iterdir()
                       if p.is_dir() and not p.name.endswith(".partial")]
        except OSError:
            return
        best = None
        for folder in folders:
            try:
                record = json.loads((folder / EVIDENCE / RECORD).read_text(encoding="utf-8"))
                if version_key(record["version"]) <= version_key(self.version):
                    continue
            except (OSError, ValueError, KeyError):
                continue
            if best is None or version_key(record["version"]) > version_key(best[1]["version"]):
                best = (folder, record)
        if best is None:
            return
        folder, record = best
        package = folder / Path(record["target"]).name
        if package.is_file():
            self.download = Download(record["version"], record["target"], state="verified",
                                     bytes_done=record.get("size") or 0,
                                     bytes_total=record.get("size") or 0,
                                     path=str(package), source=record.get("source") or "")

    def staged_folder(self) -> Path | None:
        operation = self.download
        if operation is None or operation.state != "verified" or not operation.path:
            return None
        return Path(operation.path).parent

    def admit_staged(self) -> dict:
        """The authenticated, compatible, newer staged package, checked offline."""
        folder = self.staged_folder()
        if folder is None:
            raise UpdateError("nothing_staged", "There is no verified update ready to "
                                                "install.")
        if not self.trust_root:
            raise UpdateError("unavailable", self.unavailable_reason() or "No trust root.")
        verified = verify_evidence(folder, anchor=self.trust_root,
                                   local_metadata=self.home / "metadata")
        if version_key(verified["version"]) <= version_key(self.version):
            raise UpdateError("not_newer", "The staged update is not newer than this "
                                           "version.")
        identity = self.identity or {}
        if (verified["lane"], verified["channel"]) != (identity.get("lane"),
                                                       identity.get("channel")):
            raise UpdateError("mismatch", "The staged update is for another platform or "
                                          "channel.")
        why = compatible_schema(self.schema_version, int(verified["schema_version"] or 0),
                                verified["qualified_migrations"])
        if why:
            raise UpdateError("incompatible", why)
        return verified

    def prepare_install(self, *, wait: bool = False) -> dict:
        """Verify the staged update offline and expand it beside the app, ready to swap."""
        install_path, reason = self.install_location()
        if reason:
            raise UpdateError("install_unavailable", reason)
        self._claim()
        started = False
        try:
            with self._lock:
                ready = dict(self.install) if self.install.get("state") == "ready" else None
            if ready:
                verified = self.admit_staged()
                if (ready["version"], ready["install_path"]) != (verified["version"], str(install_path)):
                    raise UpdateError("changed", "Cancel the prepared update before preparing another.")
                from backend.coordinator import app_archive
                kwargs = {} if self._codesign is None else {"codesign": self._codesign}
                try:
                    app_archive.verify_bundle(Path(ready["incoming"]), version=ready["version"],
                                              lane=self.lane, channel=self.identity["channel"],
                                              trust_root=self.identity.get("trust_root"), **kwargs)
                except app_archive.ArchiveError as exc:
                    raise UpdateError(exc.code, str(exc)) from exc
                return self.describe()
            with self._lock:
                self.install = {"state": "preparing", "started_at": _stamp()}
            thread = threading.Thread(target=self._prepare, args=(install_path,), daemon=True,
                                      name="refinix-update-prepare")
            self._install_thread = thread
            thread.start()
            started = True
        finally:
            if not started:
                self._busy.release()
        if wait:
            thread.join()
        return self.describe()

    def _prepare(self, install_path: Path) -> None:
        from backend.coordinator import app_archive
        update_id = uuid.uuid4().hex[:16]
        destination = self.home / "install" / update_id
        try:
            verified = self.admit_staged()
            package = Path(verified["package"])
            listing = app_archive.inspect(package)
            needed = listing.total_bytes + _tree_bytes(install_path) + _database_bytes(
                self.data_root) + INSTALL_MARGIN
            free = shutil.disk_usage(self.home).free
            if free < needed:
                raise UpdateError("disk", f"Installing needs about {needed // 1024 ** 2} MB "
                                          f"free; {free // 1024 ** 2} MB is available.")
            app = app_archive.extract(package, listing, destination)
            app_archive.check_tree(destination, listing)
            kwargs = {} if self._codesign is None else {"codesign": self._codesign}
            identity = app_archive.verify_bundle(
                app, version=verified["version"], lane=self.lane,
                channel=(self.identity or {}).get("channel"),
                trust_root=(self.identity or {}).get("trust_root"), **kwargs)
            if int(identity.get("schema_version") or 0) != int(
                    verified["schema_version"] or 0):
                raise UpdateError("mismatch", "The app inside the package disagrees with "
                                              "the signed offer about its data format.")
            with self._lock:
                self.install = {"state": "ready", "update_id": update_id,
                                "version": verified["version"], "incoming": str(app),
                                "install_path": str(install_path),
                                "build_set": identity.get("build_set"),
                                "prepared_at": _stamp()}
        except Exception as exc:                           # noqa: BLE001
            try:
                from backend.coordinator import app_archive as archive_module
                archive_module.remove_tree(destination)
            except OSError:
                pass
            message = str(exc) if isinstance(exc, (UpdateError,)) or \
                type(exc).__name__ == "ArchiveError" else f"{type(exc).__name__}: {exc}"
            with self._lock:
                self.install = {"state": "failed", "error": message,
                                "code": getattr(exc, "code", "failed"),
                                "failed_at": _stamp()}
        finally:
            self._busy.release()

    def cancel_install(self) -> dict:
        """Forget a prepared (not yet started) install and remove its expanded copy."""
        with self._lock:
            install = dict(self.install)
            if install.get("state") == "preparing":
                raise UpdateError("busy", "The update is still being prepared.")
            self.install = {"state": "idle"}
        if install.get("state") == "ready" and install.get("update_id"):
            shutil.rmtree(self.home / "install" / install["update_id"], ignore_errors=True)
        return self.describe()


def _tree_bytes(path: Path) -> int:
    total = 0
    for folder, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.lstat(Path(folder) / name).st_size
            except OSError:
                pass
    return total


def _database_bytes(root: Path) -> int:
    total = 0
    for name in ("coordinator.sqlite3", "coordinator.sqlite3-wal"):
        try:
            total += (Path(root) / name).stat().st_size
        except OSError:
            pass
    return total


def version_tuple(text: str) -> tuple[int, ...]:
    parts = [int(p) for p in re.findall(r"\d+", str(text))]
    if not parts:
        raise ValueError(text)
    return tuple(parts)
