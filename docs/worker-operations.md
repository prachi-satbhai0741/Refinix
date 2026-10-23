# Managed worker operations

This is the operational starting point for the retained Linux/Kubernetes backend,
not a second task board or a claim of current deployment readiness. Use it during
P02/P07–P12 and later P21/P22 under the [active plan](../tasks.md#numbered-execution-tasks).
The [architecture](architecture.md#kubernetes-execution-profile--alpha) defines the
backend; [security](security.md) owns enforcement; [evaluation](evaluation.md#beta-acceptance)
owns acceptance. Portable desktop peers follow P08/P09 rather than inheriting
Kubernetes or terminal setup as an end-user requirement.

## Before a device action

Prepare one bounded checkpoint from current source and actual host evidence.
Do not replay archived commands unchanged. Required inputs are:

- authorised task/action, actual device role, OS/architecture, shell and checkout;
- source commit and dirty state on requester and target, installed tool/runtime
  versions, current addresses/interfaces and relevant existing service ownership;
- approved image/model/build-tool source, exact version, licence, integrity,
  storage budget and artifact path; missing values are blockers, not placeholders;
- current cluster/network and listener configuration, namespace, bridge CIDR and
  protected unrelated services; historical Jenkins/port/device observations are
  not a fresh inventory;
- credential/trust handover performed privately; never return pairing codes,
  credentials, private keys, certificate bodies or fingerprints in evidence logs;
- exact commands with prerequisites, expected results, scoped rollback and the
  evidence needed to resume. Permission for a build does not authorise deployment.

## Source map and ordered checkpoints

| Stage | Current source | Exit evidence and failure boundary |
|---|---|---|
| Image build | [Dockerfile](../backend/worker-image/Dockerfile), [lock](../backend/worker-image/requirements.lock), [provenance](../backend/worker-image/provenance.json), [digest reader](../scripts/image-digests.py) | Reviewed immutable image, matching architecture, real build output and integrity record; build success does not prove deployment |
| Host isolation | [guard and service units](../deploy/k3s/host/), [namespace](../deploy/k3s/00-namespace.yaml), [runtime policy](../deploy/k3s/30-runtime-egress.yaml) | Current listeners/routes and denied/allowed network checks; no administrative/model endpoint exposed directly to LAN |
| Authenticated worker | [worker manifest](../deploy/k3s/20-worker.yaml), [API](../backend/worker/app.py), [pairing](../backend/worker/pairing.py), [pairing CLI](../backend/worker/pairing_cli.py) | Trusted TLS identity, scoped relationship, authenticated preflight and rejection of unknown/revoked identities |
| Queued execution | [Redis](../deploy/k3s/10-redis.yaml), [executor manifest](../deploy/k3s/40-executor.yaml), [dispatch](../backend/worker/dispatch.py), [executor](../backend/worker/executor.py) | Real receipt before acknowledgement, one execution per accepted attempt, ordered events, cancellation and restart reconciliation |
| Code validation | [validation manifest](../deploy/k3s/50-validation.yaml), [job builder](../backend/worker/jobspec.py), [runner](../backend/worker/validate.py), [packages](../backend/worker/packages.py) | Real restricted Job over a bounded package, limits/egress enforced, matching command/output/exit/hash and approved canonical write |
| Integrated acceptance | [coordinator dispatch](../backend/coordinator/dispatch.py), [Code service](../backend/coordinator/code_service.py), [Proof Card](../backend/coordinator/proof.py), [fixtures](../fixtures/c07/provenance.json) | Named packaged requester/target, end-to-end artifact/patch and failure drills under the Beta matrix; no fake result substitutes for device evidence |

Stages are ordered by the current P-task dependencies. Their source may be
implemented before the associated device checkpoint is accepted. Check current
API prerequisite responses rather than expecting an old blanket `501` or `503`.

## Image identity and build verification

Reuse the pinned build inputs; do not upgrade a runtime/base image while tidying
documentation. Export an OCI archive explicitly: a Docker Archive from `docker
save` does not supply the deployable manifest digest. Keep three identities
separate: **manifest digest** for image references, **config digest** for image
configuration, **archive SHA-256** for file transfer. The digest reader is read-only.

Record the actual native Docker endpoint, selected builder and its pinned image
before building; preserve global Docker context and unrelated workloads. Reuse
the [archived OCI export procedure](archive/c04-ubuntu-build-handoff.md) only after
replacing stale inputs in the reviewed checkpoint. Never substitute a config ID
for a manifest digest or upload to a registry merely to obtain one.

The Dockerfile owns the exact build suite list. It currently runs
`backend.contracts.test_contracts`, `backend.worker.test_worker_runtime`,
`backend.worker.test_worker_app`, `backend.worker.test_executor`,
`backend.worker.test_packages` and `backend.worker.test_validation` with
`--network=none`. Dependency acquisition is a separate connected build step;
a cached test layer is not a fresh test run. Do not preserve old fixed test counts
as a current acceptance threshold.

## Network and pairing safeguards

- Keep Kubernetes NodePort on loopback: `nodeport-addresses=127.0.0.1/32`.
  Do not widen it to a LAN/subnet address. NodePort traffic is DNATed/forwarded;
  an INPUT rule does not protect that path.
- Expose only the selected worker address through `aegisforge-worker-proxy`.
  The `aegisforge-worker-guard.service` uses the guard's `apply worker` operation
  and the compatibility-named `AEGIS_MAC_ADDRESS` variable for the permitted
  requester. The name is not a permanent macOS role requirement.
- Protection is installed before the listener starts. Bind the proxy to the
  selected interface/address, preserve TLS end-to-end and verify other LAN
  addresses cannot connect. Never expose Redis or Kubernetes administration as
  product endpoints.
- Keep the model endpoint loopback-bound. Pod access uses the reviewed guarded
  bridge forwarder; a guessed Docker gateway cannot reach host loopback. Observe
  the bridge CIDR before updating its narrow NetworkPolicy rule. Validation Jobs
  get no runtime/Redis/API/DNS egress exceptions.
- Generate/provision a target identity only after current address/SAN and key
  storage prerequisites are known. The prototype CLI references the private
  operator procedure in [archived C06 identity setup](archive/c06-distributed-execution-handoff.md#b-ubuntu-worker--generate-the-workers-identity).
  Confirm identity before presenting a one-time code; no blind trust-on-first-use
  or disabled TLS checks. P09 replaces manual prototype setup with guided UX.
- Build/import, guarded runtime reachability, authenticated worker preflight,
  pairing and executor deployment are separate checkpoints. Carry approved
  relationship references privately and reject stale or changed identities.

## Acceptance and return evidence

Use [Beta acceptance](evaluation.md#beta-acceptance) for required results. For the
selected managed target, exercise real dispatch, cancellation, stream reconnect,
API/executor loss, revoked trust and ambiguous receipts without duplicate writes.
Observe a real code-validation Job and its denied network/host-file access; YAML
and mocked Kubernetes checks do not establish isolation. Keep scans/Documents
local where currently required and qualify their model separately.

Return only non-sensitive build/version/hash references, commands/procedures,
exit statuses, observed timings/resource bounds, safe fixture results and failure
metadata. Tie the result to a task, attempt, environment and date. Distinguish
source checks, current device observations, historical results and requester
acceptance. Capture egress evidence using the [security procedure](security.md#13-sovereignty-proof).

For focused **offline documentation regression checks**, with the existing
repository environment and authorisation, from the repository root:

```bash
./.venv/bin/python -B -m unittest backend.coordinator.test_dispatch.TestImageBuildRunsTheExecutorSuite deploy.k3s.host.test_guard.TestNodePortIsNotWidened -q
```

These tests read source/docs and use no cluster or real model. Runtime checks
require a separately prepared device checkpoint; do not start services to make
this documentation check pass.

## Recovery and rollback

Prepare rollback before changing a host. Stop a task-owned listener before
removing its guard; do not clear the host firewall, widen exposure, remove all
containers/images or run `docker system prune`. Preserve unrelated services,
existing model stores and coordinator data. Keep image archives, known-good
manifest references and safe evidence until acceptance is resolved.

For a failed image build, remove only the checkpoint's builder/cache and task
output after preserving diagnostics. For deployment failure, stop new admissions,
reconcile in-flight receipts, restore the qualified manifests/configuration and
recheck guards before resuming. Credential rotation/revocation and state recovery
are explicit actions, not automatic deletion of pairing or job stores.
The historical [C05 rollback](archive/c05-ubuntu-deployment-handoff.md#rollback)
records host-specific precautions; it is not permission to uninstall a current
cluster. Do not use broad teardown to repair one failed capability.
