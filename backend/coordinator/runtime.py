"""Ollama adapter — the only inference path in C03.

OD-03 selected Ollama; OD-05 selected one model. Bounded settings come from the
model catalogue, including `think: false`, without which this model spends the
whole output budget reasoning and returns an empty answer.

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


def probe() -> dict:
    """Read-only health probe. Reports what was observed, never a default."""
    state = {"reachable": False, "server_version": None, "models": [],
             "digests": {}, "loaded": None, "endpoint": HOST, "error": None}
    try:
        with _request("/api/version", timeout=3) as resp:
            state["server_version"] = json.load(resp).get("version")
            state["reachable"] = True
    except Exception as exc:
        state["error"] = f"{type(exc).__name__}: {exc}"
        return state
    try:
        with _request("/api/tags", timeout=5) as resp:
            listed = json.load(resp).get("models", [])
        state["models"] = [m.get("model") for m in listed]
        # The real manifest digest, observed here rather than looked up again,
        # so a ModelRef carries integrity evidence instead of a placeholder.
        state["digests"] = {m.get("model"): (m.get("digest") or "").lower()
                            for m in listed if m.get("model")}
    except Exception as exc:
        state["error"] = f"tags unavailable: {exc}"
    try:
        with _request("/api/ps", timeout=5) as resp:
            running = json.load(resp).get("models", [])
            if running:
                state["loaded"] = {
                    "model": running[0].get("model"),
                    "size_bytes": running[0].get("size"),
                    "size_vram_bytes": running[0].get("size_vram"),
                    "expires_at": running[0].get("expires_at"),
                }
    except Exception as exc:
        state["error"] = f"ps unavailable: {exc}"
    return state


def installed_models() -> dict:
    """`{tag: manifest digest}` as the local runtime reports it, or `{}`.

    Read-only. Listing what is installed cannot install anything, and an empty
    result is reported as "could not observe", never as "nothing is installed".
    """
    try:
        with _request("/api/tags", timeout=5) as resp:
            listed = json.load(resp).get("models", [])
    except Exception:                                  # noqa: BLE001
        return {}
    return {entry.get("model"): (entry.get("digest") or "").lower()
            for entry in listed if entry.get("model")}


def model_capabilities(model: str) -> list[str] | None:
    """What the runtime says this model can do, or `None` if unobservable.

    `/api/show` is a metadata read: measured at about 10 ms locally, and it
    does not load the model. `None` means the question could not be answered
    here, which is deliberately not the same as "it can do nothing".
    """
    try:
        with _request("/api/show", {"model": model}, timeout=5) as resp:
            listed = json.load(resp).get("capabilities")
    except Exception:                                  # noqa: BLE001
        return None
    if not isinstance(listed, list):
        return None
    return [item for item in listed if isinstance(item, str)]


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
    if not health.get("reachable"):
        return {"state": "runtime_unavailable", "model": model, "digest": None,
                "capabilities": None,
                "detail": f"The local model runtime at {HOST} is not answering.",
                "runtime_version": None}
    installed = model in (health.get("models") or [])
    digest = (health.get("digests") or {}).get(model) or None
    version = health.get("server_version")
    if not installed:
        return {"state": "absent", "model": model, "digest": None,
                "capabilities": None,
                "detail": (f"{model} is not installed on this computer. Refinix "
                           "does not download models."),
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
    if requires is not None and health.get("reachable") \
            and model in (health.get("models") or []):
        observed = model_capabilities(model)
    return model_state_from(health, model, requires=requires,
                            capabilities=observed)


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


def stream_chat(messages: list[dict], *, should_cancel=None, think: bool | None = None,
                model: str | None = None, num_predict: int | None = None,
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
    reasoning = THINK if think is None else bool(think)
    output_limit = NUM_PREDICT if num_predict is None else num_predict
    payload = {
        "model": model or MODEL, "messages": _with_images(messages, images),
        "stream": True,
        "think": reasoning, "keep_alive": KEEP_ALIVE,
        # Estimates select history; the runtime must reject real overflow.
        "truncate": False, "shift": False,
        "options": {"num_ctx": NUM_CTX,
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
                        f"Context window exceeded ({NUM_CTX} tokens). Shorten your message "
                        "or start a new chat. The runtime rejected the request without trimming it.") from exc
                raise RuntimeUnavailable(f"HTTP {exc.code}: {detail[:200]}") from exc
            with resp:
                watch.response(resp)
                yield from _read_stream(resp, watch, should_cancel,
                                        output_limit=output_limit)
        except (RuntimeUnavailable, OSError, http.client.HTTPException) as exc:
            if watch.fired or (should_cancel is not None and should_cancel()):
                yield "cancelled", {}
                return
            if isinstance(exc, RuntimeUnavailable):
                raise
            raise RuntimeUnavailable(f"{HOST} unreachable: {exc}") from exc


def _read_stream(resp, watch, should_cancel, *, output_limit=NUM_PREDICT):
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
                yield "done", _metrics(obj, output_limit=output_limit)
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


def _metrics(obj: dict, *, output_limit: int = NUM_PREDICT) -> dict:
    ns = 1_000_000_000
    prompt_count, output_count = obj.get("prompt_eval_count"), obj.get("eval_count")
    limit = None
    if obj.get("done_reason") == "length":
        context_full = (isinstance(prompt_count, int) and isinstance(output_count, int)
                        and prompt_count + output_count >= NUM_CTX)
        output_full = isinstance(output_count, int) and output_count >= output_limit
        # Counts establish which bounds were reached, not which fired first.
        limit = ("context_and_output" if context_full and output_full else
                 "context" if context_full else "output" if output_full else "unknown")
    return {
        "done_reason": obj.get("done_reason"),
        "limit_reason": limit,
        "context_window": NUM_CTX,
        "output_token_limit": output_limit,
        "eval_count": obj.get("eval_count"),
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
