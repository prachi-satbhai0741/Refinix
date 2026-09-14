# Security, Privacy, and Supply Chain

## Status and authority

This document owns security implementation boundaries under
[prd.md](prd.md). Planned controls are not verified controls. A static review
cannot prove isolation, secure storage, zero egress, or resistance to attack.

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

## 9. Models and dependencies

The curated catalogue accepts only components with:

- an authoritative source;
- a compatible licence for code, weights, tokenizer, and runtime;
- a pinned version or commit;
- expected files and hashes;
- supported runtime and hardware evidence;
- recorded local modifications;
- no required cloud dependency or silent network behaviour.

Public availability does not prove permission, safety, compatibility, or
reproducibility. Arbitrary remote model code is excluded from the MVP.

Prefer suitable local/open-source components over reimplementing standard
functionality, but reject competing SIH submissions, unlicensed snippets,
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
- Authenticate metadata and packages against the installed trust root; enforce
  platform/version compatibility and reject unauthorised downgrade/replay. Key
  rotation, compromised-key recovery and stale metadata need documented behaviour.
- Qualify platform signing/notarisation and updater packaging on each supported
  OS/edition. Ad-hoc/unsigned prototypes are labelled and are not release proof.
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
