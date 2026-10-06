"""Streaming adapter for the managed `llama-server` engine.

Speaks the engine's OpenAI-compatible `/v1/chat/completions` stream and turns it
into exactly the records the rest of Refinix already consumes from the Ollama
adapter: `('thinking', text)`, `('delta', text)`, `('cancelled', {})` and one
`('done', metrics)` whose keys match `runtime._metrics`. Callers cannot tell
which engine answered except by the recorded runtime identity, which is the
point: qualification binds that identity, nothing else changes.

* Reasoning is a per-request template switch (`chat_template_kwargs`), and the
  engine returns it on its own `reasoning_content` field, so it is progress and
  never the answer.
* Structured output uses the engine's JSON-Schema decoding; the caller still
  parses strictly.
* Stop works on a stalled read: the shared `_CancelWatch` shuts the socket
  down, which also ends generation in the engine.
* Overflow is refused, not trimmed: the engine is started with the qualified
  window and reports `exceed_context_size_error`.

Standard library only. Loopback only: the endpoint host is always 127.0.0.1.
"""

from __future__ import annotations

import base64
import http.client
import json

from backend.contracts import profiles as inference_profiles
from backend.contracts import v1
from backend.coordinator.engine import Endpoint

# Matches runtime.MAX_IMAGE_BYTES / MAX_IMAGES_PER_REQUEST; imported lazily there.
TIMEOUT_SECONDS = 300


def _content(message: dict, images: list[str] | None) -> dict:
    if not images:
        return {"role": message["role"], "content": message.get("content", "")}
    parts = [{"type": "text", "text": message.get("content", "")}]
    for encoded in images:
        parts.append({"type": "image_url",
                      "image_url": {"url": f"data:image/png;base64,{encoded}"}})
    return {"role": message["role"], "content": parts}


def build_payload(messages: list[dict], *, model_id: str, inference: v1.InferenceRequest,
                  response_format: dict | None, images: list[bytes] | None,
                  sampling: dict | None = None) -> dict:
    """The request body. Images ride on the final user message only."""
    encoded = [base64.b64encode(bytes(item)).decode("ascii") for item in (images or [])]
    last_user = max((i for i, m in enumerate(messages) if m.get("role") == "user"),
                    default=None)
    if encoded and last_user is None:
        raise ValueError("an image request needs a user message to carry it")
    converted = [_content(m, encoded if i == last_user else None)
                 for i, m in enumerate(messages)]
    payload = {
        "model": model_id,
        "messages": converted,
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": inference.output_allowance_tokens,
        "chat_template_kwargs": {"enable_thinking": inference.reasoning == "enabled"},
        "cache_prompt": True,
    }
    if sampling:
        payload.update({k: v for k, v in sampling.items()
                        if k in ("temperature", "top_k", "top_p", "min_p",
                                 "presence_penalty", "repeat_penalty", "seed")})
    if response_format is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "refinix", "schema": response_format, "strict": True}}
    return payload


def metrics(final: dict, *, inference: v1.InferenceRequest | None,
            profile: v1.ExecutionProfile | None) -> dict:
    """Map the engine's final record onto the existing metric names."""
    choice = (final.get("choices") or [{}])[0]
    finish = choice.get("finish_reason")
    timings = final.get("timings") or {}
    usage = final.get("usage") or {}
    # `prompt_n` counts only tokens the engine processed for this request; the
    # ones it reused from its prompt cache are `cache_n`. The context actually
    # occupied is their sum, which is also what `usage.prompt_tokens` reports.
    if isinstance(usage.get("prompt_tokens"), int):
        prompt_tokens = usage["prompt_tokens"]
    elif isinstance(timings.get("prompt_n"), int):
        prompt_tokens = timings["prompt_n"] + (timings.get("cache_n") or 0)
    else:
        prompt_tokens = None
    output_tokens = (usage.get("completion_tokens")
                     if isinstance(usage.get("completion_tokens"), int)
                     else timings.get("predicted_n"))
    context_window = inference.context_window_tokens if inference else None
    output_limit = inference.output_allowance_tokens if inference else None
    done_reason = "stop" if finish == "stop" else "length" if finish == "length" \
        else (finish or None)
    limit = None
    if done_reason == "length":
        context_full = (isinstance(prompt_tokens, int) and isinstance(output_tokens, int)
                        and context_window is not None
                        and prompt_tokens + output_tokens >= context_window)
        output_full = (isinstance(output_tokens, int) and output_limit is not None
                       and output_tokens >= output_limit)
        limit = ("context_and_output" if context_full and output_full else
                 "context" if context_full else "output" if output_full else "unknown")
    prompt_ms = timings.get("prompt_ms")
    predicted_ms = timings.get("predicted_ms")
    total = (prompt_ms or 0) + (predicted_ms or 0) if (prompt_ms or predicted_ms) else None
    return {
        "done_reason": done_reason,
        "limit_reason": limit,
        "requested_profile_id": inference.profile_id if inference else None,
        "actual_profile_id": profile.profile_id if profile else None,
        "context_window": context_window,
        "output_token_limit": output_limit,
        "reasoning": inference.reasoning if inference else None,
        "decoder": inference.decoder if inference else None,
        "eval_count": output_tokens,
        "output_tokens": output_tokens,
        "prompt_tokens": prompt_tokens,
        "cached_prompt_tokens": timings.get("cache_n"),
        "processed_prompt_tokens": timings.get("prompt_n"),
        "prompt_eval_ms": round(prompt_ms) if prompt_ms is not None else None,
        "eval_ms": round(predicted_ms) if predicted_ms is not None else None,
        "load_ms": None,
        "total_ms": round(total) if total is not None else None,
        "tokens_per_s": (round(timings["predicted_per_second"], 2)
                         if timings.get("predicted_per_second") else None),
    }


def stream_chat(endpoint: Endpoint, messages: list[dict], *,
                profile: v1.ExecutionProfile, inference: v1.InferenceRequest,
                should_cancel=None, images: list[bytes] | None = None,
                response_format: dict | None = None, sampling: dict | None = None,
                watch_class=None, unavailable=RuntimeError):
    """Yield stream records from the managed engine, honouring Stop."""
    # The Refinix engine only serves the computer that owns the workspace, so
    # the local policy applies: a measured profile, or an honest candidate.
    try:
        inference_profiles.validate_local(profile, inference, profile.model)
    except ValueError as exc:
        raise unavailable(str(exc)) from exc
    if response_format is None and inference.decoder != "text":
        raise unavailable("the selected profile requires structured output")
    if response_format is not None:
        digest = inference_profiles.schema_sha256(response_format)
        if inference.decoder != "json_schema" or inference.decoder_schema_sha256 != digest:
            raise unavailable("the decoder schema does not match the request")
    if endpoint.host != "127.0.0.1":
        raise unavailable("the engine must listen on numeric loopback")
    try:
        payload = build_payload(messages, model_id=endpoint.model_id, inference=inference,
                                response_format=response_format, images=images,
                                sampling=sampling)
    except ValueError as exc:
        raise unavailable(str(exc)) from exc
    body = json.dumps(payload).encode("utf-8")
    connection = response = None
    with watch_class(None, should_cancel) as watch:
        try:
            if should_cancel is not None and should_cancel():
                yield "cancelled", {}
                return
            connection = watch.connection = http.client.HTTPConnection(
                endpoint.host, endpoint.port, timeout=2)
            if watch.fired:
                yield "cancelled", {}
                return
            connection.connect()
            connection.sock.settimeout(TIMEOUT_SECONDS)
            connection.request("POST", "/v1/chat/completions", body=body, headers={
                "Content-Type": "application/json", "Accept": "text/event-stream",
                "Authorization": f"Bearer {endpoint.api_key}"})
            response = connection.getresponse()
            watch.response(response)
            if response.status >= 400:
                detail = response.read(4096).decode("utf-8", "replace")
                if "exceed_context_size_error" in detail \
                        or "exceeds the available context size" in detail:
                    raise unavailable(
                        f"Context window exceeded ({inference.context_window_tokens} tokens). "
                        "Shorten your message or start a new chat. The runtime rejected "
                        "the request without trimming it.")
                raise unavailable(f"HTTP {response.status}: {detail[:200]}")
            yield from _read(response, watch, should_cancel, inference=inference,
                             profile=profile, unavailable=unavailable)
        except (OSError, http.client.HTTPException) as exc:
            if watch.fired or (should_cancel is not None and should_cancel()):
                yield "cancelled", {}
                return
            raise unavailable(f"the Refinix engine stopped answering: {exc}") from exc
        finally:
            # One request per connection; release the loopback socket however
            # the stream ended, including when the caller stops reading.
            if response is not None:
                response.close()
            if connection is not None:
                connection.close()


def _read(response, watch, should_cancel, *, inference, profile, unavailable):
    finish, timings, usage = None, None, None
    try:
        for raw in response:
            if watch.fired:
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line or line.startswith(":") or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                record = json.loads(data)
            except json.JSONDecodeError as exc:
                raise unavailable(f"malformed stream line: {data[:160]!r}") from exc
            if record.get("error"):
                raise unavailable(str(record["error"])[:256])
            if should_cancel is not None and should_cancel():
                yield "cancelled", {}
                return
            for choice in record.get("choices") or []:
                delta = choice.get("delta") or {}
                thinking = delta.get("reasoning_content") or ""
                if thinking:
                    yield "thinking", thinking
                content = delta.get("content") or ""
                if content:
                    yield "delta", content
                if choice.get("finish_reason"):
                    finish = choice["finish_reason"]
            # The engine may send timings and usage with the finish record or
            # in a trailing record with no choices; keep whichever came last.
            timings = record.get("timings") or timings
            usage = record.get("usage") or usage
    except unavailable:
        raise
    except Exception as exc:                               # noqa: BLE001
        if not watch.fired:
            raise unavailable(f"stream read failed: {exc}") from exc
    if watch.fired:
        yield "cancelled", {}
        return
    if finish is None:
        raise unavailable("stream ended without a finish record")
    final = {"choices": [{"finish_reason": finish}], "timings": timings or {},
             "usage": usage or {}}
    yield "done", metrics(final, inference=inference, profile=profile)
