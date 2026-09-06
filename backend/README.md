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

## Status: contract draft plus a running coordinator

The [shared contracts](contracts/README.md) contain versioned Python records,
protocol constants, synthetic examples, a schema exporter and runnable checks.
Their **eight** contract checks pass; the contract is **not frozen** — its
consumer-integration gate is C05.

The [coordinator](coordinator/README.md) now exists and runs: SQLite state, an
Ollama runtime adapter, a loopback API and the served interface, with **73**
offline checks passing in total. It is a real contract consumer — every job,
attempt and event is validated through `contracts.v1` before it is written.

**Still absent:** the worker service, workflow runner, policy gate, router,
Redis coordination and the Kubernetes profile. Each of those surfaces reports
itself unavailable in the interface rather than implying it works.

[Architecture technology direction](../docs/architecture.md#8-working-technology-direction)
settles Server-Sent Events, coordinator SQLite, Docker-built images, single-node
K3s, and Redis 7.2.x for the alpha. FastAPI remains the direction for the
**worker API** at C04, where a pinned install is part of the image build; the
C03 coordinator uses the Python standard library because adding a dependency is
a setup checkpoint rather than implementation. That deviation is recorded in
architecture.md. Code must implement the shared `/v1` contract and one real
model path before a second runtime, framework, or database appears.

Initial source is split only by the real process boundaries: shared contracts,
coordinator, worker API/executor, runtime adapter, and runnable checks. Do not
create a generic plugin framework or one package per future capability.

Scaffolding begins with AF-001 and must stop at the first real Service-to-Pod
model response before any optional package or abstraction is added.
