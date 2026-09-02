# Evaluation, Prototype Plan, and Demonstration

## Current status

The repository is in product-definition and prototype-planning state. It does
not currently contain a runtime source tree, model bundle, installer, or
executable proof. Every capability in this document is planned until observed
evidence changes its state.

## 1. Evidence labels

Use only:

- Planned: accepted requirement with no implementation evidence
- Prototyped: a narrow path ran but does not meet the full acceptance contract
- Verified: the documented check ran on the stated environment and passed
- Deferred: intentionally outside the current release
- Rejected: evaluated and intentionally not selected

Record the date, device, operating system, runtime, model revision, command or
procedure, input class, result, and known limitations. Another agent's summary,
a screenshot without provenance, or a static code inspection is not execution
evidence.

## 2. Five-day critical path

The purpose of the alpha is to answer the risks that could kill the product,
not to imitate every ChatGPT feature.

### Day 1: one Kubernetes worker spine

- Freeze the node, job, attempt, event, approval, HTTPS, Redis, and proof
  contracts.
- Pin K3s, Redis 7.2.x, base-image, worker-image, runtime, and model evidence.
- Start one single-node K3s cluster on Prachi's Ubuntu machine.
- Deploy Redis behind ClusterIP and the Docker-built worker behind a Kubernetes
  Service.
- Complete one real model response from a Ready worker Pod.
- Persist the job and attempt in coordinator SQLite and show it in the smallest
  local browser UI.

Exit evidence:

- model, image, K3s, Redis, and dependency source/licence/revision recorded;
- Pod, Service, runtime, and prompt are reproducible;
- no mocked inference in the claimed path.

### Day 2: Mac to Service to Redis to executor

- Connect worker API and executor Pods through Redis Streams.
- Add bounded retention, acknowledgement, pending-work recovery, cancellation,
  heartbeats, and leases.
- Authenticate the Mac coordinator to the worker Service over HTTPS.
- Route one real prompt through the Service and Redis to an executor Pod.
- Stream events back and show the request, model, Pod, queue, and routing reason.
- Complete the smallest guided preflight that selects the curated manifest,
  verifies dependencies, and runs the real self-test.
- Stop the cluster and prove the Mac's canonical SQLite history remains usable.

Exit evidence:

- reproducible Mac-to-Service-to-Redis-to-Pod-to-Mac path;
- bounded request and streamed response captured;
- Redis or cluster loss does not lose canonical history.

### Day 3: both signature workflows

- Complete the fixed Documents path from scan to page-linked extraction,
  grounded drafting, and validated Word artifact.
- Complete the fixed Code path from bounded repository context to patch.
- Run code validation as a restricted short-lived Kubernetes Job Pod.
- Preserve hashes, uncertainty, command output, exit status, and cleanup state.
- Use the same Service, Redis, event, and approval contracts for both paths.

Exit evidence:

- one openable cited Word artifact;
- one applicable patch with observed sandbox evidence;
- no direct canonical write from a worker or Job Pod.

### Day 4: concurrency, approval, and sovereignty

- Run Documents and Code attempts concurrently through separate Redis consumers
  and Pods.
- Enforce approval before canonical writes and make retries idempotent.
- Apply and verify default-deny Pod egress plus required cluster/LAN allowances.
- Produce Proof Cards from SQLite, Redis, Kubernetes, model, validation,
  integrity, approval, and network observations.
- Record sequential and concurrent timing honestly.

Exit evidence:

- both real artifacts complete concurrently;
- denial writes nothing and retry creates no duplicate final write;
- the real run records no observed public outbound flow in the named window.

### Day 5: sovereign proof and rehearsal

- Enforce or physically isolate public egress while preserving the trusted LAN.
- Run the real signature workflow.
- Capture trustworthy network, device, model, tool, integrity, and approval
  evidence.
- Exercise cancellation or one worker interruption.
- Exercise executor-Pod loss, Redis restart, and cluster loss.
- Complete third-party notices for selected components.
- Replace projected numbers with measured results.
- Rehearse and record a backup demonstration.

Exit evidence:

- reproducible offline run;
- per-job Proof Card;
- benchmark table and limitations;
- no unfinished feature presented as working.

If a gate passes early, begin the next gate. Only after Day 3 passes may the
team add the bounded image-understanding and calculation-with-steps stretch;
only after Day 4 passes may it add a second executor replica. Do not add another
framework, cluster, broker, runtime, or product surface.

## 3. Alpha acceptance

- [ ] The authoritative SIH26117 wording and IP/submission terms are retained.
- [ ] One installation creates a local workspace without a permanent role
      choice.
- [ ] Guided setup selects, installs or imports, verifies, and self-tests one
      real main engine.
- [ ] A real local chat completes.
- [ ] The pinned Docker worker image runs in a Ready Kubernetes-managed Pod.
- [ ] A Kubernetes Service exposes only the authenticated worker API to the
      trusted LAN; Redis remains cluster-internal.
- [ ] Redis dispatches one bounded attempt to an executor and reports queue,
      pending, acknowledgement, heartbeat, and cancellation state.
- [ ] One real prompt runs through the Kubernetes Service and streams back.
- [ ] The UI or logs show original request, device, model, route, and status.
- [ ] Stopping Redis or the cluster leaves canonical SQLite history intact.
- [ ] One bounded agent workflow produces a validated output.
- [ ] Consequential final write requires a recorded approval.
- [ ] Runtime endpoints and public-egress evidence are documented honestly.
- [ ] Repository instructions reproduce the claimed path.

## 4. Finals acceptance

- [ ] Chat, Documents, Code, and Control Center use one harness.
- [ ] The same installation works standalone and can use trusted workers.
- [ ] At least two task types route automatically.
- [ ] Documents and Code jobs run concurrently on different eligible nodes.
- [ ] OCR preserves source hash, page mapping, and uncertainty.
- [ ] Local retrieval returns page or section citations.
- [ ] The approval note opens as a valid Word artifact.
- [ ] Code execution uses a bounded network-disabled workspace.
- [ ] The patch, validation command, output, and exit status are returned.
- [ ] The coordinator performs no duplicate final write after retry.
- [ ] Pairing and revocation reject an invalidated worker.
- [ ] No external inference occurs during the offline evidence window.
- [ ] Installed models expose source, licence, revision, and integrity state.
- [ ] The Control Center distinguishes trusted LAN traffic from public egress.

## 5. Measurement plan

Initial targets are hypotheses:

| ID | Measure | Initial target |
|---|---|---:|
| M-01 | External inference calls in offline demo | 0 |
| M-02 | Corrupted file transfers accepted | 0 |
| M-03 | Real paired workers | At least 1 alpha, 2 where available for finals |
| M-04 | Concurrent independent workflow types | At least 2 for finals |
| M-05 | Routing accuracy on curated examples | At least 90% |
| M-06 | Worker-loss detection | Under 5 seconds |
| M-07 | Duplicate final writes after retry | 0 |
| M-08 | Distributed makespan improvement over sequential baseline | Positive and reported honestly |
| M-09 | Ready worker Pods behind the Service | At least 1 |
| M-10 | Canonical records lost after Redis restart | 0 |
| M-11 | Redis pending attempt reclaimed after executor loss | 1 fixed failure fixture succeeds |

Measurement rules:

- use the same task set for standalone and distributed comparison;
- record time to first output and end-to-end completion separately;
- report cold and warm behaviour separately;
- record queue time, RAM, VRAM, and temperature where reliable;
- score code, OCR, retrieval, and document quality separately;
- do not publish a universal AI accuracy number;
- do not claim energy, thermal, or cost improvement without comparable evidence;
- report a slower distributed result if that is what occurred.

## 6. Demonstration

### Preparation

1. Show the separate public distribution surface and release checksum only if
   they exist.
2. Show the pinned Docker image, Ready Pods, Kubernetes Services, Redis licence,
   installed model, and self-test state.
3. Confirm Redis has no LAN-exposed Service and the worker API requires the
   paired credential.
4. Disconnect or block public Internet while preserving the trusted LAN.
5. Start the evidence window.

### Standalone

1. Open the application in the local workspace.
2. Show Chat, Documents, Code, and Control Center.
3. Run the selected baseline task on this device.
4. Show the model, device, job events, and measured resource use.

### Trusted compute

1. Open Control Center and show paired devices and capabilities.
2. Start a scanned-report workflow.
3. Start a coding task while the document workflow runs.
4. Show the execution choices and automatic routing reasons.
5. Show streamed progress in the correct surfaces.
6. Open the generated cited document.
7. Inspect the returned code patch and validation.
8. Approve or deny the controlled final-write step.

### Sovereignty and resilience

1. Show the enforcing layer and network observation interval.
2. Show trusted LAN connections separately from public egress.
3. Open the job Proof Cards.
4. Disconnect one non-critical worker.
5. Show a safe requeue or recoverable failure without duplicate final output.

## 7. Sovereign Proof Card

Each demonstrated job records:

- workflow, job, step, and attempt IDs;
- original-request hash or approved reference;
- device identity, model manifest, and routing reason;
- tool and validation events;
- input and artifact hashes;
- approvals and final-write state;
- enforcement and observation method;
- public-egress and trusted-LAN observations;
- start/end times and evidence limitations.

It proves only the recorded job and observation window.

## 8. Parallel workstreams

The six useful workstreams are:

1. Frozen contracts, coordinator SQLite, routing, and integration
2. Docker worker, model runtime, Redis consumer, and SSE
3. K3s, Pods, Services, NetworkPolicies, and sandbox Jobs
4. Local browser UI, Control Center, and product acceptance
5. Documents/OCR/retrieval and Code/patch validation
6. Fixtures, contract checks, failure drills, proof, and demo

Assign one human owner per work packet and keep one integration owner. Multiple
AI agents may work on disjoint packets after the contracts freeze; they do not
share authority to change the seams. Do not create empty components merely to
give each member or agent a folder.

## 9. Major risks

| Risk | Response |
|---|---|
| Product becomes only a networking demo | Complete one real agentic artifact workflow |
| P0 scope expands again | Treat the PRD outcome table as the release boundary |
| Kubernetes consumes the sprint | Use one single-node K3s host; no Helm, operator, service mesh, HA, or multi-node cluster |
| Redis becomes a second database | Keep canonical state in SQLite; use expiring Redis coordination state only |
| Agent count creates incompatible implementations | Freeze contracts first, give each packet one human owner, and integrate twice daily |
| Worker Service exposes confidential traffic | Authenticated HTTPS only; Redis stays ClusterIP; verify NetworkPolicy and host firewall behaviour |
| Kubernetes Job is mistaken for a complete sandbox | Require observed non-root, seccomp, capability, path, resource, deadline, and egress checks |
| Setup forces unnecessary downloads | Resolve dependencies only for enabled capabilities |
| Main model is too weak | Benchmark the actual tasks before polishing UI |
| Cross-platform runtime differs | Prove one runtime path, add one fallback only for a measured blocker |
| Pairing becomes state migration | Keep pairing additive; defer coordinator transfer |
| Dashboard displays claims instead of evidence | Bind every status to an identified source and interval |
| Wi-Fi or worker fails in demo | Prefer wired links where available and record a backup run |
| Cold model loading erases concurrency benefit | Report cold/warm separately and preload only when disclosed |
| Confidential content leaks into logs | Metadata-only defaults and synthetic demo inputs |
| Open-source reuse creates licence risk | Record source, pin, licence, network behaviour, and local changes |
| Installer work consumes the prototype | Package only after the real harness path works |

## 10. Research gates

Research only questions that materially affect feasibility:

- official SIH26117 wording, evaluation expectations, and IP terms;
- one runtime across macOS, Windows, and Linux;
- main and specialist model correctness on the chosen demo inputs;
- RAM, VRAM, storage, cold-load time, and sustained thermals;
- pairing credential storage and encrypted LAN transport;
- platform sandbox behaviour;
- pinned K3s, Kubernetes workload, Docker image, and Redis 7.2.x compatibility
  and licences;
- Service exposure, Redis isolation, NetworkPolicy enforcement, and Pod
  security on Prachi's Ubuntu host;
- connected and air-gapped model installation;
- trustworthy public-egress enforcement and observation;
- dependency and model licences.

The user or requester independently verifies the final result before the project
claims completion.

## 11. Problem-statement coverage

The authoritative SIH26117 text is retained in [README.md](README.md) pending
[OD-01](prd.md#11-open-decisions). This table records which of its lines the
current scope answers, so that a deferral is a recorded decision rather than an
oversight. Status values follow the evidence labels in section 1.

### Expected Solution

| Problem-statement line | Scope | Status |
|---|---|---|
| Local deployment on a single workstation with a mid-range GPU | FR-001 | Planned |
| Model auto-selection across at least two task types | FR-006, AF-006 | Planned |
| Agentic task end to end: scanned report to Word approval note | FR-011, AF-008, AF-009 | Planned |
| Coding task run and verified in a sandbox | FR-012, AF-010, AF-011 | Planned |
| Multimodal task: image or scanned document understanding | FR-011 | Partial — OCR extraction is planned; no step yet exercises a vision model on an image |
| Logs or network monitor showing no external calls | FR-010, AF-015 | Planned |

### Description lines deferred beyond the alpha

Each of these is named in the problem statement and intentionally excluded from
the five-day sprint under
[deliberately excluded](../tasks.md#deliberately-excluded-from-the-sprint).
None is claimed as working.

| Problem-statement line | Decision |
|---|---|
| Engineering drawings, photographs, P&IDs | Deferred. Trained symbol detection needs annotated data the sprint does not have; the main engine's vision capability is an untested cheaper path |
| Handwritten notes | Deferred. Accuracy is uncertain and no fixture exists |
| Spreadsheet work and Excel output | Deferred until both signature workflows are stable |
| PowerPoint output | Deferred until both signature workflows are stable |
| Calculations with steps shown | Deferred. Closest cheap path is a computed value inside the approval note |
| Plan out multi-step work | Partial. Workflows are fixed contracts with one bounded repair attempt, not a general planner |
| Multiple open-weight models, addable without redesign | Answered by the manifest-driven catalogue gate on AF-001 |
| Grounding in manuals, SOPs, and correspondence | Answered by local retrieval in AF-009 |
| Multilingual industrial interaction | FR-019, P1 finals scope |

## 12. Mentor implementation-direction coverage

These are implementation requirements from the mentor, not claims from the
problem statement. They remain Planned until the named acceptance evidence is
observed.

| Mentor direction | Repository interpretation | Acceptance evidence | Status |
|---|---|---|---|
| Use Kubernetes and Docker | Docker builds pinned OCI worker/sandbox images; single-node K3s runs them | AF-002, AF-003: image digest plus Ready Deployment/Pod | Planned |
| Create Pods | Deployments own long-running API/executor Pods; Jobs create short-lived validation Pods | AF-002, AF-011: Pod readiness, limits, termination, and cleanup | Planned |
| Use Service API | Kubernetes Service provides a stable endpoint for the versioned FastAPI worker contract | AF-006: authenticated Mac-to-Service job completes | Planned |
| Use Redis | Redis Streams and expiring keys coordinate dispatch, leases, heartbeats, cache, cancellation, and events | AF-005: acknowledge, pending-work recovery, restart, and retention fixtures pass | Planned |
