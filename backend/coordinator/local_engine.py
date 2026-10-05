"""The managed engine as the rest of Refinix sees it.

`runtime.probe`, `runtime.model_capabilities` and `runtime.stream_chat` keep
their existing shapes and callers. When a managed engine is configured they are
answered here instead of from an external Ollama:

* **What is installed** comes from Refinix's own verified install records, not
  from whatever the engine can see. A model is listed only when its files are
  present; its digest is the Refinix model-manifest digest recorded at install.
* **Whether those files are still the installed bytes** is observed, not
  remembered (`FileChecks`). A status read compares each file's size and
  filesystem identity with the last time it was hashed; before the engine
  loads a model, any file not hashed unchanged in this process is hashed
  again. The install record's digest alone is never proof of current bytes.
* **What a model can do** comes from those records as well: vision only when a
  verified projector was installed with it.
* **How the engine runs it** comes from the reviewed preset for this model on
  this hardware tier. No preset means no launch: the request is refused rather
  than run with settings nobody qualified.

The model is loaded on first use, and the engine's own idle sleep releases its
memory after ten minutes without work.
"""

from __future__ import annotations

import hashlib
import os
import stat
import threading
from dataclasses import dataclass, field
from pathlib import Path

from backend.coordinator import engine, runtime_llamacpp

VERIFIED, PENDING, MISMATCH, MISSING = "verified", "pending", "mismatch", "missing"
_CHUNK = 4 * 1024 * 1024


@dataclass(frozen=True)
class ModelComponent:
    """One installed file and the identity recorded when it was verified."""

    role: str                 # "weights" | "projector"
    path: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class InstalledModel:
    model_id: str
    manifest_sha256: str
    weights: Path
    projector: Path | None = None
    sampling: dict = field(default_factory=dict)
    components: tuple[ModelComponent, ...] = ()

    @property
    def capabilities(self) -> list[str]:
        return ["completion"] + (["vision"] if self.projector else [])


def _fingerprint(path: Path):
    """Size and filesystem identity, without following a link; None if absent."""
    try:
        info = os.lstat(path)
    except OSError:
        return None
    if not stat.S_ISREG(info.st_mode):
        return "not a regular file"
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _sha256(path: Path, cancelled=None) -> str | None:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            if cancelled is not None and cancelled():
                return None
            digest.update(block)
    return digest.hexdigest()


class FileChecks:
    """Whether an installed model's files are still the bytes its record names.

    `look` is cheap enough for every status read: each file must be an
    ordinary file of the recorded size whose last full hash in this process
    still describes it — same device, file id, size, modification and change
    time. `confirm` hashes whatever `look` could not vouch for and runs before
    a model loads, so each launch of Refinix re-reads the bytes once. A file
    rewritten in place with its old size and timestamps restored on a
    filesystem without a change time (Windows) is caught by the next launch's
    hash, not by `look`.
    """

    def __init__(self, hasher=_sha256):
        self._hash = hasher
        self._known: dict[Path, tuple] = {}          # path -> (fingerprint, sha256)
        self._lock = threading.Lock()

    def look(self, record: InstalledModel) -> tuple[str, str]:
        if not record.components:
            return MISMATCH, "no file identities were recorded when it was installed"
        pending = False
        for item in record.components:
            name = Path(item.path).name
            observed = _fingerprint(item.path)
            if observed is None:
                return MISSING, f"{name} is missing"
            if isinstance(observed, str):
                return MISMATCH, f"{name} is {observed}"
            if observed[2] != item.size:
                return MISMATCH, (f"{name} is {observed[2]} bytes; the installed file "
                                  f"was {item.size}")
            with self._lock:
                known = self._known.get(Path(item.path))
            if known is None or known[0] != observed:
                pending = True
            elif known[1] != item.sha256:
                return MISMATCH, f"{name} no longer matches its recorded SHA-256"
        if pending:
            return PENDING, ("The files have their installed sizes and are checked "
                             "against their recorded SHA-256 before the model loads.")
        return VERIFIED, "Every file matched its recorded SHA-256 when last read."

    def confirm(self, record: InstalledModel, cancelled=None) -> tuple[str, str] | None:
        """Hash what `look` cannot vouch for. None when cancelled part-way."""
        state, detail = self.look(record)
        if state != PENDING:
            return state, detail
        for item in record.components:
            path = Path(item.path)
            before = _fingerprint(path)
            with self._lock:
                known = self._known.get(path)
            if known is not None and known[0] == before:
                continue
            digest = self._hash(path, cancelled)
            if digest is None:
                return None
            if _fingerprint(path) != before:
                return MISMATCH, f"{path.name} changed while it was being checked"
            with self._lock:
                self._known[path] = (before, digest)
        return self.look(record)


class LocalEngine:
    """Managed-engine answers for the runtime facade."""

    def __init__(self, selection: engine.Selection, data_root: Path, *,
                 registry, settings_for, managed: engine.ManagedEngine | None = None,
                 resources=None):
        self.selection = selection
        self.data_root = Path(data_root)
        # () -> (available memory bytes | None, free disk bytes | None)
        self.resources = resources or self._observe_resources
        self.registry = registry              # () -> {model_id: InstalledModel}
        self.settings_for = settings_for      # (model_id) -> LaunchSettings | None
        self.engine = managed or (engine.ManagedEngine(selection, data_root)
                                  if selection.manifest else None)
        self.checks = FileChecks()
        self._lock = threading.Lock()

    # -- observation ------------------------------------------------------
    def probe(self) -> dict:
        """What is installed, and whether its files are still the installed bytes.

        A model whose files are present is listed. Its digest is published only
        while its files are not known to differ; `file_checks` says which of
        verified, pending (sizes match, hashed before loading) or mismatch.
        """
        installed, checks = {}, {}
        try:
            for model_id, record in self.registry().items():
                state, detail = self.checks.look(record)
                if state == MISSING:
                    continue
                installed[model_id] = record
                checks[model_id] = {"state": state, "detail": detail}
        except Exception as exc:                           # noqa: BLE001
            error = f"model records unavailable: {exc}"
        else:
            error = None
        problems = list(self.selection.problems)
        if self.engine is not None and self.engine.last_error is not None:
            last = self.engine.last_error
        else:
            last = None
        loaded = None
        if self.engine is not None and self.engine.running and self.engine.model:
            loaded = {"model": self.engine.model.model_id, "size_bytes": None,
                      "size_vram_bytes": None, "expires_at": None}
        return {
            "reachable": self.selection.usable and self.engine is not None,
            "server_version": self.selection.runtime_version,
            "runtime": engine.LLAMA_CPP,
            "engine": self.engine.describe() if self.engine else self.selection.describe(),
            "models": sorted(installed),
            "digests": {k: v.manifest_sha256 for k, v in installed.items()
                        if checks[k]["state"] != MISMATCH},
            "file_checks": checks,
            "loaded": loaded,
            "endpoint": "Refinix engine (loopback, started by Refinix)",
            "error": ("; ".join(problems) if problems else
                      (str(last) if last is not None else error)),
        }

    def capabilities(self, model_id: str) -> list[str] | None:
        try:
            record = self.registry().get(model_id)
        except Exception:                                  # noqa: BLE001
            return None
        if record is None or self.checks.look(record)[0] in (MISSING, MISMATCH):
            return None
        return list(record.capabilities)

    # -- execution --------------------------------------------------------
    def stream_chat(self, messages, *, profile, inference, should_cancel=None,
                    images=None, response_format=None, watch_class=None,
                    unavailable=RuntimeError):
        if self.engine is None or not self.selection.usable:
            raise unavailable("The Refinix engine is missing or was modified: "
                              + "; ".join(self.selection.problems or ["not installed"]))
        model_id = profile.model.model_id
        record = self.registry().get(model_id)
        if record is None or self.checks.look(record)[0] == MISSING:
            raise unavailable(f"{model_id} is not installed on this computer.")
        # The profile names exact bytes. A record whose manifest differs is a
        # different model, however it is labelled.
        if record.manifest_sha256 != profile.model.manifest_sha256 \
                or profile.model.runtime != engine.LLAMA_CPP \
                or profile.model.runtime_version != self.selection.runtime_version:
            raise unavailable("the qualified profile is bound to different model "
                              "bytes or another engine build")
        settings = self.settings_for(model_id)
        if settings is None:
            raise unavailable(f"there is no reviewed engine preset for {model_id} "
                              "on this computer")
        # The bytes about to be loaded (or already loaded) are the installed
        # bytes, read now rather than remembered from the install record.
        checked = self.checks.confirm(record, cancelled=should_cancel)
        if checked is None:
            yield "cancelled", {}
            return
        if checked[0] != VERIFIED:
            self.unload(model_id)
            raise unavailable(f"{model_id} is not the verified file Refinix installed: "
                              f"{checked[1]}. Remove it and install it again from "
                              "Settings → Models.")
        files = engine.ModelFiles(model_id, Path(record.weights),
                                  Path(record.projector) if record.projector else None)
        if not (self.engine.running and self.engine.model == files
                and self.engine.settings == settings):
            short = self._short_of(settings)
            if short:
                raise unavailable(short)
        try:
            endpoint = self.engine.ensure(files, settings, cancelled=should_cancel)
        except engine.EngineError as exc:
            if exc.code == "engine_cancelled":
                yield "cancelled", {}
                return
            raise unavailable(str(exc)) from exc
        if self.checks.look(record)[0] != VERIFIED:
            # Replaced between the hash and the engine opening it.
            self.unload(model_id)
            raise unavailable(f"{model_id} changed while it was loading, so it was "
                              "not used.")
        yield from runtime_llamacpp.stream_chat(
            endpoint, messages, profile=profile, inference=inference,
            should_cancel=should_cancel, images=images,
            response_format=response_format, sampling=record.sampling,
            watch_class=watch_class, unavailable=unavailable)

    def _observe_resources(self):
        available = free = None
        try:
            import psutil
            available = int(psutil.virtual_memory().available)
        except Exception:                                  # noqa: BLE001
            pass
        try:
            import shutil
            free = int(shutil.disk_usage(self.data_root).free)
        except OSError:
            pass
        return available, free

    def _short_of(self, settings) -> str | None:
        """Why this computer cannot start the engine now, or None.

        Checked when a model is about to load, not on every request: a model
        already loaded has already taken its memory. An unknown reading is not
        a refusal; it is reported by the engine if loading then fails.
        """
        available, free = self.resources()
        gib = 1024 ** 3
        need = settings.min_available_memory_bytes
        if need and available is not None and available < need:
            return (f"There is not enough free memory to load the model: "
                    f"{available / gib:.1f} GB is free and {need / gib:.1f} GB is "
                    "needed. Close other apps, then try again.")
        need = settings.min_free_disk_bytes
        if need and free is not None and free < need:
            return (f"There is not enough free disk space for this work: "
                    f"{free / gib:.1f} GB is free and {need / gib:.1f} GB is needed "
                    "beside the workspace.")
        return None

    def unload(self, model_id: str) -> None:
        """Stop an engine serving `model_id`; a survivor is reported by `engine`."""
        if self.engine is not None and self.engine.model is not None \
                and self.engine.model.model_id == model_id:
            try:
                self.engine.stop()
            except engine.EngineError:
                pass

    def stop(self) -> bool:
        return self.engine.stop() if self.engine is not None else False
