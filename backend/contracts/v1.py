"""AF-001 wire records and pure guards; no I/O, services, or authority grants."""

from datetime import datetime
from hashlib import sha256
import json
from typing import Annotated, Literal

from pydantic import (
    AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter,
    model_validator,
)

LEGACY_CONTRACT_VERSION = "1.0"
CONTRACT_VERSION = "1.1"
SUPPORTED_CONTRACT_VERSIONS = (LEGACY_CONTRACT_VERSION, CONTRACT_VERSION)
MAX_REQUEST_BYTES = 262_144
MAX_EVENT_BYTES = 16_384
WORKER_PORT = 8443
WORKER_NODE_PORT = 30443
REDIS_PREFIX = "af:1.1"
REDIS_GROUP = "executors-v1.1"
LEASE_SECONDS = 30
HEARTBEAT_SECONDS = 10
HEARTBEAT_TTL_SECONDS = 30
RETENTION_SECONDS = 3600
MAX_DISPATCH_ENTRIES = 128
MAX_EVENT_ENTRIES = 2048

Id = Annotated[str, StringConstraints(
    pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Label = Annotated[str, StringConstraints(min_length=1, max_length=256, pattern=r"\S")]
Count = Annotated[int, Field(ge=0)]
Capability = Literal[
    "text.generate", "document.extract", "knowledge.retrieve",
    "document.generate", "code.generate", "code.validate",
]


def _utc(value: str) -> str:
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return value


# Fixed-width UTC seconds; durations carry millisecond precision separately.
Timestamp = Annotated[str, StringConstraints(
    pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
), AfterValidator(_utc)]


class Object(BaseModel):
    model_config = ConfigDict(
        strict=True, extra="forbid", hide_input_in_errors=True,
        frozen=True,
    )


class Record(Object):
    contract_version: Literal["1.0", "1.1"]


class ModelRef(Object):
    model_id: Label
    manifest_sha256: Digest
    runtime: Label
    runtime_version: Label


ReasoningMode = Literal["disabled", "enabled"]
DecoderMode = Literal["text", "json_schema"]
WorkflowMode = Literal["chat", "code.whole_file", "documents.structured"]


class ExecutionProfile(Object):
    """One measured execution capability, not a routing preference.

    ``profile_id`` is the SHA-256 identity of every material execution field.
    A caller cannot retain an identity while changing a limit, decoder,
    reasoning mode, model artifact, runtime or target-device qualification.
    """

    profile_id: Digest
    model: ModelRef
    target_profile_id: Label
    workflow_mode: WorkflowMode
    qualified_context_tokens: Annotated[int, Field(ge=512, le=262_144)]
    default_output_tokens: Annotated[int, Field(ge=1, le=65_536)]
    max_output_tokens: Annotated[int, Field(ge=1, le=65_536)]
    reasoning_modes: Annotated[list[ReasoningMode], Field(min_length=1, max_length=2)]
    default_reasoning: ReasoningMode
    decoder_modes: Annotated[list[DecoderMode], Field(min_length=1, max_length=2)]
    qualified_memory_bytes: Annotated[int, Field(ge=1_048_576)] | None
    qualification_state: Literal["qualified", "candidate", "unqualified"]
    eligible: bool
    evidence_kind: Literal["measured", "documented", "estimated", "unverified"]
    evidence_ref: Label

    @model_validator(mode="after")
    def coherent_profile(self):
        if self.default_output_tokens > self.max_output_tokens:
            raise ValueError("default output cannot exceed the qualified maximum")
        if self.max_output_tokens > self.qualified_context_tokens:
            raise ValueError("output maximum cannot exceed the context window")
        if len(set(self.reasoning_modes)) != len(self.reasoning_modes):
            raise ValueError("reasoning modes must be unique")
        if self.default_reasoning not in self.reasoning_modes:
            raise ValueError("default reasoning must be an allowed mode")
        if len(set(self.decoder_modes)) != len(self.decoder_modes):
            raise ValueError("decoder modes must be unique")
        if self.eligible != (self.qualification_state == "qualified"):
            raise ValueError("only a qualified profile may be eligible")
        if self.profile_id != execution_profile_id(self):
            raise ValueError("profile identity does not match its execution semantics")
        return self


def execution_profile_id(profile) -> str:
    """Hash all material execution semantics of a profile."""
    if isinstance(profile, BaseModel):
        values = profile.model_dump(exclude={"profile_id", "qualification_state",
                                             "eligible", "evidence_kind",
                                             "evidence_ref"})
    else:
        values = {key: value for key, value in dict(profile).items()
                  if key not in {"profile_id", "qualification_state", "eligible",
                                 "evidence_kind", "evidence_ref"}}
    return sha256(json.dumps(values, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")).hexdigest()


class InferenceRequest(Object):
    """Actual semantics requested from one already-qualified profile."""

    profile_id: Digest
    workflow_mode: WorkflowMode
    context_window_tokens: Annotated[int, Field(ge=512, le=262_144)]
    output_allowance_tokens: Annotated[int, Field(ge=1, le=65_536)]
    reasoning: ReasoningMode
    decoder: DecoderMode
    decoder_schema_sha256: Digest | None

    @model_validator(mode="after")
    def decoder_schema(self):
        if (self.decoder == "json_schema") != (self.decoder_schema_sha256 is not None):
            raise ValueError("json_schema requests require exactly one schema hash")
        return self


class InferenceMessage(Object):
    role: Literal["system", "user", "assistant"]
    content: Annotated[str, StringConstraints(min_length=1, max_length=16_384,
                                               pattern=r"\S")]


class ResourceRef(Object):
    """Opaque ID, never a URL or host path; resolve only in the assigned package."""

    resource_id: Id
    sha256: Digest
    size_bytes: Annotated[int, Field(ge=0, le=67_108_864)]
    media_type: Annotated[str, StringConstraints(min_length=3, max_length=128)]


class Node(Record):
    node_id: Id
    display_name: Label
    app_version: Label
    platform: Label
    supported_contract_versions: Annotated[list[Label], Field(min_length=1, max_length=8)]
    capabilities: Annotated[list[Capability], Field(max_length=6)]
    models: Annotated[list[ModelRef], Field(max_length=16)]
    inference_profiles: Annotated[list[ExecutionProfile], Field(max_length=32)] = Field(
        default_factory=list)
    health: Literal["healthy", "degraded", "unavailable", "unknown"]
    observed_at: Timestamp | None
    queue_depth: Count | None
    available_memory_bytes: Count | None
    loaded_model_id: Label | None

    @model_validator(mode="after")
    def observed_health(self):
        if self.contract_version == LEGACY_CONTRACT_VERSION and self.inference_profiles:
            raise ValueError("contract 1.0 cannot advertise inference profiles")
        advertised = {(model.model_id, model.manifest_sha256, model.runtime,
                       model.runtime_version) for model in self.models}
        identities = set()
        for profile in self.inference_profiles:
            bound = (profile.model.model_id, profile.model.manifest_sha256,
                     profile.model.runtime, profile.model.runtime_version)
            if bound not in advertised:
                raise ValueError("inference profile must bind an advertised model")
            if not profile.eligible or profile.qualification_state != "qualified" \
                    or profile.evidence_kind != "measured":
                raise ValueError("nodes may advertise only measured qualified profiles")
            if profile.profile_id in identities:
                raise ValueError("profile identities must be unique")
            identities.add(profile.profile_id)
        if self.observed_at is None and (
            self.health != "unknown" or self.queue_depth is not None
            or self.available_memory_bytes is not None or self.loaded_model_id is not None
        ):
            raise ValueError("health and measurements require an observation timestamp")
        if self.loaded_model_id is not None and self.loaded_model_id not in {
            model.model_id for model in self.models
        }:
            raise ValueError("loaded model must reference an advertised manifest")
        return self


class Limits(Object):
    cpu_millis: Annotated[int, Field(ge=100, le=64_000)]
    memory_bytes: Annotated[int, Field(ge=1_048_576, le=68_719_476_736)]
    runtime_seconds: Annotated[int, Field(ge=1, le=1800)]
    processes: Annotated[int, Field(ge=1, le=128)]
    workspace_bytes: Annotated[int, Field(ge=1, le=1_073_741_824)]
    output_bytes: Annotated[int, Field(ge=1, le=16_777_216)]
    tool_network: Literal["disabled"]


Validator = Literal[
    "text.nonempty", "json.schema", "document.readable",
    "citations.resolve", "patch.applies", "sandbox.exit_zero",
]
# Each output kind names the validator that proves it, then what may be added.
REQUIRED_VALIDATORS = {
    "text": frozenset({"text.nonempty"}), "json": frozenset({"json.schema"}),
    "docx": frozenset({"document.readable"}), "patch": frozenset({"patch.applies"}),
}
OPTIONAL_VALIDATORS = {
    "text": frozenset({"citations.resolve"}), "json": frozenset({"citations.resolve"}),
    "docx": frozenset({"citations.resolve"}), "patch": frozenset({"sandbox.exit_zero"}),
}


class OutputContract(Object):
    kind: Literal["text", "json", "docx", "patch"]
    validators: Annotated[list[Validator], Field(min_length=1, max_length=6)]
    schema_ref: Digest | None

    @model_validator(mode="after")
    def applicable_validators(self):
        if ("json.schema" in self.validators) != (self.schema_ref is not None):
            raise ValueError("json.schema requires exactly one approved schema hash")
        requested = set(self.validators)
        if len(requested) != len(self.validators):
            raise ValueError("each validator may be requested once")
        if missing := REQUIRED_VALIDATORS[self.kind] - requested:
            raise ValueError(f"{self.kind} output requires {sorted(missing)}")
        if extra := requested - REQUIRED_VALIDATORS[self.kind] - OPTIONAL_VALIDATORS[self.kind]:
            raise ValueError(f"{sorted(extra)} cannot validate {self.kind} output")
        return self


class JobEnvelope(Record):
    """One bounded dispatch attempt, persisted by the coordinator before send."""

    workspace_id: Id
    workflow_id: Id
    job_id: Id
    step_id: Id
    attempt_id: Id
    chat_id: Id
    coordinator_node_id: Id
    target_node_id: Id
    relationship_id: Id | None
    original_request: Annotated[str, StringConstraints(
        min_length=1, max_length=16_384, pattern=r"\S"
    )]
    system_instruction: Annotated[str, StringConstraints(
        min_length=1, max_length=4096, pattern=r"\S"
    )] | None = None
    messages: Annotated[list[InferenceMessage], Field(max_length=64)] = Field(
        default_factory=list)
    task_type: Literal["chat", "documents", "code"]
    model: ModelRef | None = None
    inference: InferenceRequest | None = None
    required_capabilities: Annotated[list[Capability], Field(min_length=1, max_length=6)]
    context: Annotated[list[ResourceRef], Field(max_length=32)]
    attachments: Annotated[list[ResourceRef], Field(max_length=16)]
    allowed_tools: Annotated[list[Capability], Field(max_length=6)]
    limits: Limits
    output: OutputContract
    approval_policy: Literal["coordinator-default-v1"]
    created_at: Timestamp
    deadline_at: Timestamp
    cancel_requested: bool

    @model_validator(mode="after")
    def dispatch_boundary(self):
        if self.deadline_at <= self.created_at:
            raise ValueError("deadline must follow creation")
        if self.target_node_id != self.coordinator_node_id and self.relationship_id is None:
            raise ValueError("remote dispatch requires a confirmed relationship")
        resources = self.context + self.attachments
        if len({item.resource_id for item in resources}) != len(resources):
            raise ValueError("resource references must be unique within the package")
        if sum(item.size_bytes for item in resources) > self.limits.workspace_bytes:
            raise ValueError("referenced inputs exceed the workspace limit")
        generation = not (self.task_type == "code"
                          and self.required_capabilities == ["code.validate"])
        if self.contract_version == LEGACY_CONTRACT_VERSION:
            if self.messages or self.inference is not None:
                raise ValueError("contract 1.0 cannot carry qualified inference semantics")
        elif generation:
            if self.model is None or self.inference is None:
                raise ValueError("contract 1.1 generation requires a model and profile")
            expected_workflow = {
                "chat": "chat",
                "documents": "documents.structured",
                "code": "code.whole_file",
            }[self.task_type]
            if self.inference.workflow_mode != expected_workflow:
                raise ValueError("task type and inference workflow do not match")
            if self.inference.workflow_mode == "chat":
                if self.task_type != "chat" or not self.messages:
                    raise ValueError("chat inference requires bounded conversation messages")
                if self.messages[-1].role != "user" \
                        or self.messages[-1].content != self.original_request:
                    raise ValueError("chat messages must end with the original request")
            elif self.messages:
                raise ValueError("non-chat workflows build messages from bounded task inputs")
            if sum(len(item.content.encode("utf-8")) for item in self.messages) > 131_072:
                raise ValueError("conversation messages exceed the bounded task package")
        return self


JobState = Literal[
    "created", "context_preparing", "queued", "routing", "running", "validating",
    "awaiting_approval", "interrupted", "completed", "failed", "cancelled", "denied",
]
JOB_TRANSITIONS = {
    "created": {"context_preparing"},
    "context_preparing": {"queued"},
    "queued": {"routing"},
    "routing": {"running", "queued", "interrupted"},
    "running": {"validating", "interrupted"},
    "validating": {"awaiting_approval", "completed", "interrupted"},
    "awaiting_approval": {"completed", "denied"},
    "interrupted": {"queued"},
}
TERMINAL_JOB_STATES = frozenset({"completed", "failed", "cancelled", "denied"})
AttemptState = Literal["queued", "running", "validating", "completed", "failed", "cancelled", "interrupted"]
ATTEMPT_TRANSITIONS = {
    "queued": {"running"}, "running": {"validating"}, "validating": {"completed"},
}
TERMINAL_ATTEMPT_STATES = frozenset({"completed", "failed", "cancelled", "interrupted"})
# Every way an attempt can stop without producing output owes a typed reason.
STOPPED_ATTEMPT_STATES = TERMINAL_ATTEMPT_STATES - {"completed"}


def require_transition(current: str, following: str, *, attempt: bool = False) -> None:
    transitions = ATTEMPT_TRANSITIONS if attempt else JOB_TRANSITIONS
    failures = {"failed", "cancelled", "interrupted"} if attempt else {"failed", "cancelled"}
    if current not in transitions or following not in transitions[current] | failures:
        raise ValueError(f"illegal {'attempt' if attempt else 'job'} transition: {current} -> {following}")


class Job(Record):
    workspace_id: Id
    workflow_id: Id
    job_id: Id
    chat_id: Id
    state: JobState
    active_attempt_id: Id | None
    created_at: Timestamp
    updated_at: Timestamp

    @model_validator(mode="after")
    def ordered_times(self):
        if self.updated_at < self.created_at:
            raise ValueError("update precedes creation")
        return self


class Failure(Object):
    code: Literal[
        "invalid_request", "incompatible_contract", "unavailable", "deadline_exceeded",
        "worker_lost", "redis_lost", "validation_failed", "permission_denied",
        "idempotency_conflict", "events_expired", "cancelled_by_user", "internal_error",
        "incompatible_profile",
    ]
    message: Label
    retryable: bool


class Attempt(Record):
    workspace_id: Id
    job_id: Id
    step_id: Id
    attempt_id: Id
    retry_of: Id | None
    node_id: Id
    model: ModelRef | None
    state: AttemptState
    route_reason: Label
    created_at: Timestamp
    started_at: Timestamp | None
    finished_at: Timestamp | None
    queue_ms: Count | None
    runtime_ms: Count | None
    error: Failure | None
    artifacts: Annotated[list[ResourceRef], Field(max_length=16)]

    @model_validator(mode="after")
    def attempt_lifecycle(self):
        if self.retry_of == self.attempt_id:
            raise ValueError("a retry needs a new attempt ID")
        if (self.state in TERMINAL_ATTEMPT_STATES) != (self.finished_at is not None):
            raise ValueError("only terminal attempts have a finish timestamp")
        if self.state in {"running", "validating", "completed"} and self.started_at is None:
            raise ValueError("executing attempts require a start timestamp")
        if self.state == "queued" and self.started_at is not None:
            raise ValueError("queued attempts have not started")
        times = [time for time in (self.created_at, self.started_at, self.finished_at) if time is not None]
        if times != sorted(times):
            raise ValueError("attempt timestamps are out of order")
        if (self.state in STOPPED_ATTEMPT_STATES) != (self.error is not None):
            raise ValueError("a stopped attempt records exactly one typed reason")
        if (self.error is not None and self.error.code == "cancelled_by_user"
                and self.state != "cancelled"):
            raise ValueError("cancelled_by_user cannot explain a failure or interruption")
        return self


class JobStateChange(Object):
    kind: Literal["job.state"]
    previous: JobState | None
    current: JobState

    @model_validator(mode="after")
    def legal_transition(self):
        if self.previous is None:
            if self.current != "created":
                raise ValueError("the first job state must be created")
        else:
            require_transition(self.previous, self.current)
        return self


class AttemptStateChange(Object):
    kind: Literal["attempt.state"]
    previous: AttemptState | None
    current: AttemptState

    @model_validator(mode="after")
    def legal_transition(self):
        if self.previous is None:
            if self.current != "queued":
                raise ValueError("the first attempt state must be queued")
        else:
            require_transition(self.previous, self.current, attempt=True)
        return self


class TextDelta(Object):
    kind: Literal["output.delta"]
    text: Annotated[str, StringConstraints(min_length=1, max_length=2048)]


class ArtifactCreated(Object):
    kind: Literal["artifact.created"]
    artifact: ResourceRef


class ApprovalRequired(Object):
    kind: Literal["approval.required"]
    approval_id: Id


class ProofUpdated(Object):
    kind: Literal["proof.updated"]
    proof_id: Id


class InferenceMetrics(Object):
    """Worker-observed execution semantics and bounded runtime counters."""

    kind: Literal["inference.metrics"]
    requested_profile_id: Digest
    actual_profile_id: Digest
    context_window: Annotated[int, Field(ge=512, le=262_144)]
    output_token_limit: Annotated[int, Field(ge=1, le=65_536)]
    reasoning: ReasoningMode
    decoder: DecoderMode
    prompt_tokens: Count | None
    output_tokens: Count | None
    runtime_ms: Count | None


class Event(Record):
    workspace_id: Id
    job_id: Id
    attempt_id: Id | None
    event_id: Id
    sequence: Annotated[int, Field(ge=1)]
    producer_node_id: Id
    producer: Literal["coordinator", "worker"]
    occurred_at: Timestamp
    data: Annotated[
        JobStateChange | AttemptStateChange | TextDelta | ArtifactCreated |
        ApprovalRequired | ProofUpdated | InferenceMetrics,
        Field(discriminator="kind"),
    ]

    @model_validator(mode="after")
    def coordinator_authority(self):
        if self.attempt_id is None and self.data.kind != "job.state":
            raise ValueError("attempt output and decisions require an attempt ID")
        if self.producer == "worker" and self.data.kind in {
            "job.state", "approval.required", "proof.updated",
        }:
            raise ValueError("workers cannot emit coordinator decisions")
        return self


class Approval(Record):
    approval_id: Id
    workspace_id: Id
    workflow_id: Id
    job_id: Id
    step_id: Id
    attempt_id: Id
    action: Literal[
        "canonical.write", "artifact.export", "network.enable", "model.install",
        "node.pair", "node.revoke",
    ]
    target: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    action_sha256: Digest
    decision: Literal["pending", "approved", "denied", "expired"]
    actor_id: Id | None
    requested_at: Timestamp
    expires_at: Timestamp
    decided_at: Timestamp | None

    @model_validator(mode="after")
    def decision_binding(self):
        if self.expires_at <= self.requested_at:
            raise ValueError("approval expiry must follow request")
        if self.decision == "pending":
            if self.actor_id is not None or self.decided_at is not None:
                raise ValueError("pending approval has no decision")
        elif self.decided_at is None or self.decided_at < self.requested_at:
            raise ValueError("a decision needs an ordered timestamp")
        elif self.decision == "expired":
            if self.decided_at < self.expires_at or self.actor_id is not None:
                raise ValueError("expiry is a system observation at or after expiry time")
        elif self.actor_id is None or self.decided_at >= self.expires_at:
            raise ValueError("approval or denial requires an actor before expiry")
        return self


class NetworkEvidence(Object):
    public_egress_policy: Literal["enforced", "not_enforced", "unavailable"]
    enforcer: Label | None
    observer: Label | None
    started_at: Timestamp | None
    ended_at: Timestamp | None
    node_ids: Annotated[list[Id], Field(max_length=16)]
    interfaces: Annotated[list[Label], Field(max_length=16)]
    public_outbound_flows: Count | None
    external_ai_calls: Count | None
    blocked_attempts: Count | None
    trusted_lan_connections: Count | None

    @model_validator(mode="after")
    def evidence_not_inference(self):
        if (self.public_egress_policy != "unavailable") != (self.enforcer is not None):
            raise ValueError("a policy claim requires its enforcing layer")
        observed = any(value is not None for value in (
            self.public_outbound_flows, self.external_ai_calls,
            self.blocked_attempts, self.trusted_lan_connections,
        ))
        has_window = self.started_at is not None and self.ended_at is not None
        if self.observer is not None or self.enforcer is not None or observed:
            if not has_window or not self.node_ids or not self.interfaces:
                raise ValueError("network evidence requires a bounded device/interface window")
        if observed and self.observer is None:
            raise ValueError("counts require a named observer")
        if (self.started_at is None) != (self.ended_at is None):
            raise ValueError("network window needs both endpoints")
        if has_window and self.ended_at <= self.started_at:
            raise ValueError("network observation window must be positive")
        return self


class PodEvidence(Object):
    namespace: Label
    pod_name: Label
    pod_uid: Label
    image_digest: Digest
    ready: bool
    restarts: Count
    observed_at: Timestamp


class Citation(Object):
    """One drafted claim bound to the source page it was taken from."""

    citation_id: Id
    resource_id: Id
    page: Annotated[int, Field(ge=1)]
    quote: Annotated[str, StringConstraints(min_length=1, max_length=2048, pattern=r"\S")]


class Proof(Record):
    proof_id: Id
    workspace_id: Id
    job_id: Id
    attempt_id: Id
    node_id: Id
    model: ModelRef | None
    pod: PodEvidence | None
    queue_ms: Count | None
    runtime_ms: Count | None
    validation: Literal["passed", "failed", "unavailable"]
    validation_source: Label | None
    artifacts: Annotated[list[ResourceRef], Field(max_length=16)]
    citations: Annotated[list[Citation], Field(max_length=64)]
    approval_id: Id | None
    network: NetworkEvidence
    recorded_at: Timestamp

    @model_validator(mode="after")
    def validation_has_source(self):
        if (self.validation != "unavailable") != (self.validation_source is not None):
            raise ValueError("validation result requires its evidence reference")
        if len({item.citation_id for item in self.citations}) != len(self.citations):
            raise ValueError("citation references must be unique within the proof")
        return self


def require_grounded_citations(envelope: JobEnvelope, proof: Proof) -> None:
    """Coordinator-side: a citation may only point at an input this attempt received."""
    # Bind evidence to one attempt: a superseded retry's proof must not clear its successor.
    for label, dispatched, observed in (
        ("workspace", envelope.workspace_id, proof.workspace_id),
        ("job", envelope.job_id, proof.job_id),
        ("attempt", envelope.attempt_id, proof.attempt_id),
        ("target node", envelope.target_node_id, proof.node_id),
    ):
        if dispatched != observed:
            raise ValueError(f"proof and envelope describe a different {label}")
    if "citations.resolve" not in envelope.output.validators:
        return
    if not proof.citations:
        raise ValueError("citations.resolve requires at least one citation")
    inputs = {item.resource_id for item in envelope.context + envelope.attachments}
    for citation in proof.citations:
        if citation.resource_id not in inputs:
            raise ValueError("citation cites a resource the job never received")
    # ponytail: page existence is unchecked until an extractor reports page counts;
    # add a per-resource page bound to ResourceRef when AF-00x OCR lands.


def parse_message(record_type: type[Record], body: bytes) -> Record:
    """Use after transport authentication, before persistence or dispatch."""
    limit = MAX_EVENT_BYTES if record_type is Event else MAX_REQUEST_BYTES
    if len(body) > limit:
        raise ValueError("message exceeds the wire size limit")
    return record_type.model_validate_json(body)


def payload_sha256(record: Record) -> str:
    # Hashes bind retries/integrity, never authenticate a peer or grant approval.
    data = json.dumps(record.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(data.encode("utf-8")).hexdigest()


def sse_frame(event: Event) -> bytes:
    body = event.model_dump_json().encode("utf-8")
    parse_message(Event, body)
    return f"id: {event.sequence}\nevent: {event.data.kind}\ndata: ".encode() + body + b"\n\n"


def redis_key(kind: str, relationship_id: str, identifier: str | None = None) -> str:
    relationship_id = TypeAdapter(Id).validate_python(relationship_id)
    prefix = f"{REDIS_PREFIX}:{relationship_id}"
    if kind == "dispatch" and identifier is None:
        return f"{prefix}:dispatch"
    if kind not in {"events", "lease", "cancel", "heartbeat", "idempotency"}:
        raise ValueError("unknown Redis key kind or unexpected identifier")
    identifier = TypeAdapter(Id).validate_python(identifier)
    return f"{prefix}:{kind}:{identifier}"


RECORDS = (Node, JobEnvelope, Job, Attempt, Event, Approval, Proof)


def export_contract() -> dict:
    """Read-only build input for future API, UI, and manifest consumers."""
    return {
        "contract_version": CONTRACT_VERSION,
        "transport": {
            "version_header": "X-AegisForge-Contract", "idempotency_header": "Idempotency-Key",
            "worker_port": WORKER_PORT, "worker_node_port": WORKER_NODE_PORT,
            "max_request_bytes": MAX_REQUEST_BYTES, "max_event_bytes": MAX_EVENT_BYTES,
        },
        "redis": {
            "prefix": REDIS_PREFIX, "group": REDIS_GROUP,
            "lease_seconds": LEASE_SECONDS, "heartbeat_seconds": HEARTBEAT_SECONDS,
            "heartbeat_ttl_seconds": HEARTBEAT_TTL_SECONDS,
            "retention_seconds": RETENTION_SECONDS,
            "max_dispatch_entries": MAX_DISPATCH_ENTRIES,
            "max_event_entries": MAX_EVENT_ENTRIES,
        },
        "schemas": {record.__name__: record.model_json_schema() for record in RECORDS},
    }
