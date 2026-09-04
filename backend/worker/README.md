# Worker service — AF-003 / C04

Executes one bounded job step for a coordinator. It owns **no canonical state**:
the coordinator persists the job, this service runs an attempt and reports
events. Losing every worker record loses nothing the coordinator needs.

## The frozen `/v1` surface

Implemented exactly as reserved in [the contract](../contracts/README.md):

| Route | Behaviour |
|---|---|
| `GET /v1/health` | `Node` record — health, capabilities and models, or `unknown` when nothing was observed |
| `GET /v1/capabilities` | The same `Node` record |
| `POST /v1/jobs` | `JobEnvelope` → `202` with the initial `Attempt`, recorded and enqueued before acknowledging |
| `GET /v1/jobs/{job_id}?attempt_id=` | The current worker `Attempt` |
| `GET /v1/jobs/{job_id}/events?attempt_id=` | SSE for that attempt |
| `DELETE /v1/jobs/{job_id}?attempt_id=` | `202`, records cancellation and stops execution |
| `POST /v1/pairing/confirm` | **`501`** — reserved pending OD-06 |
| `DELETE /v1/pairing/{relationship_id}` | **`501`** — reserved pending OD-06 |

The `attempt_id` query is required on poll, stream and cancel so a delayed
request cannot target a newer retry.

## The job routes are fail-closed

`POST /v1/jobs`, poll, events and cancel all return **`503 unavailable`** with a
typed reason. Two prerequisites do not exist:

- **OD-06 pairing** — nothing can confirm a relationship is genuine, so a
  claimed `relationship_id` under a shared bearer token proves nothing.
- **AF-005 durable receipt** — the contract requires a job to be persisted and
  enqueued *before* acknowledging. An in-memory dictionary is not that, and
  returning `202` for it would be a claim the worker cannot honour.

The execution path is implemented and covered by offline checks so C05/C06 can
enable it. Nothing in the application populates the relationship registry — no
route, no environment variable — so there is no deployable bypass. Health and
capabilities stay available for preflight and advertise **no capability** while
the worker cannot accept work.

## Honesty rules this service follows

- **It will not start without a credential.** `AEGIS_WORKER_TOKEN` is required,
  so the worker cannot accidentally run open on a LAN. Comparison is
  constant-time.
- **Pairing is not implemented.** Both pairing routes return `501` rather than
  quietly granting trust. How a credential is issued is OD-06 work.
- **A model is advertised only with a real manifest digest.** If the runtime
  does not report one, the model is not advertised — no placeholder digest.
- **Health is observed, never assumed.** Without an observation the `Node`
  reports `unknown` with no measurements, as the contract requires.
- **Truncation and shifting are disabled**, so an oversized prompt is rejected
  rather than silently trimmed.
- **Errors are metadata only** — a `Failure` code, a short message and
  `retryable`. Never a prompt, path, credential, traceback or Pydantic input.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `AEGIS_WORKER_TOKEN` | *(none — required)* | Bearer credential; the service refuses requests without it |
| `AEGIS_RUNTIME_HOST` | `http://127.0.0.1:11434` | Where the model runtime is. No default points off-host. |
| `AEGIS_MODEL` | `qwen3.5:4b-q4_K_M` | Catalogue model |
| `AEGIS_NUM_CTX` | `4096` | The Ubuntu worker keeps 4096 until it measures its own window; the Mac coordinator separately runs 8192 |
| `AEGIS_NUM_PREDICT` | `2048` | Reply limit |
| `AEGIS_NODE_ID` | zero UUID | Node identity |

## Checks

```bash
PYTHONPATH=. ./.venv/bin/python -m unittest backend.worker.test_worker_runtime
```

Ten offline checks: bounded settings, the limit classifier (including that a
capped reply after a large prompt is an **output** stop, not a context one),
failure handling, cancellation and honest probing. FastAPI lives only inside the
pinned image, so the API surface is checked at **build time** with
`--network=none` and by the Ubuntu build handoff.

Build assets and the image itself are in
[`backend/worker-image`](../worker-image/README.md).
