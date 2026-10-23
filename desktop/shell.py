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
import os
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


def _native_message(title: str, text: str, *, platform: str | None = None,
                    gtk=None, which=None, run=None) -> str:
    """A last-resort native message when no web window can be shown.

    Linux tries GTK first, then zenity (which needs no Python bindings, so it
    still works when GTK/WebKitGTK is what is missing), then standard error.
    Returns how the message was shown.
    """
    import shutil                                       # noqa: PLC0415
    import subprocess                                   # noqa: PLC0415
    platform = sys.platform if platform is None else platform
    run = run or subprocess.run
    try:
        if platform == "win32":
            import ctypes                               # noqa: PLC0415
            ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
            return "messagebox"
        if platform == "darwin":
            script = ('display alert ' + json.dumps(title) + ' message '
                      + json.dumps(text) + ' as critical')
            run(["/usr/bin/osascript", "-e", script], timeout=120, check=False)
            return "osascript"
        if (gtk or _gtk_dialog)(title, text):
            return "gtk"
        zenity = (which or shutil.which)("zenity")
        if zenity:
            result = run([zenity, "--error", "--title", title, "--text", text,
                          "--no-markup", "--width", "420"], timeout=600, check=False)
            if getattr(result, "returncode", 1) in (0, 1):
                return "zenity"
    except Exception:                                  # noqa: BLE001
        pass
    print(f"{title}: {text}", file=sys.stderr)
    return "stderr"


def _gtk_dialog(title: str, text: str) -> bool:
    """A GTK message dialog, when GTK itself is usable."""
    try:
        import gi                                      # noqa: PLC0415
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk                  # noqa: PLC0415
        if not Gtk.init_check()[0]:
            return False
        dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.OK, text=title)
        dialog.format_secondary_text(text)
        dialog.set_title(title)
        dialog.run()
        dialog.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration()
        return True
    except Exception:                                  # noqa: BLE001
        return False


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
# Window toolkit: pinned per OS, checked before use
# --------------------------------------------------------------------------

# The renderer each packaged build is qualified with. pywebview would otherwise
# pick one itself and could fall back to a different, unqualified renderer.
PINNED_GUI = {"darwin": "cocoa", "win32": "edgechromium", "linux": "gtk"}

# Microsoft's documented WebView2 runtime registration (Evergreen client id).
WEBVIEW2_CLIENT = r"{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_KEYS = (
    ("HKEY_LOCAL_MACHINE",
     "SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\" + WEBVIEW2_CLIENT),
    ("HKEY_LOCAL_MACHINE",
     "SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\" + WEBVIEW2_CLIENT),
    ("HKEY_CURRENT_USER",
     "Software\\Microsoft\\EdgeUpdate\\Clients\\" + WEBVIEW2_CLIENT),
)


def _platform_key(platform: str) -> str:
    return "linux" if platform.startswith("linux") else platform


def webview2_version(registry=None) -> str | None:
    """The installed WebView2 runtime version, or None when it is absent.

    Follows Microsoft's distribution guidance: a `pv` value that is present and
    not `0.0.0.0` under the runtime's client key means it is installed.
    """
    if registry is None:
        try:
            import winreg as registry                 # noqa: PLC0415
        except ImportError:
            return None
    for hive_name, path in WEBVIEW2_KEYS:
        try:
            with registry.OpenKey(getattr(registry, hive_name), path) as key:
                value, _kind = registry.QueryValueEx(key, "pv")
        except OSError:
            continue
        if value and value != "0.0.0.0":
            return str(value)
    return None


def toolkit_problem(platform: str | None = None, *, registry=None,
                    gtk_probe=None) -> str | None:
    """Why the pinned window toolkit cannot run here, or None when it can."""
    platform = _platform_key(sys.platform if platform is None else platform)
    if platform == "win32":
        if webview2_version(registry) is None:
            return ("Refinix needs the Microsoft Edge WebView2 Runtime to show its "
                    "window, and it is not installed on this computer. It is part "
                    "of Windows 11; on other systems install it from Microsoft, "
                    "then open Refinix again.")
        return None
    if platform == "linux":
        probe = gtk_probe or _gtk_webkit_available
        if not probe():
            return ("Refinix needs GTK and WebKitGTK 4.1 to show its window, and "
                    "they are not available on this computer. On Ubuntu they are "
                    "provided by the desktop packages libwebkit2gtk-4.1-0 and "
                    "gir1.2-webkit2-4.1.")
        return None
    return None


def _gtk_webkit_available() -> bool:
    try:
        import gi                                      # noqa: PLC0415
        gi.require_version("Gtk", "3.0")
        gi.require_version("WebKit2", "4.1")
        from gi.repository import Gtk, WebKit2          # noqa: F401,PLC0415
    except Exception:                                  # noqa: BLE001
        return False
    return True


def pinned_gui(requested: str | None, *, frozen: bool | None = None,
               platform: str | None = None) -> str | None:
    """The toolkit to start: an explicit request, else the pinned one when packaged."""
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if requested:
        return requested
    return PINNED_GUI.get(_platform_key(sys.platform if platform is None else platform)) \
        if frozen else None


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

    def choose_model_files(self, model_id) -> dict:
        """Import a catalogued model from files the person already has.

        The page names which catalogue entry, never a path: the native picker
        chooses the files, and the coordinator keeps only bytes that hash to
        that entry's pinned files.
        """
        if not isinstance(model_id, str) or not 0 < len(model_id) <= 200:
            return {"error": "Choose a model from the list.", "code": "unknown_model"}
        window = self._app.window
        if window is None:
            return {"error": "Importing needs the Refinix application window.",
                    "code": "no_window"}
        webview = _import_webview()
        chosen = window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=True,
            file_types=("Model files (*.gguf)", "All files (*.*)"))
        if not chosen:
            return {"cancelled": True}
        return self._app.import_model(model_id, [Path(p) for p in chosen])

    def choose_update_bundle(self) -> dict:
        """Import an offline update bundle chosen in the native picker."""
        window = self._app.window
        if window is None:
            return {"error": "Importing an update needs the Refinix window.",
                    "code": "no_window"}
        webview = _import_webview()
        chosen = window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=False,
            file_types=("Refinix update bundle (*.zip)", "All files (*.*)"))
        if not chosen:
            return {"cancelled": True}
        return self._app.import_update(Path(chosen[0]))

    def open_state_folder(self) -> dict:
        """Reveal the fixed application folder. No argument, no other path."""
        import subprocess
        # The workspace this window actually opened, including an explicit
        # --state, not the platform's default root.
        folder = Path(self._app.state_path).parent
        folder.mkdir(parents=True, exist_ok=True)
        opener = {"darwin": ["open"], "win32": ["explorer"]}.get(
            sys.platform, ["xdg-open"])
        try:
            subprocess.Popen([*opener, str(folder)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            return {"opened": False, "error": str(exc), "path": str(folder)}
        return {"opened": True, "path": str(folder)}

    # Links the page may ask the system browser to open. Fixed, so a page
    # (or text a model wrote into it) cannot open an arbitrary address.
    OPENABLE_URLS = frozenset({runtime.OLLAMA_DOWNLOAD_URL})

    def open_url(self, url) -> dict:
        """Open one fixed, known link in the system browser, on request."""
        if url not in self.OPENABLE_URLS:
            return {"opened": False, "error": "that link is not one Refinix opens"}
        import webbrowser
        try:
            opened = webbrowser.open(url)
        except Exception as exc:                            # noqa: BLE001
            return {"opened": False, "error": str(exc)}
        return {"opened": bool(opened)}

    # -- updates
    def install_update(self) -> dict:
        """Install the prepared, verified update and restart. Takes no argument."""
        return self._app.install_update()

    def ui_ready(self) -> dict:
        """The page has loaded; an update being verified may now be finished."""
        return self._app.ui_ready()

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
                 port: int = lifecycle.DEFAULT_PORT, on_started=None, owner=None,
                 update_gate=None):
        self.state_path = state_path
        # What the launch found about an update in progress or just finished
        # (desktop/update_apply.on_launch); None when nothing was found.
        self.update_gate = update_gate
        # The workspace lock the entry point took for this database.
        self.owner = owner
        self.preferred_port = port
        self.progress = lifecycle.Progress()
        self.window = None
        self.startup: lifecycle.Startup | None = None
        self._closing = threading.Event()
        self._retry = threading.Event()
        self._lifecycle_lock = threading.Lock()
        self._install_lock = threading.Lock()
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
                    preferred_port=self.preferred_port, cancelled=self._closing,
                    owner=self.owner)
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
                        gate = self.update_gate
                        if gate is not None and gate.notice:
                            startup.coordinator.updates.notice = gate.notice
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
                self._start_qualification_control()
                return
            # Failed: wait for the person to press Try again.
            self._retry.wait()
            self._retry.clear()
            self.progress = lifecycle.Progress()

    def _start_qualification_control(self):
        """Private qualification builds only (desktop/qualify_control.py)."""
        from backend.coordinator import build_info
        from desktop import qualify_control
        identity = build_info.embedded_identity()
        if not qualify_control.enabled(identity):
            return
        if qualify_control.should_fail_start(identity):
            # Stop before the window can confirm an update: the journey watches
            # the helper put the previous version back.
            os._exit(3)
        folder = Path(self.state_path).resolve().parent
        actions = {"import": lambda request: self.import_update(Path(request["path"])),
                   "install": lambda request: self.install_update()}
        threading.Thread(target=qualify_control.serve,
                         args=(folder, actions, self._closing), daemon=True,
                         name="qualify-control").start()

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

    def import_update(self, path: Path) -> dict:
        """Verify a natively chosen update bundle in this process's coordinator."""
        if self.startup is None or self.startup.coordinator is None:
            return {"error": "Importing an update needs the Refinix that owns this "
                             "workspace. Quit any other copy and try again.",
                    "code": "reused_coordinator"}
        from backend.coordinator import updates
        try:
            return {"updates": self.startup.coordinator.updates.import_bundle(path)}
        except updates.UpdateError as exc:
            return {"error": str(exc), "code": exc.code}

    def import_model(self, model_id: str, paths: list[Path]) -> dict:
        """Hand natively chosen model files to this process's coordinator."""
        if self.startup is None:
            return {"error": "Refinix is still starting.", "code": "starting"}
        coordinator = self.startup.coordinator
        if coordinator is None:
            # As for folders: no HTTP route accepts a filesystem path.
            return {"error": "This window is showing a Refinix coordinator that "
                             "another process started. Quit that one and open "
                             "Refinix again to import a model.",
                    "code": "reused_coordinator"}
        from backend.coordinator import provisioning
        try:
            return {"operation": coordinator.provisioner.start_import(model_id, paths)}
        except provisioning.ProvisioningError as exc:
            return {"error": str(exc), "code": exc.code}

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
            "engine": runtime.engine_label(),
            "model_configured": (s.coordinator.model_for("chat")
                                 if s and s.coordinator is not None else None),
        }

    # -- updates ------------------------------------------------------------
    def ui_ready(self) -> dict:
        """Commit an update being verified, now that its window has loaded."""
        gate = self.update_gate
        s = self.startup
        if gate is None or gate.supervised is None or s is None or s.coordinator is None:
            return {"committed": False}
        from desktop import update_apply
        try:
            journal = update_apply.commit_if_supervised(self.owner, self.state_path,
                                                        gate.supervised)
        except Exception as exc:                       # noqa: BLE001
            return {"committed": False, "error": str(exc)}
        gate.supervised = None
        if journal:
            s.coordinator.updates.notice = {"kind": "updated",
                                            "from": journal["from_version"],
                                            "to": journal["to_version"]}
        return {"committed": bool(journal)}

    def install_update(self) -> dict:
        """One native install call, including its confirmation, at a time."""
        if not self._install_lock.acquire(blocking=False):
            return {"error": "An update is already being installed."}
        try:
            with self._lifecycle_lock:
                if self._closing.is_set():
                    return {"error": "Refinix is already closing."}
            return self._install_update()
        finally:
            self._install_lock.release()

    def _install_update(self) -> dict:
        """Close, replace and reopen: drain, close the data, set it aside, hand off.

        Until the database is closed nothing has changed, and any refusal
        leaves Refinix running as it was.
        """
        from backend.coordinator import ownership, recovery, updates as updates_module
        from desktop import update_apply
        s = self.startup
        c = s.coordinator if s else None
        if c is None or self.owner is None:
            return {"error": "Installing needs the Refinix that owns this workspace."}
        u = c.updates
        install = dict(u.install)
        if install.get("state") != "ready":
            return {"error": "The update is not ready to install yet."}
        path, reason = u.install_location()
        if reason:
            return {"error": reason}
        busy_models = c.provisioner.active()
        if busy_models:
            return {"error": "A model download or import is running "
                             f"({', '.join(busy_models)}). Finish or cancel it in "
                             "Settings → Models, then install."}
        running = self.active_jobs()
        if running and self.window is not None:
            count = len(running)
            if not self.window.create_confirmation_dialog(
                    "Install the update now?",
                    f"{count} {'reply is' if count == 1 else 'replies are'} still "
                    f"running. Installing stops {'it' if count == 1 else 'them'} and "
                    f"saves {'it' if count == 1 else 'them'} as stopped; Refinix then "
                    "closes, updates and opens again."):
                return {"cancelled": True}
        with self._lifecycle_lock:
            if self._closing.is_set():
                return {"error": "Refinix is already closing."}
        identity = u.identity or {}
        database = ownership.canonical_database(self.state_path)
        environment = {key: os.environ[key] for key in update_apply.CARRIED
                       if os.environ.get(key)}
        try:
            extra = {key: install[key] for key in ("installer_sha256", "admission",
                                                   "recovery_copy", "to_maturity",
                                                   "trust_roots") if install.get(key)}
            journal = update_apply.plan_attempt(
                self.owner, database, update_id=install["update_id"],
                from_version=u.version, to_version=install["version"],
                install_path=path, incoming=Path(install["incoming"]),
                lane=identity.get("lane"), channel=identity.get("channel"),
                trust_root=identity.get("trust_root"), environment=environment,
                method=install.get("method") or "mac-app",
                extra={**extra, "from_maturity": u.maturity,
                       "publisher": u.expected_publisher()})
        except update_apply.InstallError as exc:
            return {"error": str(exc)}
        c.begin_install()
        for job in running:
            try:
                c.request_cancel(job["job_id"])
            except Exception:                          # noqa: BLE001
                pass                                   # finished meanwhile
        stuck = c.writers.wait_idle(30.0)
        if stuck:
            c.end_install()
            update_apply.cancel_attempt(self.owner, database, journal,
                                        f"{', '.join(stuck)} did not finish in time")
            return {"error": "The update was not installed because "
                             f"{', '.join(stuck)} did not finish in time. Nothing was "
                             "changed; try again."}
        # From here Refinix closes whatever happens; the helper reopens it.
        with self._lifecycle_lock:
            self._closing.set()
            self._retry.set()
        try:
            shutdown_server(s.server, c)
        except Exception:                              # noqa: BLE001
            pass
        stuck = c.close_for_install(5.0)
        try:
            s.engine_supervisor.stop()
        except Exception:                              # noqa: BLE001
            pass
        mode = "--apply-update"
        if stuck:
            mode = "--resume"          # nothing was set aside: the helper cancels
        else:
            try:
                recovery.Recovery(self.owner, database).set_aside(
                    from_version=u.version, to_version=install["version"],
                    update_id=install["update_id"], data_root=str(database.parent))
                journal = update_apply.mark(self.owner, database, journal,
                                            "snapshot_taken")
            except (recovery.RecoveryError, OSError):
                mode = "--resume"      # the helper finishes or discards the copy
        try:
            update_apply.hand_off(self.owner, database, journal,
                                  bundle=updates_module.running_install(), mode=mode)
        except Exception as exc:                       # noqa: BLE001
            # The app files are untouched; the next launch resumes the attempt.
            print(f"update helper did not start: {exc}", file=sys.stderr)
        if self.window is not None:
            threading.Timer(0.3, self.window.destroy).start()
        return {"installing": True}

    def terminate(self):
        """SIGTERM, e.g. from the update helper: stop as Quit does, without asking."""
        try:
            self.shutdown()
        finally:
            if self.window is not None:
                try:
                    self.window.destroy()
                except Exception:                      # noqa: BLE001
                    pass

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


def _stop_on_sigterm(app: "DesktopApp") -> None:
    """Turn SIGTERM into an orderly shutdown while the native run loop owns the thread.

    Python runs signal handlers only on the main thread, which the window's run
    loop holds; the wakeup pipe lets a helper thread react instead.
    """
    import os as _os
    import signal as _signal
    try:
        read_end, write_end = _os.pipe()
        _os.set_blocking(write_end, False)
        _signal.set_wakeup_fd(write_end)
        _signal.signal(_signal.SIGTERM, lambda *_args: None)
    except (ValueError, OSError, AttributeError):
        return

    def watch():
        while True:
            try:
                data = _os.read(read_end, 64)
            except OSError:
                return
            if not data:
                return
            if _signal.SIGTERM in data:
                app.terminate()
                return

    threading.Thread(target=watch, daemon=True, name="refinix-sigterm").start()


def run(*, state_path: Path = lifecycle.STATE_DB, port: int = lifecycle.DEFAULT_PORT,
        gui: str | None = None, debug: bool = False, on_started=None,
        owner=None, update_gate=None) -> int:
    """Open the window and block until it closes."""
    gui = pinned_gui(gui)
    if getattr(sys, "frozen", False):
        problem = toolkit_problem()
        if problem is not None:
            # Said before anything starts; never a silent fall-back renderer.
            print(problem, file=sys.stderr)
            _native_message("Refinix cannot open its window", problem)
            return 2
    webview = _import_webview()
    try:
        webview.settings.update({"ALLOW_DOWNLOADS": True,
                                 "OPEN_EXTERNAL_LINKS_IN_BROWSER": True,
                                 "OPEN_DEVTOOLS_IN_DEBUG": False})
    except AttributeError:                             # pragma: no cover - old pywebview
        pass

    app = DesktopApp(state_path=state_path, port=port, on_started=on_started,
                     owner=owner, update_gate=update_gate)
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

    _stop_on_sigterm(app)

    try:
        # private_mode keeps the webview from writing cookies or local storage:
        # every piece of state Refinix keeps belongs to the coordinator.
        webview.start(boot, window, gui=gui, debug=debug, private_mode=True)
    finally:
        app.shutdown()
        if worker.ident is not None:
            worker.join()  # finish cancelled startup cleanup before releasing the instance lock
    return 0
