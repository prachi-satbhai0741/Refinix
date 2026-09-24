"""Measured inference profiles shared by coordinator and worker.

This is deliberately the only production registry.  A route never creates a
profile and a remote request never supplies raw worker settings: both sides
resolve the same immutable identity and the execution target checks it again
against its current model digest and runtime version immediately before use.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable

from . import v1

MODEL_ID = "qwen3.5:4b-q4_K_M"
MODEL_DIGEST = "2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd"
RUNTIME = "ollama"

# Stable, non-secret qualification labels.  They identify the measured target
# profile, not a route, node UUID, free-memory snapshot or current queue state.
MAC_M5_16GB = "mac17-3-m5-16gb"
UBUNTU_VICTUS_RTX2050 = "hp-victus-i5-13420h-rtx2050-4gb-ubuntu-24.04"

CHAT = "chat"
CODE = "code.whole_file"
DOCUMENTS = "documents.structured"
# Reading pixels is its own workflow: a different model, a different decoder
# schema and a different failure mode from `documents.structured`.  It exists
# here so an OCR request has a workflow mode to be qualified *against*, and so
# a self-test cannot be admitted under the Documents profile by accident.  No
# OCR profile is registered below: `docs/model-catalog.md` 3.2 records the
# installed conversion's licence and provenance as UNRESOLVED and its declared
# capabilities as `["completion"]`.  Naming the workflow is not qualifying a
# model for it.
OCR = "documents.ocr"


def schema_sha256(schema: dict) -> str:
    return hashlib.sha256(json.dumps(
        schema, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()


def model_ref(runtime_version: str, *, model_id: str = MODEL_ID,
              manifest_sha256: str = MODEL_DIGEST) -> dict:
    """One model identity for a registry entry or a qualification run.

    Parameterised over the model because OCR is a different model from Chat.
    Defaulting to the Chat model keeps every existing entry unchanged; passing
    another identity is how a measured OCR profile would eventually be built,
    and is deliberately not enough on its own to register one.
    """
    return {"model_id": model_id, "manifest_sha256": manifest_sha256,
            "runtime": RUNTIME, "runtime_version": runtime_version}


def _profile(*, runtime_version: str, target: str, workflow: str,
             context: int, default_output: int, max_output: int,
             reasoning: tuple[str, ...], decoder: tuple[str, ...],
             evidence_ref: str, model_id: str = MODEL_ID,
             manifest_sha256: str = MODEL_DIGEST) -> v1.ExecutionProfile:
    values = {
        "model": model_ref(runtime_version, model_id=model_id,
                           manifest_sha256=manifest_sha256),
        "target_profile_id": target,
        "workflow_mode": workflow,
        "qualified_context_tokens": context,
        "default_output_tokens": default_output,
        "max_output_tokens": max_output,
        "reasoning_modes": list(reasoning),
        "default_reasoning": "disabled",
        "decoder_modes": list(decoder),
        "qualified_memory_bytes": None,
        "qualification_state": "qualified",
        "eligible": True,
        "evidence_kind": "measured",
        "evidence_ref": evidence_ref,
    }
    return v1.ExecutionProfile(
        profile_id=v1.execution_profile_id(values), **values)


# Exact versions are intentional.  A later runtime or another computer earns a
# new profile after measurement; an advertised model maximum is never promoted
# into this registry.
#
# There is deliberately NO `OCR` entry.  The only installed vision candidate
# has an unresolved licence and provenance and did not declare `vision` when it
# was observed, so every OCR request refuses for want of a qualified profile.
# That refusal is the correct product state, not a gap to be filled by writing
# a plausible row here.
PROFILES: tuple[v1.ExecutionProfile, ...] = (
    _profile(
        runtime_version="0.32.14", target=MAC_M5_16GB, workflow=CHAT,
        context=8192, default_output=2048, max_output=2048,
        reasoning=("disabled", "enabled"), decoder=("text",),
        evidence_ref="model-catalog#bounded-execution-macos-2026-09-04"),
    _profile(
        runtime_version="0.33.3", target=MAC_M5_16GB, workflow=CHAT,
        context=8192, default_output=2048, max_output=2048,
        reasoning=("disabled", "enabled"), decoder=("text",),
        evidence_ref="agent-memory/agentchangelog.md#ac-20260921-007"),
    _profile(
        runtime_version="0.34.2", target=MAC_M5_16GB, workflow=CHAT,
        context=8192, default_output=2048, max_output=2048,
        reasoning=("disabled", "enabled"), decoder=("text",),
        evidence_ref=("qualification-artifacts/macos/mac17-3-m5-16gb/"
                      "ollama-0.34.2-qwen3.5-4b-q4-k-m-chat.json")),
    _profile(
        runtime_version="0.32.14", target=MAC_M5_16GB, workflow=CODE,
        context=8192, default_output=2048, max_output=8128,
        reasoning=("disabled", "enabled"), decoder=("json_schema",),
        evidence_ref="agent-memory#workflow-envelope-2026-09-21"),
    _profile(
        runtime_version="0.33.3", target=MAC_M5_16GB, workflow=CODE,
        context=8192, default_output=2048, max_output=2048,
        reasoning=("disabled", "enabled"), decoder=("json_schema",),
        evidence_ref="agent-memory/agentchangelog.md#ac-20260921-007"),
    _profile(
        runtime_version="0.34.2", target=MAC_M5_16GB, workflow=CODE,
        context=8192, default_output=2048, max_output=2048,
        reasoning=("disabled", "enabled"), decoder=("json_schema",),
        evidence_ref=("qualification-artifacts/macos/mac17-3-m5-16gb/"
                      "ollama-0.34.2-qwen3.5-4b-q4-k-m-code-proposal.json")),
    _profile(
        runtime_version="0.32.14", target=MAC_M5_16GB, workflow=DOCUMENTS,
        context=8192, default_output=3072, max_output=3072,
        reasoning=("disabled", "enabled"), decoder=("json_schema",),
        evidence_ref="agent-memory#documents-envelope-2026-09-21"),
    _profile(
        runtime_version="0.33.3", target=MAC_M5_16GB, workflow=DOCUMENTS,
        context=8192, default_output=3072, max_output=3072,
        reasoning=("disabled", "enabled"), decoder=("json_schema",),
        evidence_ref="agent-memory/agentchangelog.md#ac-20260921-007"),
    _profile(
        runtime_version="0.33.2", target=UBUNTU_VICTUS_RTX2050, workflow=CHAT,
        context=4096, default_output=2048, max_output=2048,
        reasoning=("disabled",), decoder=("text",),
        evidence_ref="model-catalog#ubuntu-worker-2026-09-03"),
)


def for_observation(*, target_profile_id: str | None,
                    models: Iterable[v1.ModelRef | dict]) -> list[v1.ExecutionProfile]:
    """Return only profiles exactly supported by the current observation."""
    if not target_profile_id:
        return []
    observed = set()
    for model in models:
        item = model.model_dump() if isinstance(model, v1.ModelRef) else dict(model)
        observed.add((item.get("model_id"), item.get("manifest_sha256"),
                      item.get("runtime"), item.get("runtime_version")))
    return [profile for profile in PROFILES
            if profile.target_profile_id == target_profile_id
            and (profile.model.model_id, profile.model.manifest_sha256,
                 profile.model.runtime, profile.model.runtime_version) in observed]


def by_id(profile_id: str, candidates: Iterable[v1.ExecutionProfile]) \
        -> v1.ExecutionProfile | None:
    return next((item for item in candidates if item.profile_id == profile_id), None)


def compatible(profile: v1.ExecutionProfile, *, model_id: str, workflow: str,
               reasoning: str, decoder: str, context_window: int | None = None,
               output_allowance: int | None = None) -> bool:
    """Pure pre-dispatch compatibility check; it never renegotiates values."""
    return bool(
        profile.eligible
        and profile.qualification_state == "qualified"
        and profile.evidence_kind == "measured"
        and profile.model.model_id == model_id
        and profile.workflow_mode == workflow
        and reasoning in profile.reasoning_modes
        and decoder in profile.decoder_modes
        and (context_window is None
             or context_window <= profile.qualified_context_tokens)
        and (output_allowance is None
             or output_allowance <= profile.max_output_tokens)
    )


def request(profile: v1.ExecutionProfile, *, reasoning: str,
            decoder: str, output_allowance: int | None = None,
            context_window: int | None = None,
            decoder_schema_sha256: str | None = None) -> v1.InferenceRequest:
    """Build and validate the actual semantics requested from a profile."""
    output = (profile.default_output_tokens if output_allowance is None
              else output_allowance)
    window = (profile.qualified_context_tokens if context_window is None
              else context_window)
    if not compatible(profile, model_id=profile.model.model_id,
                      workflow=profile.workflow_mode, reasoning=reasoning,
                      decoder=decoder, context_window=window,
                      output_allowance=output):
        raise ValueError("requested inference semantics are not qualified by this profile")
    return v1.InferenceRequest(
        profile_id=profile.profile_id, workflow_mode=profile.workflow_mode,
        context_window_tokens=window, output_allowance_tokens=output,
        reasoning=reasoning, decoder=decoder,
        decoder_schema_sha256=decoder_schema_sha256)


def validate_request(profile: v1.ExecutionProfile, request: v1.InferenceRequest,
                     model: v1.ModelRef) -> None:
    """Final target-side check performed immediately before inference."""
    if request.profile_id != profile.profile_id or model != profile.model:
        raise ValueError("requested profile is stale or bound to another model")
    if not compatible(
            profile, model_id=model.model_id, workflow=request.workflow_mode,
            reasoning=request.reasoning, decoder=request.decoder,
            context_window=request.context_window_tokens,
            output_allowance=request.output_allowance_tokens):
        raise ValueError("requested inference semantics are incompatible")
