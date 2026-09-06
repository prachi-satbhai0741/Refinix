# AegisForge Execution Roadmap

Status: active execution board; tasks advance only with recorded evidence.

The alpha implementation deliberately attempts every P0 outcome plus the signature
workflow and concurrency outcomes currently labelled P1 in the PRD. This is an
aggressive execution target, not a silent change to PRD priority labels.

This file turns the [PRD](docs/prd.md) into an execution order. Product and
security requirements remain owned by the focused documents in
[docs/README.md](docs/README.md); this file owns execution chunks, named human
checkpoints, and integration gates.

## Mission

Win the internal selection with one real sovereign agent application that:

- runs useful work on one device;
- automatically routes complete task steps to trusted local workers;
- runs Documents and Code work concurrently where hardware permits;
- returns a cited Word artifact and a sandbox-validated code patch;
- keeps canonical state, approval, and final writes on the coordinator; and
- proves public egress was blocked or independently observed during the demo.

Distribution means task-level orchestration, not model sharding or combined
VRAM. No mocked inference, routing, sandbox, artifact, or network evidence may
be presented as real.

## Product acceptance

The candidate is not judged by file count, agent count, or Kubernetes objects:

- **Usable:** a new operator can open the local UI, submit a real job, follow
  progress, cancel it, and retrieve the result without a developer editing
  state by hand.
- **Viable:** one MRPL-relevant scanned-report workflow produces a grounded,
  cited, openable approval note; the infrastructure is in service of this
  outcome rather than the whole demonstration.
- **Presentable:** the team can show Docker image provenance, Ready Pods,
  Services, Redis queue state, deterministic routing, approval, failure
  recovery, and scoped offline evidence in one coherent story.

The critical path uses **two devices: the macOS coordinator and Ubuntu worker**.
OCR is part of the C08 Documents workflow on this configuration. Additional
machines stay off the critical path and are added only for a measured need
with a new device-based setup checkpoint; they remain available to build any
module. Multilingual support, voice, scaling, and visual polish remain deferred. If the
complete frozen path does not pass three consecutive rehearsals, it is not the
candidate regardless of how many individual components work.

## Operating contract

Claude builds; Codex reviews the current combined source and observed results.
Anyone may implement any AF task. No agent needs a person's identity to edit
code, and no person has exclusive ownership of a module. The board below
identifies human actions by **device role** — `macOS coordinator`, `Ubuntu
worker` — or by **requester** for acceptance, never by team member.

- **Execution order and authorisation scope are separate concerns.** Work
  follows the [grouped execution plan](#grouped-execution-plan): independent
  preparation and implementation may overlap, while dependent device actions
  and acceptance gates stay ordered. Authorisation may cover a single chunk or
  a **named range**. Authorising C03 does not authorise C04 unless the range says so.
- Within an authorised scope, resolve routine implementation questions from
  repository evidence, the established requirements and authoritative upstream
  documentation. **Those questions are not human checkpoints** and must not be
  relayed as ones. The scope covers implementation, review fixes and
  proportionate offline checks using existing dependencies and isolated test
  data.
- Stop execution for exactly three things: an essential input or decision only
  the requester can supply; **missing authorisation**; or a required device
  action or acceptance check — a download, installation, host command, pairing,
  physical operation, artifact inspection, or Git publication. **Repository
  evidence can answer a technical question; it can never grant permission.**
  Never bypass an uncleared gate by advancing another chunk. A newly discovered
  human dependency splits the chunk at that point.
- Prepare the exact action and obtain Codex's review before the human performs
  it. Whoever operates the named device returns the evidence to the requester;
  verify the result before resuming. A message saying "done" alone does not
  prove a runtime gate.
- Continue only within the authorised scope after the checkpoint is cleared.
  This board is not permission to execute an unauthorised chunk. Documentation
  approval does not start runtime implementation or authorise terminal setup.
- Inputs the requester supplies in advance through the
  [handover pack](docs/handover-pack.md) remove the *question*, never the
  *gate*. A supplied fixture still needs its acceptance check; a stated
  constraint still needs the device action it describes.
- A checkpoint belongs to a device, not a person. Anyone with access to that
  device may perform it. Change the target device in the handoff rather than
  reassigning a person; never silently operate another device.
- Keep the shared contract, coordinator authority and task acceptance gates. No
  alternate job schema, authentication scheme, Redis namespace or manifest set.
- Tests and machine operations retain the permissions in [AGENTS.md](AGENTS.md).
  Reuse applicable permissions already granted; do not transfer permission from
  one device or session to another. Missing permission is a checkpoint.
- Humans publish through [member branch -> dev -> main](CONTRIBUTING.md#the-one-rule).
  Integrate reviewed work when its acceptance and human checkpoints are clear.
  Agents do not publish without authorisation.

Task states remain `planned`, `in-progress`, `review`, `verified`, or `blocked`.
A human dependency records `blocked` plus the exact required action, not a code
failure. Only observed acceptance and requester verification justify `verified`.
The chunk map does not change the AF task states recorded below.

## Human checkpoint handoff

Every stop must contain all of the following in the conversation, ready for the
requester to relay to whoever operates the device. Do not create personal task
documents.

1. **Which device and where:** the device role — `macOS coordinator` or
   `Ubuntu worker` in the first configuration — plus its OS, architecture,
   shell and actual working directory. Identify the device, not a team member.
   Optional machines are identified the same way and stay off the critical
   path until a measured need selects one.
2. **Action and reason:** the exact decision, UI steps or copy-paste commands,
   what they change, and why the current chunk cannot proceed without them.
3. **Setup details:** for downloads/installations, approved source link,
   version/revision, licence, expected integrity value and verification command,
   download/disk requirements and destination. For deployment, pin the actual
   image digest. Give required privileges and rollback/cleanup where applicable.
4. **Return evidence:** exact output, installed path/version/hash or artifact
   observation needed, plus what success and failure look like. Exclude secrets,
   personal documents, credentials and unnecessary machine identifiers.
5. **Resume condition:** the focused check agents will perform with permission,
   remaining human acceptance and the next eligible chunk. Do not unlock later
   work from an unverified setup claim.

Unknown versions, unavailable artifacts or an unmade policy choice are reasons
for a decision checkpoint, not placeholder commands for someone to execute.
Prepare future commands against the actual implementation and current device
inventory. Do not distribute speculative installs now. The C01 read-only
[inventory commands](docs/devicespecifications.md#checkpoint-c01-read-only-inventory)
have been run and returned for all six devices; the C02 follow-up commands are
also read-only and must report missing tooling rather than install it.

## Desktop executions (separate from C01–C13)

A parallel track, numbered on its own. It does not consume, reorder or complete
any numbered chunk, and **C05 stays exactly where it is**: partially executed,
Ubuntu host powered down, pending review.

**Execution 1 — Refinix desktop foundation (review fixes verified, macOS
bundle built/opened and requester smoke test accepted 2026-09-04).** A native desktop shell around the
existing coordinator, in [`desktop/`](desktop/README.md). Product decisions this
execution settles, which change what earlier documents describe:

| Decision | What changed |
|---|---|
| Product name | Visible branding is **Refinix**. `~/.aegisforge`, the `X-AegisForge-Contract` header, the `AegisForgeCoordinator` server token and worker identifiers are compatibility-sensitive and unchanged. |
| Top-level navigation | **Chat \| Code**. Documents is no longer a top-level surface; document work becomes a selectable skill inside Chat. |
| Control Center | Renamed **Settings** and moved to secondary navigation. Its technical tables became interactive cards; the readouts moved under **Advanced**. |
| Attachments | Chat accepts files. Execution 1 stores and lists them; **nothing reads them**, and the interface says so on the request and in the export. |
| Access modes | The Code access selector is **not** rendered. The three modes are described as planned. A control implying enforcement is not added before the enforcement exists. |
| Ordinary Chat | Needs the model runtime only. Docker is never started, and an offline Ubuntu worker does not block local Chat or cause a replacement cluster on the Mac. |
| Cancellation | `/v1/cancel` now aborts a stalled model stream instead of waiting out the request timeout. |

**Observed macOS setup:** after explicit approval, installed 20 hash-verified
artifacts into `desktop/.venv` using existing CPython 3.12.13, built
`desktop/dist/Refinix.app`, verified its ad-hoc signature and opened its native
window. A copied bundle also started with repository and Homebrew Python reads
denied. Existing-instance relaunch worked after a port fallback. The correction
pass ran 161 Python checks and 8 Node checks, then all 7 final lifecycle
regressions after the native Quit repair. See the
[observed verification](desktop/README.md#observed-verification) and opening steps.
The requester subsequently confirmed starting Chat, stopping it, quitting with
Command-Q and seeing the stopped conversation after reopening, then supplied a
generated Kubernetes explanation from a follow-up request. These are requester
observations; no native screenshot was captured by the reviewer. Windows and
Ubuntu packaging/launchers and native acceptance remain unfinished. C05 stays paused.

**Execution 2 — repository editing, access-mode enforcement and the Reasoning
switch (implemented and Codex-reviewed 2026-09-05; requester acceptance
pending).** Three deliverables:

| Decision | What changed |
|---|---|
| Code surface | Connect one folder through the **native folder dialog**, select bounded UTF-8 text files, describe an edit, review a unified diff, apply. Existing-file replacement only. Creating, deleting and renaming files, project commands, Git, installs and network enablement are **denied in every mode**, Full included. |
| Access modes | **Partial / Full / Ask before actions**, enforced by one pure function in `backend/coordinator/policy.py` that every repository operation passes through. A Full-access write is recorded as `allowed_automatically` with the mode that allowed it, never as a human approval nobody gave. |
| Filesystem boundary | Descriptor-relative, no-follow traversal; identity verified again immediately before the write; same-directory temporary file replaced atomically with the original permission bits preserved. Short reads and short writes are looped to completion, and a stalled write leaves the original untouched. Where an OS cannot provide `dir_fd`, **the whole Code surface** is disabled and reported — reading included — rather than run on a weaker guarantee. |
| Review completeness | The diff is never truncated. Apply writes exactly what the diff showed, or the proposal is refused, so a person can never authorise bytes they were not shown. |
| Reasoning | Per-model **On/Off** in the composer's model pill, off by default, stored by the coordinator and snapshotted per attempt. Sets Ollama's top-level `think`; no Qwen `/think` prompt suffix. Reasoning text is never saved, searched or exported. |
| Blank conversation pane | Repaired at its root cause: the thread is no longer cleared before the replacement is built, one message's formatter failure falls back to literal text, optional fields parse defensively, and a load generation token rejects a stale result even for the **same** chat. |

**Codex review 2026-09-04 returned NEEDS FIX with seven findings; all seven are
corrected and covered by regressions** — Ask-mode listing was unusable, a
selection could survive a project switch, a late file list could land under
another project, a short write could truncate a file, a truncated diff could
authorise unseen bytes, the unsupported-platform note contradicted the code,
and the policy matrix disagreed with the audit. Reading files and sending them
to the model are now one action, `repo.read_and_propose`, so the matrix, the
approval and the recorded outcome say the same thing.

**Not part of Execution 2, and not claimed:** no sandboxed execution, no worker
dispatch, and no claim about the 4B model's coding quality.
The packaged app still carries the Execution 1 build until it is rebuilt.

**Execution 3 — document understanding, retrieval and generation (implemented
and Codex-reviewed in source 2026-09-05; requester acceptance pending).**
Document work stays a selectable skill inside Chat; there is no new top-level
page and the navigation is still Chat | Code with Settings secondary.

| Decision | What changed |
|---|---|
| Reading | `.txt`, `.md`, `.csv`, `.json` and **`.docx`** are read with the standard library — a `.docx` is a ZIP of OOXML. Pages stay separate, the digest recorded at intake is re-verified before parsing, and a page count Word did not write stays **missing** rather than becoming 1. |
| PDF and OCR | **Unavailable and reported so.** No PDF parser and no OCR engine are installed, and the standard library has neither. The capability probe names the missing prerequisite; nothing invents text for a scan, and text extraction is never called OCR. |
| Retrieval | Keyword search over SQLite FTS5, scoped to the request's own sources, bounded, round-robin across sources so one document cannot flood the context, deterministic ordering. **Labelled keyword search, not semantic** — OD-07 is unresolved and no embedding model is provisioned. |
| Citations | Every citation is re-checked against the selected sources and their real pages before it is shown. One that does not resolve becomes a visible unresolved item, never a rendered reference. |
| Generation | `inspection_report_to_approval_note` writes a **real `.docx`** with `zipfile` and OOXML, reopens it to check its structure, and records filename, media type, size, SHA-256, workflow, job, attempt and validation result. No renamed HTML or text. |
| Artifacts | Kept in `~/.aegisforge/artifacts/`, written atomically, never overwriting. Copying one out needs a **recorded one-shot approval bound to its digest**. |
| Attachments | Plain Chat still reads nothing. A supported document skill reads **only the files sent with its own request**. The skill is stored on the job, so a reopened conversation and an export both say which skill read which files. |
| Context indicator | A compact `Context ≈ 3.2k / 5.2k` pill in the Chat composer, fed by `/v1/context`, which calls `context.py` — the same estimator the request uses. No second counter in JavaScript. It warns before turns are omitted and says they stay saved. |
| Code composer | The three permanent dashboard panels are **gone**. Access is a pill in the composer using Codex-style labels over the unchanged backend ids (`ask` → Ask for approval, `partial` → Approve for me, `full` → Full access); proposals and complete diffs arrive as chronological results; approvals appear inline; the audit sits under Details. A `Choose project` row sits above the prompt and uses the native folder dialog. |
| Prompt boxes | Both composers start at one line, grow, cap, scroll inside themselves and shrink again. |

**Combined Codex review passed for source and offline checks on 2026-09-05.**
The repaired tree passed 288 coordinator tests, 60 browser-side tests, 17
packaging checks, Python/JavaScript syntax checks and `git diff --check`. The
review also closed four low-severity security findings plus five local
defence/privacy defects. OCR quality, model output quality, whether a generated
`.docx` opens in Word, packaged-app behaviour and requester acceptance remain
unverified. **C08, AF-008 and AF-009 are not marked verified**, and the
distributed Documents workflow remains later work. `desktop/dist/Refinix.app`
still contains the Execution 1 build: E2 and E3 require a rebuild before native
acceptance.

## Numbered execution tasks

The **thirteen numbered tasks** below define execution order. Building an image
and reporting its digest must precede reviewing and applying the pinned cluster
deployment. More human dependencies create additional stops; an already
satisfied setup action needs evidence, not a repeated installation.

Execute C01 → C02 → C03 → C04 → C05 → C06 → C07 → C08 → C09 → C10 → C11 →
C12 → C13. The **After** column means the previous task's reviewed work, human
checkpoint and return-evidence checks are all clear. At **Wait**, pause until
the named device returns the required evidence. Do not skip ahead while waiting.
Progress depends on these conditions. The internal demonstration target is
**8–9 September 2026**; a missed gate changes what can be demonstrated, not
the evidence required to call it complete.

**Current scope: C05 — Cluster deployment and integration.** The requester accepted C04 on 2026-09-04. Deployment assets are in [`deploy/k3s`](deploy/k3s/) pinned to the C04 manifest digest `sha256:a1eb434c…`, with host commands in [the deployment handoff](docs/c05-ubuntu-deployment-handoff.md). K3s runs without Traefik or ServiceLB so it binds no port 80/443 and leaves Jenkins on 8080 untouched.

**Partially executed on 2026-09-04. Steps A, B and D are complete; E onward are not.** The Ubuntu host was found with K3s **already installed** at the pinned `v1.36.4+k3s1` but stock-configured — no `--disable`, no `nodeport-addresses`, and 6443/10250 open to the LAN. Handoff steps C and D were therefore not run as written; the settings were applied through `/etc/rancher/k3s/config.yaml` and the cluster restarted, which the handoff now records as **D-adapt**. Recorded evidence: guard rules present *after* the restart, `nc` to 6443 from the Mac timing out where it previously connected, CoreDNS rolled out, node Ready, Jenkins/nginx/Ollama untouched. Step F applied the namespace, both Secrets, Redis and the worker; **the worker Pod is not running** — the Deployment references the image by digest while the archive imports under a tag, corrected in the handoff's step F. **The host is now powered down and off this network, so C05 cannot progress.**

**A gate distinction to settle:** C05's row lists *one real worker-model response*. Step 7e of the handoff produces one **through the worker's runtime adapter inside the Pod**, without opening dispatch. A response through the contract's *public job routes* additionally needs OD-06 pairing and the AF-005 receipt, neither implemented. **Ready Pods plus adapter-level inference is not completed integration.** Whether the gate means the adapter-level response or the dispatched one is a requester decision.

The worker speaks plain HTTP and pinned TLS belongs to OD-06, so C05 keeps the Kubernetes API and the worker NodePort **closed to the LAN** and verifies from the node itself; LAN exposure arrives with pairing. **Reviewer decision, 2026-09-04:** the documented dispatch path is Mac → authenticated worker Service → Redis → executor → Mac, with Redis internal. `nodeport-addresses=127.0.0.1/32` therefore stands for C05, and **C06 must introduce controlled LAN access to 30443** with pairing, certificate pinning, and matching forwarding and firewall controls — see [architecture](docs/architecture.md) and [security](docs/security.md).

The cluster guard covers **6443 and 10250 on both IPv4 and IPv6**. The recorded Mac denial exercised IPv4 6443 only; the 10250 and IPv6 rules were added afterwards and are **not yet proven on hardware**.

---

**C04 — Worker/API implementation and image build (accepted 2026-09-04).** The requester
accepted C03 on 2026-09-04 and assigned implementation to Claude, with Codex
orchestrating and reviewing. The authorisation covers **C03 through C13**,
including implementation, review fixes and proportionate offline checks on
existing dependencies. The requester subsequently approved the grouped
execution plan below; required acceptance gates still apply.

Ubuntu-to-Mac connectivity passed with zero packet loss. The worker API is
implemented in [`backend/worker`](backend/worker/README.md) against the frozen
`/v1` contract, and a `linux/amd64` verification build ran on the macOS
coordinator under emulation: hash-verified wheels, 8 contract checks passing
inside the image with `--network=none`, non-root execution, and a real prompt
streaming from `POST /v1/jobs` through SSE to completion. That build was
emulated and never pushed. Pairing routes return `501`; OD-06 stays recorded
but unimplemented.

**C04 build returned, 2026-09-04.** The Ubuntu worker built the image on the
native Docker endpoint (server 29.6.1, `linux/amd64`): the pinned base resolved
by digest, 13 wheels installed under `--require-hashes`, **52 in-image checks
passed with `--network=none`**, 11 layers, ~48 MB.

| | |
|---|---|
| **manifest digest — C05 pins this** | `sha256:a1eb434c91ff5e51a095ccbdc5becd10e98a099a281302ef68e86b531543a295` |
| config digest | `sha256:4d9c91892fc813c846f08a42fa17dde870b0a35f4e969431522059738dd96b5f` |
| archive checksum | `sha256:53eb20e4d77b222e783d7bd50fb3339663fbd5001feb9a704f4482800d108a9a` |

Both digests match the build's own `exporting manifest` and `exporting config`
lines. The running container reported a distinct generated node identity, empty
capabilities, `health: unavailable` and `loaded_model_id: null` — correct for a
container with no reachable runtime and fail-closed job routes.

The digest differs from the earlier emulated Mac build; image configs embed a
creation timestamp, so identical inputs do not yield identical digests. **No
reproducible-build claim is made.**

The Ubuntu `*:8080` listener is identified: **Jenkins** (`java`, PID 1239, user
`jenkins`, `jenkins.service`, working directory `/var/lib/jenkins`). It is
preserved and avoided; the coordinator uses port 8770. Its wildcard bind is
**not** evidence of safe LAN exposure, so the exposure review stays open before
worker LAN access. The worker contract ports remain 8443 and 30443. The Ubuntu
worker has two distinct Docker environments — `desktop-linux` (server 29.6.2,
~3.6 GiB) and the native socket at `unix:///var/run/docker.sock` (server 29.6.1,
12 CPUs, 16382078976 bytes) — so future host-Docker commands select the endpoint
explicitly rather than changing a global context. Earlier inventory reported
coordinator `192.168.1.3/24` and worker `192.168.29.98/24`; those addresses are
historical. On 2026-09-04 the Mac reported `192.168.68.132` on `en0`, with default
gateway `192.168.68.1`. Ubuntu's current address and peer reachability still need
checking. Different address ranges alone do not establish whether routing works.
Prepare the trusted LAN alongside C04; application pairing remains a C06 gate.

C03 is implemented and Codex's repaired-source review is **PASS**. An isolated
run returned a real loopback Ollama answer, stopped cleanly, restarted with the
same node ID, and restored the conversation. Requester acceptance is now
recorded; these local results do not establish Ubuntu or distributed readiness.

**2026-09-04 requester correction:** the mandatory third OCR device is withdrawn.
C01/C02 acceptance and all C03 repairs stand. The requester subsequently accepted
C03 and requested [Claude's C04 execution handoff](docs/c04-execution-brief.md).
C04 build inputs are [prepared](backend/worker-image/README.md); implementation
may proceed, while the actual Ubuntu image build and later deployment retain
their device checkpoints. The retained
[`scripts/qualify-ocr-worker.ps1`](scripts/qualify-ocr-worker.ps1) is **deferred**,
used only if a measured need selects a Windows execution device later.

### Sequence toward the internal demonstration

These are working targets, not completed tasks or permission to skip a gate.

| Target window | Work in the existing order | Evidence needed to keep the window |
|---|---|---|
| 4 September | C03 requester acceptance, then C04 worker/API implementation and Ubuntu image build | Accepted Mac run and actual image digest |
| 5 September | C05–C06 deployment, model response, pairing, dispatch and recovery | Real Mac-to-Ubuntu response and cancel/disconnect evidence |
| 6 September | C07–C09 synthetic fixtures, Documents/OCR and bounded Code workflow | Openable cited Word output and an observed sandbox-validated patch |
| 7 September | C10–C12 concurrent workflows, approvals, offline evidence and failure drills | Actual concurrent outputs, approval/recovery behavior and scoped network evidence |
| 8–9 September | C13 three clean-start rehearsals, backup recording and demonstration | Same setup passes the rehearsals; only supported claims enter the presentation |

**Capacity assessment:** this is a stretch plan. C04–C12 have no integrated
runtime proof yet, so the full candidate is not currently a credible commitment
for 8 September. An image/model/container or LAN delay consumes the workflow
and rehearsal window. If C06 slips beyond 5 September, report C08–C13 as at risk
immediately; if a complete C09 path is absent on 6 September, flag the full
concurrent/offline candidate as unlikely to fit. Extra devices, optional models,
voice, scaling and polish do not fit this window. Demonstrate only the verified
subset if a gate remains open, and state that the full candidate is incomplete.

---

**C02 — Environment preparation, setup and verification (accepted).** The
requester authorised C02 and recorded that C01's contract code passed review.
Codex reviewed the AF-001 fixes at `e7f44fb` and reported PASS with eight
contract checks passing and all pinned dependencies matching; that test result
is **Codex's recorded review, not a Claude run**. `backend/` is unchanged since
`e7f44fb`, so the result is reused rather than repeated. Read-only inventory was
supplied for all six devices and is recorded in
[devicespecifications.md](docs/devicespecifications.md). AF-001 stays a
**draft** until its consumer-integration gate passes at C05; OD-06 pairing is
recorded but unimplemented.

**C01/C02/C03 are accepted.** The current work is C04. Ubuntu runtime and
integration claims still need their own checks.

C02 decisions are now recorded with upstream provenance:
[OD-03 runtime](docs/model-catalog.md#od-03--ollama-is-the-first-runtime),
[OD-05 model set](docs/model-catalog.md#31-od-05--the-first-selected-model-set),
[OD-06 pairing](docs/security.md#41-od-06--the-prototype-pairing-decision) and
[OD-08 pins](docs/architecture.md#81-od-08--resolved-infrastructure-pins). One
bounded local inference path is measured on both critical-path devices
([evaluation.md §5.1](docs/evaluation.md#51-od-03-runtime-comparison)).

**C02 evidence returned, 2026-09-03:** the Ubuntu worker supplied versions,
service/socket state, privileges and storage; downloaded the selected model
into its existing Ollama store; returned five successful manifest/blob hash
checks; and measured native Ollama inference. The macOS coordinator reused its
installed model and Ollama-bundled `llama-server` for the direct-engine
comparison, then reported stopping that temporary server with Ctrl+C.
The original inventory had launched the coordinator's Ollama app through
`ollama list`; inventory commands no longer use that path. No new runtime or
driver installation, cluster deployment or worker-image build is recorded.

**Requester decision, 2026-09-03:** retain Ollama and defer the controlled
startup-to-first-answer comparison and the Ubuntu direct-engine comparison.
Both remain unmeasured; they do not block C02 acceptance. Warm fixed-prompt
measurements are not general performance or model-quality proof. Native
inference is observed; container GPU support, pairing, application persistence
and zero-egress evidence belong to later checkpoints.

**C02 review follow-up:**

- **Ubuntu wildcard listener:** identified as Jenkins as recorded above.
  Preserve it; review the host exposure before enabling worker LAN access.
- **Cancellation:** not exercised in C02 and not implemented in an application.
  C06 / AF-005–AF-007 retains the implementation and cancel exercise; streaming
  and configured request limits do not clear that gate.

**Next human action:** give Claude the [C04 execution brief](docs/c04-execution-brief.md)
and return Ubuntu's current LAN evidence while implementation proceeds.
Codex reviews the result before the Ubuntu worker runs the final image build.
OCR follows at C08 on these two devices. Other machines have no required
execution role and may still build any module.

**C03 reply repair, 2026-09-04:** raised Chat output from 512 to 2048 tokens,
persisted runtime stopping evidence, marked capped replies incomplete while
retaining their text, and handled expected browser resets. 33 local checks and
an isolated real 664-token response passed; restart retained the result.
The [updated Mac handoff](docs/handover-pack.md#verify--run-these-yourself)
recorded the then-pending acceptance gate; requester acceptance has since cleared it.

| Device role | Documented machine | Purpose in the first configuration |
|---|---|---|
| **macOS coordinator** | Apple Silicon `Mac17,3`, macOS 26.6.2 (25G83), arm64, 16 GiB unified, 340 GiB free on `/` | Primary workspace and UI, canonical SQLite state, approvals, local main-engine inference |
| **Ubuntu worker** | Ubuntu 24.04.4 LTS, x86_64, 15 GiB RAM, RTX 2050 4096 MiB (driver 580.173.02), 115 GiB free on `/` | Candidate single-node K3s host, worker image build, Redis, sandboxed code execution |

| Task number and name | After | Claude builds; Codex reviews | Wait: named human action | Verify before continuing |
|---|---|---|---|---|
| C01 — Contracts and prerequisites | — | **AF-001** — Repair output-validator requirements, typed cancellation/interruption reasons, and citation/page payloads; update examples and focused checks. Keep the contract draft until consumers integrate. | **Requester:** accept the reviewed contract changes and this documentation closeout. **Every inventoried device:** report its own read-only inventory — supplied for all six devices. | Reviewed contract diff and authorised check results; each device's current inventory or explicit unavailability. Use it to prepare setup choices. No runtime installation here. |
| C02 — Environment setup | C01 cleared | **AF-001–AF-004 preparation** — Prepare exact setup instructions and evidence-backed runtime/model/pairing choices (OD-03/05/06), plus K3s/Redis/base-image pins (OD-08); built-image digests follow C04. | **Requester:** confirm the proposed choices after Codex's review. **macOS coordinator:** confirm the reviewed dependency/runtime/model state and run the reviewed bounded local inference check. **Ubuntu worker:** return the read-only environment evidence, then perform only the reviewed worker runtime/model setup for the selected path. | Humans supply versions, paths, hashes and setup output. Agents verify compatibility with permitted checks. Only approved required components are installed; no cluster deployment or six-device model rollout. |
| C03 — Local application | C02 cleared | **AF-004, local AF-003 adapter** — Implemented in [`backend/coordinator`](backend/coordinator/README.md) and `frontend/app/`: SQLite state, Ollama streaming, contract-validated job/attempt/event records, restart reconciliation, Chat and minimum Control Center. | **macOS coordinator:** start the reviewed local commands, send a request, restart the app, then inspect the UI and history. No second installation is required on any other device. | Real local response and retained job/attempt history after restart; missing measurements display unavailable. Return observations and permitted runtime-check output. |
| C04 — Worker image build | C03 cleared | **AF-003, AF-002 preparation** — Worker API implemented in [`backend/worker`](backend/worker/README.md); build assets in [`backend/worker-image`](backend/worker-image/README.md); reviewed build and digest-inspection commands in [the handoff](docs/c04-ubuntu-build-handoff.md). | **Ubuntu worker:** run the reviewed image build and report build output, immutable image digest, architecture and provenance. | Agents inspect the actual build result and prepare a deployment pinned to that digest. Build failure stays in C04; a Dockerfile alone is not image evidence. |
| C05 — Cluster deployment and integration | C04 cleared | **AF-001–AF-004 integration** — Manifests in [`deploy/k3s`](deploy/k3s/) pinned to the C04 digest, with 16 offline invariant checks; host commands in [the handoff](docs/c05-ubuntu-deployment-handoff.md). | **Ubuntu worker:** provision and apply the reviewed cluster commands. **macOS coordinator:** perform the coordinator acceptance steps supplied for this setup. | Ready Pods, internal-only Redis, one real worker-model response, persisted coordinator metadata and shared-version consumers. Pass the C05 integration gate before C06. |
| C06 — Distributed execution | C05 cleared | **AF-005–AF-007** — Implement Redis dispatch/leases/receipt, routing, SSE replay, cancellation, recovery, preflight and truthful fallback. | **macOS coordinator and Ubuntu worker:** connect and explicitly pair the two devices, apply the reviewed trusted-LAN settings, and perform the documented disconnect/cancel exercise. | Actual Mac -> Service -> Redis -> executor -> Mac completion, correct route reason, and usable canonical history after cluster loss. Pass the C06 distributed-execution gate. |
| C07 — Workflow inputs and setup | C05 cleared for independent preparation; C06 cleared for device setup and acceptance | **AF-008–AF-011 preparation** — Prepare synthetic scan/SOP/expected-result and Python code fixtures, their checks, and only the additional model/dependency setup the two workflows require on the Mac/Ubuntu configuration. | **Requester:** approve fixture provenance and allowed validation commands. **macOS coordinator:** select the coordinator inputs. **Ubuntu worker:** install only reviewed missing workflow packages/models. | Source hashes, expected extraction/citation examples, selected repository/base and commands, plus verified installed artifacts. Another execution device needs a measured need and a new device-based setup checkpoint. |
| C08 — Documents workflow | C07 cleared; implementation alongside C09 | **AF-008–AF-009** — Implement real rendering/OCR, uncertainty, page mapping, local retrieval, cited drafting, DOCX creation and artifact checks on the two-device configuration. | **macOS coordinator:** open the Word output and compare its extracted facts and citations against the approved scan/SOP. | Openable Word output with checksum, resolvable citations and honest missing values. Fix discrepancies before accepting the combined C08/C09 result. |
| C09 — Code workflow | C07 cleared for implementation; C08 cleared before combined acceptance | **AF-010–AF-011** — Implement bounded repository context, patch generation and restricted validation Jobs. Reuse approved images where suitable; a new image needing a build creates another checkpoint before deployment. | **Ubuntu worker:** apply the reviewed sandbox configuration and run the approved host steps. **macOS coordinator:** inspect the patch and validation results on the approved fixture. | Applicable patch, observed approved-command result, enforced limits/network isolation and cleanup; canonical repository unchanged. Pass the C09 signature-workflow gate. |
| C10 — Concurrent workflows and approvals | C08 and C09 cleared | **AF-012–AF-014** — Implement concurrent workflows, exact-action approvals, durable final-write recovery and evidence-backed Proof Cards. | **macOS coordinator:** choose the output destination, exercise approve/deny/expiry, and inspect both workflows and the displayed proof against the observed results. | Concurrent progress with separate attempts/artifacts; denial writes nothing; approval writes once; no inferred health, timing or network measurements. |
| C11 — Offline evidence | C10 cleared | **AF-015** — Prepare reviewed Pod/host network controls, rollback commands and independent observation for the real concurrent run. | **Ubuntu worker:** apply the host and cluster network controls. **macOS coordinator:** apply the coordinator network controls. **A separate observing device on the same LAN:** record the named device, interface and time window using the reviewed observation procedure. | Actual concurrent outputs plus enforcement and observation evidence for the specified scope. Preserve trusted LAN traffic and pass the C11 concurrent/offline gate; absent evidence remains unavailable. |
| C12 — Recovery and measurements | C11 cleared | **AF-016–AF-017** — Prepare bounded failure drills and comparable standalone/distributed measurements; inspect results and repair confirmed recovery defects. | **macOS coordinator and Ubuntu worker:** perform the reviewed restart, disconnect, Pod, Redis and cluster operations, and record timing, resources, quality and failure outcomes. | Canonical history survives, stale attempts are fenced, no duplicate final writes, and reproducible cold/warm results on the named devices. Rerun affected checks after fixes. |
| C13 — Candidate acceptance | C12 cleared | **AF-018–AF-019** — Codex reviews the integrated source/evidence; Claude fixes remaining defects and prepares the frozen demo instructions and claim list. | **macOS coordinator:** operate three clean-start runs, record a backup, and inspect the artifacts and demo clarity. **Ubuntu worker:** operate the cluster. **Requester:** compare the results with the recorded evidence, check the selected model/runtime provenance, accept the candidate and coordinate human Git promotion. | Three successful runs on the same documented setup, backup recording, honest claims, independent review and requester acceptance. This closes the alpha, not the later finals scope. |

The AF rows below retain their dependency and acceptance meaning. For AF-001,
C01 reviews the shared draft, C02 resolves setup/security decisions, and C03–C05
prove its consumers. Dependency preparation may use that reviewed draft; neither
AF-001 nor a dependent integration gate becomes verified before its full evidence
exists. Do not claim a contract freeze from schema checks alone.

## Grouped execution plan

Requester-approved order for the remaining work; C05 must pass first:

- **C06 + C07:** build and verify distributed execution while independently
  preparing C07 fixtures, expected results and the dependency plan. C07 device
  setup and acceptance wait for C06 and their existing approvals.
- **C08 + C09:** after C07 passes, implement Documents and Code in parallel
  against agreed job, event, artifact and permission interfaces. Coordinate
  shared-file edits; verify each workflow separately and both before C10.
- **C10:** integrate concurrent workflows and approvals after both workflows pass.
- **C11–C13:** prepare one final validation session after C10, then execute
  offline evidence, recovery/measurements and candidate rehearsals in order.
  Repair failures before proceeding; retain device actions, three clean-start
  rehearsals and requester acceptance. A shared session does not combine the gates.

UI design may proceed alongside implementation; integrate it with the existing
frontend and contracts. Reuse valid check results and shared setup to reduce
waiting; grouping does not promise a fixed completion time.

## Verification and team explanation

- Before building, name the smallest check that demonstrates the chunk's
  changed behavior. Run it only with the required permission.
- Claude supplies changed paths, exact commands, environment and observed
  results. Codex inspects the combined diff and independently verifies the
  material claims with proportionate authorised checks.
- Reuse valid results tied to the same source/environment. Rerun checks affected
  by changes; broaden only for a shared-boundary risk or a required gate. Do not
  repeat a full suite after every edit or add CI triggers to police each chunk.
- Exercise the relevant end-to-end path at each task acceptance gate and the
  three final rehearsals. Contract tests cannot replace model, device, sandbox,
  approval or network evidence. Tests reduce risk; they do not guarantee perfection.
- After **every build and review cycle**, explain to the requester: **Built**
  (plain language plus one example), **Verified** (observed checks and limits),
  and **Next / Human action** (device, instructions, return evidence and resume
  condition). Review reports use `PASS`, `NEEDS FIX`, or `BLOCKED`; a code-review
  pass does not clear an outstanding human or runtime gate.

## AF implementation requirements

### AF-001–AF-004 — Contracts and local execution

| ID | State | Task | Depends on | Acceptance gate |
|---|---|---|---|---|
| AF-001 | in-progress | Freeze versioned node, job, attempt, event, approval, proof, HTTPS, Redis-key, and idempotency contracts | — | Coordinator, worker, UI, and manifests consume one contract version; schema examples pass the smallest contract check |
| AF-002 | planned | Provision one pinned single-node K3s cluster on the authorised Ubuntu host and deploy pinned Redis 7.2.x behind ClusterIP | AF-001 | Kubernetes reports Ready Redis and worker placeholders; Redis is unreachable from the LAN; versions, digests, and licences are recorded |
| AF-003 | planned | Build the smallest Docker worker image with FastAPI, one runtime adapter, the frozen Service API, and one real model | AF-001, AF-002 | A real prompt streams from a worker Pod; source, licence, revision, image digest, memory, and latency are recorded |
| AF-004 | planned | Implement SQLite-backed coordinator state and the smallest local browser UI over one event stream | AF-001 | A local job reaches a truthful terminal state after restart; Chat and Control Center show live state while unfinished surfaces say unavailable |

AF-001 has a [contract draft with eight passing local checks](backend/contracts/README.md),
now including kind-matched output validators, typed stop reasons, and citation
payloads with a grounding guard.
The OD-06 pairing decision, shared consumers and requester verification remain
open; the C05 application integration gate has not passed.

C05 gate: the pinned Docker image runs in a Ready Kubernetes Pod, one real
response streams through the worker API, and the coordinator persists the job,
attempt, model, device, and timing record. No workflow work starts before this
spine passes.

### AF-005–AF-007 — Distributed execution

| ID | State | Task | Depends on | Acceptance gate |
|---|---|---|---|---|
| AF-005 | planned | Connect the worker API and executor through Redis Streams, leases, cancellation, bounded retention, and cleanup | AF-002, AF-003 | One queued attempt is consumed and acknowledged; a killed consumer leaves recoverable pending work; Redis restart loses no canonical record |
| AF-006 | planned | Route from the Mac coordinator to the Kubernetes Service using capability, health, queue, and explicit-target rules | AF-003–AF-005 | Mac -> authenticated Service -> Redis -> executor -> SSE response completes with visible route reason and local fallback |
| AF-007 | planned | Finish the usable Chat and Control Center slice with guided preflight/self-test, node health, Pod readiness, model, queue, progress, cancel, disconnect, and fallback state | AF-004–AF-006 | A fresh documented setup selects the curated manifest and reaches a real self-test; every displayed value has a source and missing evidence displays unavailable |

C06 gate: a real Mac -> Kubernetes Service -> Redis -> executor Pod -> Mac
inference completes, and stopping the cluster leaves the Mac workspace and its
canonical history usable.

While C06 is unverified, preserve the standalone baseline and repair the
existing distributed path before C07 device setup or acceptance. Independent
C07 preparation may overlap as described above. Infrastructure expansion remains blocked. Do not add nodes, replicas, Helm,
Ingress, another broker, or another runtime to repair an unproven single path.

### Requester placement decision, 2026-09-05

**Documents runs on the macOS coordinator. Code runs on the Ubuntu worker.**

| Workflow | Where it executes | What runs there |
|---|---|---|
| Documents (C08) | macOS coordinator, locally | PDF page rendering (Quartz), scan reading through the local Ollama vision model, SOP retrieval, cited drafting, DOCX generation, approval-gated export |
| Code (C09) | Ubuntu worker, distributed | Code generation on the worker's Ollama model, then validation in a restricted short-lived Kubernetes Job |

The Ubuntu sandbox is a **restricted Kubernetes Job, not a second model**. C10
concurrency therefore means one local workflow and one distributed workflow
running at the same time with completely separate state — not two Redis
consumers and not two model Pods.

### C07–C10 source and artifact preparation, 2026-09-05

Source for C07 preparation through C10 was implemented in one consolidated
cycle **ahead of the C06–C10 human acceptance gates**, as authorised schedule
compression. This is recorded separately from acceptance on purpose:

- **Implemented and covered by offline checks:** C08 Documents (rendering,
  vision transport, honest extraction), C09 resource packages, remote code
  generation, the restricted validation Job, C10 concurrency, approval binding,
  durable final-write recovery and Proof Cards.
- **NOT accepted:** C06, C07, C08, C09 and C10 remain unaccepted. Later code or
  an image build existing is not evidence for an earlier runtime gate.
- **Runtime blocker recorded:** the configured C08 scan-reading model
  `MedAIBase/PaddleOCR-VL:0.9b` is installed and does **not** declare the
  `vision` capability, so scan reading currently reports itself unavailable.
  See [`docs/c08-dependency-plan.md`](docs/c08-dependency-plan.md) §3.
- **Artifact state:** requester-returned Ubuntu output on 2026-09-06 shows the
  linux/amd64 C09 worker image built with its offline layer under
  `--network=none`. Digest and archive evidence are recorded in
  `backend/worker-image/provenance.json`; K3s import and rollout are pending.

**C06 setup resumed on a new router.** The C09 replacement image is built but
not yet imported or rolled out. Address-bound TLS, the guarded LAN forwarder,
pairing, relationship-ID installation, executor deployment, real distributed
inference, cancellation, disconnect recovery and requester acceptance all
remain pending. The consolidated next steps are in
[`docs/c07-c10-runtime-handoff.md`](docs/c07-c10-runtime-handoff.md).

### AF-008–AF-011 — Signature workflows

| ID | State | Task | Depends on | Acceptance gate |
|---|---|---|---|---|
| AF-008 | source implemented; acceptance pending | Implement scan rendering plus local OCR/vision extraction with source hash, page mapping, and explicit uncertainty through the shared job contract | AF-003, AF-006 | The public sample scan produces structured, page-linked extraction without fabricated missing values |
| AF-009 | source implemented; acceptance pending | Add the minimum local SOP retrieval, cited drafting, Word generation, and artifact validation path | AF-008 | `inspection_report_to_approval_note` returns an openable cited `.docx` with checksum |
| AF-010 | source implemented; acceptance pending | Implement bounded repository context and patch generation inside an assigned temporary workspace | AF-003, AF-006 | `repository_request_to_validated_patch` returns an applicable patch without modifying the canonical repository |
| AF-011 | source implemented; acceptance pending | Run each approved validation command as a short-lived restricted Kubernetes Job Pod | AF-002, AF-010 | Default-deny egress, non-root execution, limits, deadline, cleanup TTL, command output, and artifact hashes are observed; no Docker socket is mounted |

C09 gate: the application produces one real Word approval note and one real
validated code patch through the same Service, Redis, job, event, and approval
contracts.

### AF-012–AF-015 — Concurrency, approvals and offline evidence

| ID | State | Task | Depends on | Acceptance gate |
|---|---|---|---|---|
| AF-012 | source implemented; acceptance pending | Run an independent local Documents attempt and a remote Code attempt concurrently | AF-005, AF-009, AF-011 | Both jobs progress simultaneously, retain separate attempt/artifact state, and show honest queue time. **Superseded wording:** this row previously said "separate Redis consumers and Pods". The requester's accepted topology is one LOCAL workflow (Documents, on the Mac) plus one DISTRIBUTED workflow (Code, on Ubuntu), so Documents has no Redis consumer and no Pod, and claiming either would be evidence of something that does not exist. |
| AF-013 | source implemented; acceptance pending | Enforce approval before canonical writes and bind it to the exact action, target, and attempt | AF-004, AF-009, AF-011 | Denial writes nothing; retry cannot reuse a stale approval; approval performs one bounded final write |
| AF-014 | source implemented; acceptance pending | Produce per-job Proof Cards from SQLite, Redis, Kubernetes, model, validation, integrity, approval, and network evidence | AF-012, AF-013 | Every displayed value has an identified source and observation window; unavailable evidence is not inferred |
| AF-015 | planned | Enforce default-deny Pod egress and host public-egress blocking while retaining authenticated Service traffic | AF-011, AF-014 | The real concurrent run completes with zero observed public outbound flow in the named interval and only documented LAN/cluster flows |

C11 gate: Documents and Code complete concurrently on distributed compute,
with visible Pods, Redis queue state, routing, approvals, artifacts, and scoped
zero-egress evidence.

### AF-016–AF-019 — Recovery and candidate acceptance

| ID | State | Task | Depends on | Acceptance gate |
|---|---|---|---|---|
| AF-016 | planned | Exercise cancellation, executor-Pod loss, Redis restart, cluster loss, retry, and local fallback | AF-012–AF-015 | Failure is recoverable, canonical history survives, and no duplicate final write occurs |
| AF-017 | planned | Run the same standalone and Kubernetes fixtures; record cold/warm latency, queue time, RAM/VRAM, restarts, and output quality | AF-008–AF-016 | Results are reproducible and slower results are reported honestly |
| AF-018 | planned | Review the integrated source, licences, evidence, demo claims, and remaining blockers | AF-017 | Every claimed feature is observed; planned or broken paths are labelled and excluded from the script |
| AF-019 | planned | Run the frozen demo from clean start three consecutive times and record one backup demonstration | AF-018 | Three successful runs use the same documented setup and public sample inputs |

C13 gate: no feature work remains. Only demo-breaking fixes, evidence repair,
and rehearsal may enter the internal candidate.

## Internal demo order

1. Show the Ready worker, executor, and Redis Pods plus the worker and internal
   Redis Services; explain that Docker built the pinned workload images.
2. Open the application and show Chat, Documents, Code, and Control Center.
3. Show the installed model, Kubernetes worker, queue, and route reason.
4. Block public Internet and start the named observation window.
5. Start the scanned-report workflow and the code workflow.
6. Show Redis dispatch and separate executing Pods without exposing payloads.
7. Open the cited Word artifact and the validated code patch.
8. Approve one bounded write, deny another, then terminate one executor Pod.
9. Show recovery, both Proof Cards, and the end of the observation window.

## Optional work after verified tasks

Proceed to the next eligible task only when its prerequisites and human
checkpoint are clear. C07–C09 remain required after C06. Additional scope needs
requester approval and these prerequisites:

1. **After C09 passes:** add one bounded image-understanding moment and one
   calculation-with-steps inside the approval note.
2. **After C11 passes:** add a second executor replica and prove Redis-backed
   concurrency and Pod-loss recovery on the same cluster.
3. **After C13 passes:** evaluate one additional physical worker on measured need,
   with a new device-based setup checkpoint, or
   the narrow text-only part of FR-019.

Do not unlock multi-node Kubernetes, voice, PPT, Excel, broad P&ID support,
another runtime, or another broker for the alpha candidate.

## After internal selection: finals tasks

This later scope is not activated by the alpha execution pass. Anyone may
implement it. Define named human checkpoints from then-current hardware and
requirements before starting it; do not retain permanent build assignments.

| Task | Focus | Exit gate |
|---:|---|---|
| F01 | Triage judge feedback and freeze the finals claim set | Every accepted change maps to a PRD requirement or observed demo weakness |
| F02 | Harden node identity, pairing credentials, compatibility checks, and revocation | Invalid, expired, and revoked workers are rejected |
| F03 | Harden retries, cancellation, worker-loss recovery, idempotency, and cleanup | Interrupted jobs recover without duplicate final writes or retained temp data |
| F04 | Improve OCR/vision on the fixed public scan set | Page mapping and uncertainty meet the recorded quality threshold |
| F05 | Improve local retrieval, citations, drafting, and Word validation | The approval note is grounded, readable, cited, and reproducible |
| F06 | Improve repository context selection and patch validation | The coding fixture passes without unrestricted repository transfer |
| F07 | Harden the Linux sandbox and verify its actual resource/network boundaries | Escape, network, timeout, process, and filesystem checks fail safely |
| F08 | Complete guided setup, capability detection, manifests, and offline bundle import | A reset installation reaches honest self-test status without silent downloads |
| F09 | Finish Control Center, approval UX, evidence semantics, and Proof Cards | No security or health value is hard-coded or inferred from missing evidence |
| F10 | Benchmark standalone versus distributed cold/warm runs | Same fixtures produce honest performance and quality comparisons |
| F11 | Break the complete system across supported demo machines and repair blockers | Full demo survives worker loss, bad input, denied approval, and unavailable evidence |
| F12 | Freeze code, licences, artifacts, instructions, video, and presentation | Three clean rehearsals pass; no unverified capability appears in the pitch |

## Definition of done for every implementation task

- The task's real caller and shared contract are used; no parallel mock path is
  sold as implementation.
- Trust-boundary inputs are validated and failures are visible.
- Non-trivial logic leaves the smallest runnable regression check.
- The implementer reports exact changed paths and commands actually run.
- The reviewer inspects the current combined diff and reruns only authorised
  checks needed for the claim.
- Source, pinned version or commit, licence, network behaviour, and material
  changes are recorded for reused open-source components.
- Runtime evidence is labelled `prototyped` or `verified` only after it is
  observed on the named device.

## Outside the alpha scope

- model sharding or pooled VRAM;
- training or fine-tuning;
- a generic multi-agent or visual workflow builder;
- multi-node or highly available Kubernetes, Helm, an operator, a service mesh,
  Redis Cluster, another message broker, or a custom model runtime;
- production multi-user IAM, high availability, or coordinator transfer;
- voice, PPT, Excel, and broad P&ID support before the two signature workflows
  and distributed proof are stable;
- perfect installers for every operating system.

Each exclusion that the problem statement names is recorded against its source
line in [problem-statement coverage](docs/evaluation.md#11-problem-statement-coverage).
Exclusion means excluded from the alpha, not abandoned: multilingual
and voice work is FR-019 in the finals scope.

Add an excluded item only after its prerequisite task passes and the requester
accepts the resulting risk to the frozen demo.
