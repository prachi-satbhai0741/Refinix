# Worker service — AF-003 / C04

Executes one bounded job step for a coordinator. It owns **no canonical state**:
the coordinator persists the job, this service runs an attempt and reports
events. Canonical state stays on the coordinator, but worker receipts/leases
must be retained or reconciled to resolve uncertain work safely.

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
| `POST /v1/pairing/confirm` | Redeems a one-time code for a scoped relationship credential |
| `DELETE /v1/pairing/{relationship_id}` | Revokes the authenticated relationship and fences its work |

The `attempt_id` query is required on poll, stream and cancel so a delayed
request cannot target a newer retry.

## The job routes are fail-closed

The API accepts supported bounded work only with valid relationship authority and
available configured receipt/package/runtime prerequisites. Redis dispatch commits
the durable receipt before acknowledgement; the separate executor claims leases,
emits events and reconciles cancellation/restart. Missing prerequisites still fail
closed. The [source audit](../../docs/evaluation.md#beta-source-audit) records the
remaining receiver-wide admission and portable packaging gaps; current deployment
is not inferred from source or an older image.

## Honesty rules this service follows

- **It will not start without a credential.** `AEGIS_WORKER_TOKEN` is required,
  so the worker cannot accidentally run open on a LAN. Comparison is
  constant-time.
- **Pairing is scoped and revocable.** The prototype uses a one-time code over
  pinned TLS; ordinary-user graphical setup remains [P09](../../tasks.md#numbered-execution-tasks).
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

The runtime suite covers bounded settings, failure/cancellation and probing.
`test_worker_app.py`, `test_executor.py`, `test_packages.py` and
`test_validation.py` cover the API/dispatch and validation paths using synthetic
inputs and test doubles. The pinned image build and source CI include worker
checks; their existence is not an observed current build/deployment pass. See
[evaluation](../../docs/evaluation.md#current-status) for recorded results and gaps.

Build assets and the image itself are in
[`backend/worker-image`](../worker-image/README.md).
