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

### Day 1: baseline and one local engine

- Freeze the P0 outcomes and authoritative problem-statement copy.
- Select the smallest service/UI boundary and one runtime candidate.
- Define the node, model-manifest, job, event, and proof contracts.
- Complete one real local main-engine inference on the primary machine.
- Record cold/warm latency and memory.

Exit evidence:

- model source/licence/revision recorded;
- local runtime and prompt are reproducible;
- no mocked inference in the claimed path.

### Day 2: one real paired-worker path

- Start the harness on the primary workspace device.
- Start the same worker service on one Windows device.
- Add a clearly labelled prototype pairing flow.
- Report heartbeat, capabilities, model, and health.
- Route one real prompt and stream output back.
- Show original request, selected device/model, and routing reason.

Exit evidence:

- reproducible prompt-to-worker-to-coordinator path;
- bounded request and streamed response captured;
- disconnect leaves the local workspace usable.

### Day 3: onboarding and policy

- Turn the proven runtime path into guided main-engine setup.
- Add one curated manifest and integrity check.
- Add enabled-capability dependency resolution.
- Add the fixed action matrix and awaiting-approval state.
- Show real health, model, and job events in the Control Center.

Exit evidence:

- clean installation or reset reaches a real self-test;
- required dependencies cannot be reported enabled when missing;
- canonical final write remains approval-gated.

### Day 4: signature workflows

- Complete the fixed Documents pipeline.
- Complete the fixed Code pipeline.
- Preserve OCR page mapping and uncertainty.
- Generate the cited Word artifact.
- Validate the code patch in an isolated network-disabled workspace.
- Run independent tasks concurrently where hardware permits.

Exit evidence:

- real artifacts from both workflows;
- validation evidence for each;
- sequential and concurrent timings on the same task set.

### Day 5: sovereign proof and rehearsal

- Enforce or physically isolate public egress while preserving the trusted LAN.
- Run the real signature workflow.
- Capture trustworthy network, device, model, tool, integrity, and approval
  evidence.
- Exercise cancellation or one worker interruption.
- Complete third-party notices for selected components.
- Replace projected numbers with measured results.
- Rehearse and record a backup demonstration.

Exit evidence:

- reproducible offline run;
- per-job Proof Card;
- benchmark table and limitations;
- no unfinished feature presented as working.

### Day 6: buffer if available

Only fix demo-breaking defects, improve reproduction, and rehearse. Do not add a
new framework, workflow, model, runtime, or product surface.

## 3. Alpha acceptance

- [ ] The authoritative SIH26117 wording and IP/submission terms are retained.
- [ ] One installation creates a local workspace without a permanent role
      choice.
- [ ] Guided setup selects, installs or imports, verifies, and self-tests one
      real main engine.
- [ ] A real local chat completes.
- [ ] A second installation pairs explicitly and reports capabilities.
- [ ] One real prompt runs on the paired worker and streams back.
- [ ] The UI or logs show original request, device, model, route, and status.
- [ ] Disconnecting the worker leaves both local workspaces intact.
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
2. Show completed local setup, installed models, licences, and self-test state.
3. Disconnect or block public Internet while preserving the trusted LAN.
4. Start the evidence window.

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

1. Harness, state, and job lifecycle
2. Worker, runtime, pairing, and streaming
3. Onboarding, task surfaces, and Control Center
4. Documents, OCR, retrieval, and artifact validation
5. Code context, sandbox, patch, and validation
6. Security evidence, model provenance, integration, and demo

Assign owners by capability and keep one integration owner. Do not create empty
components merely to give each member a folder.

## 9. Major risks

| Risk | Response |
|---|---|
| Product becomes only a networking demo | Complete one real agentic artifact workflow |
| P0 scope expands again | Treat the PRD outcome table as the release boundary |
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
- connected and air-gapped model installation;
- trustworthy public-egress enforcement and observation;
- dependency and model licences.

The user or requester independently verifies the final result before the project
claims completion.
