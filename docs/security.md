# Security, Privacy, and Supply Chain

## Status and authority

This document owns security implementation boundaries under
[PROJECT.md](PROJECT.md). Planned controls are not verified controls. A static review
cannot prove isolation, secure storage, zero egress, or resistance to attack.

The [standalone Beta scope](PROJECT.md#25-platform-support-and-beta-scope) narrows the profiles offered in Beta;
they do not relax authentication, model provenance, approval, sandbox, data-loss
or offline-runtime boundaries. Local model admission follows the open-model compatibility policy
in PROJECT.md; lack of team measurement alone is not a refusal. Advertised measurements, tool
containment and package/security claims still require their own evidence. Beta in-app updates and manual recovery follow
[release acceptance](releases.md#beta-01-publication). Qualify every offered installation/update/
recovery path. Peer discovery, pairing, remote execution and admission are post-Beta capabilities;
their controls remain required when exposed. Deferring mesh work does not weaken local isolation,
protected credential storage, approval, data preservation or offline evidence requirements.

## 1. Security objectives

Refinix must:

- keep selected confidential work inside the trusted environment;
- prevent silent public inference and background traffic during offline runtime;
- minimise data sent to workers and tools;
- keep canonical state and consequential writes under coordinator control;
- make device, model, tool, integrity, and network evidence inspectable;
- reject untrusted models, dependencies, devices, paths, and actions.

Availability and model quality matter, but they never override confidentiality,
integrity, or explicit user authority.

## 2. Trust boundaries

1. Public website and release storage
2. Installer and application-update boundary
3. Connected model source or offline import boundary
4. Local desktop interface
5. Coordinator service and canonical workspace
6. Paired worker service
7. Private-server worker
8. Local model runtime
9. Tool sandbox
10. User-selected documents and repositories
11. Local application-data and credential stores
12. Kubernetes API, worker Service, Pods, and node boundary
13. Redis coordination service

Data crossing a boundary requires an explicit contract, minimum content,
authentication where applicable, size limits, integrity metadata, and an audit
event.

## 3. Network modes

### Connected setup

The user explicitly enables networked provisioning for approved installers,
runtimes, or model artifacts. The app:

- shows the intended source and download;
- records version, licence, and expected hash;
- performs no unrelated inference or telemetry;
- ends connected setup before an offline-runtime claim begins.

### Offline runtime

Normal work:

- requires no public Internet route;
- uses no cloud inference;
- performs no public DNS, telemetry, analytics, crash upload, update check, or
  model download; explicit local discovery may use link-local mDNS without
  contacting a public resolver or advertising private task data;
- keeps local model runtimes on loopback;
- permits only required authenticated worker traffic on the trusted LAN.

The strongest demonstration uses operating-system or network enforcement plus
independent observation. Application logs alone cannot prove that traffic was
blocked.

### Existing local Ollama reuse

Connect only to the supported numeric loopback endpoint; bypass proxies and reject inference redirects.
Before sending work or a check, establish that the selected model is local using the supported API's
model metadata. Cloud/remote-backed models are excluded from offline work; model-name suffixes alone
are insufficient. Unknown locality must be explained before confidential input is sent.

Use required API/feature compatibility and known security/incompatibility exclusions rather than an
exact team-measured version allowlist. A newer version alone is not evidence of failure. An endpoint
answering on loopback is not independent proof of publisher identity, zero egress or safe host setup.
Do not silently change the user's service, cloud settings, model store, credentials or updater.

Ollama reuse is read-and-run in Beta: list metadata and issue bounded inference; do not copy, pull,
remove or modify its models. Handle startup graphically under user authority. Manage Refinix's own
jobs and resources without terminating an externally owned service or interrupting unrelated clients.
No arbitrary executable model code, permissions expansion or unrestricted host-tool fallback is added.
Source, licence, identity, observed compatibility and published/team evidence remain separately labelled.

### Kubernetes worker exposure

These controls apply to the retained managed Kubernetes profile; desktop peer
operation must not require Kubernetes or expose its administrative API.

- The Kubernetes API is administered only from the Linux host and is not the
  product's worker API.
- The worker API is the only cluster workload exposed to the trusted LAN, using
  a fixed Kubernetes Service port and authenticated HTTPS. The host firewall
  limits that port to the coordinator address or named trusted subnet, and the
  coordinator pins the prototype certificate fingerprint during pairing.
- Redis remains behind a ClusterIP Service. It is not exposed through NodePort,
  LoadBalancer, Ingress, or a host port.
- Default-deny NetworkPolicies are applied before confidential fixtures enter
  the cluster. The team must verify that the selected K3s network-policy
  controller enforces them; accepted YAML alone is not proof.
- Public image pulls, package downloads, and model downloads finish before the
  offline evidence window. Runtime Pods use only preloaded, pinned images.

## 4. Node identity, pairing, and revocation

- Every installation creates a unique local node identity.
- Discovery never grants trust.
- Pairing requires explicit confirmation and a short-lived one-time value.
- Each workspace relationship receives a unique revocable credential.
- Coordinator-to-worker traffic is authenticated and encrypted with standard
  HTTPS credentials or mTLS.
- Unknown, revoked, expired, or incompatible nodes are rejected.
- Credentials are stored in the operating-system credential store.
- Worker APIs expose only the minimum LAN surface and enforce message-size,
  heartbeat, timeout, and rate limits.

Pairing permits bounded compute work; it does not authorise state migration,
general file browsing, direct model-runtime access, or unrestricted shell use.

### 4.1 OD-06 — the prototype pairing decision

**Historical prototype decision.** Pairing routes now exist in the coordinator
and worker source; this record does not prove current deployment security. The
manual fingerprint exchange below records the prototype bootstrap. Production
requires guided identity confirmation and OS-protected credentials without
manual certificate commands, while preserving authenticated encrypted transport.

Established mechanisms only — no bespoke cryptography, no custom handshake.

**Bootstrap.** The worker generates a long-lived self-signed TLS certificate in
its own state directory on first start. The operator reads two values off the
worker host: the certificate's SHA-256 fingerprint, and a short-lived single-use
pairing code. Both travel to the coordinator **out of band**, read by a human,
never over the network. The coordinator operator enters the worker address, the
fingerprint and the code; the coordinator then presents the code once over the
already-pinned channel and receives a per-relationship credential in return. The
code is single-use and expires whether or not it was used.

This is deliberately *not* blind trust-on-first-use. The fingerprint is
confirmed by a human before the first byte of credential material moves, the
same shape as verifying an SSH host key.

**TLS verification.** The coordinator does not use the system trust store for
worker connections. The pinned self-signed certificate is loaded as the sole
trust anchor for that relationship — in Python, `SSLContext.load_verify_locations(cadata=…)`
with `verify_mode=CERT_REQUIRED` and `check_hostname=False`, since a LAN
worker is reached by address rather than by a name in a public certificate. A
fingerprint or chain mismatch **aborts the connection**. There is no downgrade,
no "continue anyway", and no retry against an unverified endpoint; the operator
sees that the worker identity changed.

**Credential scope.** One credential per (workspace, worker node) relationship.
It is a bearer token, valid **only** inside that pinned TLS channel, and it
authorises only the worker job surface: submit an attempt, stream its events,
cancel it, and read health. It does not authorise the Kubernetes API, a shell,
filesystem browsing, direct model-runtime access, coordinator transfer, or
state migration. **Coordinator authority is unchanged by pairing** — the worker
executes bounded work and returns results; canonical state, approval and final
writes stay on the coordinator.

**Storage.**

- Coordinator: the operating-system credential store — the macOS Keychain on
  the coordinator. Never SQLite, never a dotfile, never the repository.
- Worker: only a **hash** of the credential, in its state directory, mode
  `0600`, owned by the service user. The worker can verify a presented token
  without holding a replayable copy.
- Neither value appears in logs, events, Proof Cards, ledgers or handoffs.

**Revocation.** `DELETE /v1/pairing/{relationship_id}` from the coordinator
deletes the worker-side hash; the worker then rejects that credential. Local
revocation is deleting the stored hash on the worker and restarting it. Either
route must **fence work in flight**: attempts belonging to the revoked
relationship stop with a typed stop reason, and the coordinator keeps their
canonical history rather than losing or duplicating it.

**Failure behaviour.** Every case fails closed and visibly:

| Condition | Result |
|---|---|
| Unknown, expired or revoked credential | Rejected with a typed reason; no partial service |
| Certificate fingerprint mismatch | Connection aborted; no fallback; surfaced as a worker-identity change |
| Pairing code expired or reused | Rejected; a fresh code is required |
| Worker unreachable | Node marked unavailable, local execution resumes with a visible route reason — never a silent retry against an unverified endpoint |
| Contract-version mismatch | Rejected with the typed incompatibility reason |

**Not claimed:** that any of this is secure, tested, or implemented. It is the
decision C02 owed, so that C04–C06 build against one recorded policy instead of
inventing one under time pressure.

## 5. Data ownership and minimisation

- Canonical personal chats, memory, rules, files, approvals and artifacts remain
  with their workspace coordinator. Pairing never merges them.
- Compute workers receive only required bounded input and return hashed artifacts;
  full repositories, corpora and history are not transferred by default.
- Only selected files/folders are indexed. Hardware scanning does not authorise
  scanning user documents. Treat documents, retrieved text and model output as
  untrusted data that cannot grant tool permissions.
- Organisation-hosted corpora are a separate explicit storage role. Authenticate
  the requesting user, filter retrieval by document access before searching or
  returning snippets, and check execution-device eligibility before context leaves
  that service. Cache/index scope includes corpus version and access policy.
- Corpus deletion, edits and permission revocation invalidate affected chunks,
  vectors and caches. Backups and retained artifacts have an explicit retention
  policy; deleting an index alone is not secure erasure of every copy.
- A trusted compute host can access the content it executes, including through
  privileged administration. Transport encryption does not hide prompts from
  that host. Sensitive organisation work should use approved compute; peer
  membership alone does not make an employee device an approved data destination.
- Audit logs contain metadata by default, not confidential prompts. Sensitive
  logging is explicit, visible and subject to retention. Receiver notifications
  show requester identity and task type, not full prompt content by default.
- Temporary inputs, output, vector caches and crash/recovery data follow documented
  retention and cleanup after completion, cancellation, failure and revocation.
- Redis is ephemeral coordination in the Kubernetes profile, with bounded expiry,
  a memory limit, persistence disabled in the retained prototype profile and no
  ordinary payload logging. It is not canonical corpus or chat storage.

### Personal and organisation authority

Personal installations let their owner pair, revoke, pause sharing and set resource
limits. Managed deployments add administrator-controlled users, device eligibility,
model policy and quotas. They do not silently grant access to personal workspaces.
Receiver-side admission enforces policy across all requesters, and one peer cannot
cancel, read events for, or retrieve artifacts from another peer's jobs. Revocation
must take effect for queued work and active sessions, not just future logins.
Employee task-assignment/project-management features are outside this product scope.

## 6. Local application data

- Application-data directories are owner-only where supported.
- Secrets, tokens, private keys, and device credentials never enter AGENTS.md,
  memory.md, ordinary state exports, or logs; use protected credential storage.
- The target profile's AGENTS.md contains user-editable instructions, not secrets
  or authority to override enforced security/organisation policy. Legacy rules.md
  is mapped only through the documented migration. Retrieved files with either
  name are untrusted content, not automatically adopted instructions.
- memory.md contains curated durable summaries only and must not automatically
  absorb raw confidential conversations or documents.
- Structured state belongs in the local database, not Markdown files.
- Temporary work belongs in per-job directories with cleanup after success,
  cancellation, or failure.
- User exports/backups require an explicit destination and approval. An accepted
  application update authorises its disclosed local migration snapshot under the
  same owner protections; it does not authorise an external upload.
- Follow the [data migration contract](architecture.md#legacy-data-migration);
  never silently merge old/new stores, overwrite user instructions or remove
  the only recoverable copy during a rename/update.
- KV caches can contain private context. Isolate reuse by user/workspace, model,
  adapter and compatible prefix/configuration; permission changes invalidate
  affected reuse. Disk persistence is disabled by default. Cleanup must cover
  crash/restart and job retention, without claiming guaranteed physical erasure.
- Training needs separate opt-in and authorised data/compute scope. Adapters may
  memorise private examples; protect their storage/distribution accordingly.
  Deleting corpus records or training examples is not proof of model unlearning.
  Follow [optional adaptation gates](model-catalog.md#11-personalisation-and-optional-model-adaptation).

## 7. Action authority

The coordinator enforces the action matrix in
[workflows.md](workflows.md#7-action-and-approval-policy).

Security-sensitive requirements:

- the model cannot expand its own tools or permissions;
- the worker cannot approve its own output;
- an approval is bound to the exact action, target, and attempt;
- a retry does not reuse approval for materially different input or output;
- canonical final writes are idempotent;
- denied actions remain denied after routing or worker failure;
- network enablement, model installation, pairing, revocation, export, and
  canonical modification require explicit authority.

## 8. Filesystem and sandbox

Workers and code tools:

- write only inside assigned temporary workspaces;
- reject absolute-path escape, traversal, hard-link abuse, and symlink escape;
- mount only explicit inputs and output locations;
- cannot access host secrets, credentials, or the user's home directory;
- run with networking disabled by default;
- enforce bounded CPU, memory, runtime, process count, and filesystem usage;
- capture command, stdout, stderr, exit status, and produced artifacts;
- clean temporary state after the retention boundary.

A container is a candidate isolation mechanism, not proof of isolation on every
macOS, Windows, and Linux configuration. Platform behaviour requires runtime
verification. The current Kubernetes validator is a bounded Python/unittest path;
it is not arbitrary-language or standalone desktop sandbox support. A timed host
subprocess is not a security sandbox. Keep execution unavailable when no qualified
isolation backend exists, while preserving patch proposal and review. A remote
sandbox does not satisfy standalone sandbox acceptance on an unsupported OS.

[Windows Sandbox excludes Home editions](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/),
so it cannot be the universal backend for the recorded Windows fleet. Qualify
bundled isolation or guided prerequisites against the published OS/edition matrix
before promising zero-terminal code execution. Never weaken the limits below to
make installation appear complete.

The Kubernetes alpha applies these Pod controls unless a narrower exception is
recorded and reviewed:

- non-root user and group;
- `allowPrivilegeEscalation: false`;
- all Linux capabilities dropped;
- `seccompProfile: RuntimeDefault`;
- read-only root filesystem plus explicit writable temporary volumes;
- CPU, memory, process, output-size, and active-deadline limits;
- no privileged containers, host networking, host PID/IPC, host home mounts, or
  Docker socket;
- no service-account token by default;
- a namespace-scoped service account only for the component that creates and
  inspects validation Jobs, with no Secret or cluster-wide access;
- default-deny ingress and egress; only infrastructure service components receive
  narrowly required DNS, Redis, API and model access. Generated-code validation
  Jobs do not inherit those exceptions and keep networking disabled.

Finished validation Jobs use a cleanup TTL. Inputs mount read-only, output uses
one disposable volume, and the coordinator accepts only validated artifacts
whose hashes match the active attempt.

### 8.1 Standalone Code validation on Ubuntu (provisional)

Profile `ubuntu-systemd-landlock` ([`sandbox_local.py`](../backend/coordinator/sandbox_local.py),
[`sandbox_launcher.py`](../backend/coordinator/sandbox_launcher.py)). Generated code runs only when
every control below is in force; otherwise nothing runs and the missing controls are named. There is
no fallback to running code directly on the computer. macOS and Windows do not offer sandbox
validation in Beta and say so.

- **Service:** a transient systemd user service — `RestrictAddressFamilies=none`, a system-call
  filter from `@system-service` that also denies sockets, signals (`kill`, `tkill`, `tgkill`,
  `pidfd_*`), tracing (`ptrace`, `process_vm_*`), io_uring, BPF, keyrings, namespace creation and
  mounts (failing with `EPERM`), `NoNewPrivileges`, `RestrictNamespaces`, and memory (no swap),
  process, CPU, run-time, file-size, descriptor and core-dump limits.
- **Storage:** a fixed-size ext4 image (256 MB, 4096 inodes) mounted `nosuid,nodev` through udisks
  without user interaction, or `fuse2fs` where udisks would ask; the filesystem itself caps bytes
  and files.
- **Launcher (Ubuntu's `/usr/bin/python3`, standard library only):** closes every inherited
  descriptor except stdin/stdout/stderr, replaces the environment (no D-Bus, display, XDG or
  credential variables; `HOME` is the workspace), applies Landlock (read-only interpreter, standard
  library and shared libraries; read-write workspace only; abstract-socket and signal scoping on
  ABI 6+), then checks from the inside that a socket cannot be created, an outside path cannot be
  read, signals and io_uring are refused and the cgroup limits are the requested ones. It hashes the
  staged copies against the reviewed digests before running `python3 -I -m unittest`; output is
  capped.
- **Binding:** a local result is bound to the proposal digest, the staged-input digest, the command
  and the profile. Apply relies on a pass only when all four match **and**, immediately before the
  write record is created, every selected file — the edited ones and the unedited tests and context
  the sandbox ran — still has exactly the bytes that were validated; a changed, missing or replaced
  input voids the pass (`validation_stale`). After a failed, mismatched or stale run, applying without
  the sandbox is a separate, explicit, audited choice; a failure is never turned into a pass.
- **Pass, Cancel and deadline:** a pass needs the launcher's closing report marked with the run's own
  code (which the tests cannot read) and a normal service exit. Output is read on its own thread, so
  Cancel and the deadline are checked every 0.1 s whether or not the tests print anything; both stop
  the whole service. Inside the service `kill` is denied, so at its own limit the launcher reports and
  exits and systemd ends what is left.
- **Cleanup:** a run's journal record is dropped only once its service is confirmed stopped and its
  storage confirmed unmounted and detached; otherwise the record is kept with what failed, retried at
  the next start and before the next run, and no new validation starts while a workspace is still
  mounted. Only the run's own unit, mount and loop device are touched.
- **"No sockets"** is claimed only as a property of the complete policy plus the qualification
  tests, never of `RestrictAddressFamilies=none` alone.
- **Status:** provisional. Landlock was observed enforced (ABI 8) in a Linux container; the systemd,
  storage and limit controls await the Ubuntu 24.04 desktop feasibility check and qualification
  (connections, host files and escapes, signals and tracing, process/memory/disk/file/time/output
  limits, cleanup after cancel and failures).

## 9. Models and dependencies

The curated catalogue accepts only components with:

- an authoritative source;
- a compatible licence for code, weights, tokenizer, and runtime;
- a pinned version or commit;
- expected files and hashes;
- actual format/runtime compatibility information and labelled published, observed or estimated hardware evidence;
- recorded local modifications;
- no required cloud dependency or silent network behaviour.

Public availability does not prove permission, safety, compatibility, or reproducibility. Prefer
identifiable publishers and recorded upstream assets; reuse available model cards, hashes and source
metadata. Broad model discovery does not require manual team measurement of every candidate.
Third-party conversions and missing evidence are disclosed. Runtime-owned user assets remain distinct
from models endorsed or redistributed by Refinix. Arbitrary remote model code is excluded from the MVP.

Prefer suitable local/open-source components over reimplementing standard
functionality, but reject code copied from other teams' competition entries, unlicensed snippets,
incompatible copyleft obligations, unreviewed installers, and components that
silently contact external services.

Docker base images, Kubernetes workload images, K3s, Redis, clients, and model
runtimes require the same recorded source, pinned version or digest, licence,
hash where available, and runtime network review. `latest` image tags are not
accepted in the reproducible demo path.

## 10. Application and release supply chain

- Follow [releases.md](releases.md) for the planned publish/check/download/install
  contract. A commit on main or a successful CI run is not a published update.
- Published artifacts are immutable, versioned, hashed and authenticated by a
  qualified signing/update mechanism. A checksum alone proves no publisher identity.
  Refinix Beta 0.1's macOS and Windows packages carry no Apple or Microsoft publisher
  signature (user direction, 2026-10-10): first downloads are authenticated by HTTPS from the
  release page and the published SHA-256, the macOS app's ad-hoc seal is checked strictly as
  integrity evidence (not Developer ID or notarisation), each OS's warning is shown before
  download, and in-app updates are authenticated by the Beta TUF root embedded in the package.
- Authenticate metadata and packages against the installed trust root; enforce
  platform/version compatibility and reject unauthorised downgrade/replay. Key
  rotation, compromised-key recovery and stale metadata need documented behaviour.
- Qualify platform signing/notarisation and updater packaging on each supported
  OS/edition before claiming them. Unsigned Beta packages are labelled unsigned everywhere they
  appear (release.json, cards, notes, Settings) and are never presented as signed.
- Every published package carries a native qualification record bound to its exact name,
  size, SHA-256 and embedded identity; a private `--scratch` test build is never published.
  Private test builds alone accept the token-gated qualification control
  (`desktop/qualify_control.py`); a publishable package ignores it.
- Signing credentials remain outside source control/build artifacts and are
  available only to authorised release jobs, never untrusted pull-request code.
- Staging, interruption, low disk space, active jobs, migrations and recovery must
  preserve the working installation/data or provide a verified recovery path.
  Never execute an unverified download or silently discard newer user work.
- Checking/downloading is explicitly connected; offline package import applies
  the same trust checks. No startup/background checks, telemetry or automatic
  model download is introduced. Update failure cannot disable offline operation
  of an otherwise working installed version.
- Release binaries and model weights are not committed to this repository.
  The public site contains no secrets, private data, chats or telemetry; offline
  runtime never depends on that site remaining available.

### 10.1 The Beta update channel as implemented

- **Trust root.** Each Beta package embeds the channel's TUF root and feed configuration. An
  incoming package may ship the same root or a **newer root authenticated from it** (in the kept
  evidence or the client's validated root history); older or unconnected roots are refused, and the
  shipped root file must hash to the identity's record. The publisher refuses a package whose root
  is not already in the feed.
- **Redirects.** Metadata and pointers never follow a redirect. Package downloads may follow at
  most three HTTPS redirects, only to hosts listed in the embedded feed configuration; the bytes are
  authenticated by their signed length and SHA-256 either way.
- **Freshness and replay.** A check or import judges expiry and rollback with the full client. An
  already-verified download installs, resumes and recovers later without a clock, from its kept
  evidence. On Ubuntu the privileged admission repeats the full check, including expiry, on
  root-owned copies against root's own trust state; later privileged steps re-verify those copies
  offline.
- **Online-key compromise.** The snapshot/timestamp keys alone cannot authorise a package. Their
  holder could hide updates for up to the remaining targets lifetime (180 days) or push versions
  ahead until recovery: a new root version, signed offline, replaces those keys, and clients drop
  cached metadata the revoked keys signed (tested).
- **Privileged step (Ubuntu).** Only `/opt/refinix/Refinix` with one fixed first argument, through
  polkit `auth_admin` every time; dispatched before anything else loads; never starts the UI, the
  coordinator or a runtime and never touches user data. The request folder must be the caller's own,
  in their home, writable by nobody else, reached without following links; only fixed names are read,
  sizes are bounded, and nothing the caller supplied is trusted after it is copied. Only the
  `refinix` package changes: Debian's own tools plan and install it under dpkg's front-end lock.
- **Windows installer containment.** The setup is created inside a job object only the helper holds,
  killing every process in it when the helper ends, with no breakaway; if the job cannot be made,
  nothing is installed.
- **Maturity.** Accepted installations never take a preview, from any source; the label's tag, the
  build identity, the signed pointer and the package target must all agree.
- **Custody.** Root and targets keys offline; online keys only in the website repository's
  environments; Windows signing secrets only in the source repository's `beta-sign` environment.

## 11. Repository content

Never commit:

- model weights;
- generated installers or release binaries;
- signing keys, credentials, or tokens;
- private documents or real confidential scans;
- local chats, memory exports, indexes, or application databases;
- environment files containing secrets;
- captured network data containing confidential payloads.

Use synthetic or explicitly approved non-sensitive fixtures.

## 12. Control Center evidence semantics

The Control Center distinguishes enforcement from observation:

| Signal | Meaning |
|---|---|
| Public egress policy: enforced | An identified system or network control is active |
| Public outbound flows observed: 0 | The selected observer saw no public flow in the stated interval |
| External AI/API calls observed: 0 | No known external inference destination was observed in that interval |
| Blocked attempts: N | The named enforcing layer recorded N blocked attempts |
| Trusted LAN connections: N | Allowed local coordinator/worker connections; not public egress |

Unknown or unavailable evidence remains unknown or unavailable. The UI must not
infer enforced from zero observed traffic or display zero external connections
while trusted LAN traffic exists.

## 13. Sovereignty proof

For the demonstration:

1. Finish connected setup before the evidence window.
2. Disable or block public Internet egress while preserving the trusted LAN.
3. Record the enforcing layer, observation method, devices, interfaces, and
   start/end time.
4. Run the real local or distributed workflow.
5. Record node identity, model manifest, tool events, input/output hashes,
   validation, approvals, and network observations.
6. Produce a per-job Sovereign Proof Card.
7. Keep raw captures only when they contain no confidential payload or have an
   approved protected location.

The Proof Card reports what was observed; it does not claim universal security,
penetration resistance, or permanent zero egress.

## 14. Threat-driven checks

| Threat | Required response |
|---|---|
| Unknown device sends work | Reject before job creation |
| Paired worker requests more context | Coordinator sends only the signed task package |
| Model attempts an external call | Sandbox or egress policy blocks it and records evidence |
| Generated path escapes workspace | Reject before read or write |
| Worker retries after disconnect | New attempt ID; final write remains exactly once |
| Confidential data enters logs | Metadata-only default and redacted error handling |
| Model bundle is altered | Checksum mismatch rejects installation |
| Dashboard cannot read network evidence | Display unavailable, never secure or zero |

These checks need executable proof before the related feature is called
verified.
