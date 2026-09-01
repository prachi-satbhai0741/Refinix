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
lists Python/FastAPI, Server-Sent Events, and SQLite as candidates, not settled
choices. One real local inference path and one paired-worker path come before a
message broker, generic agent framework, runtime plugin system, or vector
database.

Scaffolding begins only after the team accepts the v1 baseline and first runtime
decision.
