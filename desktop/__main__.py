"""Open Refinix.

    python3 -m desktop                 native window
    python3 -m desktop --no-window     local services only, no toolkit needed

The command-line coordinator (`python3 -m backend.coordinator`) is unchanged and
keeps working on its own.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

from desktop import lifecycle

parser = argparse.ArgumentParser(prog="python3 -m desktop", description="Open Refinix.")
parser.add_argument("--state", type=Path, default=lifecycle.STATE_DB,
                    help="SQLite database path (outside the repository)")
parser.add_argument("--port", type=int, default=lifecycle.DEFAULT_PORT,
                    help="preferred loopback port; another free one is used if it is taken")
parser.add_argument("--no-window", action="store_true",
                    help="start the local services and print the address, without a window")
parser.add_argument("--gui", default=None,
                    help="pywebview backend override, for example 'cocoa', 'edgechromium', 'qt'")
parser.add_argument("--debug", action="store_true", help="pywebview debug mode")
args = parser.parse_args()


def _second_launch(existing: dict) -> int:
    """Another Refinix already holds the lock. Bring it forward, do not start."""
    port = existing.get("port")
    if port is None and existing.get("mode") == "starting":
        print("Refinix is still starting. Use the window that is already open.")
        return 0
    identity = lifecycle.identify_occupant(port) if isinstance(port, int) else None
    if identity is None:
        print("Refinix is already running, but its coordinator did not answer. "
              "Quit the other copy and try again.", file=sys.stderr)
        return 1
    import urllib.request
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/desktop/focus", data=b"{}", method="POST",
        headers={"Content-Type": "application/json", "Host": f"127.0.0.1:{port}"})
    try:
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5)
    except OSError as exc:
        print(f"Refinix is already running but could not be focused: {exc}", file=sys.stderr)
        return 1
    print(f"Refinix is already open on http://127.0.0.1:{port}/ "
          f"(process {existing.get('pid', 'unknown')}). Brought it to the front.")
    return 0


def main() -> int:
    instance = lifecycle.SingleInstance()
    existing = instance.acquire()
    if existing is not None:
        return _second_launch(existing)

    try:
        if not args.no_window:
            from desktop import shell
            try:
                instance.record(port=None, mode="starting")
                return shell.run(state_path=args.state, port=args.port,
                                 gui=args.gui, debug=args.debug,
                                 on_started=lambda startup: instance.record(
                                     port=startup.port, mode="window"))
            except shell.MissingToolkit as exc:
                print(exc, file=sys.stderr)
                return 2

        # Headless: the same startup sequence, printed instead of drawn.
        progress = lifecycle.Progress()
        try:
            startup = lifecycle.run_startup(progress, state_path=args.state,
                                            preferred_port=args.port)
        except lifecycle.StartupError as exc:
            print(f"Refinix could not start: {exc}\n  {exc.detail}", file=sys.stderr)
            return 1
        instance.record(port=startup.port, mode="no-window")
        for step in progress.snapshot()["steps"]:
            mark = {"ok": "ok  ", "attention": "note", "failed": "fail"}.get(step["state"], "    ")
            print(f"  [{mark}] {step['label']}: {step['detail']}".rstrip())
            if step["action"] and step["action"].get("command"):
                print(f"           {step['action']['command']}")
        print(f"\nRefinix: {startup.url}  (this computer only)")
        if startup.server is None:
            print("Reusing the coordinator that was already running; nothing to serve here.")
            return 0

        stopping = False

        def stop(_signum, _frame):
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        import threading
        threading.Thread(target=startup.server.serve_forever,
                         kwargs={"poll_interval": 0.2}, daemon=True).start()
        while not stopping:
            time.sleep(0.2)
        print("\nstopping")
        from backend.coordinator.server import shutdown_server
        shutdown_server(startup.server, startup.coordinator)
        if startup.engine_supervisor.stop():
            print("stopped the AI engine Refinix had started")
        print("stopped")
        return 0
    finally:
        instance.release()


sys.exit(main())
