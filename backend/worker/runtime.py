"""Ollama adapter for the worker.

Deliberately a near-copy of the coordinator's adapter rather than a shared
import: the worker ships inside a pinned image with its own dependency set, and
must not acquire a build-time dependency on coordinator code that is not in the
image. The bounded settings come from the same model catalogue.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from backend.contracts import profiles as inference_profiles
from backend.contracts import v1

# In a Pod the runtime is reached through an explicit address. There is no
# default that silently points at the public Internet.
HOST = os.environ.get("AEGIS_RUNTIME_HOST", "http://127.0.0.1:11434")
MODEL = os.environ.get("AEGIS_MODEL", "qwen3.5:4b-q4_K_M")

# docs/model-catalog.md, "Bounded execution settings for the first path".
# The worker keeps 4096 until the Ubuntu device measures its own window.
# These legacy environment values remain visible for deployment diagnostics,
# but no production model call trusts them.  Qualified profiles below own the
# settings a remote caller is allowed to request.
NUM_CTX = int(os.environ.get("AEGIS_NUM_CTX", "4096"))
NUM_PREDICT = int(os.environ.get("AEGIS_NUM_PREDICT", "2048"))
THINK = False
TARGET_PROFILE_ID = os.environ.get("AEGIS_TARGET_PROFILE_ID", "").strip() or None
KEEP_ALIVE = os.environ.get("AEGIS_KEEP_ALIVE", "10m")


class RuntimeUnavailable(RuntimeError):
    """The local runtime did not answer. Never dressed up as a model reply."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def _post(path: str, payload=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"{HOST}{path}", data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect())
    return opener.open(request, timeout=timeout)


def probe() -> dict:
    """Read-only health probe. Reports what was observed, never a default."""
    state = {"reachable": False, "server_version": None, "models": [],
             "digests": {}, "loaded": None, "endpoint": HOST, "error": None}
    try:
        with _post("/api/version", timeout=3) as response:
            state["server_version"] = json.load(response).get("version")
            state["reachable"] = True
    except Exception as exc:                                  # noqa: BLE001
        state["error"] = f"{type(exc).__name__}: {exc}"
        return state
    try:
        with _post("/api/tags", timeout=5) as response:
            listed = json.load(response).get("models", [])
        state["models"] = [m.get("model") for m in listed]
        # The real manifest digest, so ModelRef carries integrity evidence
        # rather than a placeholder.
        state["digests"] = {m.get("model"): (m.get("digest") or "").lower()
                            for m in listed}
    except Exception as exc:                                  # noqa: BLE001
        state["error"] = f"tags unavailable: {exc}"
    try:
        # Being installed is not being loaded. Only /api/ps observes residency.
        with _post("/api/ps", timeout=5) as response:
            resident = json.load(response).get("models") or []
        state["loaded"] = resident[0].get("model") if resident else None
    except Exception:                                          # noqa: BLE001
        state["loaded"] = None
    return state


def qualified_profiles(observed: dict | None = None) -> list[v1.ExecutionProfile]:
    observed = probe() if observed is None else observed
    if not observed.get("reachable"):
        return []
    refs = []
    for model, digest in (observed.get("digests") or {}).items():
        if model and isinstance(digest, str) and len(digest) == 64:
            try:
                refs.append(v1.ModelRef(
                    model_id=model, manifest_sha256=digest, runtime="ollama",
                    runtime_version=observed.get("server_version") or "unknown"))
            except ValueError:
                continue
    return inference_profiles.for_observation(
        target_profile_id=TARGET_PROFILE_ID, models=refs)


def resolve_profile(profile_id: str, observed: dict | None = None) \
        -> v1.ExecutionProfile | None:
    return inference_profiles.by_id(profile_id, qualified_profiles(observed))


def stream_chat(messages: list[dict], *, profile: v1.ExecutionProfile,
                inference: v1.InferenceRequest, should_cancel=None,
                timeout: float = 600.0, response_format: dict | None = None):
    """Yield ('delta', text) then ('done', metrics).

    Truncation and context shifting are disabled, so an oversized prompt is
    rejected rather than silently trimmed.
    """
    current = resolve_profile(inference.profile_id)
    if current is None or current.profile_id != profile.profile_id:
        raise RuntimeUnavailable("the requested profile is stale or no longer qualified")
    try:
        inference_profiles.validate_request(current, inference, current.model)
    except ValueError as exc:
        raise RuntimeUnavailable(str(exc)) from exc
    if response_format is None and inference.decoder != "text":
        raise RuntimeUnavailable("the selected profile requires structured output")
    if response_format is not None:
        digest = inference_profiles.schema_sha256(response_format)
        if inference.decoder != "json_schema" \
                or inference.decoder_schema_sha256 != digest:
            raise RuntimeUnavailable("the decoder schema does not match the request")
    payload = {
        "model": current.model.model_id, "messages": messages, "stream": True,
        "think": inference.reasoning == "enabled", "keep_alive": KEEP_ALIVE,
        "truncate": False, "shift": False,
        "options": {"num_ctx": inference.context_window_tokens,
                    "num_predict": inference.output_allowance_tokens},
    }
    if response_format is not None:
        payload["format"] = response_format
    try:
        response = _post("/api/chat", payload, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:512].lower()
        if b"context" in detail or exc.code == 400:
            raise RuntimeUnavailable(
                f"Context window exceeded ({inference.context_window_tokens} tokens). The runtime "
                "rejected the request without trimming it.") from exc
        # Status only. The body may contain prompt or filesystem detail.
        raise RuntimeUnavailable(f"the local runtime returned HTTP {exc.code}") from exc
    except OSError as exc:
        raise RuntimeUnavailable(f"local runtime unreachable: {exc}") from exc

    with response:
        for raw in response:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeUnavailable("malformed runtime stream") from exc
            if obj.get("error"):
                # Upstream text can carry prompt or path data; do not echo it.
                raise RuntimeUnavailable("the local runtime reported an error")
            if should_cancel is not None and should_cancel():
                yield "cancelled", {}
                return
            chunk = (obj.get("message") or {}).get("content") or ""
            if chunk:
                yield "delta", chunk
            if obj.get("done"):
                prompt_count = obj.get("prompt_eval_count")
                output_count = obj.get("eval_count")
                limit = None
                if obj.get("done_reason") == "length":
                    context_full = (isinstance(prompt_count, int) and isinstance(output_count, int)
                                    and prompt_count + output_count
                                    >= inference.context_window_tokens)
                    output_full = (isinstance(output_count, int) and output_count
                                   >= inference.output_allowance_tokens)
                    # Counts establish which bounds were reached, not which fired
                    # first. Matches the accepted C03 coordinator semantics.
                    limit = ("context_and_output" if context_full and output_full else
                             "context" if context_full else "output" if output_full else "unknown")
                yield "done", {
                    "done_reason": obj.get("done_reason"),
                    "limit_reason": limit,
                    "requested_profile_id": inference.profile_id,
                    "actual_profile_id": current.profile_id,
                    "context_window": inference.context_window_tokens,
                    "output_token_limit": inference.output_allowance_tokens,
                    "reasoning": inference.reasoning,
                    "decoder": inference.decoder,
                    "prompt_tokens": prompt_count,
                    "output_tokens": output_count,
                    "runtime_ms": round(obj["total_duration"] / 1e6)
                    if obj.get("total_duration") else None,
                }
                return
    raise RuntimeUnavailable("stream ended without a done record")
