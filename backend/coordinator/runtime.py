"""Ollama adapter — the only inference path in C03.

OD-03 selected Ollama; OD-05 selected one model. Bounded settings come from the
model catalogue, including `think: false`, without which this model spends the
whole output budget reasoning and returns an empty answer.

Standard library only. Nothing here reaches beyond loopback.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

HOST = "http://127.0.0.1:11434"
MODEL = "qwen3.5:4b-q4_K_M"

# docs/model-catalog.md, "Bounded execution settings for the first path".
# 8192 measured on the macOS coordinator 2026-09-04: +220 MiB resident over
# 4096, warm time-to-first-token unchanged (0.196 s -> 0.203 s), and a fact
# planted at the start of a 3052-token prompt was still retrieved. The Ubuntu
# worker keeps 4096 until it is measured at its own device checkpoint.
NUM_CTX = 8192
NUM_PREDICT = 2048
THINK = False
KEEP_ALIVE = "10m"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeUnavailable("local runtime redirect rejected")


class RuntimeUnavailable(RuntimeError):
    """The local runtime did not answer. Never dressed up as a model reply."""


def _request(path: str, payload=None, timeout=10):
    url = f"{HOST}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
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


def stream_chat(messages: list[dict], *, should_cancel=None):
    """Yield ('delta', text) then ('done', metrics).

    `should_cancel` is polled between chunks so a cancel request stops the read
    promptly. Raises RuntimeUnavailable rather than returning a plausible-looking
    empty answer.
    """
    payload = {
        "model": MODEL, "messages": messages, "stream": True,
        "think": THINK, "keep_alive": KEEP_ALIVE,
        # Estimates select history; the runtime must reject real overflow.
        "truncate": False, "shift": False,
        "options": {"num_ctx": NUM_CTX, "num_predict": NUM_PREDICT},
    }
    try:
        resp = _request("/api/chat", payload, timeout=300)
    except urllib.error.HTTPError as exc:
        with exc:
            detail = exc.read().decode("utf-8", "replace")
        if "exceed_context_size_error" in detail or "exceeds the available context size" in detail:
            raise RuntimeUnavailable(
                f"Context window exceeded ({NUM_CTX} tokens). Shorten your message "
                "or start a new chat. The runtime rejected the request without trimming it.") from exc
        raise RuntimeUnavailable(f"HTTP {exc.code}: {detail[:200]}") from exc
    except OSError as exc:
        raise RuntimeUnavailable(f"{HOST} unreachable: {exc}") from exc

    with resp:
        for raw in resp:
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
            chunk = (obj.get("message") or {}).get("content") or ""
            if chunk:
                yield "delta", chunk
            if obj.get("done"):
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
                yield "done", {
                    "done_reason": obj.get("done_reason"),
                    "limit_reason": limit,
                    "context_window": NUM_CTX,
                    "output_token_limit": NUM_PREDICT,
                    "eval_count": obj.get("eval_count"),
                    # Runtime-reported counts. These are MEASURED, unlike
                    # the coordinator's character-based pre-flight estimate.
                    "prompt_tokens": obj.get("prompt_eval_count"),
                    "prompt_eval_ms": round(obj["prompt_eval_duration"] / 1e6)
                    if obj.get("prompt_eval_duration") else None,
                    "eval_ms": round(obj["eval_duration"] / 1e6)
                    if obj.get("eval_duration") else None,
                    "load_ms": round(obj["load_duration"] / 1e6)
                    if obj.get("load_duration") else None,
                    "total_ms": round(obj["total_duration"] / 1e6)
                    if obj.get("total_duration") else None,
                    "tokens_per_s": round(
                        obj["eval_count"] / (obj["eval_duration"] / ns), 2)
                    if obj.get("eval_count") and obj.get("eval_duration") else None,
                }
                return
    raise RuntimeUnavailable("stream ended without a done record")
