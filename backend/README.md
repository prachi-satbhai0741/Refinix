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

## Status: no scaffolding yet

There is no pyproject.toml, source tree, or dependency set.

[Architecture technology direction](../docs/architecture.md#8-working-technology-direction)
settles Python/FastAPI, Server-Sent Events, coordinator SQLite, Docker-built
images, single-node K3s, and Redis 7.2.x for the five-day alpha. The first code
must implement the frozen `/v1` contract and one real model path before a second
runtime, framework, or database appears.

Initial source is split only by the real process boundaries: shared contracts,
coordinator, worker API/executor, runtime adapter, and runnable checks. Do not
create a generic plugin framework or one package per future capability.

Scaffolding begins with AF-001 and must stop at the first real Service-to-Pod
model response before any optional package or abstraction is added.
