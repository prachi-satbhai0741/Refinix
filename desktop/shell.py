"""The Refinix native window.

A thin pywebview shell. It owns four things and nothing else:

* a window that appears immediately, with readable startup progress;
* the startup sequence in `desktop.lifecycle`, run off the UI thread;
* a small native bridge — file selection, the state folder, quit — with no
  method that accepts a filesystem path or a command from the page;
* shutdown that stops only what this application started.

The page it loads is the same local application the coordinator already serves,
so nothing about Chat, history, drafts or the event stream changes here.
"""

from __future__ import annotations

import base64
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from backend.coordinator import db, runtime
from backend.coordinator.server import shutdown_server
from desktop import lifecycle

WINDOW_TITLE = "Refinix"
MIN_SIZE = (960, 640)
DEFAULT_SIZE = (1280, 840)
GROUND = "#050608"                        # the brand ground, matching the icon

# Native file selection is bounded by the same rules the coordinator enforces,
# so a file that would be rejected on upload is refused before it is read.
DIALOG_FILE_TYPES = ("Documents and images (*.pdf;*.png;*.jpg;*.jpeg;*.tif;"
                     "*.tiff;*.heic;*.webp;*.txt;*.md;*.csv;*.json;*.docx;"
                     "*.xlsx;*.pptx)", "All files (*.*)")


class MissingToolkit(RuntimeError):
    """pywebview is not installed, so no native window can be opened."""


def _import_webview():
    try:
        import webview                              # noqa: PLC0415
    except ImportError as exc:                      # pragma: no cover - env gate
        raise MissingToolkit(
            "pywebview is not installed in this Python environment, so Refinix "
            "cannot open a native window. Install the pinned desktop "
            "requirements (desktop/requirements-desktop.txt) or run "
            "`python3 -m desktop --no-window` to start the local services only."
        ) from exc
    return webview


# --------------------------------------------------------------------------
# Startup page
# --------------------------------------------------------------------------

def _data_uri(path: Path) -> str:
    try:
        return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
    except OSError:
        return ""


def startup_html(assets: Path) -> str:
    """The first thing on screen. Local markup, no network, no framework."""
    logo = _data_uri(assets / "refinix-wordmark.png")
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Refinix</title>
<style>
  :root {{ color-scheme: dark; }}
  html, body {{ height: 100%; }}
  body {{ margin: 0; background: {GROUND}; color: #E8ECF2;
         font: 13px/1.5 -apple-system, "Segoe UI", system-ui, sans-serif;
         display: grid; place-items: center; }}
  .card {{ width: min(560px, 88vw); }}
  img {{ height: 34px; display: block; margin-bottom: 22px; }}
  h1 {{ font-size: 15px; font-weight: 600; margin: 0 0 4px; letter-spacing: .01em; }}
  p.msg {{ margin: 0 0 18px; color: #A9B5C6; }}
  ol {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 9px; }}
  li {{ display: grid; grid-template-columns: 14px 1fr; gap: 10px;
        align-items: start; color: #93A0B2; }}
  li[data-state="ok"] {{ color: #E8ECF2; }}
  li[data-state="failed"] {{ color: #F0908A; }}
  li[data-state="attention"] {{ color: #E8B96A; }}
  .dot {{ width: 9px; height: 9px; margin-top: 5px; border-radius: 50%;
          border: 1px solid #4A5462; }}
  li[data-state="running"] .dot {{ border-color: #6DB3F2; animation: pulse 1.1s infinite; }}
  li[data-state="ok"] .dot {{ background: #57C79A; border-color: #57C79A; }}
  li[data-state="attention"] .dot {{ background: #E8B96A; border-color: #E8B96A; }}
  li[data-state="failed"] .dot {{ background: #F0908A; border-color: #F0908A; }}
  @keyframes pulse {{ 50% {{ opacity: .25; }} }}
  .detail {{ display: block; color: #7C8798; }}
  .cmd {{ display: inline-block; margin-top: 6px; padding: 4px 8px;
          background: #12161C; border: 1px solid #2A313B; border-radius: 4px;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 12px; color: #C8D2E0; user-select: all; }}
  button {{ margin-top: 20px; padding: 7px 14px; background: #12161C;
            color: #E8ECF2; border: 1px solid #3A424E; border-radius: 5px;
            font: inherit; cursor: pointer; }}
  button:hover {{ border-color: #6DB3F2; }}
</style>
<div class="card">
  {'<img alt="Refinix" src="' + logo + '">' if logo else '<h1>Refinix</h1>'}
  <h1 id="phase">Starting…</h1>
  <p class="msg" id="msg">Bringing up the local services on this computer.</p>
  <ol id="steps"></ol>
  <button id="retry" hidden>Try again</button>
</div>
<script>
  const steps = document.getElementById('steps');
  const retry = document.getElementById('retry');
  function render(s) {{
    document.getElementById('phase').textContent =
      s.phase === 'failed' ? 'Refinix could not start' :
      s.phase === 'ready' ? 'Ready' :
      s.phase === 'attention' ? 'Almost ready' : 'Starting…';
    document.getElementById('msg').textContent = s.message;
    steps.replaceChildren();
    for (const step of s.steps) {{
      const li = document.createElement('li');
      li.dataset.state = step.state;
      const dot = document.createElement('span'); dot.className = 'dot';
      const body = document.createElement('span');
      body.append(document.createTextNode(step.label));
      if (step.detail) {{
        const d = document.createElement('span'); d.className = 'detail';
        d.textContent = step.detail; body.append(d);
      }}
      if (step.action && step.action.command) {{
        const c = document.createElement('span'); c.className = 'cmd';
        c.textContent = step.action.command; body.append(c);
      }}
      li.append(dot, body);
      steps.append(li);
    }}
    retry.hidden = s.phase !== 'failed';
  }}
  retry.addEventListener('click', () => {{
    retry.hidden = true;
    window.pywebview.api.retry_startup();
  }});
  async function tick() {{
    if (window.pywebview && window.pywebview.api) {{
      try {{ render(await window.pywebview.api.progress()); }} catch (e) {{}}
    }}
    setTimeout(tick, 400);
  }}
  tick();
</script>
"""


# --------------------------------------------------------------------------
# Native bridge
# --------------------------------------------------------------------------

class Bridge:
    """The only native surface the page can reach.

    Deliberately narrow. No method takes a filesystem path, a URL or a command
    from the page: `choose_files` opens a native dialog the person has to act
    on, and `open_state_folder` uses one fixed directory. Page content —
    including anything a model wrote — therefore cannot read a chosen file, run
    a command, or reach a path of its own choosing.
    """

    def __init__(self, app: "DesktopApp"):
        self._app = app

    # -- startup
    def progress(self) -> dict:
        return self._app.progress.snapshot()

    def retry_startup(self) -> dict:
        self._app.retry()
        return {"restarting": True}

    # -- files
    def choose_files(self) -> dict:
        """Open the native picker, then hand the bytes to the coordinator.

        The page never sees a path. Rejections come back as readable reasons,
        one per file, so a wrong type or an oversized file is explained rather
        than silently dropped.
        """
        window = self._app.window
        if window is None:
            return {"accepted": [], "rejected": [
                {"filename": "", "reason": "The native file picker is unavailable."}]}
        webview = _import_webview()
        chosen = window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=True, file_types=DIALOG_FILE_TYPES)
        return self._app.take_files([Path(p) for p in (chosen or [])])

    def choose_repository(self) -> dict:
        """Open the native folder dialog and connect what the person chose.

        The narrowest possible addition: it takes no argument, so the page
        cannot supply a path, a picker default, a URL or a command. The chosen
        folder is canonicalised and registered by the coordinator, and only an
        opaque repository id and display name come back.
        """
        window = self._app.window
        if window is None:
            return {"error": "Connecting a folder needs the Refinix application "
                             "window.", "code": "no_window"}
        webview = _import_webview()
        chosen = window.create_file_dialog(webview.FOLDER_DIALOG)
        if not chosen:
            return {"cancelled": True}
        return self._app.connect_repository(str(chosen[0]))

    def open_state_folder(self) -> dict:
        """Reveal the fixed application folder. No argument, no other path."""
        import subprocess
        folder = lifecycle.STATE_DIR
        folder.mkdir(parents=True, exist_ok=True)
        opener = {"darwin": ["open"], "win32": ["explorer"]}.get(
            sys.platform, ["xdg-open"])
        try:
            subprocess.Popen([*opener, str(folder)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            return {"opened": False, "error": str(exc), "path": str(folder)}
        return {"opened": True, "path": str(folder)}

    # -- window / services
    def shell_info(self) -> dict:
        return self._app.shell_info()

    def quit(self) -> dict:
        self._app.request_quit()
        return {"quitting": True}


# --------------------------------------------------------------------------
# The application
# --------------------------------------------------------------------------

class DesktopApp:
    def __init__(self, *, state_path: Path = lifecycle.STATE_DB,
                 port: int = lifecycle.DEFAULT_PORT, on_started=None):
        self.state_path = state_path
        self.preferred_port = port
        self.progress = lifecycle.Progress()
        self.window = None
        self.startup: lifecycle.Startup | None = None
        self._closing = threading.Event()
        self._retry = threading.Event()
        self._lifecycle_lock = threading.Lock()
        self.on_started = on_started
        self._startup_worker = None

    # -- resources
    @property
    def assets(self) -> Path:
        from backend.coordinator.server import static_root
        return static_root() / "assets"

    # -- startup ----------------------------------------------------------
    def _startup_thread(self):
        self._startup_worker = threading.current_thread()
        while not self._closing.is_set():
            try:
                startup = lifecycle.run_startup(
                    self.progress, state_path=self.state_path,
                    preferred_port=self.preferred_port, cancelled=self._closing)
            except lifecycle.StartupCancelled:
                return
            except lifecycle.StartupError as exc:
                self.progress.set("coordinator", "failed", f"{exc} {exc.detail}".strip(),
                                  exc.action)
                self.progress.finish("failed", str(exc))
            except Exception as exc:                  # noqa: BLE001
                self.progress.finish("failed", f"{type(exc).__name__}: {exc}")
            else:
                with self._lifecycle_lock:
                    if self._closing.is_set():
                        if startup.server is not None:
                            startup.server.server_close()
                            startup.coordinator.conn.close()
                        startup.engine_supervisor.stop()
                        return
                    self.startup = startup
                    if startup.coordinator is not None:
                        startup.coordinator.desktop = self.shell_info()
                        threading.Thread(target=self._serve, daemon=True,
                                         name="coordinator-http").start()
                    if self.on_started is not None:
                        self.on_started(startup)
                if self._closing.is_set():
                    return
                if self.window is not None:
                    self.window.load_url(self.startup.url)
                threading.Thread(target=self._focus_poll, daemon=True,
                                 name="focus-poll").start()
                return
            # Failed: wait for the person to press Try again.
            self._retry.wait()
            self._retry.clear()
            self.progress = lifecycle.Progress()

    def _serve(self):
        try:
            self.startup.server.serve_forever(poll_interval=0.2)
        except OSError:
            pass

    def retry(self):
        self._retry.set()

    # -- second launch ----------------------------------------------------
    def _focus_poll(self):
        url = f"http://127.0.0.1:{self.startup.port}/v1/desktop/focus"
        while not self._closing.wait(1.5):
            try:
                _headers, body = lifecycle.get_json(url, 2.0)
                wanted = isinstance(body, dict) and body.get("focus")
            except Exception:                          # noqa: BLE001
                continue
            if wanted and self.window is not None:
                try:
                    self.window.restore()
                    self.window.show()
                except Exception:                      # noqa: BLE001
                    pass

    # -- files ------------------------------------------------------------
    def take_files(self, paths: list[Path]) -> dict:
        """Read chosen files and post them to the coordinator over loopback."""
        accepted, rejected = [], []
        if self.startup is None:
            return {"accepted": [], "rejected": [
                {"filename": "", "reason": "Refinix is still starting."}]}
        chat_id = self._current_chat()
        for path in paths[:db.MAX_ATTACHMENTS_PER_REQUEST]:
            try:
                if path.is_symlink() or not path.is_file():
                    raise db.AttachmentRejected("Only ordinary files can be attached.")
                size = path.stat().st_size
                if size > db.MAX_ATTACHMENT_BYTES:
                    raise db.AttachmentRejected(
                        f"{path.name} is larger than "
                        f"{db.MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB.")
                db.classify_attachment(path.name)
                data = path.read_bytes()
            except db.AttachmentRejected as exc:
                rejected.append({"filename": path.name, "reason": str(exc)})
                continue
            except OSError as exc:
                rejected.append({"filename": path.name,
                                 "reason": f"Could not read this file: {exc.strerror or exc}"})
                continue
            result = self._post("/v1/attachments", {
                "chat_id": chat_id, "filename": path.name,
                "data": base64.b64encode(data).decode()})
            if "error" in result:
                rejected.append({"filename": path.name, "reason": result["error"]})
            else:
                accepted.append(result["attachment"])
        return {"accepted": accepted, "rejected": rejected}

    def connect_repository(self, selected: str) -> dict:
        """Register a natively chosen folder. Never called with a page value."""
        if self.startup is None:
            return {"error": "Refinix is still starting.", "code": "starting"}
        coordinator = self.startup.coordinator
        if coordinator is None:
            # This window is showing a coordinator another process owns. There
            # is deliberately no HTTP route that accepts a filesystem path, so
            # the folder cannot be handed across; say so rather than opening a
            # second connection to the same database or adding that route.
            return {"error": "This window is showing a Refinix coordinator that "
                             "another process started. Quit that one and open "
                             "Refinix again to connect a folder.",
                    "code": "reused_coordinator"}
        try:
            return {"repository": coordinator.code.connect(selected)}
        except Exception as exc:                       # noqa: BLE001
            return {"error": str(exc), "code": getattr(exc, "code", "failed")}

    def _current_chat(self) -> str:
        """Ask the page which conversation the selection belongs to."""
        try:
            value = self.window.evaluate_js("window.refinixDraftId || '__new__'")
        except Exception:                              # noqa: BLE001
            value = None
        return value if isinstance(value, str) and 0 < len(value) <= 36 else "__new__"

    def _post(self, route: str, payload: dict) -> dict:
        url = f"http://127.0.0.1:{self.startup.port}{route}"
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Host": f"127.0.0.1:{self.startup.port}"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            with exc:
                try:
                    return json.load(exc)
                except ValueError:
                    return {"error": f"HTTP {exc.code}"}
        except (OSError, ValueError) as exc:
            return {"error": str(exc)}

    # -- information ------------------------------------------------------
    def shell_info(self) -> dict:
        s = self.startup
        return {
            "shell": "pywebview",
            "platform": sys.platform,
            "packaged": bool(getattr(sys, "frozen", False)),
            "port": s.port if s else None,
            "reused_coordinator": s.reused_coordinator if s else None,
            "engine_started_by_refinix": bool(
                s and s.engine_supervisor and s.engine_supervisor.owned),
            "state_folder": str(self.state_path.parent),
            "model_configured": runtime.MODEL,
        }

    # -- shutdown ---------------------------------------------------------
    def active_jobs(self) -> list[dict]:
        c = self.startup.coordinator if self.startup else None
        if self.startup is None:
            return []
        if c is not None:
            return c.active_jobs()
        _headers, body = lifecycle.get_json(
            f"{self.startup.url}v1/jobs/active", 3)
        return body["jobs"]

    def _cancel_jobs(self, jobs):
        c = self.startup.coordinator
        for job in jobs:
            try:
                if c is not None:
                    c.request_cancel(job["job_id"])
                else:
                    result = self._post("/v1/cancel", {"job_id": job["job_id"]})
                    if "error" in result:
                        raise RuntimeError(result["error"])
            except Exception:
                # Completing between the read and the cancel is harmless.
                if any(j["job_id"] == job["job_id"] for j in self.active_jobs()):
                    raise

    def on_closing(self) -> bool:
        """Window close and Quit both land here.

        Active work is named before it is stopped, and the answer is truthful:
        the jobs are cancelled through the same path the Stop button uses, and
        the records keep their real cancelled state.
        """
        if self._closing.is_set():
            return self._startup_worker is None or not self._startup_worker.is_alive()
        try:
            running = self.active_jobs()
        except Exception as exc:
            if self.window is not None:
                self.window.create_confirmation_dialog(
                    "Could not check running work", f"{exc}\nTry quitting again once the coordinator answers.")
            return False
        if running and self.window is not None:
            count = len(running)
            confirmed = self.window.create_confirmation_dialog(
                "Quit Refinix?",
                f"{count} {'reply is' if count == 1 else 'replies are'} still "
                "running on this computer. Quitting stops "
                f"{'it' if count == 1 else 'them'} and saves "
                f"{'it' if count == 1 else 'them'} as stopped.")
            if not confirmed:
                return False
        try:
            if running:
                self._cancel_jobs(running)
                deadline = time.monotonic() + 3
                while self.active_jobs() and time.monotonic() < deadline:
                    time.sleep(0.05)
                if self.active_jobs():
                    raise RuntimeError("The request is still stopping. Please try quitting again shortly.")
        except Exception as exc:
            if self.window is not None:
                self.window.create_confirmation_dialog("Could not stop running work", str(exc))
            return False
        self.shutdown()
        if self.startup is None and self._startup_worker is not None and self._startup_worker.is_alive():
            # Cocoa Quit can exit the process without Python's finally blocks.
            # Reject that immediate quit, then close the window after startup
            # has released its resources. Do not block the native UI thread.
            self.progress.finish("stopping", "Stopping startup…")

            def close_after_startup():
                self._startup_worker.join()
                if self.window is not None:
                    self.window.destroy()

            threading.Thread(target=close_after_startup, daemon=True).start()
            return False
        return True

    def request_quit(self):
        if self.window is not None and self.on_closing():
            self.window.destroy()

    def shutdown(self):
        with self._lifecycle_lock:
            if self._closing.is_set():
                return
            self._closing.set()
            self._retry.set()
            s = self.startup
        if s is None:
            return
        coordinator = s.coordinator
        if coordinator is not None:
            for job in self.active_jobs():
                try:
                    coordinator.request_cancel(job["job_id"])
                except Exception:                      # noqa: BLE001
                    pass
            # Give the generation threads a moment to record the cancellation
            # before the listener goes away.
            deadline = time.monotonic() + 3.0
            while self.active_jobs() and time.monotonic() < deadline:
                time.sleep(0.1)
            try:
                shutdown_server(s.server, coordinator)
            except Exception:                          # noqa: BLE001
                pass
        if s.engine_supervisor is not None:
            # Only a runtime Refinix started is stopped. One that was already
            # running on this computer is left exactly as it was.
            s.engine_supervisor.stop()


def run(*, state_path: Path = lifecycle.STATE_DB, port: int = lifecycle.DEFAULT_PORT,
        gui: str | None = None, debug: bool = False, on_started=None) -> int:
    """Open the window and block until it closes."""
    webview = _import_webview()
    try:
        webview.settings.update({"ALLOW_DOWNLOADS": True,
                                 "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
                                 "OPEN_DEVTOOLS_IN_DEBUG": False})
    except AttributeError:                             # pragma: no cover - old pywebview
        pass

    app = DesktopApp(state_path=state_path, port=port, on_started=on_started)
    bridge = Bridge(app)
    window = webview.create_window(
        WINDOW_TITLE, html=startup_html(app.assets), js_api=bridge,
        width=DEFAULT_SIZE[0], height=DEFAULT_SIZE[1], min_size=MIN_SIZE,
        background_color=GROUND, text_select=True)
    app.window = window
    window.events.closing += app.on_closing

    worker = threading.Thread(target=app._startup_thread, name="refinix-startup")

    def boot(_window):
        worker.start()

    try:
        # private_mode keeps the webview from writing cookies or local storage:
        # every piece of state Refinix keeps belongs to the coordinator.
        webview.start(boot, window, gui=gui, debug=debug, private_mode=True)
    finally:
        app.shutdown()
        if worker.ident is not None:
            worker.join()  # finish cancelled startup cleanup before releasing the instance lock
    return 0
