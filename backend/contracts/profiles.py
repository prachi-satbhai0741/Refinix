"""Measured inference profiles shared by coordinator and worker.

This is deliberately the only production registry.  A route never creates a
profile and a remote request never supplies raw worker settings: both sides
resolve the same immutable identity and the execution target checks it again
against its current model digest and runtime version immediately before use.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from . import v1

MODEL_ID = "qwen3.5:4b-q4_K_M"
MODEL_DIGEST = "2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd"
RUNTIME = "ollama"

# Stable, non-secret qualification labels.  They identify the measured target
# profile, not a route, node UUID, free-memory snapshot or current queue state.
MAC_M5_16GB = "mac17-3-m5-16gb"

# The managed engine's main model and the engine build it was qualified with.
# Kept here (the contract layer does not import the coordinator); a test holds
# these equal to the catalogue's manifest digest and the pinned engine.
MANAGED_MODEL_ID = "qwen3.5-4b-q4_k_m"
MANAGED_MODEL_DIGEST = "c0d7259fae4642a79a12e9b6a20b3693c5b816166459511d79d14df45cb6db2f"
MANAGED_RUNTIME = "llama.cpp"
MAC_TIER = "macos-applesilicon-metal-16g"
MAC_MANAGED_EVIDENCE = ("qualification-artifacts/macos/macos-applesilicon-metal-16g/"
                        "qualification-managed-b11390-metal-2026-10-05.json")
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
              manifest_sha256: str = MODEL_DIGEST, runtime: str = RUNTIME) -> dict:
    """One model identity for a registry entry or a qualification run.

    Parameterised over the model because OCR is a different model from Chat.
    Defaulting to the Chat model keeps every existing entry unchanged; passing
    another identity is how a measured OCR profile would eventually be built,
    and is deliberately not enough on its own to register one.
    """
    return {"model_id": model_id, "manifest_sha256": manifest_sha256,
            "runtime": runtime, "runtime_version": runtime_version}


def _profile(*, runtime_version: str, target: str, workflow: str,
             context: int, default_output: int, max_output: int,
             reasoning: tuple[str, ...], decoder: tuple[str, ...],
             evidence_ref: str, model_id: str = MODEL_ID,
             manifest_sha256: str = MODEL_DIGEST,
             runtime: str = RUNTIME) -> v1.ExecutionProfile:
    values = {
        "model": model_ref(runtime_version, model_id=model_id,
                           manifest_sha256=manifest_sha256, runtime=runtime),
        "target_profile_id": target,
        "workflow_mode": workflow,
        "qualified_context_tokens": context,
        "default_output_tokens": default_output,
        "max_output_tokens": max_output,
        "reasoning_modes": list(reasoning),
        "default_reasoning": "disabled" if "disabled" in reasoning else "enabled",
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
    # The managed engine (llama.cpp b11390, Metal) on the Apple M-series 16 GB
    # tier, measured on the tier's representative device (Mac17,3, macOS 26.7)
    # by scripts/qualify_execution.py --engine managed on 2026-10-05.
    # Documents claims reasoning disabled only: with reasoning on, approval
    # notes used the whole 3072-token allowance without an answer in 3 of 3
    # parity runs on both this engine and Ollama 0.34.4, and general documents
    # in 1 of 3. Code is the small-edit proposal envelope only; no sandbox or
    # full-program evidence exists.
    _profile(
        runtime_version="b11390-metal", target=MAC_TIER, workflow=CHAT,
        context=8192, default_output=2048, max_output=2048,
        reasoning=("disabled", "enabled"), decoder=("text",),
        evidence_ref=MAC_MANAGED_EVIDENCE, model_id=MANAGED_MODEL_ID,
        manifest_sha256=MANAGED_MODEL_DIGEST, runtime=MANAGED_RUNTIME),
    _profile(
        runtime_version="b11390-metal", target=MAC_TIER, workflow=CODE,
        context=8192, default_output=2048, max_output=2048,
        reasoning=("disabled", "enabled"), decoder=("json_schema",),
        evidence_ref=MAC_MANAGED_EVIDENCE, model_id=MANAGED_MODEL_ID,
        manifest_sha256=MANAGED_MODEL_DIGEST, runtime=MANAGED_RUNTIME),
    _profile(
        runtime_version="b11390-metal", target=MAC_TIER, workflow=DOCUMENTS,
        context=8192, default_output=3072, max_output=3072,
        reasoning=("disabled",), decoder=("json_schema",),
        evidence_ref=MAC_MANAGED_EVIDENCE, model_id=MANAGED_MODEL_ID,
        manifest_sha256=MANAGED_MODEL_DIGEST, runtime=MANAGED_RUNTIME),
)


# --------------------------------------------------------------------------
# Hardware tiers and engine presets for the managed engine
# --------------------------------------------------------------------------
#
# A **tier** describes a class of computer by measurable facts: OS family and
# minimum version, architecture, the engine backend, the CPU/chip family and
# memory floors. Brand or product names appear only in `examples`, as labels of
# representative evidence; they are never matched.
#
# A **preset** binds one model's exact bytes and one engine build to one tier,
# with every engine setting given explicitly and the capacity floors checked
# before work is admitted. Presets are prepared during engineering from
# published research and representative Refinix measurements; setup only
# matches them. There is deliberately no preset without Refinix evidence: an
# unqualified combination is refused, never guessed.

GIB = 1024 ** 3


@dataclass(frozen=True)
class HardwareTier:
    tier_id: str
    label: str
    os_family: str
    min_os_version: tuple[int, ...]
    architectures: tuple[str, ...]
    backend: str
    min_memory_bytes: int
    min_gpu_memory_bytes: int | None = None
    chip_prefixes: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    evidence: str = ""
    # Linux tiers name the distribution their evidence covers, and the version
    # range as [min_os_version, below_os_version). A version number is only
    # meaningful within its own distribution.
    distributions: tuple[str, ...] = ()
    below_os_version: tuple[int, ...] | None = None

    def matches(self, facts: dict) -> bool:
        if facts.get("os_family") != self.os_family:
            return False
        if self.distributions and facts.get("os_distribution") not in self.distributions:
            return False
        version = facts.get("os_version_tuple")
        if not version or tuple(version) < self.min_os_version:
            return False
        if self.below_os_version is not None and tuple(version) >= self.below_os_version:
            return False
        if facts.get("architecture") not in self.architectures:
            return False
        memory = facts.get("memory_total_bytes")
        if not isinstance(memory, int) or memory < self.min_memory_bytes:
            return False
        if self.chip_prefixes and not str(facts.get("cpu_brand") or "").startswith(
                self.chip_prefixes):
            return False
        if self.backend != "cpu":
            devices = facts.get("engine_devices")
            if devices is None:
                return False
            needed = self.min_gpu_memory_bytes or 0
            if not any((d.get("memory_mib") or 0) * 1024 * 1024 >= needed
                       and _device_backend(d) == self.backend for d in devices):
                return False
        return True


def _device_backend(device: dict) -> str:
    ident = str(device.get("id", "")).upper()
    if ident.startswith("MTL"):
        return "metal"
    if ident.startswith("VULKAN"):
        return "vulkan"
    if ident.startswith("CUDA"):
        return "cuda"
    return "cpu"


# Candidate tiers. Floors use the usable memory computers actually report: a
# "16 GB" laptop shows between 15 and 16 GiB to the OS. Minimum OS versions come
# from the shipped dependencies — the pinned engine's macOS build declares
# 13.3 — not from the computer used for development. The Ubuntu tiers cover
# Ubuntu 24.04 (all its point releases report VERSION_ID 24.04) and nothing
# else until another release or distribution has its own evidence.
TIERS: tuple[HardwareTier, ...] = (
    HardwareTier(
        "macos-applesilicon-metal-16g", "Mac with Apple M-series chip, 16 GB",
        "macos", (13, 3), ("arm64",), "metal", 15 * GIB,
        chip_prefixes=("Apple M",), examples=("MacBook Air M5 16 GB",),
        evidence="engine minos 13.3 (otool, b11390); representative device: Mac17,3"),
    HardwareTier(
        "windows-x64-vulkan-4g-16g",
        "Windows 11 PC with a 4 GB+ graphics card and 16 GB memory",
        "windows", (10, 0, 22000), ("x86_64",), "vulkan", 15 * GIB,
        min_gpu_memory_bytes=int(3.5 * GIB),
        examples=("RTX 2050/3050 laptops in the recorded fleet",),
        evidence="candidate; no Refinix measurement yet"),
    HardwareTier(
        "windows-x64-cpu-16g", "Windows 11 PC, 16 GB memory, processor only",
        "windows", (10, 0, 22000), ("x86_64",), "cpu", 15 * GIB,
        evidence="candidate; no Refinix measurement yet"),
    HardwareTier(
        "linux-x64-vulkan-4g-16g",
        "Ubuntu 24.04 PC with a 4 GB+ graphics card and 16 GB memory",
        "linux", (24, 4), ("x86_64",), "vulkan", 15 * GIB,
        min_gpu_memory_bytes=int(3.5 * GIB),
        examples=("RTX 2050 laptop in the recorded fleet",),
        evidence="candidate; no Refinix measurement yet",
        distributions=("ubuntu",), below_os_version=(24, 5)),
    HardwareTier(
        "linux-x64-cpu-16g", "Ubuntu 24.04 PC, 16 GB memory, processor only",
        "linux", (24, 4), ("x86_64",), "cpu", 15 * GIB,
        evidence="candidate; no Refinix measurement yet",
        distributions=("ubuntu",), below_os_version=(24, 5)),
)

TIERS_BY_ID = {tier.tier_id: tier for tier in TIERS}


@dataclass(frozen=True)
class EnginePreset:
    """Reviewed engine settings for one model's bytes on one tier."""

    tier_id: str
    model_id: str
    manifest_sha256: str
    runtime_version: str
    context_tokens: int
    slots: int
    gpu_layers: str
    cache_type_k: str
    cache_type_v: str
    flash_attention: str
    min_available_memory_bytes: int
    min_free_disk_bytes: int
    measured_peak_rss_bytes: int | None
    evidence_kind: str           # measured_refinix | measured_external | estimated
    evidence_ref: str


# Filled only from Refinix qualification artifacts. Each preset is the exact
# engine configuration its profiles were measured with.
PRESETS: tuple[EnginePreset, ...] = (
    # Measured on Mac17,3 (Apple M5, 16 GB, macOS 26.7): qualification passed
    # Chat and Code in both reasoning modes and Documents with reasoning off;
    # the same-bytes parity run measured a 4.29 GiB engine peak RSS, 34.9
    # tokens/s median and loopback-only sockets.
    # Admission floors are estimates, not measured minimums. About 3.2 GiB of
    # that peak is the memory-mapped model files, which the OS can reclaim; the
    # 2 GiB memory floor covers the rest (8192-token cache and compute buffers)
    # with a margin. Behaviour below it was not tested. The disk floor covers
    # logs and a document's output.
    EnginePreset(
        tier_id=MAC_TIER, model_id=MANAGED_MODEL_ID,
        manifest_sha256=MANAGED_MODEL_DIGEST, runtime_version="b11390-metal",
        context_tokens=8192, slots=1, gpu_layers="all", cache_type_k="f16",
        cache_type_v="f16", flash_attention="auto",
        min_available_memory_bytes=2 * GIB, min_free_disk_bytes=1 * GIB,
        measured_peak_rss_bytes=4_606_459_904, evidence_kind="measured_refinix",
        evidence_ref=MAC_MANAGED_EVIDENCE + "; qualification-artifacts/macos/"
        "macos-applesilicon-metal-16g/parity-llamacpp-b11390-metal-vs-ollama-"
        "2026-10-04.json"),
)


def matching_tiers(facts: dict) -> list[HardwareTier]:
    """Tiers this computer meets, most capable (GPU) first."""
    found = [tier for tier in TIERS if tier.matches(facts)]
    return sorted(found, key=lambda tier: tier.backend == "cpu")


def preset_for(*, model_id: str, manifest_sha256: str, runtime_version: str,
               tier_ids: Iterable[str]) -> EnginePreset | None:
    for tier_id in tier_ids:
        for preset in PRESETS:
            if (preset.tier_id, preset.model_id, preset.manifest_sha256,
                    preset.runtime_version) == (tier_id, model_id, manifest_sha256,
                                                runtime_version):
                return preset
    return None


def for_observation(*, target_profile_id: str | Iterable[str] | None,
                    models: Iterable[v1.ModelRef | dict]) -> list[v1.ExecutionProfile]:
    """Return only profiles exactly supported by the current observation.

    `target_profile_id` may name several targets: the exact measured device
    (developer baseline) and the hardware tiers this computer matches.
    """
    if not target_profile_id:
        return []
    targets = {target_profile_id} if isinstance(target_profile_id, str) \
        else set(target_profile_id)
    observed = set()
    for model in models:
        item = model.model_dump() if isinstance(model, v1.ModelRef) else dict(model)
        observed.add((item.get("model_id"), item.get("manifest_sha256"),
                      item.get("runtime"), item.get("runtime_version")))
    return [profile for profile in PROFILES
            if profile.target_profile_id in targets
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
