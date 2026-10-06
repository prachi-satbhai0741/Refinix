"""One typed answer to "can Chat run on this computer, and if not, why?".

Each problem has its own code, decided in one place, and the interface renders
by code. Codes, most fundamental first, so the message names the thing that
has to change first:

    engine_missing, engine_unverified, engine_stop_blocked, engine_failed,
    engine_not_running, ollama_update_recommended, setup_incomplete,
    model_not_installed, model_integrity_mismatch, model_disabled,
    cloud_model_excluded, locality_unknown, no_usable_model, ready

A hardware class nobody measured, or a model/runtime combination without a
team measurement, is not a reason Chat cannot run: those are evidence labels,
not admission rules. Chat is ready whenever an installed local model can run
it on either runtime.

Actions are graphical. Nothing here installs, updates or starts software on
its own.

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
    "start_ollama": {"kind": "start_ollama", "label": "Start Ollama"},
    "update_ollama": {"kind": "open_url", "url": "https://ollama.com/download",
                      "label": "Get the current Ollama"},
}


def _result(code, state, message, detail="", action=None) -> dict:
    return {"code": code, "state": state, "message": message, "detail": detail,
            "action": dict(_ACTIONS[action]) if action else None}


def assess(*, runtime_state: dict, engine: dict | None, chat_row: dict | None,
           model_id: str, chat_profile_found: bool, device_tier: str | None,
           managed: bool, refusal: str | None = None, ollama: dict | None = None,
           usable_models: int | None = None) -> dict:
    """The single readiness answer for ordinary Chat on this computer.

    `device_tier` is accepted for the status page's description only: a
    computer that matches no measured hardware class is not thereby unable to
    run Chat.
    """
    engine = engine or {}
    ollama = ollama or {}
    row_origin = (chat_row or {}).get("origin")
    # The Refinix engine's own failures decide readiness when Chat would use
    # it — or when nothing else could run it. A broken engine does not make a
    # working Ollama model unready.
    engine_matters = managed and (row_origin in (None, "llama.cpp")
                                  or not chat_profile_found)
    if engine_matters:
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
    if ollama.get("update_recommended") and (row_origin in (None, "ollama")
                                             and not chat_profile_found):
        return _result(
            "ollama_update_recommended", "attention",
            " ".join(f"Your Ollama {ollama.get('version') or ''} is older than "
                     f"{(ollama.get('baseline') or {}).get('minimum')}.".split()),
            "Refinix needs Ollama to refuse an over-long prompt rather than "
            "trim it silently, and to say which models run on another host. "
            "Update Ollama, then check again. Refinix never updates it for you.",
            "update_ollama")
    if not managed and not runtime_state.get("reachable"):
        return _result(
            "engine_not_running", "failed", "Ollama is not answering.",
            "This copy of Refinix uses Ollama because no Refinix engine is part "
            "of it. Start Ollama, or fetch the Refinix engine "
            "(`python desktop/engine/fetch.py --lane <lane>`), then check again.",
            "start_ollama" if ollama.get("startable") else "retry")
    no_models = (usable_models == 0) if usable_models is not None \
        else not runtime_state.get("models")
    if no_models:
        return _result(
            "setup_incomplete", "attention",
            "Choose a model to finish setting up Refinix.",
            "No local model is installed yet. Download one, or import one you "
            "already have, from Settings → Models"
            + (", or start Ollama to use the models you have there."
               if ollama.get("startable") else "."),
            "start_ollama" if ollama.get("startable") else "settings_models")

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
        if refusal and chat_row is None and not chat_profile_found:
            return _result("no_usable_model", "attention", refusal,
                           "Choose or download a model in Settings → Models.",
                           "settings_models")
        return _result(
            "model_not_installed", "attention",
            f"The selected model {model_id} is not installed on this computer.",
            "Install it, or choose another installed model or Auto, in "
            "Settings → Models.", "settings_models")
    if not chat_row.get("enabled", True):
        return _result("model_disabled", "attention",
                       f"The selected model {model_id} is switched off for new work.",
                       "Switch it back on, or choose another model.", "enable")
    if chat_row.get("locality") == "remote":
        return _result(
            "cloud_model_excluded", "attention",
            f"{model_id} runs on another host through Ollama, so Refinix does not "
            "send your work to it.",
            "Choose a local model, or Auto, in Settings → Models.", "settings_models")
    if chat_row.get("locality") == "unknown":
        return _result(
            "locality_unknown", "attention",
            f"Whether {model_id} runs on this computer could not be confirmed.",
            "Nothing is sent to a model until that is known. Check again, or choose "
            "another model.", "retry")
    if chat_profile_found:
        return _result(READY, "ok", "Ready on this computer.")
    return _result(
        "no_usable_model", "attention",
        refusal or f"{model_id} cannot run Chat on this computer.",
        "Choose another installed model, or Auto, in Settings → Models.",
        "settings_models")
