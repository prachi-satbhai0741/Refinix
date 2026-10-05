"""One typed answer to "can Chat run on this computer, and if not, why?".

The ready line used to receive prose and collapse several different problems —
a modified engine, an external runtime upgrade, a missing model, a switched-off
model — into "The selected model is unavailable for new work." Each of those
needs a different fix, so each has its own code here, decided in one place, and
the interface renders by code.

Codes, most fundamental first, so the message names the thing that has to
change first:

    engine_missing, engine_unverified, engine_stop_blocked, engine_failed,
    engine_not_running, setup_incomplete, model_not_installed, model_integrity_mismatch,
    model_disabled, device_unsupported, no_qualified_profile, ready

Actions are graphical. A terminal command is offered only for the developer
engine (an external Ollama in a source checkout), and is labelled as such.

Pure: no I/O. `server.status` passes in what it has already observed.
"""

from __future__ import annotations

READY = "ready"

_ACTIONS = {
    "settings_models": {"kind": "open_settings", "target": "models",
                        "label": "Open Settings → Models"},
    "retry": {"kind": "retry", "label": "Check again"},
    "reinstall": {"kind": "reinstall", "label": "How to repair Refinix"},
    "enable": {"kind": "open_settings", "target": "models",
               "label": "Switch the model back on"},
}


def _result(code, state, message, detail="", action=None) -> dict:
    return {"code": code, "state": state, "message": message, "detail": detail,
            "action": dict(_ACTIONS[action]) if action else None}


def assess(*, runtime_state: dict, engine: dict | None, chat_row: dict | None,
           model_id: str, chat_profile_found: bool, device_tier: str | None,
           managed: bool) -> dict:
    """The single readiness answer for ordinary Chat on this computer."""
    engine = engine or {}
    if managed:
        problems = engine.get("problems") or []
        if not engine.get("release") and problems:
            return _result(
                "engine_missing", "failed",
                "The Refinix engine is not part of this installation.",
                "; ".join(problems) + ". Reinstall Refinix from a verified package; "
                "nothing is downloaded automatically.", "reinstall")
        if problems:
            return _result(
                "engine_unverified", "failed",
                "The Refinix engine files were changed, so the engine was not started.",
                "; ".join(problems[:3]) + ". Reinstall Refinix from a verified "
                "package. Your conversations and models are kept.", "reinstall")
        if engine.get("error_code") == "engine_stop_blocked":
            return _result(
                "engine_stop_blocked", "failed",
                "An earlier Refinix engine is still running and could not be stopped.",
                (engine.get("error") or "") + " Refinix will not start a second "
                "engine beside it.", "retry")
        if engine.get("error_code") in ("engine_failed", "engine_foreign",
                                         "engine_no_port"):
            return _result("engine_failed", "attention",
                           "The Refinix engine could not start.",
                           engine.get("error") or "", "retry")
        if not runtime_state.get("models"):
            return _result(
                "setup_incomplete", "attention",
                "Choose a model to finish setting up Refinix.",
                "No model is installed yet. Download one, or import one you "
                "already have, from Settings → Models.", "settings_models")
    elif not runtime_state.get("reachable"):
        return _result(
            "engine_not_running", "failed",
            "The developer engine (external Ollama) is not answering.",
            "This source checkout uses an external Ollama because no Refinix "
            "engine has been fetched. Start Ollama, or run "
            "`python desktop/engine/fetch.py --lane <lane>` to use the Refinix "
            "engine instead.", "retry")

    integrity = (((chat_row or {}).get("integrity") or {}).get("local") or {})
    # Before "not installed": changed files withhold their digest, and are
    # still the installed model, only no longer the verified one.
    if integrity.get("state") == "mismatch":
        return _result(
            "model_integrity_mismatch", "failed",
            f"The installed {model_id} is not the verified file Refinix expects.",
            (integrity.get("detail") or "Its bytes differ from the recorded manifest")
            + ", so it is not used. Remove it and install it again from "
            "Settings → Models.", "settings_models")
    if chat_row is None or not (chat_row.get("digests") or {}).get("local"):
        return _result(
            "model_not_installed", "attention",
            f"The selected model {model_id} is not installed on this computer.",
            "Install it, or choose another installed model, in Settings → Models.",
            "settings_models")
    if not chat_row.get("enabled", True):
        return _result("model_disabled", "attention",
                       f"The selected model {model_id} is switched off for new work.",
                       "Switch it back on, or choose another model.", "enable")
    if managed and device_tier is None:
        return _result(
            "device_unsupported", "attention",
            "This computer does not match a reviewed hardware preset yet.",
            "Refinix only runs models with settings that were checked for a "
            "matching class of computer. Settings → Models lists what was checked.",
            "settings_models")
    if not chat_profile_found:
        engine_name = ("the Refinix engine " + str(runtime_state.get("server_version"))
                       if managed else
                       "Ollama " + str(runtime_state.get("server_version") or ""))
        return _result(
            "no_qualified_profile", "attention",
            f"{model_id} has not been qualified with {engine_name.strip()} on this "
            "kind of computer.",
            "The model is installed, but no checked setting exists for this engine "
            "and hardware combination, so Refinix does not run it. Choose a model "
            "listed as ready in Settings → Models.", "settings_models")
    return _result(READY, "ok", "Ready on this computer.")
