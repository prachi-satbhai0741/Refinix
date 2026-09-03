"""Local coordinator: HTTP API, SSE event stream and static UI.

Standard library only. `backend/requirements.txt` pins pydantic for the shared
contract and nothing else; FastAPI is not installed, and installing it would be
a setup checkpoint rather than C03 implementation. FastAPI remains the recorded
direction for the worker API at C04, where a pinned install is part of the
image build.

Binds loopback only, per the offline-runtime invariant.
"""

from __future__ import annotations

import json
import queue
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from backend.contracts import v1
from backend.coordinator import context, db, runtime

REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "frontend" / "app"
BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8770          # not 8443/30443 (worker contract) and not 8080 (Jenkins)

MEDIA = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
         ".png": "image/png", ".webmanifest": "application/manifest+json"}


class RequestError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Hub:
    """Fan-out of coordinator events to connected SSE readers."""

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: dict[int, queue.Queue] = {}
        self._next = 0

    def subscribe(self):
        q = queue.Queue(maxsize=1024)
        with self._lock:
            self._next += 1
            key = self._next
            self._subscribers[key] = q
        return key, q

    def unsubscribe(self, key):
        with self._lock:
            self._subscribers.pop(key, None)

    def publish(self, event: dict):
        with self._lock:
            targets = list(self._subscribers.values())
        for q in targets:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass          # a stalled reader must not block generation


class Coordinator:
    def __init__(self, state_path: Path, node_id: str | None = None):
        self.conn = db.connect(state_path)
        self.node_id = node_id or self._identity("node_id")
        self.hub = Hub()
        self.workspace_id = self._identity("workspace_id")
        self._cancelled: set[str] = set()
        self._cancel_lock = threading.Lock()
        # Set on Ctrl+C so streaming loops leave promptly instead of holding
        # the process open.
        self.stopping = threading.Event()
        self.repaired = db.reconcile_on_start(self.conn, self.node_id)

    def _identity(self, key) -> str:
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if row:
            return row["value"]
        workspace_id = db.new_id()
        with self.conn:
            self.conn.execute("INSERT INTO meta(key, value) VALUES (?, ?)",
                              (key, workspace_id))
        return workspace_id

    @db.serialized
    def request_cancel(self, job_id: str):
        row = self.conn.execute("SELECT state FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            raise RequestError("unknown job", 404)
        if row["state"] in v1.TERMINAL_JOB_STATES or row["state"] == "interrupted":
            raise RequestError("job has already stopped", 409)
        with self._cancel_lock:
            self._cancelled.add(job_id)

    def is_cancelled(self, job_id: str) -> bool:
        with self._cancel_lock:
            return job_id in self._cancelled

    def _emit(self, job_id, attempt_id, data):
        event = db.append_event(self.conn, job_id=job_id, attempt_id=attempt_id,
                                node_id=self.node_id, data=data)
        self.hub.publish(event)

    @db.serialized
    def submit(self, chat_id: str, text: str) -> str:
        """Persist the job before any work starts, so a crash leaves a record."""
        if not self.conn.execute("SELECT 1 FROM chats WHERE chat_id=? AND workspace_id=?",
                                 (chat_id, self.workspace_id)).fetchone():
            raise RequestError("unknown conversation", 404)
        if any(j["state"] not in v1.TERMINAL_JOB_STATES | {"interrupted"}
               for j in self.jobs(chat_id, limit=-1)):
            raise RequestError("wait for this conversation's reply or cancel it first", 409)
        job_id = db.create_job(self.conn, workspace_id=self.workspace_id,
                               chat_id=chat_id, request=text)
        db.add_message(self.conn, chat_id, "user", text, job_id=job_id)
        self._emit(job_id, None, {"kind": "job.state", "previous": None,
                                  "current": "created"})
        threading.Thread(target=self._run, args=(job_id, chat_id),
                         daemon=True).start()
        return job_id

    def _advance_job(self, job_id, following, previous):
        db.set_job_state(self.conn, job_id, following)
        self._emit(job_id, None, {"kind": "job.state", "previous": previous,
                                  "current": following})

    def _run(self, job_id: str, chat_id: str):
        attempt_id = None
        try:
            for previous, following in (("created", "context_preparing"),
                                        ("context_preparing", "queued")):
                self._advance_job(job_id, following, previous)

            history = self.chat_messages(chat_id)
            # Saved history stays whole; only the request is bounded.
            messages, selection = context.select(
                history, window=runtime.NUM_CTX,
                output_allowance=runtime.NUM_PREDICT)

            attempt_id = db.create_attempt(
                self.conn, job_id=job_id, node_id=self.node_id,
                route_reason="local coordinator: no paired worker in C03",
            )
            self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                            "previous": None, "current": "queued"})
            db.set_attempt_selection(self.conn, attempt_id, selection.as_dict())
            if not selection.newest_fits:
                raise runtime.RuntimeUnavailable(selection.note)
            self._advance_job(job_id, "routing", "queued")
            self._advance_job(job_id, "running", "routing")
            db.set_attempt_state(self.conn, attempt_id, "running")
            self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                            "previous": "queued", "current": "running"})

            collected, metrics = [], {}
            for kind, payload in runtime.stream_chat(
                    messages,
                    should_cancel=lambda: self.is_cancelled(job_id)
                    or self.stopping.is_set()):
                if kind == "delta":
                    collected.append(payload)
                    db.append_output(self.conn, attempt_id, payload)
                    # The contract caps a delta at 2048 characters.
                    for i in range(0, len(payload), 2048):
                        self._emit(job_id, attempt_id,
                                   {"kind": "output.delta", "text": payload[i:i + 2048]})
                elif kind == "cancelled":
                    self._stop(job_id, attempt_id, "cancelled", "running", {
                        "code": "cancelled_by_user",
                        "message": "cancelled from the local interface",
                        "retryable": True})
                    return
                elif kind == "done":
                    metrics = payload

            db.set_attempt_state(self.conn, attempt_id, "validating",
                                 runtime_ms=metrics.get("total_ms"), metrics=metrics)
            self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                            "previous": "running", "current": "validating"})
            self._advance_job(job_id, "validating", "running")

            answer = "".join(collected)
            if not answer.strip():
                # An empty answer is a failure, not a successful blank reply.
                raise runtime.RuntimeUnavailable(
                    "the runtime returned no visible output")

            with db.LOCK:
                if self.is_cancelled(job_id):
                    self._stop(job_id, attempt_id, "cancelled", "validating", {
                        "code": "cancelled_by_user",
                        "message": "cancelled before the response was saved",
                        "retryable": True})
                    return
                reason = metrics.get("done_reason")
                if reason != "stop":
                    if reason == "length":
                        # Keep the partial reply in history so the user can continue it.
                        db.add_message(self.conn, chat_id, "assistant", answer, job_id=job_id)
                        message = (
                            f"Incomplete reply: output limit reached "
                            f"({metrics.get('output_token_limit', runtime.NUM_PREDICT)} tokens). "
                            "Partial text saved; ask to continue from the last sentence.")
                    else:
                        message = f"Completion unverified: runtime stop reason {reason or 'not reported'}"
                    self._stop(job_id, attempt_id, "failed", "validating", {
                        "code": "validation_failed", "message": message[:256],
                        "retryable": True})
                    return
                db.add_message(self.conn, chat_id, "assistant", answer, job_id=job_id)
                db.set_attempt_state(self.conn, attempt_id, "completed",
                                     runtime_ms=metrics.get("total_ms"))
                self._emit(job_id, attempt_id, {"kind": "attempt.state",
                                                "previous": "validating", "current": "completed"})
                self._advance_job(job_id, "completed", "validating")
        except runtime.RuntimeUnavailable as exc:
            self._stop(job_id, attempt_id, "failed", None, {
                "code": "unavailable", "message": str(exc)[:256], "retryable": True})
        except Exception as exc:                       # noqa: BLE001
            traceback.print_exc()
            self._stop(job_id, attempt_id, "failed", None, {
                "code": "internal_error",
                "message": f"{type(exc).__name__}: {exc}"[:256], "retryable": False})
        finally:
            with self._cancel_lock:
                self._cancelled.discard(job_id)

    @db.serialized
    def _stop(self, job_id, attempt_id, state, previous, error):
        """One typed reason per stopped attempt, as the contract requires."""
        try:
            if attempt_id:
                row = self.conn.execute("SELECT state FROM attempts WHERE attempt_id=?",
                                        (attempt_id,)).fetchone()
                db.set_attempt_state(self.conn, attempt_id, state, error=error)
                self._emit(job_id, attempt_id,
                           {"kind": "attempt.state", "previous": previous or row["state"],
                            "current": state})
            job = self.conn.execute("SELECT state FROM jobs WHERE job_id=?",
                                    (job_id,)).fetchone()
            job_state = "cancelled" if state == "cancelled" else "failed"
            db.set_job_state(self.conn, job_id, job_state)
            self._emit(job_id, None, {"kind": "job.state", "previous": job["state"],
                                      "current": job_state})
        except Exception:                              # noqa: BLE001
            traceback.print_exc()

    # ---- reads -----------------------------------------------------------

    @db.serialized
    def search(self, term):
        return db.search(self.conn, term)

    def export(self, chat_id, fmt):
        return db.export_chat(self.conn, chat_id, fmt)

    def chats(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM chats ORDER BY pinned DESC, updated_at DESC LIMIT 100")]

    @db.serialized
    def chat_messages(self, chat_id):
        return [dict(r) for r in self.conn.execute(
            "SELECT m.*, a.error_json FROM messages m"
            " LEFT JOIN jobs j ON j.job_id=m.job_id AND m.role='assistant'"
            " LEFT JOIN attempts a ON a.attempt_id=j.active_attempt_id"
            " WHERE m.chat_id=? ORDER BY m.created_at, m.rowid",
            (chat_id,))]

    @db.serialized
    def jobs(self, chat_id=None, limit=50):
        sql = "SELECT * FROM jobs"
        args = ()
        if chat_id:
            sql += " WHERE chat_id=?"
            args = (chat_id,)
        sql += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        return [dict(r) for r in self.conn.execute(sql, args + (limit,))]

    @db.serialized
    def job_detail(self, job_id):
        job = self.conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if job is None:
            return None
        attempts = [dict(r) for r in self.conn.execute(
            "SELECT * FROM attempts WHERE job_id=? ORDER BY created_at", (job_id,))]
        for a in attempts:
            raw = a.pop("selection_json", None)
            a["selection"] = json.loads(raw) if raw else None
        events = [dict(r) for r in self.conn.execute(
            "SELECT * FROM events WHERE job_id=? ORDER BY sequence", (job_id,))]
        for e in events:
            e["data"] = json.loads(e.pop("data_json"))
        return {"job": dict(job), "attempts": attempts, "events": events}

    def status(self):
        with db.LOCK:
            counts = {row["state"]: row["n"] for row in self.conn.execute(
                "SELECT state, COUNT(*) AS n FROM jobs GROUP BY state")}
        return {
            "node_id": self.node_id,
            "workspace_id": self.workspace_id,
            "contract_version": v1.CONTRACT_VERSION,
            "contract_status": "reviewed draft; not frozen, integration pending C05",
            "bind": f"{BIND_HOST}",
            "runtime": runtime.probe(),
            "model_configured": runtime.MODEL,
            "bounded": {"num_ctx": runtime.NUM_CTX,
                        "num_predict": runtime.NUM_PREDICT,
                        "think": runtime.THINK},
            "context": {
                "window_tokens": runtime.NUM_CTX,
                "reply_allowance_tokens": runtime.NUM_PREDICT,
                "conversation_budget_tokens": context.input_budget(
                    runtime.NUM_CTX, runtime.NUM_PREDICT),
                "counting_method": context.Selection().counting_method,
                "policy": "Older complete exchanges are left out of a request "
                          "when it will not fit. Saved history is never changed.",
            },
            "jobs_by_state": counts,
            "repaired_on_start": len(self.repaired),
            "surfaces": {"chat": "available", "control": "available",
                         "documents": "unavailable", "code": "unavailable"},
            # Every value below needs evidence this chunk cannot produce.
            "unavailable": {
                "workers": "no worker is paired; C06 establishes pairing",
                "cluster": "no cluster is deployed; C05 provisions it",
                "approvals": "the approval path is implemented at C10",
                "proof": "Proof Cards are produced at C10",
                "egress": "zero-egress evidence is collected at C11",
            },
        }


class Handler(BaseHTTPRequestHandler):
    server_version = "AegisForgeCoordinator/0.1"
    protocol_version = "HTTP/1.1"
    coordinator: Coordinator = None      # injected by serve()

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError):
            # Closing a browser connection does not cancel its persisted job.
            self.close_connection = True

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}", flush=True)

    # -- helpers
    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1:
            raise RequestError("one Content-Length is required")
        if self.headers.get_content_type() != "application/json":
            raise RequestError("Content-Type must be application/json", 415)
        if not lengths[0].isascii() or not lengths[0].isdigit():
            raise RequestError("invalid Content-Length")
        length = int(lengths[0])
        if length > v1.MAX_REQUEST_BYTES:
            raise RequestError("request is too large", 413)
        self.connection.settimeout(10)
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("incomplete body")
            body = json.loads(raw)
        except (ValueError, OSError) as exc:
            raise RequestError("invalid JSON body") from exc
        if not isinstance(body, dict):
            raise RequestError("JSON body must be an object")
        return body

    def _local_request(self):
        hosts = {f"127.0.0.1:{self.server.server_port}",
                 f"localhost:{self.server.server_port}"}
        host = self.headers.get("Host")
        if len(self.headers.get_all("Host", [])) != 1 or host not in hosts:
            raise RequestError("local Host required", 403)
        origins = self.headers.get_all("Origin", [])
        if (origins and origins != [f"http://{host}"]) or self.headers.get(
                "Sec-Fetch-Site") == "cross-site":
            raise RequestError("same-origin access required", 403)

    @staticmethod
    def _text(payload, key, maximum=16_384):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise RequestError(f"{key} must be nonempty text of at most {maximum} characters")
        return value.strip()

    def _export(self, c, query):
        """A download the user explicitly asked for, of saved history only."""
        fmt = (query.get("format") or ["md"])[0]
        if fmt not in ("md", "txt"):
            raise RequestError("format must be md or txt")
        name, body = c.export(query["chat_id"][0], fmt)
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type",
                         f"text/{'markdown' if fmt == 'md' else 'plain'}; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _static(self, path):
        name = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC / unquote(name)).resolve()
        if not target.is_relative_to(STATIC.resolve()) or not target.is_file():
            self._json({"error": "not found"}, 404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MEDIA.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    # -- routes
    def do_GET(self):
        parsed = urlparse(self.path)
        route, query = parsed.path, parse_qs(parsed.query)
        c = self.coordinator
        try:
            self._local_request()
            if route == "/v1/status":
                self._json(c.status())
            elif route == "/v1/chats":
                self._json({"chats": c.chats()})
            elif route == "/v1/messages":
                self._json({"messages": c.chat_messages(query["chat_id"][0])})
            elif route == "/v1/jobs":
                self._json({"jobs": c.jobs((query.get("chat_id") or [None])[0])})
            elif route == "/v1/job":
                detail = c.job_detail(query["job_id"][0])
                self._json(detail or {"error": "not found"}, 200 if detail else 404)
            elif route == "/v1/search":
                self._json({"results": c.search((query.get("q") or [""])[0])})
            elif route == "/v1/draft":
                self._json({"text": db.get_draft(c.conn, query["chat_id"][0])})
            elif route == "/v1/export":
                self._export(c, query)
            elif route == "/v1/events":
                self._sse()
            else:
                self._static(route)
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
        except RequestError as exc:
            self.close_connection = True
            self._json({"error": str(exc)}, exc.status)
        except KeyError as exc:
            self._json({"error": f"missing parameter {exc}"}, 400)
        except (ConnectionResetError, BrokenPipeError):
            raise  # handled once at the connection boundary
        except Exception as exc:                       # noqa: BLE001
            traceback.print_exc()
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def do_POST(self):
        route = urlparse(self.path).path
        c = self.coordinator
        try:
            self._local_request()
            payload = self._body()
            if route == "/v1/chats":
                chat_id = db.create_chat(c.conn, c.workspace_id,
                                         self._text(payload, "title", 120)
                                         if "title" in payload else "New chat")
                self._json({"chat_id": chat_id}, 201)
            elif route == "/v1/messages":
                text = self._text(payload, "text")
                chat_id = self._text(payload, "chat_id", 36)
                job_id = c.submit(chat_id, text)
                # Clear only the version that was sent; newer typing survives.
                db.clear_draft_if_matches(c.conn, chat_id, text)
                self._json({"job_id": job_id}, 202)
            elif route == "/v1/chat/rename":
                chat_id = self._text(payload, "chat_id", 36)
                title = db.rename_chat(c.conn, chat_id, payload.get("title", ""))
                self._json({"chat_id": chat_id, "title": title})
            elif route == "/v1/chat/pin":
                chat_id = self._text(payload, "chat_id", 36)
                pinned = bool(payload.get("pinned"))
                db.set_pinned(c.conn, chat_id, pinned)
                self._json({"chat_id": chat_id, "pinned": pinned})
            elif route == "/v1/chat/delete":
                chat_id = self._text(payload, "chat_id", 36)
                db.delete_chat(c.conn, chat_id)
                self._json({"deleted": chat_id})
            elif route == "/v1/draft":
                db.set_draft(c.conn, self._text(payload, "chat_id", 36),
                             str(payload.get("text", ""))[:16384])
                self._json({"saved": True})
            elif route == "/v1/cancel":
                c.request_cancel(self._text(payload, "job_id", 36))
                self._json({"cancel_requested": payload["job_id"]}, 202)
            else:
                self._json({"error": "not found"}, 404)
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
        except RequestError as exc:
            self.close_connection = True
            self._json({"error": str(exc)}, exc.status)
        except KeyError as exc:
            self._json({"error": f"missing field {exc}"}, 400)
        except (ConnectionResetError, BrokenPipeError):
            raise  # handled once at the connection boundary
        except Exception as exc:                       # noqa: BLE001
            traceback.print_exc()
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def _sse(self):
        key, q = self.coordinator.hub.subscribe()
        stopping = self.coordinator.stopping
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            idle = 0
            while not stopping.is_set():
                try:
                    # A short wait keeps shutdown responsive; the keep-alive
                    # frame still only goes out every ~15s.
                    event = q.get(timeout=1)
                    frame = f"data: {json.dumps(event)}\n\n"
                    idle = 0
                except queue.Empty:
                    idle += 1
                    if idle < 15:
                        continue
                    idle = 0
                    frame = ": keep-alive\n\n"
                self.wfile.write(frame.encode())
                self.wfile.flush()
        finally:
            self.coordinator.hub.unsubscribe(key)


def serve(state_path: Path, port: int = DEFAULT_PORT):
    coordinator = Coordinator(state_path)
    Handler.coordinator = coordinator
    httpd = ThreadingHTTPServer((BIND_HOST, port), Handler)
    httpd.daemon_threads = True
    # ThreadingMixIn.block_on_close defaults to True, which makes server_close()
    # join every handler thread. A held-open SSE connection never returns, so
    # Ctrl+C would hang the process instead of stopping it.
    httpd.block_on_close = False
    # flush=True: the operator must see this even when stdout is a pipe.
    banner = [
        "AegisForge coordinator",
        f"  contract   {v1.CONTRACT_VERSION} (reviewed draft, not frozen)",
        f"  state      {state_path}",
        f"  node       {coordinator.node_id}",
        f"  repaired   {len(coordinator.repaired)} interrupted job(s) on start",
        f"  listening  http://{BIND_HOST}:{port}  (loopback only)",
    ]
    print("\n".join(banner), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping", flush=True)
    finally:
        coordinator.stopping.set()     # release streaming loops first
        httpd.shutdown()
        httpd.server_close()
        # Daemon generation threads may still be leaving a blocked runtime read.
        # Process exit closes SQLite; closing it under those threads is unsafe.
        print("stopped", flush=True)
