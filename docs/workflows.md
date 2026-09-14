# Workflows

## Status and purpose

This document owns onboarding, task surfaces, approval behaviour, and failure
flows within [prd.md](prd.md). These are target contracts. Existing implementations
and remaining gaps are distinguished in [evaluation.md](evaluation.md#current-status);
this document does not certify current runtime behaviour.

## 1. Design rule

Preserve the current Chat surface (including document and image work), IDE-style
Code surface, Settings and right-hand job status card. Documents is a workflow,
not a required separate top-level screen. All use the same harness, identity,
context, policy and job contracts.

The user chooses two things independently:

| Choice | Options |
|---|---|
| Work surface | Chat (including documents/images), Code |
| Execution target | Auto, this device, trusted devices, or a specific paired node |

Control Center means installation and job controls exposed through Settings and
status UI; it does not require a new main navigation surface.

## 2. First-run onboarding

### Step 1: establish the local installation

The website offers OS/architecture-specific installers. Installation and setup
package or graphically provision all qualified application dependencies, with no
terminal, Python, container or certificate setup expected from an ordinary user.
Explain any unavoidable OS approval or unsupported driver/sandbox prerequisite.
Do not report an unsupported environment ready. The app automatically:

- creates a local node identity;
- creates an empty local workspace;
- chooses the platform-native application-data location;
- starts only loopback-bound local services;
- detects hardware, storage, and supported existing runtimes.

There is no permanent Create Workspace, Join Workspace, Coordinator, Worker, or
Server choice.

### Step 2: choose the main engine

For local execution, recommend up to six compatible models, highest suitability
score first, followed by **Show more**. Let the user choose another supported
model or advanced import; recommendations are not mandatory selections. A
remote-only client can connect to authorised compute without a local model.

Use the [scoring contract](model-catalog.md#6-onboarding-selection): suitability
is out of 100, with clearly labelled estimates and measurements. Never present
a fit score as universal accuracy or a percentage probability of correctness.
Warn about slow or memory-heavy choices and block known incompatible execution.

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

- each configured local engine answers a real local test prompt; a remote-only
  setup proves its authorised remote path and labels local inference unavailable;
- runtime endpoints are confirmed loopback-only;
- installed manifests and hashes are recorded;
- each enabled capability runs its smallest representative test;
- failures are reported as unavailable or unverified rather than hidden.

The user may revisit model and capability setup from the Control Center without
resetting the workspace.

### Updates after installation

Settings provides **Check for updates → Download → Install and restart**, plus
**Import update** for a verified offline package. Show installed/available versions,
release notes, download size and progress, and the last successful check. Being
offline means availability is unknown, not that this version is current. There
are no automatic startup, background or reconnection checks.

A brief connection can fetch metadata or make download progress; it need not
finish a large package. Preserve the working installation until the complete
package is authenticated. Explain active-job handling before restart, preserve
user data and show a recoverable failure if installation/migration cannot finish.
Receiving peers pause new admission and reconcile active work before updating.
Full behaviour and publication gates belong in [releases.md](releases.md).

### Personal context and knowledge

Settings lets the user inspect, edit and delete durable instructions/memory and
manage selected corpus sources, indexing status and citations. Explain whether a
change affects preferences, retrieved knowledge or an optional trained adapter.
Do not ingest the device's files or save raw conversations as permanent memory
by default. A user correction does not automatically start training.

The [.refinix profile and installed data layout](architecture.md#5-local-application-data)
remain separate from replaceable application files. Context selection is bounded;
trimming a request to fit the model does not delete the conversation history.

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

Chat continues locally when a suitable local model is installed. A remote-only
client retains history and explains that execution needs an available trusted target.

## 5. Documents workflow

Current source includes document parsing, FTS5 retrieval, scan/image paths and
artifact generation. Platform-specific dependencies and model compatibility still
need device qualification; see [the source snapshot](evaluation.md#current-status).
Semantic retrieval and arbitrary peer placement are target additions.

The first fixed document workflow is
inspection_report_to_approval_note:

1. The user selects a scan and optional local SOP corpus.
2. The coordinator records source hashes and creates the workflow.
3. OCR or vision extracts content with page association and uncertainty.
4. Extraction checks flag unsupported or inconsistent values and preserve unresolved
   fields; they cannot guarantee detection of every fabricated value.
5. Local retrieval selects relevant SOP passages with page or section metadata.
6. The main engine receives only the validated extraction and retrieved
   passages required to draft the note.
7. The document generator produces a Word artifact.
8. Artifact validation records readability, citations, origin job, and checksum.
9. The user reviews the draft before any consequential export or final write.

Prefer co-locating the workflow on one eligible node; move bounded steps only when
capability, performance or data policy justifies it. The coordinator passes typed,
validated output; models do not share unrestricted memory. Corpus permissions
apply before retrieval, and citations retain source/version/page references.

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

Current source also has an explicitly selected local Apply path with verified
backups and Undo, labelled “Not sandbox tested — local device mode”. Preserve
that distinction and its approval/backup safeguards; do not present it as sandbox
validation or silently change its behaviour during a runtime migration. The
validated workflow above has a separate, observed sandbox result.

## 7. Action and approval policy

The following target policy must be enforced at both coordinator and execution agent.
Current Code permissions live in `backend/coordinator/policy.py`; preserve its
bounded access modes and canonical-write checks while expanding capabilities.
Sandbox support must be positively qualified on each execution profile.

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

Preserve existing access modes as explicit action rules. A user-granted scope can
cover repeated routine reads and drafts without repeated prompts. Code that modifies
canonical files still needs the applicable approval. Verification also covers
Chat, OCR, retrieval and documents: user approval and quality testing are different
requirements, and successful parsing does not prove factual correctness.

## 8. Connecting compute

Settings → Connect opens the local-network device view:

1. Show discoverable Refinix devices, availability and compatible capabilities.
   A radar animation represents reachable peers, not measured physical distance.
2. Use a guided address/pairing-code fallback when automatic discovery is blocked.
3. Both devices show identity and explicitly confirm a scoped relationship.
4. Issue unique revocable credentials through standard secure pairing; users do
   not copy certificate fingerprints or run terminal commands for normal setup.
5. The receiver enables sharing and chooses permitted workloads/resource limits.
6. Advertise current model availability, capacity and health only to trusted peers.
7. When a remote task starts, show “Device X is executing a Code task on your
   device”, its resource use and a stop control. Do not expose the full prompt
   in a notification by default.

Personal use requires device-owner consent, not a mandatory administrator.
Organisation mode adds administrator policy for membership, users, quotas and
eligible compute. Compute permission and corpus access are separate permissions.
Pairing does not merge chats or give access to arbitrary files. Pause sharing
stops new admissions and makes the disposition of running jobs explicit;
revocation prevents further access and cancels/reconciles affected attempts.
Disconnecting or revoking does not delete the local workspace.

The inference runtime remains on loopback; peers use only the authenticated
application API. All discovery and execution work without a public Internet route.

## 9. Execution choice

Every task starts with Auto by default:

- Auto selects an eligible model/device pair, considering task quality, loaded
  models, queue, transfer/loading time, resource reservations and data policy.
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
- optional CPU/GPU utilisation, RAM/VRAM, battery and temperature in the lower-right
  status area where reported reliably; missing sensors read unavailable, not zero;
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

The attempt becomes interrupted. Reconcile its receipt and side effects before
retrying; a lost response does not prove work never ran. Safely repeatable work
may get a new attempt on a compatible authorised target. Otherwise show an
inspectable recoverable failure. Never silently move pinned/private work or
repeat a canonical final write.

### Approval expires or is denied

The affected action does not run. The job remains inspectable and may be
cancelled or replanned within the same authority.

### Validation fails

The result is not promoted to a final artifact or canonical write. The app shows
the command, failure, and bounded retry options.

### Offline evidence is unavailable

The app reports evidence unavailable or observation-only. It never replaces
missing enforcement evidence with a green sovereignty claim.
