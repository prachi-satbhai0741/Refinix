#!/usr/bin/env python3
"""OD-03 runtime comparison: Ollama versus llama.cpp's llama-server.

Measures one runtime per invocation against the same model, chat template,
prompt, context, output limit and sampling settings, and prints one JSON block
to return as checkpoint evidence.

This script never installs, downloads or starts anything. If the target server
is not already listening it exits with instructions and changes nothing. Start
the server yourself at the human checkpoint; the agent does not start services.

Failure is never silent. A malformed line, a streaming error object, a missing
terminal record or a missing metric aborts the run with a non-zero exit rather
than contributing a partial number to a median.

Standard library only, so it runs on the macOS coordinator (Python 3.14) and the
Ubuntu worker (Python 3.12) with no new dependency. The stream parsers are pure
functions over lines; scripts/test_od03_parser.py exercises them with no server.

Usage:
    python3 scripts/od03_runtime_comparison.py --target ollama --unload-first
    python3 scripts/od03_runtime_comparison.py --target llama-server
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request

# Identical across both runtimes. Changing any of these invalidates the
# comparison, so they are constants rather than flags. Both runtimes receive a
# CHAT request so the model's own chat template is applied on both sides; a raw
# completion on one side and a templated chat on the other is not a comparison.
PROMPT = (
    "In exactly three sentences, explain what a message queue does "
    "in a distributed system."
)
MESSAGES = [{"role": "user", "content": PROMPT}]
NUM_CTX = 4096
NUM_PREDICT = 128
TEMPERATURE = 0.0
SEED = 42

# qwen3.5 is a thinking model. Left on, it spends the whole output budget in its
# reasoning channel and returns an EMPTY visible answer -- measured on the macOS
# coordinator at both num_predict 128 and 512. Thinking is therefore off on both
# sides, and each runtime's own control is used: Ollama's `think` field and
# llama-server's `chat_template_kwargs.enable_thinking`.
THINK = False

# Prompt caching is left at each runtime's default. Disabling it on one side
# only would make the warm runs measure different work.

OLLAMA_URL = "http://127.0.0.1:11434"
LLAMA_URL = "http://127.0.0.1:8080"

THINK_MARKERS = ("<think>", "</think>", "<|thinking|>")


class StreamError(RuntimeError):
    """The stream was malformed, errored, or ended without its metrics."""


# --------------------------------------------------------------------------
# Request bodies -- returned with the results so a reviewer can see exactly
# what was held constant on each side.
# --------------------------------------------------------------------------

def ollama_body(model: str, keep_alive: str) -> dict:
    return {
        "model": model,
        "messages": MESSAGES,
        "stream": True,
        "keep_alive": keep_alive,
        "think": THINK,
        "options": {
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "temperature": TEMPERATURE,
            "seed": SEED,
        },
    }


def llama_body() -> dict:
    return {
        "messages": MESSAGES,
        "max_tokens": NUM_PREDICT,
        "temperature": TEMPERATURE,
        "seed": SEED,
        "stream": True,
        "stream_options": {"include_usage": True},
        # llama.cpp passes these into the GGUF's chat template; Qwen-style
        # templates read enable_thinking.
        "chat_template_kwargs": {"enable_thinking": THINK},
    }


# --------------------------------------------------------------------------
# Pure stream parsers -- no sockets, unit-testable offline.
# --------------------------------------------------------------------------

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def parse_ollama_stream(lines) -> dict:
    """lines: iterable of (elapsed_seconds, raw_line). Raises StreamError."""
    ttft = None
    response, thinking = [], []
    final = None
    for elapsed, raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StreamError(f"malformed JSON line: {line[:200]!r}") from exc
        if not isinstance(obj, dict):
            raise StreamError(f"unexpected stream item: {line[:200]!r}")
        if obj.get("error"):
            raise StreamError(f"server reported an error: {obj['error']}")
        msg = obj.get("message") or {}
        chunk, think_chunk = msg.get("content") or "", msg.get("thinking") or ""
        response.append(chunk)
        thinking.append(think_chunk)
        if ttft is None and (chunk or think_chunk):
            ttft = elapsed
        if obj.get("done"):
            final = obj
    if final is None:
        raise StreamError("stream ended without a done record")

    eval_count, eval_ns = final.get("eval_count"), final.get("eval_duration")
    if not eval_count or not eval_ns:
        raise StreamError(f"done record is missing eval metrics: {final!r}")
    if ttft is None:
        raise StreamError("no token was ever emitted")

    text = "".join(response)
    think_text = "".join(thinking)
    return {
        "ttft_s": round(ttft, 4),
        "output_tokens": eval_count,
        "tokens_per_s": round(eval_count / (eval_ns / 1e9), 2),
        "response_chars": len(text),
        "response_sha256": _hash(text),
        "thinking_chars": len(think_text),
        "thinking_suppressed": len(think_text) == 0,
        "visible_output_empty": len(text) == 0,
        "server_reported": {
            "load_duration_s": _ns(final.get("load_duration")),
            "prompt_eval_duration_s": _ns(final.get("prompt_eval_duration")),
            "eval_duration_s": _ns(eval_ns),
            "total_duration_s": _ns(final.get("total_duration")),
            "done_reason": final.get("done_reason"),
        },
    }


def parse_openai_stream(lines) -> dict:
    """OpenAI-compatible SSE, as served by llama-server. Raises StreamError."""
    ttft = None
    parts, reasoning = [], []
    usage, timings, saw_done = None, None, False
    for elapsed, raw in lines:
        line = raw.strip()
        if not line:
            continue
        if not line.startswith("data:"):
            raise StreamError(f"non-SSE line in stream: {line[:200]!r}")
        payload = line[5:].strip()
        if payload == "[DONE]":
            saw_done = True
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise StreamError(f"malformed SSE payload: {payload[:200]!r}") from exc
        if not isinstance(obj, dict):
            raise StreamError(f"unexpected SSE item: {payload[:200]!r}")
        if obj.get("error"):
            raise StreamError(f"server reported an error: {obj['error']}")
        if obj.get("usage"):
            usage = obj["usage"]
        if obj.get("timings"):
            timings = obj["timings"]
        for choice in obj.get("choices") or []:
            delta = choice.get("delta") or {}
            content = delta.get("content") or ""
            thought = delta.get("reasoning_content") or ""
            parts.append(content)
            reasoning.append(thought)
            if ttft is None and (content or thought):
                ttft = elapsed
    if not saw_done:
        raise StreamError("stream ended without the [DONE] sentinel")
    if ttft is None:
        raise StreamError("no token was ever emitted")
    if not usage and not timings:
        raise StreamError("stream carried neither a usage nor a timings record")

    text = "".join(parts)
    think_text = "".join(reasoning)
    tokens = (usage or {}).get("completion_tokens") or (timings or {}).get("predicted_n")
    if type(tokens) is not int or tokens <= 0:
        raise StreamError("no valid completion-token count in the stream")
    tps = (timings or {}).get("predicted_per_second")
    if tps is None:
        duration_ms = (timings or {}).get("predicted_ms")
        if (type(duration_ms) not in (int, float)
                or not math.isfinite(duration_ms) or duration_ms <= 0):
            raise StreamError("missing or invalid generation timing")
        tps = tokens / (duration_ms / 1000)
    if type(tps) not in (int, float) or not math.isfinite(tps) or tps <= 0:
        raise StreamError("missing or invalid generation timing")
    leaked = [m for m in THINK_MARKERS if m in text]
    return {
        "ttft_s": round(ttft, 4),
        "output_tokens": tokens,
        "tokens_per_s": round(tps, 2),
        "response_chars": len(text),
        "response_sha256": _hash(text),
        "thinking_chars": len(think_text),
        "thinking_suppressed": not think_text and not leaked,
        "thinking_markers_found": leaked,
        "visible_output_empty": len(text) == 0,
        "server_reported": {
            "prompt_ms": (timings or {}).get("prompt_ms"),
            "predicted_ms": (timings or {}).get("predicted_ms"),
            "usage": usage,
        },
    }


def _ns(v):
    return round(v / 1e9, 4) if isinstance(v, (int, float)) else None


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------

def _post_stream(url: str, payload: dict, timeout: int = 300):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                yield time.perf_counter() - started, raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise StreamError(f"HTTP {exc.code} from {url}: {exc.read()[:300]!r}") from exc
    except OSError as exc:
        raise StreamError(f"transport failure against {url}: {exc}") from exc


def _reachable(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=3).read(1)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def memory_snapshot(process_match: str) -> dict:
    out = {"rss_mb": None, "vram_mb": None, "note": ""}
    try:
        ps = subprocess.run(["ps", "-Ao", "rss,comm"],
                            capture_output=True, text=True, timeout=10)
        rss = [int(l.split()[0]) for l in ps.stdout.splitlines()[1:]
               if process_match in l.lower()]
        if rss:
            out["rss_mb"] = round(max(rss) / 1024, 1)
    except Exception as exc:
        out["note"] = f"rss unavailable: {exc}"
    try:
        smi = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=process_name,used_memory",
             "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        if smi.returncode == 0 and smi.stdout.strip():
            out["vram_mb"] = smi.stdout.strip()
    except FileNotFoundError:
        out["note"] = (out["note"] + " no nvidia-smi (expected on macOS)").strip()
    except Exception as exc:
        out["note"] = (out["note"] + f" vram unavailable: {exc}").strip()
    return out


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["ollama", "llama-server"], required=True)
    ap.add_argument("--model", default="qwen3.5:4b-q4_K_M",
                    help="Ollama model tag; ignored for llama-server")
    ap.add_argument("--warm-runs", type=int, default=3)
    ap.add_argument("--unload-first", action="store_true",
                    help="Ollama only: release the model first so the first run "
                         "genuinely includes model load.")
    args = ap.parse_args()

    if args.target == "ollama":
        url, proc = OLLAMA_URL, "ollama"
        body = lambda ka="10m": ollama_body(args.model, ka)   # noqa: E731
        run = lambda ka="10m": parse_ollama_stream(               # noqa: E731
            _post_stream(f"{OLLAMA_URL}/api/chat", body(ka)))
        start_hint = "ollama serve   (in its own terminal)"
    else:
        url, proc = LLAMA_URL, "llama-server"
        body = lambda ka=None: llama_body()                       # noqa: E731
        run = lambda ka=None: parse_openai_stream(                # noqa: E731
            _post_stream(f"{LLAMA_URL}/v1/chat/completions", llama_body()))
        start_hint = (
            "llama-server -m ~/.ollama/models/blobs/"
            "sha256-81fb60c7daa80fc1123380b98970b320ae233409f0f71a72ed7b9b0d62f40490 "
            f"-c {NUM_CTX} -ngl 999 --host 127.0.0.1 --port 8080"
        )

    if not _reachable(url):
        print(f"{args.target} is not listening on {url}.", file=sys.stderr)
        print("This script does not start services. Start it yourself with:",
              file=sys.stderr)
        print(f"    {start_hint}", file=sys.stderr)
        return 2

    result = {
        "target": args.target,
        "host": {"platform": platform.platform(), "machine": platform.machine(),
                 "python": platform.python_version()},
        "request_body": body(),
        "settings_summary": {
            "prompt": PROMPT, "num_ctx": NUM_CTX, "num_predict": NUM_PREDICT,
            "temperature": TEMPERATURE, "seed": SEED, "think": THINK,
            "templated_chat_request": True,
            "prompt_cache": "runtime default on both sides",
            "model": args.model if args.target == "ollama" else "GGUF passed to -m",
        },
        "collected_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    try:
        if args.target == "ollama":
            if args.unload_first:
                run("0")            # keep_alive 0 releases the model
                time.sleep(3)
                first_label = "cold_after_forced_unload"
                includes_load = True
            else:
                first_label = "first_request_model_may_be_resident"
                includes_load = False
        else:
            # llama-server loads the model at SERVER START, so its first request
            # does not include model load and is NOT comparable to Ollama's cold
            # run. A comparable figure must time server start -> first success.
            first_label = "first_request_after_server_start"
            includes_load = False

        print(f"{first_label} ...", file=sys.stderr)
        first = run()
        first["phase"] = first_label
        first["includes_model_load"] = includes_load
        if not includes_load:
            first["caveat"] = (
                "Model load is NOT inside this number. For llama-server, time "
                "server startup to the first successful request instead."
            )
        first["memory"] = memory_snapshot(proc)
        result["first_request"] = first

        warm = []
        for i in range(args.warm_runs):
            print(f"warm run {i + 1}/{args.warm_runs} ...", file=sys.stderr)
            warm.append(run())
        result["warm_runs"] = warm
    except StreamError as exc:
        print(f"RUN FAILED: {exc}", file=sys.stderr)
        print("No partial result is reported.", file=sys.stderr)
        return 1

    result["warm_median"] = {
        "ttft_s": round(statistics.median(r["ttft_s"] for r in warm), 4),
        "tokens_per_s": (round(statistics.median(
            r["tokens_per_s"] for r in warm), 2)
            if all(r["tokens_per_s"] for r in warm) else None),
    }
    hashes = {r["response_sha256"] for r in [first] + warm}
    result["all_responses_identical"] = len(hashes) == 1
    result["response_sha256_set"] = sorted(hashes)
    result["warm_memory"] = memory_snapshot(proc)

    if any(r["visible_output_empty"] for r in [first] + warm):
        print("WARNING: at least one run returned no visible output.",
              file=sys.stderr)
    if not all(r.get("thinking_suppressed") for r in [first] + warm):
        print("WARNING: thinking was not suppressed; latency is not comparable.",
              file=sys.stderr)

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
