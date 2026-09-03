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
- performs no silent DNS, telemetry, analytics, crash upload, update check, or
  model download;
- keeps local model runtimes on loopback;
- permits only required authenticated worker traffic on the trusted LAN.

The strongest demonstration uses operating-system or network enforcement plus
independent observation. Application logs alone cannot prove that traffic was
blocked.

### Kubernetes worker exposure

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

**Prototype grade, recorded not verified.** No pairing route is implemented.
`backend/contracts` reserves the paths and grants no trust through them, and
nothing below has been exercised. F02 replaces this with finals-grade identity.

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

- Canonical chats, memory, rules, files, approvals, and artifacts remain with
  the workspace coordinator.
- Workers receive only referenced content required for the assigned job step.
- The complete repository, document corpus, chat history, or memory file is not
  transferred by default.
- Attachments and returned artifacts carry hashes.
- Audit logs store metadata by default, not full prompts or confidential
  content.
- Sensitive logging is opt-in, visibly labelled, and subject to retention.
- Temporary task data is deleted after a documented retention period or
  explicit cleanup.
- Redis stores only bounded task envelopes and ephemeral coordination state,
  with expiry and a memory limit. Persistence is disabled for the alpha, and
  payload values are excluded from ordinary logs.
- Pairing, disconnecting, or revoking never silently merges or deletes local
  workspace data.

## 6. Local application data

- Application-data directories are owner-only where supported.
- Secrets, tokens, private keys, and device credentials never enter rules.md,
  memory.md, state exports, or ordinary logs.
- rules.md contains user-editable instructions and policy, not secrets.
- memory.md contains curated durable summaries only and must not automatically
  absorb raw confidential conversations or documents.
- Structured state belongs in the local database, not Markdown files.
- Temporary work belongs in per-job directories with cleanup after success,
  cancellation, or failure.
- Backup and export require an explicit destination and approval.

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
verification.

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
- default-deny ingress and egress, then the minimum DNS, Redis, API, and model
  traffic explicitly allowed.

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

- Every published installer has a version and SHA-256 checksum.
- Production installers should be signed for each supported platform.
- Unsigned prototypes are labelled honestly with manual verification steps.
- Signing credentials remain outside source control and build artifacts.
- Release binaries and model weights are not committed to this repository.
- The public site never contains secrets, private data, chats, or telemetry.
- Offline runtime never depends on the public site remaining available.

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
