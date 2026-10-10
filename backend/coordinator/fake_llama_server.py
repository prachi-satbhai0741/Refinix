"""A stand-in for `llama-server`, used only by the offline engine tests.

Behaviour is chosen by `fake-mode.json` beside this file, because the managed
engine deliberately starts its process with a minimal environment:

    {"mode": "ok" | "anonymous" | "wrong_build" | "die" | "stall" | "overflow"
             | "malformed" | "length" | "never_ready",
     "build": "b11390-test", "record": "<path to write the last request>"}

Not shipped: `desktop/packaging_plan.py` excludes it by name.
"""

from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def main(argv):
    config_path = Path(_arg(argv, "--fake-config", str(HERE / "fake-mode.json")))
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        config = {}
    mode = config.get("mode", "ok")
    if mode == "die":
        print("error loading model", flush=True)
        return 3
    port = int(_arg(argv, "--port", "8080"))
    key = _arg(argv, "--api-key")
    model = _arg(argv, "-m")
    alias = _arg(argv, "--alias", "model")
    build = config.get("build", "b11390-test")
    started = time.monotonic()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def _json(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorised(self):
            if mode == "anonymous":
                return True
            return self.headers.get("Authorization") == f"Bearer {key}"

        def do_GET(self):
            if self.path == "/health":
                if mode == "never_ready" or time.monotonic() - started < 0.2:
                    return self._json(503, {"error": "loading"})
                return self._json(200, {"status": "ok"})
            if self.path == "/props":
                if not self._authorised():
                    return self._json(401, {"error": "unauthorised"})
                reported = "b99999-other" if mode == "wrong_build" else build
                return self._json(200, {"build_info": reported, "model_path": model,
                                        "modalities": {"vision": "--mmproj" in argv}})
            return self._json(404, {})

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                return self._json(404, {})
            if not self._authorised():
                return self._json(401, {"error": "unauthorised"})
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if config.get("record"):
                Path(config["record"]).write_text(json.dumps(body), encoding="utf-8")
            if mode == "overflow":
                return self._json(400, {"error": {
                    "code": 400, "type": "exceed_context_size_error",
                    "message": "the request exceeds the available context size"}})
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()

            def send(record):
                self.wfile.write(f"data: {json.dumps(record)}\n\n".encode())
                self.wfile.flush()

            if mode == "malformed":
                self.wfile.write(b"data: {not json\n\n")
                self.wfile.flush()
                return
            thinking = body.get("chat_template_kwargs", {}).get("enable_thinking")
            if thinking:
                send({"choices": [{"delta": {"reasoning_content": "weighing it"}}]})
            send({"choices": [{"delta": {"content": "Hello"}}]})
            if mode == "stall":
                time.sleep(30)
            send({"choices": [{"delta": {"content": " there."}}]})
            finish = "length" if mode == "length" else "stop"
            send({"choices": [{"delta": {}, "finish_reason": finish}]})
            send({"choices": [], "usage": {"prompt_tokens": 40, "completion_tokens": 3},
                  "timings": {"prompt_n": 40, "prompt_ms": 12.5, "predicted_n": 3,
                              "predicted_ms": 30.0, "predicted_per_second": 100.0,
                              "cache_n": 8}})
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
