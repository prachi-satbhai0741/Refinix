# Evaluation, Prototype Plan, and Demonstration

## Current status

The repository has the shared contract draft with passing local schema and
lifecycle checks, documented in [AF-001](../backend/contracts/README.md), and a
**running local coordinator** — Chat and a minimum Control Center over SQLite
state and one local model, with restart reconciliation and bounded context
selection. There is still no worker, cluster, Documents or Code workflow,
approval path, model bundle or installer. Product capabilities in this document
remain planned until observed evidence changes their state.

## 1. Evidence labels

Use only:

- Planned: accepted requirement with no implementation evidence
- Prototyped: a narrow path ran but does not meet the full acceptance contract
- Verified: the documented check ran on the stated environment and passed
- Deferred: intentionally outside the current release
- Rejected: evaluated and intentionally not selected

Record the date, device, operating system, runtime, model revision, command or
procedure, input class, result, and known limitations. Another agent's summary,
a screenshot without provenance, or a static code inspection is not execution
evidence.

## 2. Task acceptance sequence

The purpose of the alpha is to answer the risks that could kill the product,
not to imitate every ChatGPT feature.

Execute these outcomes through the [numbered tasks and named human
checkpoints](../tasks.md#numbered-execution-tasks). The implementer builds, the reviewer checks the actual diff and
results, and execution stops for the named human action. A reported installation
or code-review pass does not satisfy a runtime gate. Verify the returned evidence
before continuing within the authorised scope.

Choose focused checks before each chunk. Reuse evidence only when its source and
environment still apply; rerun affected checks after changes and the required
end-to-end path at task acceptance gates. Add broader checks only for a concrete remaining
risk. After each build/review cycle, explain what was built, what was observed,
what remains unverified and the next named action using the
[team report](../tasks.md#verification-and-team-explanation).

### C05: Contracts and local execution

- Freeze the node, job, attempt, event, approval, HTTPS, Redis, and proof
  contracts.
- Pin K3s, Redis 7.2.x, base-image, worker-image, runtime, and model evidence.
- Start one single-node K3s cluster on the authorised Ubuntu host confirmed at
  the human checkpoint — the **Ubuntu worker** in the first configuration.
- Deploy Redis behind ClusterIP and the Docker-built worker behind a Kubernetes
  Service.
- Complete one real model response from a Ready worker Pod.
- Persist the job and attempt in coordinator SQLite and show it in the smallest
  local browser UI.

Exit evidence:

- model, image, K3s, Redis, and dependency source/licence/revision recorded;
- Pod, Service, runtime, and prompt are reproducible;
- no mocked inference in the claimed path.

### C06: Distributed execution

- Connect worker API and executor Pods through Redis Streams.
- Add bounded retention, acknowledgement, pending-work recovery, cancellation,
  heartbeats, and leases.
- Authenticate the Mac coordinator to the worker Service over HTTPS.
- Route one real prompt through the Service and Redis to an executor Pod.
- Stream events back and show the request, model, Pod, queue, and routing reason.
- Complete the smallest guided preflight that selects the curated manifest,
  verifies dependencies, and runs the real self-test.
- Stop the cluster and prove the Mac's canonical SQLite history remains usable.

Exit evidence:

- reproducible Mac-to-Service-to-Redis-to-Pod-to-Mac path;
- bounded request and streamed response captured;
- Redis or cluster loss does not lose canonical history.

### C09: Signature workflows

- Complete the fixed Documents path from scan to page-linked extraction,
  grounded drafting, and validated Word artifact.
- Complete the fixed Code path from bounded repository context to patch.
- Run code validation as a restricted short-lived Kubernetes Job Pod.
- Preserve hashes, uncertainty, command output, exit status, and cleanup state.
- Use the same Service, Redis, event, and approval contracts for both paths.

Exit evidence:

- one openable cited Word artifact;
- one applicable patch with observed sandbox evidence;
- no direct canonical write from a worker or Job Pod.

### C11: Concurrency, approvals and offline evidence

- Run Documents and Code attempts concurrently through separate Redis consumers
  and Pods.
- Enforce approval before canonical writes and make retries idempotent.
- Apply and verify default-deny Pod egress plus required cluster/LAN allowances.
- Produce Proof Cards from SQLite, Redis, Kubernetes, model, validation,
  integrity, approval, and network observations.
- Record sequential and concurrent timing honestly.

Exit evidence:

- both real artifacts complete concurrently;
- denial writes nothing and retry creates no duplicate final write;
- the real run records no observed public outbound flow in the named window.

### C13: Recovery and candidate acceptance

- Enforce or physically isolate public egress while preserving the trusted LAN.
- Run the real signature workflow.
- Capture trustworthy network, device, model, tool, integrity, and approval
  evidence.
- Exercise cancellation or one worker interruption.
- Exercise executor-Pod loss, Redis restart, and cluster loss.
- Complete third-party notices for selected components.
- Replace projected numbers with measured results.
- Rehearse and record a backup demonstration.

Exit evidence:

- reproducible offline run;
- per-job Proof Card;
- benchmark table and limitations;
- no unfinished feature presented as working.

When a task passes, proceed to the next eligible, authorised task after
clearing its human prerequisites. Only after C09 passes may the team add the
bounded image-understanding and calculation-with-steps stretch; only after C11
passes may it add a second executor replica. Additional scope needs requester
approval. Do not add another
framework, cluster, broker, runtime, or product surface.

## 3. Alpha acceptance

- [ ] The authoritative SIH26117 wording and IP/submission terms are retained.
- [ ] One installation creates a local workspace without a permanent role
      choice.
- [ ] Guided setup selects, installs or imports, verifies, and self-tests one
      real main engine.
- [ ] A real local chat completes.
- [ ] The pinned Docker worker image runs in a Ready Kubernetes-managed Pod.
- [ ] A Kubernetes Service exposes only the authenticated worker API to the
      trusted LAN; Redis remains cluster-internal.
- [ ] Redis dispatches one bounded attempt to an executor and reports queue,
      pending, acknowledgement, heartbeat, and cancellation state.
- [ ] One real prompt runs through the Kubernetes Service and streams back.
- [ ] The UI or logs show original request, device, model, route, and status.
- [ ] Stopping Redis or the cluster leaves canonical SQLite history intact.
- [ ] One bounded agent workflow produces a validated output.
- [ ] Consequential final write requires a recorded approval.
- [ ] Runtime endpoints and public-egress evidence are documented honestly.
- [ ] Repository instructions reproduce the claimed path.

## 4. Finals acceptance

- [ ] Chat, Documents, Code, and Control Center use one harness.
- [ ] The same installation works standalone and can use trusted workers.
- [ ] At least two task types route automatically.
- [ ] Documents and Code jobs run concurrently on different eligible nodes.
- [ ] OCR preserves source hash, page mapping, and uncertainty.
- [ ] Local retrieval returns page or section citations.
- [ ] The approval note opens as a valid Word artifact.
- [ ] Code execution uses a bounded network-disabled workspace.
- [ ] The patch, validation command, output, and exit status are returned.
- [ ] The coordinator performs no duplicate final write after retry.
- [ ] Pairing and revocation reject an invalidated worker.
- [ ] No external inference occurs during the offline evidence window.
- [ ] Installed models expose source, licence, revision, and integrity state.
- [ ] The Control Center distinguishes trusted LAN traffic from public egress.

## 5. Measurement plan

Initial targets are hypotheses:

| ID | Measure | Initial target |
|---|---|---:|
| M-01 | External inference calls in offline demo | 0 |
| M-02 | Corrupted file transfers accepted | 0 |
| M-03 | Real paired workers | At least 1 alpha, 2 where available for finals |
| M-04 | Concurrent independent workflow types | At least 2 for finals |
| M-05 | Routing accuracy on curated examples | At least 90% |
| M-06 | Worker-loss detection | Under 5 seconds |
| M-07 | Duplicate final writes after retry | 0 |
| M-08 | Distributed makespan improvement over sequential baseline | Positive and reported honestly |
| M-09 | Ready worker Pods behind the Service | At least 1 |
| M-10 | Canonical records lost after Redis restart | 0 |
| M-11 | Redis pending attempt reclaimed after executor loss | 1 fixed failure fixture succeeds |

Measurement rules:

- use the same task set for standalone and distributed comparison;
- record time to first output and end-to-end completion separately;
- report cold and warm behaviour separately;
- record queue time, RAM, VRAM, and temperature where reliable;
- score code, OCR, retrieval, and document quality separately;
- do not publish a universal AI accuracy number;
- do not claim energy, thermal, or cost improvement without comparable evidence;
- report a slower distributed result if that is what occurred.

## 5.1 OD-03 runtime comparison

OD-03 asks whether a direct engine provides enough benefit to justify another
adapter. The recorded macOS comparison uses **Ollama's bundled `llama-server`**,
not a separately installed upstream llama.cpp release. It measures one fixed
prompt and does not isolate wrapper overhead or rank runtimes generally.

**Method** — [`scripts/od03_runtime_comparison.py`](../scripts/od03_runtime_comparison.py),
standard library only, no benchmark framework. It never starts a service: if the
target server is not already listening it exits with instructions.

Requested settings for the macOS comparison:

| Setting | Value |
|---|---|
| Model file | the same GGUF — the Ollama blob `sha256:81fb60c7…` is a real GGUF, so `llama-server -m <blob path>` loads identical weights with no second download |
| Request shape | a **chat** request on both sides — Ollama `/api/chat`, llama-server `/v1/chat/completions` — so the model's own chat template is applied to both. A raw completion against a templated chat is not a comparison. |
| Prompt | one fixed user message, compiled into the script |
| Context | `num_ctx` / `-c` 4096 — the value held constant for **this comparison**; the coordinator now runs 8192, measured separately in [§5.2](#52-context-window-sizing--macos-coordinator-2026-09-04) |
| Output limit | `num_predict` / `max_tokens` 128 |
| Sampling | `temperature` 0, `seed` 42; direct-server launch also sets `top_k` 20, `top_p` 0.95, `min_p` 0, `presence_penalty` 1.5 to match the selected model's settings |
| GPU allocation | macOS direct-server launch requests `--n-gpu-layers all`; Ollama chooses placement. Ubuntu's separately recorded partial GPU allocation is not held equal to the Mac. |
| Thinking | off on both — Ollama `think: false`, llama-server `chat_template_kwargs.enable_thinking: false`. Separate reasoning output or a leaked thinking marker flags the run as non-comparable; TTFT includes the first token from either channel. |
| Prompt cache | each runtime's **default**, untouched. Disabling it on one side only would make the warm runs measure different work. |

The exact request body is echoed into the result JSON. Server launch settings
are recorded below because they cannot be inferred from that body alone.

**Failures cannot become evidence.** A malformed line, a streaming error object,
a missing terminal record or a missing metric aborts the run with a non-zero
exit; no partial result reaches a median.
[`scripts/test_od03_parser.py`](../scripts/test_od03_parser.py) exercises those
paths offline, including separate reasoning and absent or invalid generation
timing — no server, no model.

**Cold and warm are separated.** `--unload-first` makes a preparation inference
with `keep_alive: 0`, waits three seconds, then records one cold and three warm
requests with `keep_alive: "10m"`. The preparation request is not in the four
recorded runs. A forced model reload is not a cold operating-system disk cache.
For the direct server, model loading occurs before requests; its first-request
TTFT excludes model load and cannot be compared to Ollama's cold figure.

**Cancellation was not exercised in C02.** The recorded requests demonstrate
streaming with configured context and output limits; they do not demonstrate
user cancellation, runtime work stopping after a disconnect, or a persisted
cancelled attempt. The script's transport timeout is not cancellation evidence.
Application cancellation is unimplemented; C06 / AF-005–AF-007 owns its
implementation and the device cancel exercise in [tasks.md](../tasks.md#numbered-execution-tasks).

**Provenance:** the earlier coordinator Ollama measurement is retained from
the C02 execution record. The Ubuntu inventory, checksums, inference JSON and
follow-up memory output, plus the Mac direct-engine startup log and inference
JSON, were returned by the requester on 2026-09-03. Closeout reviewed those
outputs without repeating inference or querying either live service.

### Measured — Ollama on the macOS coordinator, 2026-09-03

`ollama` 0.32.14, `qwen3.5:4b-q4_K_M`, four runs through `/api/chat`.

| Phase | Time to first token | Generation | Model load | Prompt eval |
|---|---:|---:|---:|---:|
| Cold — `cold_after_forced_unload`, **includes model load** | **2.504 s** | 37.8 tok/s | 2.300 s | 0.199 s |
| Warm (median of 3) | **0.225 s** | 37.9 tok/s | 0.175 s | 0.048 s |

All four runs returned 89 tokens / 598 characters, `done_reason: stop`, and
**one** response SHA-256 (`c400b210dc824a26…`) — so the output was byte-identical,
established by hash rather than inferred from counts. Thinking was suppressed on
every run. The historical report called its RSS samples 3.83 → 3.90 GB; the old
collector actually selected the largest name-matched process and divided KiB
by 1024. Those samples are not aggregate or peak RAM and are excluded from
memory comparisons. VRAM is not separately reported on Apple unified memory.

Generation speed is effectively identical cold and warm, so the whole 2.279 s
time-to-first-token penalty sits before generation: **93.2 % is model load
(2.124 s) and 6.6 % is prompt evaluation (0.151 s)**, an ~11.1× difference.

An earlier run of this measurement used the untemplated `/api/generate` endpoint
and recorded ~29.3 tok/s. It is superseded, not averaged in: it did not hold the
chat template constant, so it is not comparable to a `llama-server` chat request.

Also observed on this device: the server listens on `127.0.0.1:11434` only
(`lsof`/`netstat`), not on a wildcard address.

### Measured — Ollama on the Ubuntu worker, 2026-09-03

Ollama **0.33.2**, Ubuntu 24.04.4 LTS / Linux `7.0.0-30-generic`, x86_64,
Python **3.12.3**, RTX 2050 4096 MiB. JSON timestamp
`2026-09-03T09:39:24Z`; model and settings match the catalogue entry.

| Recorded request | TTFT (s) | Generation (tok/s) | Load (s) | Prompt eval (s) | Generation duration (s) | Total (s) |
|---|---:|---:|---:|---:|---:|---:|
| Cold after forced unload, includes load | 16.0149 | 10.16 | 14.6906 | 1.3155 | 8.7597 | 24.7737 |
| Warm 1 | 0.5012 | 10.28 | 0.0029 | 0.3151 | 8.6534 | 9.1532 |
| Warm 2 | 0.3267 | 10.14 | 0.0025 | 0.3168 | 8.7742 | 9.1000 |
| Warm 3 | 0.3369 | 9.84 | 0.0022 | 0.3266 | 9.0451 | 9.3808 |
| Warm median | **0.3369** | **10.14** | — | — | — | — |

All four returned 89 tokens / 605 characters, no reported thinking output,
nonempty visible output and `done_reason: stop`. All share SHA-256
`6264a0c46c55fc537bba65a00f2bbace642b6b98fe3938c7e3e0c3024858aab9`.
The raw response text was not supplied for quality scoring. This hash differs
from the Mac output; determinism is observed within each run set only.

The follow-up `/api/ps` reported the catalogue manifest digest, context 4096,
model allocation **3,727,561,846 bytes** and GPU allocation
**2,217,780,180 bytes**. These are runtime allocation fields, not process RSS
or an offloaded-layer count. The accompanying process snapshot was:

| Process | PID / parent PID | RSS from `ps` (KiB) | RSS (MiB) |
|---|---|---:|---:|
| Ollama daemon | 2052 / 1 | 56,004 | 54.7 |
| Model runner (`llama-server`) | 17155 / 2052 | 2,209,224 | 2157.4 |

The benchmark's older `rss_mb: 69.7` measured only a daemon candidate and is
**invalid as runner or total RAM**. Its NVIDIA sample reported the runner at
2948 MiB, taken at a different time from `/api/ps`; do not equate these memory
categories or add them. The repaired collector emits `processes` with PID,
parent PID, name, `rss_mib` and PID-matched `vram_mib`. It lists all matching
runtime candidates, does not attribute them to an endpoint or sum shared
memory, and leaves unavailable metrics null. It replaces the misleading
top-level `rss_mb` and raw-string `vram_mb` fields for future runs.

### Measured — bundled engine on the macOS coordinator, 2026-09-03

macOS **26.6.2**, arm64, Python **3.14.6**. The installed binary is
`/Applications/Ollama.app/Contents/Resources/llama-server`, from Ollama
**0.32.14**. Its version output reports **0.1.0-dev**, build **1**, commit
**7e4c0a968**, AppleClang 21.0.0.21000099 / Darwin arm64; binary SHA-256 is
`05b7f7f8a4047f3012ce094b6e78a39a9c737a0b221524a148021c210447b85d`.
This fingerprints the installed MIT-licensed bundle, not an independently
verified upstream release. No runtime download, build or local modification
was needed; the model's Apache-2.0 provenance remains in the catalogue.

JSON timestamp `2026-09-03T09:57:13Z`:

| Recorded request | TTFT (s) | Generation (tok/s) | Prompt (ms) | Generation (ms) | Cached prompt tokens |
|---|---:|---:|---:|---:|---:|
| First after server start, **excludes load** | 0.1824 | 36.67 | 173.503 | 2399.867 | 0 |
| Warm 1 | 0.0988 | 36.50 | 58.744 | 2411.145 | 24 |
| Warm 2 | 0.0502 | 36.61 | 48.646 | 2403.832 | 24 |
| Warm 3 | 0.0495 | 36.43 | 48.131 | 2415.372 | 24 |
| Warm median | **0.0502** | **36.50** | — | — | — |

Each response has 89 completion tokens, 28 prompt tokens, 598 visible
characters, zero reported reasoning and no thinking markers. All four share
SHA-256 `c400b210dc824a2699b26f8a815e7e3d65bdd8a4de91d163421a1da7f9d5c5ba`.
The earlier Mac Ollama record retained that prefix and matching counts; full
cross-runtime identity is not independently established by the prefix alone.
Legacy process samples were 3213.5 and 3368.2 MiB, not aggregate or peak RAM.

The startup log showed readiness at elapsed **1.301843 s**, but the first
request arrived at **44.377747 s** after a manual terminal switch. There is no
controlled startup-to-first-answer result; neither adding readiness to request
TTFT nor including the operator's delay would establish one. The log also
records Ollama-format qwen35 compatibility fixes, disabled mmap for transformed
tensors, token metadata overrides and unused tensors. Successful requests
demonstrate this bounded path, not general model correctness.

Warm direct-engine TTFT was lower than the earlier Mac Ollama median by
174.8 ms, while generation stayed roughly 36–38 tok/s. Warm direct requests
cached 24 of 28 prompt tokens, so this is repeated-prompt latency, not latency
for new prompts. Different runtime implementations, versions across devices
and a small sequential sample limit broader conclusions.

### Reproduce the recorded path at an authorised human checkpoint

These are retained reproduction instructions, **not a request to rerun C02**.
The requester stopped the temporary Mac server with Ctrl+C. The deferred
comparisons require a future approved measurement if they become necessary.

**Ubuntu worker — bash, `~/SIH/AegisForge`**, with existing loopback Ollama and
the catalogue model already hash-checked:

```bash
cd ~/SIH/AegisForge &&
NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
python3 -B scripts/od03_runtime_comparison.py \
  --target ollama --model qwen3.5:4b-q4_K_M --unload-first
```

**macOS coordinator — zsh, `/Users/adityatadge/Documents/GitHub/AegisForge`.**
For that device's Ollama baseline:

```zsh
cd /Users/adityatadge/Documents/GitHub/AegisForge &&
NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
python3 -B scripts/od03_runtime_comparison.py \
  --target ollama --model qwen3.5:4b-q4_K_M --unload-first
```

To reproduce the direct-engine run, first check
`lsof -nP -iTCP:8080 -sTCP:LISTEN`; proceed only
if the command succeeds with no listener or exits 1 with no output. Any
listener or other error requires inspection. Do not terminate another process.
In one terminal, release Ollama's model, then launch the installed bundle:

```zsh
curl -q --noproxy '*' --fail --silent --show-error --max-time 30 \
  http://127.0.0.1:11434/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.5:4b-q4_K_M","keep_alive":0,"stream":false}' &&
/Applications/Ollama.app/Contents/Resources/llama-server \
  --model "$HOME/.ollama/models/blobs/sha256-81fb60c7daa80fc1123380b98970b320ae233409f0f71a72ed7b9b0d62f40490" \
  --host 127.0.0.1 --port 8080 \
  --cors-origins localhost --no-cors-credentials \
  --ctx-size 4096 --parallel 1 --n-gpu-layers all \
  --temp 0 --seed 42 --top-k 20 --top-p 0.95 --min-p 0 \
  --presence-penalty 1.5 --reasoning off \
  --sse-ping-interval -1 --perf --offline --no-ui
```

Wait for the listening message. In a second terminal:

```zsh
cd /Users/adityatadge/Documents/GitHub/AegisForge &&
NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
python3 -B scripts/od03_runtime_comparison.py --target llama-server
```

Return startup/version output and the full JSON, including errors. Four
successful recorded requests should have nonempty visible output, suppressed
thinking and valid timings. Stop the temporary server with Ctrl+C afterward;
Ollama loads its model again on the next authorised request. These flags are
for this measured bundle, not unverified Ubuntu or upstream builds.

### Finding that changes the bounded settings

`qwen3.5:4b-q4_K_M` is a **thinking model**. With thinking left on it spent the
whole output budget in its reasoning channel and returned an **empty** visible
answer — at `num_predict` 128 *and* at 512, both stopping on `length`. With
`think: false` the same prompt completed in **89 tokens** and stopped naturally.

A bounded output limit is therefore not sufficient on its own: `think: false`
is required, or a C03 job would report success while returning nothing. This is
recorded in the [bounded execution settings](model-catalog.md#bounded-execution-settings-for-the-first-path).

### Deferred by requester at C02 closeout, 2026-09-03

| Run | Device | Evidence still missing |
|---|---|---|
| Direct-engine comparison | Ubuntu worker | Direct-launch compatibility, controlled allocation and timing; its bundled runner exists, but was not tested independently. Port 8080 was occupied in inventory. |
| Comparable cold-start figure | macOS coordinator / Ubuntu worker | Controlled server-start-to-first-answer timing, including model loading, without a manual gap |

**Ollama remains selected.** These explicit deferrals do not block C02
acceptance and do not become successful measurements. A separate upstream
llama.cpp release, Windows, output quality, application persistence, container
GPU access, trusted-LAN pairing and zero-egress operation are not established
by the native runtime checks above. C03 begins only after closeout acceptance
and its own authorisation.

## 5.2 Context window sizing — macOS coordinator, 2026-09-04

Request-local settings only; no service or install was changed. Same installed
model, synthetic near-boundary input with a fact planted at the start.

| Setting | Prompt tokens | Cold TTFT | Warm TTFT | Resident bytes | Early fact retrieved |
|---|---:|---:|---:|---:|---|
| `num_ctx` 4096 | 919 | 3.796 s | 0.196 s | 3,144,910,109 | yes |
| `num_ctx` 8192 | 919 | 3.409 s | 0.198 s | 3,375,617,800 | yes |
| `num_ctx` 8192, larger input | 3052 | 4.543 s | 0.203 s | 3,375,617,800 | yes |

**8192 adopted for the macOS coordinator.** It costs about **220 MiB** more
resident memory, warm time-to-first-token is unchanged, and a fact at the start
of a 3052-token prompt was still answerable. The Ubuntu worker keeps 4096 until
it is measured at its own device checkpoint; the Mac repair was not held for it.

### Context selection observed end to end

A seven-turn synthetic conversation on the coordinator drove the selector past
its budget. Estimated input rose 35 → 1690 → 3376 → 5063 → 5132 of a
5168-token budget, then omission began: 4 messages omitted at turn 6, 6 at
turn 7, each with a visible notice. Saved history stayed at 16 messages
throughout — nothing was trimmed from storage.

When the turn carrying a planted fact had been omitted, the model answered
**"I no longer have it"** rather than inventing the value. That is the intended
behaviour: omission is visible and its consequence is honest.

**Estimate versus measurement.** The pre-flight estimate is characters ÷ 3.0
and was conservative for this fixture: at turn 6 it predicted 5053 tokens where
the runtime reported **2832**. This is not a bound for other inputs or scripts.
Runtime-reported prompt and output counts are recorded separately as measured
values; the enforcement check below covers underestimates.

## 5.3 C03 review repairs — macOS coordinator, 2026-09-04

Observed using the installed `qwen3.5:4b-q4_K_M` GGUF, Ollama **0.32.14**, and
disposable SQLite state. Reproduce from the repository with:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. ./.venv/bin/python -m backend.coordinator.check_runtime_context
```

The script makes three explicit local-model requests with `num_ctx: 8192`,
`num_predict: 2048`, `think: false`, `truncate: false`, `shift: false` and the
existing request-local `keep_alive: "10m"`. It installs nothing and does not
read or write the user's chat database.

| Synthetic case | Observed result | Coordinator elapsed |
|---|---|---:|
| Early label before 5,000 CJK padding characters | 5,034 prompt tokens, 5 output tokens; correct label retained, normal completion | 9.618 s |
| 12,000 CJK characters accepted by the selection estimate | Runtime rejected input; no output or assistant message; visible shorten/new-chat error | 0.250 s |
| Counting after near-window CJK padding | 8,042 prompt + 150 output = 8,192; `length`, classified **context**; partial reply saved and job marked incomplete/failed | 6.191 s |

A direct rejection probe reported **12,012 actual prompt tokens**, exceeding
8,192. This demonstrates why the character heuristic is not enforcement.
The loaded runner reported context 8,192, resident allocation **3,375,617,800
bytes**, and model digest
`2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`.
These are bounded functional checks, not new cold-start, quality or memory-pressure benchmarks.

Offline regressions cover draft response/write ordering and newer typing,
failed sends, atomic submit/delete exclusion, HTTP 409 for unfinished states,
Unicode download headers and combining marks, and output/context limit notices.
Browser checks on an isolated server observed draft isolation and reload
recovery, disabled busy deletion, Cancel focused in the native confirmation,
cancel preserving history, and confirmed deletion remaining absent after reload
with the other chat intact. Both Marathi Markdown and text downloads returned
HTTP 200 with the correct filename and no unsent draft content.

This evidence applies to the macOS coordinator. It does not accept C03 on behalf
of the requester, qualify Ubuntu, or advance C04. See the
[repair handoff](c03-repair-handoff.md) for exact verification and Git paths.

## 6. Demonstration

### Preparation

1. Show the separate public distribution surface and release checksum only if
   they exist.
2. Show the pinned Docker image, Ready Pods, Kubernetes Services, Redis licence,
   installed model, and self-test state.
3. Confirm Redis has no LAN-exposed Service and the worker API requires the
   paired credential.
4. Disconnect or block public Internet while preserving the trusted LAN.
5. Start the evidence window.

### Standalone

1. Open the application in the local workspace.
2. Show Chat, Documents, Code, and Control Center.
3. Run the selected baseline task on this device.
4. Show the model, device, job events, and measured resource use.

### Trusted compute

1. Open Control Center and show paired devices and capabilities.
2. Start a scanned-report workflow.
3. Start a coding task while the document workflow runs.
4. Show the execution choices and automatic routing reasons.
5. Show streamed progress in the correct surfaces.
6. Open the generated cited document.
7. Inspect the returned code patch and validation.
8. Approve or deny the controlled final-write step.

### Sovereignty and resilience

1. Show the enforcing layer and network observation interval.
2. Show trusted LAN connections separately from public egress.
3. Open the job Proof Cards.
4. Disconnect one non-critical worker.
5. Show a safe requeue or recoverable failure without duplicate final output.

## 7. Sovereign Proof Card

Each demonstrated job records:

- workflow, job, step, and attempt IDs;
- original-request hash or approved reference;
- device identity, model manifest, and routing reason;
- tool and validation events;
- input and artifact hashes;
- approvals and final-write state;
- enforcement and observation method;
- public-egress and trusted-LAN observations;
- start/end times and evidence limitations.

It proves only the recorded job and observation window.

## 8. Implementation areas

The six implementation areas are:

1. Frozen contracts, coordinator SQLite, routing, and integration
2. Docker worker, model runtime, Redis consumer, and SSE
3. K3s, Pods, Services, NetworkPolicies, and sandbox Jobs
4. Local browser UI, Control Center, and product acceptance
5. Documents/OCR/retrieval and Code/patch validation
6. Fixtures, contract checks, failure drills, proof, and demo

Anyone may implement any area. Follow the numbered task sequence, use the
shared contracts, review the combined changes, and stop at named human
checkpoints. A person is named for a human action or device access, not exclusive
code ownership. Do not create empty components merely to give someone a folder.

## 9. Major risks

| Risk | Response |
|---|---|
| Product becomes only a networking demo | Complete one real agentic artifact workflow |
| P0 scope expands again | Treat the PRD outcome table as the release boundary |
| Infrastructure displaces workflow work | Use one single-node K3s host; no Helm, operator, service mesh, HA, or multi-node cluster |
| Redis becomes a second database | Keep canonical state in SQLite; use expiring Redis coordination state only |
| Agent count creates incompatible implementations | Use reviewed shared contracts, integrate accepted tasks and verify named human checkpoints |
| Worker Service exposes confidential traffic | Authenticated HTTPS only; Redis stays ClusterIP; verify NetworkPolicy and host firewall behaviour |
| Kubernetes Job is mistaken for a complete sandbox | Require observed non-root, seccomp, capability, path, resource, deadline, and egress checks |
| Setup forces unnecessary downloads | Resolve dependencies only for enabled capabilities |
| Main model is too weak | Benchmark the actual tasks before polishing UI |
| Cross-platform runtime differs | Prove one runtime path, add one fallback only for a measured blocker |
| Pairing becomes state migration | Keep pairing additive; defer coordinator transfer |
| Dashboard displays claims instead of evidence | Bind every status to an identified source and interval |
| Wi-Fi or worker fails in demo | Prefer wired links where available and record a backup run |
| Cold model loading erases concurrency benefit | Report cold/warm separately and preload only when disclosed |
| Confidential content leaks into logs | Metadata-only defaults and synthetic demo inputs |
| Open-source reuse creates licence risk | Record source, pin, licence, network behaviour, and local changes |
| Installer work consumes the prototype | Package only after the real harness path works |

## 10. Research gates

Research only questions that materially affect feasibility:

- official SIH26117 wording, evaluation expectations, and IP terms;
- one runtime across macOS, Windows, and Linux;
- main and specialist model correctness on the chosen demo inputs;
- RAM, VRAM, storage, cold-load time, and sustained thermals;
- pairing credential storage and encrypted LAN transport;
- platform sandbox behaviour;
- pinned K3s, Kubernetes workload, Docker image, and Redis 7.2.x compatibility
  and licences;
- Service exposure, Redis isolation, NetworkPolicy enforcement, and Pod
  security on the Ubuntu worker;
- connected and air-gapped model installation;
- trustworthy public-egress enforcement and observation;
- dependency and model licences.

The user or requester independently verifies the final result before the project
claims completion.

## 11. Problem-statement coverage

The authoritative SIH26117 text is retained in [README.md](README.md) pending
[OD-01](prd.md#11-open-decisions). This table records which of its lines the
current scope answers, so that a deferral is a recorded decision rather than an
oversight. Status values follow the evidence labels in section 1.

### Expected Solution

| Problem-statement line | Scope | Status |
|---|---|---|
| Local deployment on a single workstation with a mid-range GPU | FR-001 | Planned |
| Model auto-selection across at least two task types | FR-006, AF-006 | Planned |
| Agentic task end to end: scanned report to Word approval note | FR-011, AF-008, AF-009 | Planned |
| Coding task run and verified in a sandbox | FR-012, AF-010, AF-011 | Planned |
| Multimodal task: image or scanned document understanding | FR-011 | Partial — OCR extraction is planned; no step yet exercises a vision model on an image |
| Logs or network monitor showing no external calls | FR-010, AF-015 | Planned |

### Description lines deferred beyond the alpha

Each of these is named in the problem statement and intentionally excluded from
the alpha under
[deliberately excluded](../tasks.md#outside-the-alpha-scope).
None is claimed as working.

| Problem-statement line | Decision |
|---|---|
| Engineering drawings, photographs, P&IDs | Deferred. Trained symbol detection needs annotated data the project does not have; the main engine's vision capability is an untested cheaper path |
| Handwritten notes | Deferred. Accuracy is uncertain and no fixture exists |
| Spreadsheet work and Excel output | Deferred until both signature workflows are stable |
| PowerPoint output | Deferred until both signature workflows are stable |
| Calculations with steps shown | Deferred. Closest cheap path is a computed value inside the approval note |
| Plan out multi-step work | Partial. Workflows are fixed contracts with one bounded repair attempt, not a general planner |
| Multiple open-weight models, addable without redesign | Answered by the manifest-driven catalogue gate on AF-001 |
| Grounding in manuals, SOPs, and correspondence | Answered by local retrieval in AF-009 |
| Multilingual industrial interaction | FR-019, P1 finals scope |

## 12. Mentor implementation-direction coverage

These are implementation requirements from the mentor, not claims from the
problem statement. They remain Planned until the named acceptance evidence is
observed.

| Mentor direction | Repository interpretation | Acceptance evidence | Status |
|---|---|---|---|
| Use Kubernetes and Docker | Docker builds pinned OCI worker/sandbox images; single-node K3s runs them | AF-002, AF-003: image digest plus Ready Deployment/Pod | Planned |
| Create Pods | Deployments own long-running API/executor Pods; Jobs create short-lived validation Pods | AF-002, AF-011: Pod readiness, limits, termination, and cleanup | Planned |
| Use Service API | Kubernetes Service provides a stable endpoint for the versioned FastAPI worker contract | AF-006: authenticated Mac-to-Service job completes | Planned |
| Use Redis | Redis Streams and expiring keys coordinate dispatch, leases, heartbeats, cache, cancellation, and events | AF-005: acknowledge, pending-work recovery, restart, and retention fixtures pass | Planned |
