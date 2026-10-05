"""Settings → Updates: checked only when asked, verified before anything runs.

The update metadata is TUF (python-tuf's client). A package carries the
publisher's trust root (`refinix-update-root.json`) and, for a channel that
has one, where its feed lives (`refinix-update-feed.json`). Both are placed in
the package at build time beside `refinix-build.json`; a source checkout or a
package built without them reports that it cannot check for updates rather
than pretending to be up to date.

Per channel and lane the repository signs one small target,
`<channel>/<lane>/latest.json`, naming the offered version and its package
target. The client:

1. **Checks** only when the person presses Check for updates. It fetches TUF
   metadata and that one target: nothing about this computer, its work or its
   models is sent.
2. **Offers** an update only when its lane and channel match this build, its
   version is newer, and its data format is not older than this one's.
3. **Downloads** the package into a staging folder with TUF verifying length
   and SHA-256; a partial or mismatched file is discarded and never offered.
4. **Imports** an offline bundle (metadata plus package, for example from a
   USB drive) through the same client, trust root and checks.

Installing a staged package from inside Refinix (with recovery to the
previous version) is not available in this build, so no Install control is
offered; the verified package's location is shown instead.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import threading
import time
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
INSTALL_NOTE = ("Installing an update from inside Refinix is not available in this "
                "build yet. Quit Refinix and install the verified package from the "
                "folder shown, the same way you installed this one. Your data is kept.")


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


@dataclass
class Download:
    version: str
    target: str
    state: str = "running"                     # running | verified | failed | cancelled
    bytes_done: int = 0
    bytes_total: int = 0
    path: str | None = None
    error: str | None = None
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def as_dict(self) -> dict:
        return {"version": self.version, "state": self.state, "bytes_done": self.bytes_done,
                "bytes_total": self.bytes_total, "path": self.path, "error": self.error}


def _fetcher_class():
    from tuf.api import exceptions
    from tuf.ngclient import FetcherInterface

    class HttpsFetcher(FetcherInterface):
        """HTTPS only, OS-backed certificate verification, progress and Stop."""

        def __init__(self, pool=None):
            self._pool = pool
            self.progress = None                   # (bytes) -> None
            self.cancelled = None                  # () -> bool

        def _fetch(self, url: str):
            if urlsplit(url).scheme != "https":
                raise exceptions.DownloadError(f"refusing a non-HTTPS update URL: {url}")
            if self._pool is None:
                from backend.coordinator import provisioning
                self._pool = provisioning._pool()
            response = self._pool.request("GET", url, preload_content=False,
                                          redirect=False)
            if response.status >= 400 or response.status in (301, 302, 303, 307, 308):
                response.release_conn()
                raise exceptions.DownloadHTTPError(
                    f"the update server answered {response.status}", response.status)
            return self._chunks(response)

        def _chunks(self, response):
            try:
                for block in response.stream(256 * 1024):
                    if self.cancelled is not None and self.cancelled():
                        raise exceptions.DownloadError("cancelled")
                    if self.progress is not None:
                        self.progress(len(block))
                    yield block
            finally:
                response.release_conn()

    class BundleFetcher(FetcherInterface):
        """Serves `refinix-bundle:///<path>` from an unpacked offline bundle."""

        def __init__(self, root: Path):
            self.root = Path(root).resolve()

        def _fetch(self, url: str):
            parts = urlsplit(url)
            if parts.scheme != BUNDLE_SCHEME:
                raise exceptions.DownloadError(f"not a bundle URL: {url}")
            path = (self.root / parts.path.lstrip("/")).resolve()
            if self.root not in path.parents or not path.is_file():
                raise exceptions.DownloadHTTPError("not in the bundle", 404)
            return iter([path.read_bytes()])

    return HttpsFetcher, BundleFetcher


class UpdateService:
    """Check, download and import for this installation's channel and lane."""

    def __init__(self, data_root: Path, *, identity: dict | None = None,
                 trust_root: bytes | None = None, feed: dict | None = None,
                 schema_version: int, os_version=None, pool=None):
        self.home = Path(data_root) / "updates"
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
        self.trust_root, self.feed = trust_root, feed
        self.schema_version = schema_version
        self.os_version = os_version
        self._pool = pool
        self._lock = threading.Lock()
        self.last_check: dict | None = None
        self.offer: dict | None = None
        self.download: Download | None = None
        self._thread: threading.Thread | None = None

    # -- what the interface reads -----------------------------------------
    @property
    def version(self) -> str:
        return (self.identity or {}).get("version") or build_info.APP_VERSION

    def unavailable_reason(self) -> str | None:
        if not self.identity:
            return ("This is a source checkout, not an installed package, so it does "
                    "not check for updates.")
        if not self.trust_root:
            return ("This package was built without an update trust root, so it cannot "
                    "verify updates. Install a newer package yourself when you have one.")
        return None

    def describe(self) -> dict:
        with self._lock:
            return {
                "version": self.version,
                "channel": (self.identity or {}).get("channel", "development"),
                "lane": (self.identity or {}).get("lane"),
                "can_check": self.unavailable_reason() is None and bool(self.feed),
                "can_import": self.unavailable_reason() is None,
                "unavailable": self.unavailable_reason() or (
                    None if self.feed else "No online update source is set for this "
                    "build's channel. You can still import a verified update bundle."),
                "last_check": self.last_check, "offer": self.offer,
                "download": self.download.as_dict() if self.download else None,
                "install_supported": False, "install_note": INSTALL_NOTE,
            }

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
        HttpsFetcher, _ = _fetcher_class()
        fetcher = HttpsFetcher(self._pool)
        return fetcher, self._updater(fetcher, self.feed["metadata_url"],
                                      self.feed["targets_url"])

    def check(self) -> dict:
        """Refresh signed metadata and decide whether an update is offered."""
        try:
            fetcher, updater = self._online()
            offer = self._decide(updater)
        except UpdateError as exc:
            self._record_check("failed", str(exc))
            raise
        except Exception as exc:                           # noqa: BLE001
            self._record_check("failed", _plain(exc))
            raise UpdateError("check_failed", _plain(exc)) from exc
        with self._lock:
            self.offer = offer
        self._record_check("update_available" if offer else "up_to_date",
                           f"Version {offer['version']} is available." if offer else
                           f"Version {self.version} is the newest for this channel.")
        return self.describe()

    def _record_check(self, result: str, detail: str) -> None:
        with self._lock:
            self.last_check = {"at": _stamp(), "result": result, "detail": detail}
            if result == "failed":
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
        if int(latest.get("schema_version", 0)) < self.schema_version:
            raise UpdateError("incompatible", "The offered version reads an older data "
                              "format than this one has written, so it was refused.")
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
                "target": latest["artifact"], "size": package.length,
                "sha256": package.hashes.get("sha256"),
                "notes": str(latest.get("notes") or "")[:4000],
                "prerequisites": list(latest.get("prerequisites") or [])[:16],
                "engine_release": latest.get("engine_release"),
                "schema_version": latest.get("schema_version"),
                "min_os": minimum}

    # -- downloading -------------------------------------------------------
    def start_download(self) -> dict:
        with self._lock:
            offer = self.offer
            running = self._thread is not None and self._thread.is_alive()
        if offer is None:
            raise UpdateError("no_offer", "Check for updates first.")
        if running:
            raise UpdateError("busy", "An update is already being downloaded.")
        fetcher, updater = self._online()
        operation = Download(offer["version"], offer["target"], bytes_total=offer["size"])
        fetcher.cancelled = operation.cancel.is_set
        fetcher.progress = lambda n: setattr(operation, "bytes_done",
                                             operation.bytes_done + n)
        with self._lock:
            self.download = operation
            self._thread = threading.Thread(
                target=self._stage, args=(updater, operation), daemon=True,
                name="refinix-update-download")
            self._thread.start()
        return operation.as_dict()

    def _stage(self, updater, operation: Download) -> None:
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
            shutil.rmtree(staging, ignore_errors=True)
            partial.rename(staging)
            operation.path, operation.state = str(staging / name), "verified"
            operation.bytes_done = info.length
        except Exception as exc:                           # noqa: BLE001
            shutil.rmtree(partial, ignore_errors=True)
            operation.state = "cancelled" if operation.cancel.is_set() else "failed"
            operation.error = None if operation.cancel.is_set() else _plain(exc)

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
        _, BundleFetcher = _fetcher_class()
        with tempfile.TemporaryDirectory(dir=self._scratch()) as folder:
            root = Path(folder)
            try:
                with zipfile.ZipFile(path) as archive:
                    for member in archive.infolist():
                        target = (root / member.filename).resolve()
                        if root.resolve() not in target.parents and target != root.resolve():
                            raise UpdateError("bad_bundle", "The bundle contains an "
                                                            "unsafe path.")
                    archive.extractall(root)
            except (OSError, zipfile.BadZipFile) as exc:
                raise UpdateError("bad_bundle", f"The bundle cannot be read: {exc}") from exc
            updater = self._updater(BundleFetcher(root), f"{BUNDLE_SCHEME}:///metadata/",
                                    f"{BUNDLE_SCHEME}:///targets/")
            try:
                offer = self._decide(updater)
            except UpdateError:
                raise
            except Exception as exc:                       # noqa: BLE001
                raise UpdateError("bad_bundle", _plain(exc)) from exc
            if offer is None:
                raise UpdateError("not_newer", "That bundle is not newer than this "
                                               "version, so nothing was imported.")
            operation = Download(offer["version"], offer["target"],
                                 bytes_total=offer["size"])
            self._stage(updater, operation)
        with self._lock:
            self.offer, self.download = offer, operation
            self.last_check = {"at": _stamp(), "result": "imported",
                               "detail": f"Version {offer['version']} was imported "
                                         "from a bundle."}
        if operation.state != "verified":
            raise UpdateError("bad_bundle", operation.error or "The package failed "
                                                               "verification.")
        return self.describe()

    def _scratch(self) -> str:
        folder = self.home / "import"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        return str(folder)


def version_tuple(text: str) -> tuple[int, ...]:
    parts = [int(p) for p in re.findall(r"\d+", str(text))]
    if not parts:
        raise ValueError(text)
    return tuple(parts)


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
    if "Download" in name or "Retrieval" in name:
        return f"The update server could not be reached: {text}"
    return text
