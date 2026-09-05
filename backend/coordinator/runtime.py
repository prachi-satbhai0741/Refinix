"""Ollama adapter — the only inference path in C03.

OD-03 selected Ollama; OD-05 selected one model. Bounded settings come from the
model catalogue, including `think: false`, without which this model spends the
whole output budget reasoning and returns an empty answer.

Standard library only. Nothing here reaches beyond loopback.
"""

from __future__ import annotations

import json
import http.client
import socket
import threading
import urllib.error
import urllib.request
from urllib.parse import urlsplit

HOST = "http://127.0.0.1:11434"
MODEL = "qwen3.5:4b-q4_K_M"

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
             "loaded": None, "endpoint": HOST, "error": None}
    try:
        with _request("/api/version", timeout=3) as resp:
            state["server_version"] = json.load(resp).get("version")
            state["reachable"] = True
    except Exception as exc:
        state["error"] = f"{type(exc).__name__}: {exc}"
        return state
    try:
        with _request("/api/tags", timeout=5) as resp:
            state["models"] = [m.get("model") for m in json.load(resp).get("models", [])]
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


def stream_chat(messages: list[dict], *, should_cancel=None, think: bool | None = None,
                model: str | None = None, num_predict: int | None = None):
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
    payload = {
        "model": model or MODEL, "messages": messages, "stream": True,
        "think": reasoning, "keep_alive": KEEP_ALIVE,
        # Estimates select history; the runtime must reject real overflow.
        "truncate": False, "shift": False,
        "options": {"num_ctx": NUM_CTX,
                    "num_predict": NUM_PREDICT if num_predict is None else num_predict},
    }
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
                yield from _read_stream(resp, watch, should_cancel)
        except (RuntimeUnavailable, OSError, http.client.HTTPException) as exc:
            if watch.fired or (should_cancel is not None and should_cancel()):
                yield "cancelled", {}
                return
            if isinstance(exc, RuntimeUnavailable):
                raise
            raise RuntimeUnavailable(f"{HOST} unreachable: {exc}") from exc


def _read_stream(resp, watch, should_cancel):
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
                yield "done", _metrics(obj)
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


def _metrics(obj: dict) -> dict:
    ns = 1_000_000_000
    prompt_count, output_count = obj.get("prompt_eval_count"), obj.get("eval_count")
    limit = None
    if obj.get("done_reason") == "length":
        context_full = (isinstance(prompt_count, int) and isinstance(output_count, int)
                        and prompt_count + output_count >= NUM_CTX)
        output_full = isinstance(output_count, int) and output_count >= NUM_PREDICT
        # Counts establish which bounds were reached, not which fired first.
        limit = ("context_and_output" if context_full and output_full else
                 "context" if context_full else "output" if output_full else "unknown")
    return {
        "done_reason": obj.get("done_reason"),
        "limit_reason": limit,
        "context_window": NUM_CTX,
        "output_token_limit": NUM_PREDICT,
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
