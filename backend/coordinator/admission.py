"""Which local models may run which workflow here, and under what bounds.

The measured registry (`backend/contracts/profiles.py`) records what the team
qualified on particular computers. It is evidence, not a list of the only
models a person may use. A model the team never measured can still run on the
computer that owns the workspace when its runtime says it can do the work:

* it is installed, runs locally and has an observed identity;
* it declares the capability the workflow needs (`completion`, and `vision`
  for page images);
* the runtime offers the decoder the workflow needs (plain text, or JSON-schema
  output for structured Documents, Code proposals and page readings).

Such a model gets a `candidate` ExecutionProfile: `eligible` is False and its
evidence is `documented` (bounds taken from what the runtime declared) or
`estimated` (a conservative default because nothing was declared). It is never
labelled measured or qualified, never advertised to another computer and never
dispatched. When an exact measured profile exists for the same bytes, runtime
build, workflow and computer, that profile is used instead.

The bounds are conservative starting points, not a model's maximum: an 8192
token window unless the model declares less, replies of 2048 tokens (3072 for
Documents) and at most half the window. A request that needs more may ask for a
larger window up to what the model declares (`window` below); the window it ran
with is recorded with the attempt.

Pure: no I/O. Callers pass what they already observed.
"""

from __future__ import annotations

import hashlib
import json

from backend.contracts import profiles as inference_profiles
from backend.contracts import v1

DEFAULT_WINDOW = 8192
MIN_WINDOW = 2048
DEFAULT_OUTPUT = {inference_profiles.CHAT: 2048, inference_profiles.CODE: 2048,
                  inference_profiles.DOCUMENTS: 3072, inference_profiles.OCR: 2048}
LOCAL_TARGET = "this-computer"
POLICY_VERSION = "local-admission-v1"

# Workflow -> (decoders it needs, capability it needs beyond completion).
WORKFLOWS = {
    inference_profiles.CHAT: (("text",), None),
    inference_profiles.CODE: (("json_schema",), None),
    inference_profiles.DOCUMENTS: (("json_schema",), None),
    inference_profiles.OCR: (("json_schema",), "vision"),
}

# Documents and page reading run with reasoning off: measured runs used the
# whole Documents allowance reasoning without an answer (profiles.py, managed
# b11390 notes), and a page reading has no use for it.
REASONING_OFF_ONLY = {inference_profiles.DOCUMENTS, inference_profiles.OCR}


def offers_reasoning(observation: dict) -> bool:
    """Whether this model has a reasoning switch the runtime can honour.

    Ollama reports `thinking` itself. For the Refinix engine the switch is a
    chat-template argument, offered when a measured profile for these bytes
    offered it or the publisher's card lists reasoning among its strengths.
    """
    capabilities = observation.get("capabilities") or []
    if "thinking" in capabilities:
        return True
    return bool(observation.get("reasoning_hint"))


def generates(observation: dict) -> bool:
    """Completion is required to generate; unknown capabilities do not refuse."""
    capabilities = observation.get("capabilities")
    return capabilities is None or "completion" in capabilities


def _window(declared: int | None, requested: int | None) -> tuple[int, str]:
    if requested is not None:
        limit = declared if declared else DEFAULT_WINDOW
        return max(MIN_WINDOW, min(requested, limit)), (
            "documented" if declared else "estimated")
    if declared:
        return max(MIN_WINDOW, min(DEFAULT_WINDOW, declared)), "documented"
    return DEFAULT_WINDOW, "estimated"


def candidate(observation: dict, workflow: str, *,
              window: int | None = None) -> v1.ExecutionProfile | None:
    """A local candidate profile for one observed model and workflow, or None.

    `observation` carries: model_id, digest, origin, runtime_version,
    capabilities (list or None), context_length (int or None) and, for the
    Refinix engine, reasoning_hint.
    """
    if workflow not in WORKFLOWS or observation.get("locality") != "local":
        return None
    digest = observation.get("digest") or ""
    if len(digest) != 64 or not generates(observation):
        return None
    decoders, needs = WORKFLOWS[workflow]
    capabilities = observation.get("capabilities")
    if needs is not None and (capabilities is None or needs not in capabilities):
        return None
    size, evidence = _window(observation.get("context_length"), window)
    default = DEFAULT_OUTPUT[workflow]
    maximum = max(default, size // 2)
    if default > size or maximum > size:
        return None
    reasoning = (("disabled",) if workflow in REASONING_OFF_ONLY
                 or not offers_reasoning(observation)
                 else ("disabled", "enabled"))
    values = {
        "model": {"model_id": observation["model_id"], "manifest_sha256": digest,
                  "runtime": observation["origin"],
                  "runtime_version": observation.get("runtime_version") or "unknown"},
        "target_profile_id": LOCAL_TARGET,
        "workflow_mode": workflow,
        "qualified_context_tokens": size,
        "default_output_tokens": default,
        "max_output_tokens": maximum,
        "reasoning_modes": list(reasoning),
        "default_reasoning": "disabled",
        "decoder_modes": list(decoders),
        "qualified_memory_bytes": None,
        "qualification_state": "candidate",
        "eligible": False,
        "evidence_kind": evidence,
        "evidence_ref": f"{POLICY_VERSION}:{observation['origin']}",
    }
    try:
        return v1.ExecutionProfile(profile_id=v1.execution_profile_id(values), **values)
    except ValueError:
        return None


def measured_for(observation: dict, targets: list[str]) -> list[v1.ExecutionProfile]:
    """Exact measured profiles for these bytes, runtime build and computer."""
    try:
        ref = v1.ModelRef(model_id=observation["model_id"],
                          manifest_sha256=observation.get("digest") or "",
                          runtime=observation["origin"],
                          runtime_version=observation.get("runtime_version") or "unknown")
    except (KeyError, ValueError):
        return []
    return inference_profiles.for_observation(target_profile_id=targets, models=[ref])


def profiles_for(observation: dict, targets: list[str]) -> list[v1.ExecutionProfile]:
    """Every profile this model may run under here: measured first, else candidate."""
    if observation.get("locality") != "local":
        return []
    measured = measured_for(observation, targets)
    covered = {profile.workflow_mode for profile in measured}
    result = list(measured)
    for workflow in WORKFLOWS:
        if workflow in covered:
            continue
        derived = candidate(observation, workflow)
        if derived is not None:
            result.append(derived)
    return result


# --------------------------------------------------------------------------
# Evidence labels
# --------------------------------------------------------------------------

COMPATIBLE = "compatible"
PUBLISHED = "published"
CHECKED_HERE = "checked_here"
MEASURED = "measured"
NOT_USABLE = "not_usable"

LABELS = {
    COMPATIBLE: "Compatible — meets the requirements, not yet run here",
    PUBLISHED: "Published evidence — the publisher's claims, cited",
    CHECKED_HERE: "Checked here — an actual result on this computer",
    MEASURED: "Measured in Refinix",
    NOT_USABLE: "Not usable for this task",
}


def evidence_label(profile: v1.ExecutionProfile | None, *, checked: bool) -> str:
    """One profile's evidence, never stronger than what was observed."""
    if profile is None:
        return NOT_USABLE
    if profile.qualification_state == "qualified" and profile.evidence_kind == "measured":
        return MEASURED
    return CHECKED_HERE if checked else COMPATIBLE


# --------------------------------------------------------------------------
# Check fingerprints
# --------------------------------------------------------------------------

# Bump when a self-test's prompt, parser, render settings or pass criteria
# change, so a result recorded under the old definition stops counting.
# v3 (2026-10-07): the Chat check rejects a reply spread over several lines
# before normalising whitespace, and failures record their kind.
# v4 (2026-10-07): the Chat check accepts the verdict and number without the
# "smaller number:" label (D1), and an answer cut off by the check's output
# limit is a recorded failure of kind "incomplete" (D9).
CHECK_DEFINITION_VERSION = "selftest-v4"


def check_fingerprint(profile: v1.ExecutionProfile | None, scope: str,
                      settings: dict | None = None) -> str | None:
    """Durable identity of what a self-test actually exercised.

    Binds the exact execution profile (model bytes, runtime build, window,
    output bounds, reasoning and decoder modes), the check definition version
    and any extra settings the check depends on (for example the page render
    size). If any of them changes, an old result no longer matches and is
    shown as history rather than as current.
    """
    if profile is None:
        return None
    body = {"profile_id": profile.profile_id, "scope": scope,
            "definition": CHECK_DEFINITION_VERSION, "settings": settings or {}}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()
