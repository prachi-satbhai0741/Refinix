"""Automation for private qualification builds only; inert in every publishable package.

The native update journeys (scripts/qualify_update_journey.py) must import a
signed update bundle and press Install and restart in a real packaged
Refinix, on a disposable runner, without a person at the window. Those two
actions are native-window calls with no HTTP route. This module lets the
journey ask for them, and only when all of these hold:

* the running package's embedded build identity is a Beta-channel build
  recorded as **not publishable** (`desktop/build.py --scratch`): a release
  package can never turn this on, whatever its environment says;
* `REFINIX_QUALIFY_TOKEN` in the environment holds at least 32 characters;
* a request file in the scratch data folder carries that same token.

Requests are files, not a network surface: `qualify-request.json` beside the
workspace database, answered in `qualify-result.json`. Actions: `import`
(a bundle path) and `install` (the same call the Install button makes).

`REFINIX_QUALIFY_FAIL_START=<version>` makes that one version stop right after
starting, before its window can confirm an update — the journeys' way to watch
a new version fail and be rolled back. `REFINIX_QUALIFY_PAUSE_AT=<journal
state>` makes the update helper hold for a while right after recording that
state (desktop/update_apply.py), so a journey can stop the helper exactly
there. Both obey the same gate.
"""

from __future__ import annotations

import hmac
import json
import os
import threading
from pathlib import Path

TOKEN_VARIABLE = "REFINIX_QUALIFY_TOKEN"
FAIL_START_VARIABLE = "REFINIX_QUALIFY_FAIL_START"
REQUEST = "qualify-request.json"
RESULT = "qualify-result.json"


def enabled(identity: dict | None, environ=None) -> bool:
    environ = os.environ if environ is None else environ
    return (isinstance(identity, dict) and identity.get("channel") == "beta"
            and identity.get("publishable") is False
            and len(environ.get(TOKEN_VARIABLE, "")) >= 32)


def should_fail_start(identity: dict | None, environ=None) -> bool:
    environ = os.environ if environ is None else environ
    return enabled(identity, environ) and \
        environ.get(FAIL_START_VARIABLE) == (identity or {}).get("version")


def _write_result(folder: Path, value: dict) -> None:
    temporary = folder / f".{RESULT}.tmp"
    temporary.write_text(json.dumps(value, default=str), encoding="utf-8")
    os.replace(temporary, folder / RESULT)


def serve(folder: Path, actions: dict, stop: threading.Event, environ=None,
          interval: float = 0.5) -> None:
    """Answer token-signed requests in `folder` until `stop` is set."""
    environ = os.environ if environ is None else environ
    token = environ.get(TOKEN_VARIABLE, "")
    path = Path(folder) / REQUEST
    while not stop.wait(interval):
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
            path.unlink()
        except (OSError, ValueError):
            continue
        if not isinstance(request, dict) or not hmac.compare_digest(
                str(request.get("token", "")), token):
            continue
        action = actions.get(request.get("action"))
        try:
            result = action(request) if action else {"error": "unknown action"}
        except Exception as exc:                           # noqa: BLE001
            result = {"error": f"{type(exc).__name__}: {exc}"}
        _write_result(Path(folder), {"id": request.get("id"), "result": result})
