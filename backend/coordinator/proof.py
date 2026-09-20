"""AF-014 Proof Cards: one record per attempt, every value with a source.

This module builds `backend.contracts.v1.Proof` records. It does not invent a
parallel evidence object, and it does not compute anything: every field is read
out of something that was actually observed and stored, or it is reported as
unavailable.

The rules below are the whole module, and each exists because the opposite is
an easy and convincing lie:

* **`unavailable` is not `zero`, `false`, or `healthy`.** A queue time that was
  never recorded is `None`, not `0`. A validation nobody ran is `unavailable`,
  not `failed`.
* **A local attempt has no Pod evidence.** Documents runs on the computer the
  user is at. Attaching a `PodEvidence` to it would describe a Pod that does
  not exist.
* **A device is named by its role, not by an operating system.** Where an
  attempt ran is "this computer" or "paired worker"; writing "macOS
  coordinator" into the record made every Windows and Linux installation
  report a machine that is not theirs.
* **A validation attempt has no model evidence.** The sandbox runs no model, so
  `model` is `None` — not the model that happened to generate the patch.
* **Configuration is not observation.** A NetworkPolicy that denies egress is
  not evidence that nothing left; an image named in a manifest is not evidence
  that it ran. Pod and image facts come from what the API returned, and network
  evidence stays `unavailable` until the C11 observation window exists.
* **Proof belongs to one attempt.** A superseded attempt's proof cannot clear
  its retry, and a citation may only name an input that exact attempt received.
  `v1.require_grounded_citations` enforces the second; the per-attempt build
  enforces the first.

Standard library only.
"""

from __future__ import annotations

import json

from backend.contracts import v1
from backend.coordinator import db, device

# Where each displayed value came from. The UI shows these next to the value,
# so a reader can tell a measurement from a record from an absence.
SOURCE_SQLITE = "coordinator SQLite"
SOURCE_KUBERNETES = "Kubernetes API (observed)"
SOURCE_VALIDATION = "sandbox validation result"
SOURCE_CATALOGUE = "local model catalogue"

NETWORK_UNAVAILABLE_NOTE = (
    "Network evidence is unavailable. Nothing has observed this run's traffic: "
    "the C11 observation window, with a named device, interface and time range, "
    "has not been recorded. A default-deny NetworkPolicy is a configuration, "
    "not a measurement, and is never reported here as zero egress.")

VALIDATION_UNAVAILABLE_NOTE = (
    "No sandbox validation result has been recorded for this attempt.")


def _empty_network() -> v1.NetworkEvidence:
    """The only network evidence this build can honestly produce."""
    return v1.NetworkEvidence(
        public_egress_policy="unavailable", enforcer=None, observer=None,
        started_at=None, ended_at=None, node_ids=[], interfaces=[],
        public_outbound_flows=None, external_ai_calls=None,
        blocked_attempts=None, trusted_lan_connections=None)


def _model_ref(raw: dict | None) -> v1.ModelRef | None:
    """A `ModelRef` only when every field it needs was actually recorded."""
    if not raw:
        return None
    digest = (raw.get("manifest_sha256") or "").lower()
    if not raw.get("model_id") or len(digest) != 64:
        # A model row without its manifest digest is not integrity evidence,
        # and a placeholder digest would look exactly like a real one.
        return None
    try:
        return v1.ModelRef(model_id=raw["model_id"], manifest_sha256=digest,
                           runtime=raw.get("runtime") or "ollama",
                           runtime_version=raw.get("runtime_version") or "unknown")
    except ValueError:
        return None


def _pod_evidence(validation: dict | None) -> v1.PodEvidence | None:
    """Pod facts, only from what the Kubernetes API returned."""
    if not validation:
        return None
    pod = validation.get("pod") or {}
    digest = (pod.get("image_digest") or "").lower()
    if not pod.get("pod_uid") or len(digest) != 64:
        # The API reported no container status yet, so there is no image
        # digest. Substituting the digest the manifest ASKED for would be
        # evidence of a request, not of an execution.
        return None
    observed = validation.get("finished_at") or validation.get("created_at")
    if not observed:
        return None
    try:
        return v1.PodEvidence(
            namespace=pod.get("namespace") or "aegisforge",
            pod_name=pod.get("pod_name") or "unknown",
            pod_uid=pod["pod_uid"], image_digest=digest,
            ready=bool(pod.get("ready")), restarts=int(pod.get("restarts") or 0),
            observed_at=observed)
    except ValueError:
        return None


def _citations(rows: list[dict]) -> list[v1.Citation]:
    found = []
    for row in rows:
        try:
            found.append(v1.Citation(
                citation_id=row["citation_id"], resource_id=row["resource_id"],
                page=int(row["page"]), quote=row["quote"]))
        except (KeyError, ValueError, TypeError):
            continue
    return found


def _artifact_refs(rows: list[dict]) -> list[v1.ResourceRef]:
    refs = []
    for row in rows:
        try:
            refs.append(v1.ResourceRef(
                resource_id=row["artifact_id"], sha256=row["sha256"],
                size_bytes=int(row["byte_size"]),
                media_type=row["media_type"]))
        except (KeyError, ValueError, TypeError):
            continue
    return refs


def attempt_proof(*, workspace_id: str, job_id: str, attempt: dict,
                  local_node_id: str, validation: dict | None,
                  artifacts: list[dict], citations: list[dict],
                  approval_id: str | None) -> dict:
    """One attempt's proof, plus the source label for each displayed value."""
    remote = attempt["node_id"] != local_node_id
    is_validation = bool(validation and validation["attempt_id"] == attempt["attempt_id"])

    # A validation attempt ran no model. Carrying the generation model here
    # would describe two different pieces of work as one.
    model = None if is_validation else _model_ref(attempt.get("model"))
    pod = _pod_evidence(validation) if is_validation else None

    if is_validation:
        state = "passed" if validation["passed"] else (
            "failed" if validation["observed"] else "unavailable")
        source = (f"{SOURCE_VALIDATION} {validation['result_sha256'][:16]}…"
                  if validation.get("result_sha256") else None)
        if state == "unavailable":
            source = None
    else:
        state, source = "unavailable", None

    record = v1.Proof(
        contract_version=v1.CONTRACT_VERSION,
        proof_id=attempt["attempt_id"], workspace_id=workspace_id,
        job_id=job_id, attempt_id=attempt["attempt_id"],
        node_id=attempt["node_id"], model=model, pod=pod,
        # Measured or missing. Never derived from timestamps that were not
        # recorded for this purpose.
        queue_ms=attempt.get("queue_ms"), runtime_ms=attempt.get("runtime_ms"),
        validation=state, validation_source=source,
        artifacts=_artifact_refs(artifacts), citations=_citations(citations),
        approval_id=approval_id, network=_empty_network(),
        recorded_at=attempt.get("finished_at") or attempt.get("created_at"))

    return {
        "proof": json.loads(record.model_dump_json()),
        "where": device.location_label(local=not remote),
        "sources": {
            "state": SOURCE_SQLITE,
            "route_reason": SOURCE_SQLITE,
            "queue_ms": SOURCE_SQLITE if attempt.get("queue_ms") is not None
                        else "unavailable — queue time was not recorded",
            "runtime_ms": SOURCE_SQLITE if attempt.get("runtime_ms") is not None
                          else "unavailable — runtime was not recorded",
            "model": SOURCE_CATALOGUE if model else (
                "not applicable — this attempt ran no model" if is_validation
                else "unavailable — no model manifest was recorded"),
            "pod": SOURCE_KUBERNETES if pod else (
                "unavailable — the Kubernetes API reported no container status"
                if is_validation else
                "not applicable — this attempt ran on the coordinator"),
            "validation": source or VALIDATION_UNAVAILABLE_NOTE,
            "artifacts": SOURCE_SQLITE,
            "citations": SOURCE_SQLITE,
            "approval": (SOURCE_SQLITE if approval_id else
                         "unavailable — no approval is bound to this attempt"),
            "network": NETWORK_UNAVAILABLE_NOTE,
        },
        "route_reason": attempt.get("route_reason"),
        "state": attempt.get("state"),
        "validation_detail": ({
            "command": validation["command"], "exit_status": validation["exit_status"],
            "tests_run": validation.get("tests_run"),
            "observed": validation["observed"], "passed": validation["passed"],
            "job_name": validation["job_name"], "job_uid": validation["job_uid"],
            "stdout": validation["stdout"][:4000],
            "stderr": validation["stderr"][:4000],
            "detail": validation["detail"],
        } if is_validation else None),
    }


def job_card(coordinator, job_id: str) -> dict | None:
    """Every material attempt of one job, aggregated into one card.

    Aggregation is display only: each attempt keeps its own `Proof` record, so
    a card never merges a Mac extraction and an Ubuntu validation into a single
    claim about "the job".
    """
    conn = coordinator.conn
    job = conn.execute(
        "SELECT * FROM jobs WHERE job_id=? AND workspace_id=?",
        (job_id, coordinator.workspace_id)).fetchone()
    if job is None:
        return None
    attempts = [{
        "attempt_id": row["attempt_id"], "step_id": row["step_id"],
        "node_id": row["node_id"], "state": row["state"],
        "route_reason": row["route_reason"],
        "model": json.loads(row["model_json"]) if row["model_json"] else None,
        "queue_ms": row["queue_ms"], "runtime_ms": row["runtime_ms"],
        "created_at": row["created_at"], "finished_at": row["finished_at"],
    } for row in conn.execute(
        "SELECT * FROM attempts WHERE job_id=? ORDER BY created_at, rowid",
        (job_id,))]

    validations = {row["attempt_id"]: db.validation_row(row)
                   for row in conn.execute(
                       "SELECT * FROM proposal_validations WHERE job_id=?",
                       (job_id,)) if row["attempt_id"]}
    artifacts = {}
    for row in conn.execute(
            "SELECT * FROM artifacts WHERE job_id=? AND workspace_id=?",
            (job_id, coordinator.workspace_id)):
        artifacts.setdefault(row["attempt_id"], []).append({
            "artifact_id": row["artifact_id"], "filename": row["filename"],
            "media_type": row["media_type"], "byte_size": row["byte_size"],
            "sha256": row["sha256"],
            "citations": json.loads(row["citations_json"] or "[]")})
    approvals = {}
    for row in conn.execute(
            "SELECT approval_id, attempt_id, decision FROM approvals"
            " WHERE workspace_id=? AND job_id=?",
            (coordinator.workspace_id, job_id)):
        approvals[row["attempt_id"]] = {"approval_id": row["approval_id"],
                                        "decision": row["decision"]}

    cards = []
    for attempt in attempts:
        own_artifacts = artifacts.get(attempt["attempt_id"], [])
        citations = []
        for artifact in own_artifacts:
            for citation in artifact["citations"]:
                if not citation.get("citation_id"):
                    continue
                citations.append({
                    "citation_id": citation["citation_id"],
                    "resource_id": citation.get("source_id"),
                    "page": citation.get("page"),
                    "quote": (citation.get("label") or "cited page")[:2048]})
        approval = approvals.get(attempt["attempt_id"]) or {}
        cards.append(attempt_proof(
            workspace_id=coordinator.workspace_id, job_id=job_id,
            attempt=attempt, local_node_id=coordinator.node_id,
            validation=validations.get(attempt["attempt_id"]),
            artifacts=own_artifacts, citations=citations,
            approval_id=approval.get("approval_id")))

    return {
        "job_id": job_id,
        "workflow_id": job["workflow_id"],
        "task_type": job["task_type"],
        "state": job["state"],
        "created_at": job["created_at"],
        "attempts": cards,
        # Stated once for the whole card, so no attempt row can imply it has
        # network evidence of its own.
        "network": NETWORK_UNAVAILABLE_NOTE,
        "evidence_note": (
            "Every value on this card was read from a record of something "
            "observed. Anything not observed is shown as unavailable rather "
            "than as zero, false or healthy."),
    }
