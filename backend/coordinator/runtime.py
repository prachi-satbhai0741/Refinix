"""The inference runtime facade every caller uses.

Two runtimes sit behind the same functions — `probe`, `model_capabilities`,
`model_state`, `stream_chat` — and the same normalised stream records, and
both may serve the same process at once:

* the **Refinix engine** (`local_engine` + `runtime_llamacpp`), a pinned,
  integrity-verified llama.cpp that Refinix starts itself on loopback; and
* **Ollama**, when the person has it, used through its official local API so
  the models they already pulled run where they are, without copying weights.

Which one runs a request is decided by the model's origin, recorded in its
`ModelRef.runtime`, never by a process-wide switch. Model identity across both
is an origin-qualified key (`model_key`), because one model name may exist in
each runtime and a bare name cannot say which.

Bounded settings come from the execution profile, including the reasoning
switch, without which some models spend the whole output budget reasoning and
return an empty answer.

Ollama is used only when its API meets `OLLAMA_BASELINE`: the request fields
that make it refuse an oversized prompt instead of silently trimming it
(`truncate`, `shift`; v0.12.6) and the model fields that say whether a model
runs on another host (`remote_host`, `remote_model`; v0.12.0). Both dates are
read from the official `api/types.go` at those tags. A newer version is never
refused for being new.

Standard library only. Nothing here reaches beyond loopback.
"""

from __future__ import annotations

import base64
import json
import http.client
import os
import socket
import threading
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from backend.contracts import profiles as inference_profiles
from backend.contracts import v1

HOST = "http://127.0.0.1:11434"
MODEL = "qwen3.5:4b-q4_K_M"

# The vision component C08 sends rendered scan pages to. Recorded in
# docs/model-catalog.md as an INSTALLED CANDIDATE: the tag is a third-party
# Ollama conversion, and nothing here infers its provenance, licence, accuracy
# or MODALITY from its name. The exact tag is configuration, never discovery —
# a missing model fails as absent rather than being fetched.
#
# The override exists so a device checkpoint can point C08 at a different
# ALREADY-INSTALLED model without a code change and without a download. It is
# not a download manager and it cannot fetch anything: an unknown tag is
# reported absent.
OCR_MODEL = os.environ.get("AEGIS_OCR_MODEL", "").strip() or "MedAIBase/PaddleOCR-VL:0.9b"

# What a model must declare before this build will send it a page image.
# Ollama reports a model's modalities on /api/show; a tag whose name contains
# "VL" or "OCR" is a name, not an observation.
VISION_CAPABILITY = "vision"

# One page's rendered image, after base64. Ollama takes the encoded string, so
# the ceiling is applied to the raw bytes before encoding.
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGES_PER_REQUEST = 1

# docs/model-catalog.md, "Bounded execution settings for the first path".
# 8192 measured on the macOS coordinator 2026-09-04: +220 MiB resident over
# 4096, warm time-to-first-token unchanged (0.196 s -> 0.203 s), and a fact
# planted at the start of a 3052-token prompt was still retrieved. The Ubuntu
# worker keeps 4096 until it is measured at its own device checkpoint.
NUM_CTX = 8192
NUM_PREDICT = 2048
# The safe default, not a prohibition. docs/model-catalog.md records why:
# with reasoning on, this model spent the whole 128- and 512-token output
# budget thinking and returned an empty answer. Chat now allows 2048, and the
# user can turn reasoning on per model; a request that still ends with nothing
# visible fails honestly rather than saving a blank reply.
THINK = False
KEEP_ALIVE = "10m"


OLLAMA = "ollama"
LLAMA_CPP = "llama.cpp"
ORIGINS = (OLLAMA, LLAMA_CPP)
KEY_SEPARATOR = "|"

# The oldest Ollama whose API carries everything Refinix relies on: overflow
# refusal (`truncate`/`shift` on /api/chat, added in v0.12.6) and model
# locality (`remote_host`/`remote_model` on /api/tags and /api/show, added in
# v0.12.0). Below it a long prompt could be trimmed without saying so, and a
# cloud model could not be told apart from a local one.
OLLAMA_BASELINE = (0, 12, 6)
OLLAMA_BASELINE_LABEL = "0.12.6"
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"

# Locality answers. "unknown" is never treated as local.
LOCAL, REMOTE, UNKNOWN = "local", "remote", "unknown"

# How long a capability/locality read is reused by status pages. The read made
# immediately before input is sent is always fresh.
SHOW_CACHE_SECONDS = 30.0

# The Refinix engine, when this process has one. Set once at startup by the
# desktop lifecycle.
_MANAGED = None
# Whether Ollama is consulted beside the Refinix engine. Without a Refinix
# engine Ollama is the only runtime and is always consulted; with one, the
# desktop lifecycle turns this on so a person's existing Ollama models stay
# usable. Tests that configure a fake engine leave it off and stay isolated
# from whatever Ollama happens to be running on the developer's computer.
_OLLAMA_ALONGSIDE = False
_SHOW_CACHE: dict[str, tuple[float, dict | None]] = {}
_SHOW_LOCK = threading.Lock()


def configure_managed(backend) -> None:
    """Make Refinix's own engine available to this process."""
    global _MANAGED
    _MANAGED = backend


def configure_ollama(enabled: bool) -> None:
    """Consult the person's Ollama beside the Refinix engine."""
    global _OLLAMA_ALONGSIDE
    _OLLAMA_ALONGSIDE = bool(enabled)


def managed_engine():
    return _MANAGED


def ollama_active() -> bool:
    return _MANAGED is None or _OLLAMA_ALONGSIDE


def model_key(origin: str, model_id: str) -> str:
    """One model's identity across runtimes: its origin, then its exact name."""
    return f"{origin}{KEY_SEPARATOR}{model_id}"


def split_key(value: str) -> tuple[str | None, str]:
    """`(origin, model_id)`, or `(None, value)` for a bare legacy name.

    Ollama names cannot contain the separator and Refinix chooses its own
    engine's ids, so a value only splits when it starts with a known origin.
    """
    origin, separator, rest = (value or "").partition(KEY_SEPARATOR)
    if separator and origin in ORIGINS and rest:
        return origin, rest
    return None, value


def version_tuple(text) -> tuple[int, ...] | None:
    """`0.34.2-rc1` -> (0, 34, 2); None when no leading version is readable."""
    parts = []
    for piece in str(text or "").strip().lstrip("v").split("."):
        digits = ""
        for char in piece:
            if not char.isdigit():
                break
            digits += char
        if not digits:
            break
        parts.append(int(digits))
        if len(digits) != len(piece):
            break
    return tuple(parts) if len(parts) >= 2 else None


def ollama_baseline_met(version) -> bool | None:
    """True/False against `OLLAMA_BASELINE`; None when the version is unreadable."""
    parsed = version_tuple(version)
    if parsed is None:
        return None
    padded = parsed + (0,) * (3 - len(parsed))
    return padded >= OLLAMA_BASELINE


def engine_label(origin: str | None = None) -> str:
    """How a runtime is named to a person, on any OS."""
    if origin == OLLAMA or (origin is None and _MANAGED is None):
        return "Ollama"
    return "the Refinix engine"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeUnavailable("local runtime redirect rejected")


class RuntimeUnavailable(RuntimeError):
    """The local runtime did not answer. Never dressed up as a model reply."""


class _CancelWatch:
    """Aborts a blocked stream read so a cancel does not wait out the timeout.

    Polling `should_cancel` between chunks only works while chunks arrive. When
    the model stalls, the socket read blocks for the whole 300 s request
    timeout, and the user's Stop appears to do nothing. This watcher shuts the
    socket down from a second thread, which makes the blocked read return at
    once; the reader then reports the cancellation.
    """

    POLL_SECONDS = 0.2

    def __init__(self, response, should_cancel):
        self._response = response
        self.connection = None
        self._should_cancel = should_cancel
        self._done = threading.Event()
        self.fired = False
        self._thread = threading.Thread(target=self._watch, daemon=True,
                                        name="runtime-cancel-watch")

    def __enter__(self):
        if self._should_cancel is not None:
            self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._done.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)
        if self.connection is not None:
            self.connection.close()
        return False

    def response(self, response):
        self._response = response
        if self.fired:
            self._abort()

    def _watch(self):
        while not self._done.wait(self.POLL_SECONDS):
            try:
                cancelled = self._should_cancel()
            except Exception:                          # noqa: BLE001
                cancelled = False
            if not cancelled:
                continue
            self.fired = True
            self._abort()
            return

    def _abort(self):
        """Close the connection under the blocked reader, then release it."""
        sock = getattr(getattr(self._response, "fp", None), "raw", None)
        sock = getattr(sock, "_sock", None)
        sock = sock or getattr(self.connection, "sock", None)
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        try:
            self._response.close()
        except Exception:                              # noqa: BLE001
            pass


def _request(path: str, payload=None, timeout=10, *, watch=None):
    url = f"{HOST}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    if watch is not None:
        # Own the connection before waiting for response headers. urllib.open
        # returns too late to cancel a model that has not sent any headers yet.
        address = urlsplit(HOST)
        if address.scheme != "http" or address.hostname not in ("127.0.0.1", "::1"):
            raise RuntimeUnavailable("the model runtime must use numeric loopback HTTP")
        connection = watch.connection = http.client.HTTPConnection(
            address.hostname, address.port, timeout=2)
        if watch.fired:
            raise RuntimeUnavailable("request cancelled")
        connection.connect()
        if watch.fired:
            watch._abort()
            raise RuntimeUnavailable("request cancelled")
        connection.sock.settimeout(timeout)
        connection.request("POST" if data is not None else "GET", path,
                           body=data, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        watch.response(response)
        if 300 <= response.status < 400:
            response.close()
            raise RuntimeUnavailable("local runtime redirect rejected")
        if response.status >= 400:
            raise urllib.error.HTTPError(url, response.status, response.reason,
                                         response.headers, response)
        return response
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    # Ignore environment proxies and redirects, including on health reads.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    return opener.open(req, timeout=timeout)


def _is_remote(record: dict) -> bool:
    """Whether Ollama says this model runs on another host (v0.12.0 fields)."""
    return bool(record.get("remote_host") or record.get("remote_model"))


def ollama_running(timeout: float = 5) -> list[dict]:
    """Every model Ollama holds resident now (`/api/ps`), whoever loaded it."""
    with _request("/api/ps", timeout=timeout) as resp:
        running = json.load(resp).get("models", [])
    return [{
        "model": item.get("model"),
        "digest": (item.get("digest") or "").lower() or None,
        "size_bytes": item.get("size"),
        "size_vram_bytes": item.get("size_vram"),
        "context_length": item.get("context_length"),
        "expires_at": item.get("expires_at"),
    } for item in running if item.get("model")]


def probe_ollama() -> dict:
    """Read-only Ollama health probe. Reports what was observed, never a default."""
    state = {"reachable": False, "server_version": None, "models": [],
             "digests": {}, "loaded": None, "loaded_all": [], "endpoint": HOST,
             "error": None, "runtime": OLLAMA, "remote": [], "capabilities": {},
             "sizes": {}, "details": {}, "tags_read": False,
             "baseline": {"minimum": OLLAMA_BASELINE_LABEL, "met": None}}
    try:
        with _request("/api/version", timeout=3) as resp:
            state["server_version"] = json.load(resp).get("version")
            state["reachable"] = True
    except Exception as exc:
        state["error"] = f"{type(exc).__name__}: {exc}"
        return state
    state["baseline"]["met"] = ollama_baseline_met(state["server_version"])
    try:
        with _request("/api/tags", timeout=5) as resp:
            listed = json.load(resp).get("models", [])
        state["models"] = [m.get("model") for m in listed if m.get("model")]
        # The real manifest digest, observed here rather than looked up again,
        # so a ModelRef carries integrity evidence instead of a placeholder.
        state["digests"] = {m.get("model"): (m.get("digest") or "").lower()
                            for m in listed if m.get("model")}
        state["remote"] = [m["model"] for m in listed
                           if m.get("model") and _is_remote(m)]
        state["capabilities"] = {
            m["model"]: [c for c in m["capabilities"] if isinstance(c, str)]
            for m in listed if m.get("model") and isinstance(m.get("capabilities"), list)}
        state["sizes"] = {m["model"]: m["size"] for m in listed
                          if m.get("model") and isinstance(m.get("size"), int)}
        state["details"] = {m["model"]: m["details"] for m in listed
                            if m.get("model") and isinstance(m.get("details"), dict)}
        state["tags_read"] = True
    except Exception as exc:
        state["error"] = f"tags unavailable: {exc}"
    # Each local model's own description (cached briefly): what it can do,
    # how long a context it declares, and a second locality answer.
    state["context_lengths"] = {}
    state["show_read"] = {}
    if state["baseline"]["met"]:
        for model_id in state["models"]:
            if model_id in state["remote"]:
                continue
            facts = show_model(model_id)
            state["show_read"][model_id] = facts is not None
            if facts is None:
                continue
            if facts["locality"] == REMOTE:
                state["remote"].append(model_id)
                continue
            if facts.get("capabilities") is not None:
                state["capabilities"][model_id] = facts["capabilities"]
            if facts.get("context_length"):
                state["context_lengths"][model_id] = facts["context_length"]
    try:
        # Every resident model, including ones other applications loaded:
        # Refinix counts their memory and never unloads them.
        state["loaded_all"] = ollama_running()
        if state["loaded_all"]:
            first = state["loaded_all"][0]
            state["loaded"] = {key: first[key] for key in
                               ("model", "size_bytes", "size_vram_bytes", "expires_at")}
    except Exception as exc:
        state["error"] = f"ps unavailable: {exc}"
    return state


def probe() -> dict:
    """Read-only health probe of every runtime this process uses.

    One runtime keeps its own flat shape. With both, the answer carries each
    runtime under `runtimes` plus origin-qualified `models` and `digests`.
    Callers read either through `entries`, never by assuming a shape.
    """
    if _MANAGED is None:
        return probe_ollama()
    managed = _MANAGED.probe()
    if not _OLLAMA_ALONGSIDE:
        return managed
    return merge({LLAMA_CPP: managed, OLLAMA: probe_ollama()})


def merge(states: dict[str, dict]) -> dict:
    """Combine per-runtime probes into one origin-qualified view."""
    view = {"runtimes": states, "runtime": None, "server_version": None,
            "reachable": any(s.get("reachable") for s in states.values()),
            "endpoint": "loopback runtimes", "loaded": None}
    found = entries(view)
    view["models"] = sorted(found)
    view["digests"] = {key: item["digest"] for key, item in found.items()
                       if item["digest"]}
    managed = states.get(LLAMA_CPP) or {}
    view["engine"] = managed.get("engine")
    view["file_checks"] = {model_key(LLAMA_CPP, model_id): check for model_id, check
                           in (managed.get("file_checks") or {}).items()}
    errors = [f"{origin}: {s['error']}" for origin, s in states.items()
              if s.get("error")]
    view["error"] = "; ".join(errors) or None
    return view


def substate(state: dict | None, origin: str) -> dict:
    """One runtime's own probe out of either shape; {} when it was not probed."""
    if not state:
        return {}
    if "runtimes" in state:
        return state["runtimes"].get(origin) or {}
    return state if (state.get("runtime") or OLLAMA) == origin else {}


def _entries_one(sub: dict, origin: str) -> dict[str, dict]:
    if not sub or not sub.get("reachable"):
        return {}
    version = sub.get("server_version")
    remote = set(sub.get("remote") or ())
    capabilities = sub.get("capabilities") or {}
    digests = sub.get("digests") or {}
    baseline = ollama_baseline_met(version) if origin == OLLAMA else True
    found = {}
    for model_id in sub.get("models") or []:
        if not model_id:
            continue
        if origin == LLAMA_CPP:
            # Started by Refinix from its verified binary, on loopback, with
            # --offline: local by construction rather than by a metadata read.
            locality = LOCAL
        elif model_id in remote:
            locality = REMOTE
        elif baseline and sub.get("tags_read", True):
            # Under the v0.12+ response contract an absent remote field is a
            # statement that the model is local, not a gap in the reading.
            locality = LOCAL
        else:
            locality = UNKNOWN
        key = model_key(origin, model_id)
        found[key] = {
            "key": key, "origin": origin, "model_id": model_id,
            "digest": (digests.get(model_id) or "").lower() or None,
            "runtime_version": version, "locality": locality,
            "capabilities": capabilities.get(model_id),
            "context_length": (sub.get("context_lengths") or {}).get(model_id),
            "reasoning_hint": bool((sub.get("reasoning_hints") or {}).get(model_id)),
            "hints": tuple((sub.get("hints") or {}).get(model_id) or ()),
            "size_bytes": (sub.get("sizes") or {}).get(model_id),
            "details": (sub.get("details") or {}).get(model_id),
        }
    return found


def entries(state: dict | None) -> dict[str, dict]:
    """Every observed model, by origin-qualified key, from either probe shape."""
    if not state:
        return {}
    if "runtimes" in state:
        found = {}
        for origin, sub in (state.get("runtimes") or {}).items():
            found.update(_entries_one(sub, origin))
        return found
    return _entries_one(state, state.get("runtime") or OLLAMA)


def find(state: dict | None, model: str) -> dict | None:
    """One observed model by key, or by a bare name only when it is unambiguous."""
    found = entries(state)
    origin, model_id = split_key(model or "")
    if origin is not None:
        return found.get(model)
    matches = [item for item in found.values() if item["model_id"] == model_id]
    return matches[0] if len(matches) == 1 else None


def _show(model_id: str) -> dict | None:
    """One `/api/show` read: capabilities, locality and declared context."""
    try:
        with _request("/api/show", {"model": model_id}, timeout=5) as resp:
            body = json.load(resp)
    except Exception:                                  # noqa: BLE001
        return None
    listed = body.get("capabilities")
    info = body.get("model_info") if isinstance(body.get("model_info"), dict) else {}
    architecture = info.get("general.architecture")
    context = info.get(f"{architecture}.context_length") if architecture else None
    return {
        "capabilities": ([item for item in listed if isinstance(item, str)]
                         if isinstance(listed, list) else None),
        "locality": REMOTE if _is_remote(body) else LOCAL,
        "context_length": context if isinstance(context, int) and context > 0 else None,
        "architecture": architecture if isinstance(architecture, str) else None,
        "details": body.get("details") if isinstance(body.get("details"), dict) else {},
        "requires": body.get("requires") if isinstance(body.get("requires"), str) else None,
    }


def show_model(model_id: str, *, fresh: bool = False) -> dict | None:
    """Cached `/api/show` facts for status reads; `fresh` always asks again."""
    import time
    now = time.monotonic()
    if not fresh:
        with _SHOW_LOCK:
            cached = _SHOW_CACHE.get(model_id)
        if cached is not None and now - cached[0] < SHOW_CACHE_SECONDS:
            return cached[1]
    observed = _show(model_id)
    with _SHOW_LOCK:
        _SHOW_CACHE[model_id] = (now, observed)
    return observed


def model_facts(model: str) -> dict | None:
    """Capabilities, locality and declared context for one model key or name."""
    origin, model_id = split_key(model)
    if origin is None:
        origin = (LLAMA_CPP if _MANAGED is not None and not _OLLAMA_ALONGSIDE
                  else OLLAMA)
        if _MANAGED is not None and _OLLAMA_ALONGSIDE:
            try:
                if model_id in _MANAGED.registry():
                    origin = LLAMA_CPP
            except Exception:                          # noqa: BLE001
                pass
    if origin == LLAMA_CPP:
        if _MANAGED is None:
            return None
        listed = _MANAGED.capabilities(model_id)
        facts = getattr(_MANAGED, "facts", None)
        extra = facts(model_id) if callable(facts) else {}
        return {"capabilities": listed, "locality": LOCAL, **(extra or {})}
    if not ollama_active():
        return None
    return show_model(model_id)


def model_capabilities(model: str) -> list[str] | None:
    """What the runtime says this model can do, or `None` if unobservable.

    `/api/show` is a metadata read: measured at about 10 ms locally, and it
    does not load the model. `None` means the question could not be answered
    here, which is deliberately not the same as "it can do nothing".
    """
    facts = model_facts(model)
    return None if facts is None else facts.get("capabilities")


def confirm_ollama(model: v1.ModelRef) -> dict:
    """Re-read one Ollama model's identity and locality right before use.

    The digest comes from `/api/tags` (`/api/show` has none) and locality from
    both reads. A changed version, digest or locality means the model is no
    longer the one this attempt was admitted with, so nothing is sent.
    Returns the fresh `/api/show` facts.
    """
    try:
        with _request("/api/version", timeout=3) as resp:
            version = json.load(resp).get("version")
    except Exception as exc:
        raise RuntimeUnavailable(f"Ollama did not answer: {exc}") from exc
    if ollama_baseline_met(version) is not True:
        raise RuntimeUnavailable(
            f"Ollama {version or '(version unreadable)'} is older than "
            f"{OLLAMA_BASELINE_LABEL}, which Refinix needs so long prompts are refused "
            f"rather than silently trimmed. Update Ollama ({OLLAMA_DOWNLOAD_URL}).")
    if version != model.runtime_version:
        raise RuntimeUnavailable(
            f"Ollama changed from {model.runtime_version} to {version} after this "
            "request was prepared, so it was not sent. Try again.")
    try:
        with _request("/api/tags", timeout=5) as resp:
            listed = json.load(resp).get("models", [])
    except Exception as exc:
        raise RuntimeUnavailable(f"Ollama's model list could not be read: {exc}") from exc
    record = next((item for item in listed if item.get("model") == model.model_id), None)
    if record is None:
        raise RuntimeUnavailable(f"{model.model_id} is no longer installed in Ollama.")
    if (record.get("digest") or "").lower() != model.manifest_sha256:
        raise RuntimeUnavailable(
            f"{model.model_id} changed in Ollama after this request was prepared, "
            "so it was not sent. Try again.")
    if _is_remote(record):
        raise RuntimeUnavailable(
            f"{model.model_id} runs on another host through Ollama, so Refinix "
            "does not send your work to it.")
    facts = show_model(model.model_id, fresh=True)
    if facts is None:
        raise RuntimeUnavailable(
            f"Ollama did not describe {model.model_id}, so its locality could not "
            "be confirmed and nothing was sent.")
    if facts["locality"] != LOCAL:
        raise RuntimeUnavailable(
            f"{model.model_id} runs on another host through Ollama, so Refinix "
            "does not send your work to it.")
    return facts


def model_state_from(health: dict, model: str, *, requires: str | None = None,
                     capabilities: list[str] | None = None) -> dict:
    """Read one model's state out of an ALREADY OBSERVED probe.

    Separated from `model_state` so a status page that has just probed the
    runtime does not probe it again per model. Nothing here can cause a
    download: it only reports what that observation contained.

    `requires` names a modality the caller needs — `vision` for C08. It is
    checked against `capabilities`, which the caller observed from
    `/api/show`. A model that is installed but does not declare the modality
    is its own state: it needs neither a runtime restart nor an install, so
    folding it into `absent` or `runtime_unavailable` would send someone to
    fix the wrong thing.
    """
    origin, model_id = split_key(model or "")
    if not health.get("reachable") or (origin is not None
                                       and not substate(health, origin).get("reachable")):
        label = engine_label(origin)
        return {"state": "runtime_unavailable", "model": model, "digest": None,
                "capabilities": None,
                "detail": f"{label[0].upper()}{label[1:]} is not answering.",
                "runtime_version": None}
    entry = find(health, model) if model else None
    version = (entry or {}).get("runtime_version") or health.get("server_version")
    if entry is None:
        return {"state": "absent", "model": model, "digest": None,
                "capabilities": None,
                "detail": (f"{model_id} is not installed on this computer. Choose "
                           "or download a model in Settings → Models."),
                "runtime_version": version}
    model = model_id
    digest = entry["digest"]
    if entry["locality"] != LOCAL:
        return {"state": "not_local", "model": model, "digest": digest,
                "capabilities": None,
                "detail": (f"{model} runs on another host through Ollama, so Refinix "
                           "does not use it." if entry["locality"] == REMOTE else
                           f"Whether {model} runs on this computer could not be "
                           "confirmed, so Refinix does not use it."),
                "runtime_version": version}
    if requires is not None:
        if capabilities is None:
            return {"state": "capability_unknown", "model": model, "digest": digest,
                    "capabilities": None,
                    "detail": (f"The runtime did not report what {model} can do, so "
                               f"Refinix cannot confirm it accepts {requires} input."),
                    "runtime_version": version}
        if requires not in capabilities:
            return {"state": "missing_capability", "model": model, "digest": digest,
                    "capabilities": list(capabilities),
                    "detail": (f"{model} is installed, but the runtime reports it as "
                               f"{', '.join(capabilities) or 'having no capabilities'} "
                               f"— it does not accept {requires} input on this "
                               "computer."),
                    "runtime_version": version}
    return {"state": "installed", "model": model, "digest": digest,
            "capabilities": list(capabilities) if capabilities is not None else None,
            "detail": f"{model} is installed and the runtime answered.",
            "runtime_version": version}


def model_state(model: str, *, requires: str | None = None) -> dict:
    """Whether one exact tag is usable here, separating every failure mode.

    "The runtime is not answering", "the runtime does not have this model" and
    "the model is here and cannot do this" need three different fixes, so they
    are never collapsed into one unavailable. Nothing in this function can
    cause a download.
    """
    health = probe()
    observed = None
    entry = find(health, model) if health.get("reachable") else None
    if requires is not None and entry is not None:
        observed = model_capabilities(entry["key"])
    return model_state_from(health, model, requires=requires,
                            capabilities=observed)


def _check_images(images: list[bytes] | None) -> None:
    """The same bounds for every engine: raw bytes, counted and capped."""
    if not images:
        return
    if len(images) > MAX_IMAGES_PER_REQUEST:
        raise RuntimeUnavailable(
            f"at most {MAX_IMAGES_PER_REQUEST} image(s) may be sent in one request")
    for item in images:
        if not isinstance(item, (bytes, bytearray)):
            raise RuntimeUnavailable("images must be supplied as raw bytes")
        if not item:
            raise RuntimeUnavailable("an empty image cannot be sent")
        if len(item) > MAX_IMAGE_BYTES:
            raise RuntimeUnavailable(
                f"an image exceeded {MAX_IMAGE_BYTES // (1024 * 1024)} MB")


def _with_images(messages: list[dict], images: list[bytes] | None) -> list[dict]:
    """Attach request-scoped image bytes to the final user message.

    Images are base64-encoded in memory and never written to disk, never
    referenced by path or URL, and never taken from the model: only the caller
    that rendered the page can supply them.
    """
    if not images:
        return messages
    if len(images) > MAX_IMAGES_PER_REQUEST:
        raise RuntimeUnavailable(
            f"at most {MAX_IMAGES_PER_REQUEST} image(s) may be sent in one request")
    encoded = []
    for item in images:
        if not isinstance(item, (bytes, bytearray)):
            # A str here would be a path or a URL. Neither is ever fetched.
            raise RuntimeUnavailable("images must be supplied as raw bytes")
        if not item:
            raise RuntimeUnavailable("an empty image cannot be sent")
        if len(item) > MAX_IMAGE_BYTES:
            raise RuntimeUnavailable(
                f"an image exceeded {MAX_IMAGE_BYTES // (1024 * 1024)} MB")
        encoded.append(base64.b64encode(bytes(item)).decode("ascii"))
    prepared = [dict(message) for message in messages]
    for message in reversed(prepared):
        if message.get("role") == "user":
            message["images"] = encoded
            return prepared
    raise RuntimeUnavailable("an image request needs a user message to carry it")


def stream_chat(messages: list[dict], *, profile: v1.ExecutionProfile,
                inference: v1.InferenceRequest, should_cancel=None,
                images: list[bytes] | None = None,
                response_format: dict | None = None):
    """Yield ('delta', text), optionally ('thinking', text), then ('done', metrics).

    `think` is the request-scoped reasoning choice and becomes Ollama's
    top-level `/api/chat` field. It is snapshotted by the caller, so changing
    the switch later cannot alter a request that is already running. No Qwen
    `/think` or `/nothink` prompt suffix is used: this model documents
    API-controlled thinking and does not support those Qwen 3 soft switches.

    `should_cancel` is polled between chunks, and also on its own thread by
    `_CancelWatch`, which aborts the connection when the stream stalls — without
    it a cancel would wait out the whole request timeout, and a quiet reasoning
    period looks exactly like a stall. Raises RuntimeUnavailable rather than
    returning a plausible-looking empty answer.
    """
    if profile.model.runtime == LLAMA_CPP:
        if _MANAGED is None:
            raise RuntimeUnavailable("The Refinix engine is not part of this installation.")
        _check_images(images)
        yield from _MANAGED.stream_chat(
            messages, profile=profile, inference=inference,
            should_cancel=should_cancel, images=images,
            response_format=response_format, watch_class=_CancelWatch,
            unavailable=RuntimeUnavailable)
        return
    if profile.model.runtime != OLLAMA or not ollama_active():
        raise RuntimeUnavailable(
            f"{profile.model.runtime} is not a runtime this installation uses.")
    # Local policy: this function only ever runs on the computer that owns the
    # workspace. Workers validate with the strict measured-only check.
    try:
        inference_profiles.validate_local(profile, inference, profile.model)
    except ValueError as exc:
        raise RuntimeUnavailable(str(exc)) from exc
    # The model must still be the exact local bytes this attempt was admitted
    # with. Nothing is sent when it changed or runs elsewhere.
    confirm_ollama(profile.model)
    if response_format is None and inference.decoder != "text":
        raise RuntimeUnavailable("the selected profile requires structured output")
    if response_format is not None:
        digest = inference_profiles.schema_sha256(response_format)
        if inference.decoder != "json_schema" \
                or inference.decoder_schema_sha256 != digest:
            raise RuntimeUnavailable("the decoder schema does not match the request")
    reasoning = inference.reasoning == "enabled"
    output_limit = inference.output_allowance_tokens
    context_window = inference.context_window_tokens
    payload = {
        "model": profile.model.model_id,
        "messages": _with_images(messages, images),
        "stream": True,
        "think": reasoning, "keep_alive": KEEP_ALIVE,
        # Estimates select history; the runtime must reject real overflow.
        "truncate": False, "shift": False,
        "options": {"num_ctx": context_window,
                    "num_predict": output_limit},
    }
    if response_format is not None:
        # Ollama structured output. The schema constrains the decoder, so a
        # malformed shape is far less likely — it is not a guarantee, and the
        # caller still parses strictly and refuses anything unexpected.
        payload["format"] = response_format
    with _CancelWatch(None, should_cancel) as watch:
        try:
            if should_cancel is not None and should_cancel():
                yield "cancelled", {}
                return
            try:
                resp = _request("/api/chat", payload, timeout=300, watch=watch)
            except urllib.error.HTTPError as exc:
                with exc:
                    detail = exc.read().decode("utf-8", "replace")
                if "exceed_context_size_error" in detail or "exceeds the available context size" in detail:
                    raise RuntimeUnavailable(
                        f"Context window exceeded ({context_window} tokens). Shorten your message "
                        "or start a new chat. The runtime rejected the request without trimming it.") from exc
                raise RuntimeUnavailable(f"HTTP {exc.code}: {detail[:200]}") from exc
            with resp:
                watch.response(resp)
                yield from _read_stream(resp, watch, should_cancel,
                                        output_limit=output_limit,
                                        context_window=context_window,
                                        profile=profile, inference=inference)
        except (RuntimeUnavailable, OSError, http.client.HTTPException) as exc:
            if watch.fired or (should_cancel is not None and should_cancel()):
                yield "cancelled", {}
                return
            if isinstance(exc, RuntimeUnavailable):
                raise
            raise RuntimeUnavailable(f"{HOST} unreachable: {exc}") from exc


def _read_stream(resp, watch, should_cancel, *, output_limit=NUM_PREDICT,
                 context_window=NUM_CTX, profile=None, inference=None):
    """Yield stream records until the runtime finishes or the watcher aborts."""
    try:
        for raw in resp:
            if watch.fired:
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeUnavailable(f"malformed stream line: {line[:160]!r}") from exc
            if obj.get("error"):
                raise RuntimeUnavailable(str(obj["error"]))
            if should_cancel is not None and should_cancel():
                yield "cancelled", {}
                return
            message = obj.get("message") or {}
            # Reasoning arrives on its own field. It is progress, never the
            # answer: it is not collected, saved, searched, exported or shown.
            reasoning = message.get("thinking") or ""
            if reasoning:
                yield "thinking", reasoning
            chunk = message.get("content") or ""
            if chunk:
                yield "delta", chunk
            if obj.get("done"):
                yield "done", _metrics(
                    obj, output_limit=output_limit,
                    context_window=context_window, profile=profile,
                    inference=inference)
                return
    except RuntimeUnavailable:
        raise
    except Exception as exc:                           # noqa: BLE001
        # Destroying the connection is how a cancel reaches a blocked read, so
        # once the watcher has fired, ANY failure from that read is our own
        # doing and means cancelled — not a runtime fault. Which exception
        # arrives depends on where the read was: an aborted chunked response
        # raises http.client.IncompleteRead, which is neither OSError nor
        # ValueError, so narrowing this except clause lets it escape.
        if not watch.fired:
            raise RuntimeUnavailable(f"stream read failed: {exc}") from exc
    if watch.fired:
        yield "cancelled", {}
        return
    raise RuntimeUnavailable("stream ended without a done record")


def _metrics(obj: dict, *, output_limit: int = NUM_PREDICT,
             context_window: int = NUM_CTX,
             profile: v1.ExecutionProfile | None = None,
             inference: v1.InferenceRequest | None = None) -> dict:
    ns = 1_000_000_000
    prompt_count, output_count = obj.get("prompt_eval_count"), obj.get("eval_count")
    limit = None
    if obj.get("done_reason") == "length":
        context_full = (isinstance(prompt_count, int) and isinstance(output_count, int)
                        and prompt_count + output_count >= context_window)
        output_full = isinstance(output_count, int) and output_count >= output_limit
        # Counts establish which bounds were reached, not which fired first.
        limit = ("context_and_output" if context_full and output_full else
                 "context" if context_full else "output" if output_full else "unknown")
    return {
        "done_reason": obj.get("done_reason"),
        "limit_reason": limit,
        "requested_profile_id": inference.profile_id if inference else None,
        "actual_profile_id": profile.profile_id if profile else None,
        "context_window": context_window,
        "output_token_limit": output_limit,
        "reasoning": inference.reasoning if inference else None,
        "decoder": inference.decoder if inference else None,
        "eval_count": obj.get("eval_count"),
        "output_tokens": obj.get("eval_count"),
        # Runtime-reported counts. These are MEASURED, unlike the
        # coordinator's character-based pre-flight estimate.
        "prompt_tokens": obj.get("prompt_eval_count"),
        "prompt_eval_ms": round(obj["prompt_eval_duration"] / 1e6)
        if obj.get("prompt_eval_duration") else None,
        "eval_ms": round(obj["eval_duration"] / 1e6)
        if obj.get("eval_duration") else None,
        "load_ms": round(obj["load_duration"] / 1e6)
        if obj.get("load_duration") else None,
        "total_ms": round(obj["total_duration"] / 1e6)
        if obj.get("total_duration") else None,
        "tokens_per_s": round(obj["eval_count"] / (obj["eval_duration"] / ns), 2)
        if obj.get("eval_count") and obj.get("eval_duration") else None,
    }
