"""Ollama's identity reads, answered for an offline test stand-in.

Before any input is sent, the runtime facade re-reads a model's identity and
locality (`runtime.confirm_ollama`): `/api/version`, `/api/tags` (the digest)
and `/api/show` (capabilities and locality). A test server that replays a chat
stream answers those reads through this helper, so the real confirmation path
is exercised instead of being stubbed out.

Test support only: nothing in the product imports it.
"""

from __future__ import annotations

import json


def _send(handler, body: dict) -> None:
    data = json.dumps(body).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)
    handler.wfile.flush()


def answer(handler, model, *, capabilities=("completion", "thinking"),
           remote: bool = False) -> bool:
    """Answer one identity read for `model` (a ModelRef); True when it was one."""
    path = handler.path.split("?", 1)[0]
    extra = {"remote_host": "https://ollama.com:443", "remote_model": model.model_id} \
        if remote else {}
    if handler.command == "GET" and path == "/api/version":
        _send(handler, {"version": model.runtime_version})
        return True
    if handler.command == "GET" and path == "/api/tags":
        _send(handler, {"models": [{"name": model.model_id, "model": model.model_id,
                                    "digest": model.manifest_sha256, "size": 1,
                                    **extra}]})
        return True
    if handler.command == "POST" and path == "/api/show":
        _send(handler, {"capabilities": list(capabilities),
                        "model_info": {"general.architecture": "test",
                                       "test.context_length": 8192},
                        "details": {}, **extra})
        return True
    return False
