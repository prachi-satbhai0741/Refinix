"""Strict, evidence-only records for execution-profile qualification runs.

Artifacts deliberately contain *candidate* profiles.  Passing this schema is
not runtime admission or release acceptance; a reviewed result must still be
added to the production registry as a measured qualified profile.
"""

from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from . import v1


ARTIFACT_VERSION = "1.0"
MAX_ARTIFACT_BYTES = 1_048_576

Verification = Literal[
    "runtime.identity",
    "profile.identity",
    "workflow.completed",
    "reasoning.disabled",
    "reasoning.separated",
    "answer.nonempty",
    "structured.decoder",
    "proposal.schema",
    "proposal.small_edit",
    "canonical.unchanged",
    "representative.compile",
    "representative.behavior",
    "document.schema",
    "document.readable",
    "document.required_facts",
    "source.fenced",
]

_COMMON = {"runtime.identity", "profile.identity", "workflow.completed"}
_WORKFLOW = {
    "chat": {"answer.nonempty"},
    "code.whole_file": {
        "structured.decoder", "proposal.schema", "canonical.unchanged",
    },
    "documents.structured": {
        "structured.decoder", "document.schema", "document.readable",
        "document.required_facts", "source.fenced",
    },
}


class DeviceObservation(v1.Object):
    os_family: Literal["macos", "windows", "linux"]
    os_release: v1.Label
    architecture: v1.Label
    target_profile_id: v1.Label


class RunEvidence(v1.Object):
    reasoning: v1.ReasoningMode
    decoder: v1.DecoderMode
    requested_profile_id: v1.Digest
    actual_profile_id: v1.Digest
    context_window_tokens: Annotated[int, Field(ge=512, le=262_144)]
    output_allowance_tokens: Annotated[int, Field(ge=1, le=65_536)]
    done_reason: Literal["stop"]
    prompt_tokens: Annotated[int, Field(ge=1)]
    output_tokens: Annotated[int, Field(ge=1)]
    total_ms: Annotated[int, Field(ge=0)]
    output_sha256: v1.Digest
    thinking_observed: bool
    verifications: Annotated[list[Verification], Field(min_length=4, max_length=13)]

    @model_validator(mode="after")
    def coherent_evidence(self):
        if len(set(self.verifications)) != len(self.verifications):
            raise ValueError("verification evidence must be unique")
        required = {"reasoning.separated"} if self.reasoning == "enabled" \
            else {"reasoning.disabled"}
        if not _COMMON | required <= set(self.verifications):
            raise ValueError("qualification evidence is incomplete")
        if self.thinking_observed != (self.reasoning == "enabled"):
            raise ValueError("reasoning-channel evidence does not match the request")
        return self


class WorkflowQualification(v1.Object):
    profile: v1.ExecutionProfile
    result: Literal["passed"]
    evidence: Annotated[list[RunEvidence], Field(min_length=1, max_length=4)]

    @model_validator(mode="after")
    def measured_candidate(self):
        profile = self.profile
        if (profile.qualification_state, profile.eligible, profile.evidence_kind) != (
                "candidate", False, "unverified"):
            raise ValueError("an artifact may contain only a non-admissible candidate profile")
        expected = set(product(profile.reasoning_modes, profile.decoder_modes))
        observed = {(item.reasoning, item.decoder) for item in self.evidence}
        if observed != expected or len(observed) != len(self.evidence):
            raise ValueError("every claimed reasoning and decoder combination must be measured once")
        required = set(_WORKFLOW[profile.workflow_mode])
        if profile.workflow_mode == "code.whole_file" \
                and profile.max_output_tokens > profile.default_output_tokens:
            required |= {"representative.compile", "representative.behavior"}
        for item in self.evidence:
            if item.requested_profile_id != profile.profile_id \
                    or item.actual_profile_id != profile.profile_id:
                raise ValueError("requested and actual profile identities must match the candidate")
            if item.context_window_tokens != profile.qualified_context_tokens \
                    or item.output_allowance_tokens != profile.max_output_tokens:
                raise ValueError("evidence must exercise the candidate's exact qualified limits")
            if item.decoder not in profile.decoder_modes:
                raise ValueError("evidence decoder is not part of the candidate")
            if not required <= set(item.verifications):
                raise ValueError("workflow-specific qualification evidence is incomplete")
        return self


class QualificationArtifact(v1.Object):
    artifact_version: Literal["1.0"]
    generated_at: v1.Timestamp
    device: DeviceObservation
    observed_model: v1.ModelRef
    result: Literal["passed"]
    release_accepted: Literal[False]
    workflows: Annotated[list[WorkflowQualification], Field(min_length=1, max_length=3)]

    @model_validator(mode="after")
    def exact_observation(self):
        modes = [item.profile.workflow_mode for item in self.workflows]
        if len(set(modes)) != len(modes):
            raise ValueError("an artifact may qualify each workflow only once")
        for item in self.workflows:
            if item.profile.model != self.observed_model:
                raise ValueError("candidate model/runtime identity differs from the observation")
            if item.profile.target_profile_id != self.device.target_profile_id:
                raise ValueError("candidate device identity differs from the observation")
        return self


def loads(raw: bytes | str) -> QualificationArtifact:
    data = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(data) > MAX_ARTIFACT_BYTES:
        raise ValueError("qualification artifact exceeds the size limit")
    return QualificationArtifact.model_validate_json(data)


def read(path: Path) -> QualificationArtifact:
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("qualification artifact exceeds the size limit")
    return loads(path.read_bytes())


def write(path: Path, artifact: QualificationArtifact) -> None:
    """Create one immutable-on-purpose evidence file; never replace one."""
    with path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(artifact.model_dump_json(indent=2) + "\n")
