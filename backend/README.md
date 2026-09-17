# backend

Local harness and worker service boundary.

## Intended boundary

From [architecture.md](../docs/architecture.md):

- **Local service** — owns workspace state and serves the loopback-only desktop
  API.
- **Coordinator** — owns canonical chats, rules, context, approvals, jobs,
  artifacts, and final writes for one workspace.
- **Worker service** — executes one bounded job step on one complete model and
  may run locally, on a paired device, or headlessly on a private server.
- **Workflow runner** — executes the named Chat, Documents, and Code contracts.
- **Policy gate** — enforces automatic, approval-required, and denied actions.
- **Router and scheduler** — selects only trusted, healthy, compatible nodes.
- **Runtime adapter** — integrates one existing local model runtime first.
- **Redis coordination** — carries bounded dispatch, lease, heartbeat,
  cancellation, cache, and event state between worker API and executor Pods;
  it is not canonical storage.
- **Kubernetes profile** — runs the Docker-built worker API and executor as
  Deployments behind a Service and code validation as short-lived Jobs.
- **Validators and proof events** — verify outputs and feed the task surfaces
  and Control Center.

An installation does not have a permanent coordinator or worker identity. It
always owns a local workspace and may accept bounded work from a paired
workspace without merging canonical state.

The [security boundaries](../docs/security.md) apply throughout: offline
runtime has no required Internet traffic, runtimes bind to loopback, LAN
services are authenticated and encrypted, worker writes remain inside assigned
temporary workspaces, and code execution is network-disabled and resource
bounded by default.

## Current implementation boundary

The shared contracts, coordinator, worker API/executor, pairing/revocation,
Code policy/proposals/validation, document workflows, FTS5 and proof builder exist.
Docker/K3s/Redis implement the retained managed execution profile. These are
source observations, not fresh deployment results; see the
[current audit](../docs/evaluation.md#beta-source-audit) for paths, tests and gaps.

The [task graph](../tasks.md#numbered-execution-tasks) qualifies these paths for
Beta before adding wider production support. Portable packaged receivers,
receiver-wide admission, automatic model/device placement and full model lifecycle
remain implementation work. Reuse the current process boundaries and contract;
no generic plugin framework, new database or alternate harness is required.
