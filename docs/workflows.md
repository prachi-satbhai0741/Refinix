# Workflows

## Status and purpose

This document owns onboarding, task surfaces, approval behaviour, and failure
flows within the scope set by [prd.md](prd.md). These are planned contracts, not
implemented behaviour.

## 1. Design rule

Chat, Documents, and Code are opinionated entry points into one agent harness.
They are not independent applications and do not maintain separate identity,
memory, security, job, or routing systems.

The user chooses two things independently:

| Choice | Options |
|---|---|
| Work surface | Chat, Documents, Code |
| Execution target | Auto, this device, trusted devices, or a specific paired node |

The Control Center manages the installation; it is not an agent profile.

## 2. First-run onboarding

### Step 1: establish the local installation

The app automatically:

- creates a local node identity;
- creates an empty local workspace;
- chooses the platform-native application-data location;
- starts only loopback-bound local services;
- detects hardware, storage, and supported existing runtimes.

There is no permanent Create Workspace, Join Workspace, Coordinator, Worker, or
Server choice.

### Step 2: choose the main engine

The user must choose one compatible main engine from a curated list. The
default picker presents:

- Recommended: best measured fit for this device;
- Fast: lower resource use;
- Quality: higher resource use where supported;
- Advanced: exact approved model and runtime.

The picker must show:

- source and licence;
- model/version identifier;
- download and installed size;
- quantisation;
- expected RAM and VRAM;
- supported runtime and operating systems;
- measured, reported, or unverified evidence status.

Marketing labels such as fast or quality are guidance, not guarantees.

### Step 3: enable capabilities

Chat is part of the interactive baseline. The user may enable:

- Documents;
- Code;
- semantic local knowledge;
- later optional packs such as voice.

Enabling a capability creates a required dependency plan. The user cannot skip
a dependency and still receive an enabled status. A separate model is not
downloaded when an already installed compatible model satisfies the profile.

### Step 4: review and install

Before any networked installation, show:

- every model and runtime action;
- total download and storage requirement;
- source, licence, version, and checksum availability;
- permissions and data locations;
- which features remain unavailable if installation fails.

The user explicitly confirms the plan. There are no silent downloads.

Connected setup may use an approved runtime or model source. Air-gapped setup
imports a verified bundle from removable media or an internal server. Both
paths produce the same local manifest.

### Step 5: self-test

Onboarding completes only after:

- the main engine answers a real local test prompt;
- runtime endpoints are confirmed loopback-only;
- installed manifests and hashes are recorded;
- each enabled capability runs its smallest representative test;
- failures are reported as unavailable or unverified rather than hidden.

The user may revisit model and capability setup from the Control Center without
resetting the workspace.

## 3. Agent profiles

An agent profile combines:

- one compatible model reference;
- profile instructions;
- allowed tools;
- workflow contract;
- action and approval policy;
- output validator.

Initial profiles:

| Profile | Tools | Validator |
|---|---|---|
| General Chat | Local retrieval and approved read-only tools | Response and citation checks where applicable |
| Document Agent | OCR/vision, retrieval, structured extraction, document generation | Page mapping, uncertainty, citations, artifact integrity |
| Coding Agent | Approved repository reads, bounded file search, isolated execution | Patch applicability, approved paths, command output, exit status |

Multiple profiles may share one model. Models do not gain direct access to
files, tools, or other models; the harness grants each bounded action.

## 4. Chat workflow

1. The user starts or opens a chat.
2. The harness preserves the original request.
3. The context manager selects recent context, curated memory, and relevant
   local knowledge within the model limit.
4. The router selects an eligible model and device.
5. The model streams output and visible tool events.
6. Citations and tool results are validated where used.
7. The coordinator records the response and proof metadata.

Chat remains usable on this device when no paired compute is available.

## 5. Documents workflow

The first fixed document workflow is
inspection_report_to_approval_note:

1. The user selects a scan and optional local SOP corpus.
2. The coordinator records source hashes and creates the workflow.
3. OCR or vision extracts content with page association and uncertainty.
4. A validator rejects fabricated values and preserves unresolved fields.
5. Local retrieval selects relevant SOP passages with page or section metadata.
6. The main engine receives only the validated extraction and retrieved
   passages required to draft the note.
7. The document generator produces a Word artifact.
8. Artifact validation records readability, citations, origin job, and checksum.
9. The user reviews the draft before any consequential export or final write.

Each step may run on a different eligible node. The coordinator passes typed,
validated output between steps; models do not communicate directly or share
unrestricted memory.

## 6. Code workflow

The first fixed code workflow is repository_request_to_validated_patch:

1. The user selects an approved repository or folder and describes the change.
2. The coordinator identifies the minimum relevant file set.
3. It creates an isolated temporary workspace.
4. Required files are copied or transmitted with hashes.
5. The coding agent prepares a patch inside the temporary workspace.
6. Approved validation runs with networking disabled and resource limits.
7. The worker returns the patch, command, stdout, stderr, exit status, and
   artifact hashes.
8. The coordinator verifies target paths and patch applicability.
9. The user inspects the diff and approves or denies the canonical write.
10. An approved final write occurs exactly once.

The entire repository is not transferred for every task. Workers never write
directly to the canonical repository.

## 7. Action and approval policy

The prototype uses one safe default policy:

| Action | Behaviour |
|---|---|
| Read explicitly selected files | Automatic |
| OCR, retrieval, analysis, and draft generation | Automatic |
| Write inside the assigned temporary workspace | Automatic |
| Network-disabled sandbox validation | Automatic |
| Modify canonical files or persistent organisational data | Approval required |
| Export or publish outside the workspace | Approval required |
| Enable network access, pair/revoke devices, or install models | Approval required |
| Access unselected paths, host secrets, or unrestricted execution | Denied |
| Contact a public AI service during offline runtime | Denied |

Approval is enforced by the coordinator and records the action, target,
workflow/job/attempt, decision, actor, and timestamp. A denial does not become a
generic failure; it ends or replans the affected step clearly.

Configurable Autonomous, Controlled, and Approval presets are P1 or later. They
must remain presets over explicit action rules, never broad switches that bypass
the policy boundary.

## 8. Connecting compute

Pairing is available from Control Center at any time:

1. One installation invites another with a short-lived code or QR value.
2. Both sides show workspace and device identity.
3. A user explicitly confirms the relationship.
4. The node receives a unique revocable credential.
5. It advertises verified hardware, runtime, model, health, and capability data.
6. The coordinator may route bounded jobs while trust remains active.

The receiving installation keeps its local workspace unchanged. Disconnecting
stops new remote work; revocation invalidates the credential. Neither action
deletes or merges local user data.

Automatic LAN discovery may help find a candidate device but never establishes
trust or exposes a model runtime directly.

## 9. Execution choice

Every task starts with Auto by default:

- Auto selects an eligible device through deterministic routing.
- This device prevents remote execution.
- Trusted devices allows any compatible paired node.
- A specific target pins the task when compatible.

If a selected target is unavailable or incompatible, the app explains why and
offers a compatible alternative. It does not silently send the task elsewhere.

## 10. Control Center

The Control Center presents:

- local hardware, runtime, model, and storage status;
- enabled agent profiles and self-test state;
- active, queued, awaiting-approval, failed, and completed jobs;
- paired devices, capabilities, heartbeat, and revocation;
- resource usage where the operating system reports it reliably;
- connected-setup versus offline-runtime state;
- trusted LAN traffic and observed or blocked public egress;
- audit events, proof cards, retention, cleanup, and export controls.

It consumes the harness event stream and worker health reports. It must not use
hard-coded healthy, secure, blocked, or zero-traffic values.

## 11. Failure behaviour

### Model installation fails

The capability remains unavailable. Existing installed capabilities and local
workspace state remain usable.

### Worker disconnects

The attempt becomes interrupted. The coordinator either requeues on another
compatible node with a new attempt identifier or returns a recoverable failure.
It never repeats a canonical final write.

### Approval expires or is denied

The affected action does not run. The job remains inspectable and may be
cancelled or replanned within the same authority.

### Validation fails

The result is not promoted to a final artifact or canonical write. The app shows
the command, failure, and bounded retry options.

### Offline evidence is unavailable

The app reports evidence unavailable or observation-only. It never replaces
missing enforcement evidence with a green sovereignty claim.
