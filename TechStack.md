# Refinix technology stack

Updated: 2026-09-14. This maps the [product direction](docs/prd.md) to existing
components and qualification candidates. It does not install, migrate or certify
anything. Reuse current source first; preserve the UI and shared harness.

## 1. Language choices

Keep Python for orchestration, contracts, workflow tools and packaging; existing
HTML/CSS/JavaScript for the frontend; SQLite for local state and retrieval. Native
inference engines perform model computation. Dockerfiles and Kubernetes YAML
remain specific to the optional managed backend. Do not rewrite the app in React,
Go or Rust merely to change deployment shape.

## 2. What exists and what is proposed

| Layer | Current source | Production direction / qualification |
|---|---|---|
| UI | [frontend/app/](frontend/app/) is the runtime UI; frontend/design is a reference | Preserve Chat/document workflows, IDE-style Code, Settings and status card |
| Desktop | [desktop/](desktop/) uses pywebview; macOS py2app packaging exists | Qualify platform installers, signing, native libraries, upgrades and rollback; no wrapper replacement selected |
| Local service | [backend/coordinator/](backend/coordinator/) uses Python standard-library HTTP, SQLite and shared contracts | Extend existing service and durable job/context ownership; no framework migration required |
| Worker API | [backend/worker/app.py](backend/worker/app.py) and shared Pydantic contracts; FastAPI worker | Reuse authenticated job protocol for an app-managed peer execution agent |
| Model execution | Ollama adapter, selected Qwen3.5-4B prototype model | Preferred bundled llama.cpp candidate, pending exact-build/model and installer parity |
| Placement | Workflow model preferences and a single active paired-worker selection | Rank eligible model/device pairs and enforce receiving capacity across concurrent requesters |
| Local search | [retrieval.py](backend/coordinator/retrieval.py), SQLite FTS5 | Add qualified local embeddings and embedded vector search alongside lexical retrieval |
| Document tools | Existing parsers, scan/image paths, DOCX/PDF/XLSX generation | Reuse; qualify macOS-specific Quartz/AppKit replacements for other platforms |
| Distributed backend | [deploy/k3s/](deploy/k3s/), Redis Streams, API/executor services and validation Jobs | Retain as optional managed backend; not a desktop prerequisite |
| Code sandbox | Restricted Kubernetes validation Jobs; bounded Python unittest commands | Qualify standalone isolation and toolchains per OS/edition; never substitute unrestricted host execution |

These entries are source observations, not a claim that all paths pass runtime
acceptance. See [evaluation.md](docs/evaluation.md#current-status).

## 3. Frontend and product surfaces

Extend current components rather than rebuilding the interface. Add onboarding,
six scored recommendations plus Show more, a Connect device view and receiver
notifications through existing Settings/status flows. Keep routing automatic and
show a concise model/device/reason; detailed diagnostic evidence is secondary.
Use reliable OS telemetry where available, with unavailable states for missing
sensors. Keep keyboard access, readable status and untrusted-output sanitisation.
No CDN, remote font, analytics or cloud login dependency in offline operation.

## 4. Coordinator, workers and data

The [architecture](docs/architecture.md) owns the algorithm and contracts. Keep
SQLite as canonical local storage, existing event streams and authenticated
HTTPS worker requests. A peer execution agent needs a bounded queue, admission,
receipts, leases, cancellation and reconciliation; preserve those semantics from
the Redis path without requiring Redis installation on every laptop. Multiple
workspace schedulers can use receiver-side atomic admission; no new global
scheduler service is required.

Keep each SQLite database on its owning host, not a shared network drive. Use
short transactions and consistent backups. Share explicit API results, not database
files. Organisation corpus access is separate from compute pairing and personal
workspace storage.

Evaluate [python-zeroconf](https://github.com/python-zeroconf/python-zeroconf) for
LAN discovery. It needs an exact pin, licence review, platform packaging and
firewall/reachability checks before adoption. It discovers services; it neither
establishes trust nor measures physical distance. Provide a graphical manual
address/code fallback and use established TLS/OS credential mechanisms.

## 5. Inference, documents and code tools

| Component | Proposed use | Adoption gate |
|---|---|---|
| [llama.cpp / llama-server](https://github.com/ggml-org/llama.cpp) | Bundled loopback inference process managed by Refinix | Same-model correctness, structured outputs, vision assets, context, cancellation, resource/concurrency and clean-install parity on each supported backend |
| Qwen3.5-4B | Reuse baseline across qualified chat, code, reasoning and vision tasks | Workload evaluation; integrity/smoke checks alone do not establish broad quality |
| [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | Local semantic retrieval | Exact artifact/runtime, memory, retrieval quality, source/version/access controls |
| [sqlite-vec](https://github.com/asg017/sqlite-vec) | Embedded vector retrieval alongside FTS5 | Pin/review extension, packaging and representative hybrid-search evaluation |
| Existing OCR and document adapters | Extract, cite and create real artifacts | Platform-independent path where required; scanned tables, image inputs, units, readability and rendering checks |
| Additional code/OCR models | Specialist alternatives for automatic routing | Demonstrable improvement and compatible target hardware; no compulsory second model per feature |
| Sandbox backend | Network-disabled isolated code tools | OS/edition isolation, resource bounds, host-file protection and guided prerequisites; still unresolved across all desktops |

RAG is the extraction → indexing → retrieval → grounded generation pipeline;
an embedding model is one component. No foundation-model training is required.
Use editable instructions/curated memory before optional adapter or preference
training; follow [adaptation gates](docs/model-catalog.md#11-personalisation-and-optional-model-adaptation).
Use the inference engine's existing cache mechanisms under Refinix's
[resource policy](docs/architecture.md#kv-cache-and-runtime-resource-policy),
not a new custom allocator. PagedAttention and cache quantisation require measured
benefit and backend qualification.
Rebuild affected embeddings after embedding-version changes and invalidate deleted
or unauthorised sources. Add a reranker only if evaluation shows a useful gain.

Refinix itself is the harness. DeepSeek Harness remains an unadopted research
option; do not introduce another framework without a concrete integration benefit.
The model engine is not a sandbox, scheduler or document generator. Future speech
and image-generation packs may need additional qualified runtimes; llama.cpp is
not a universal engine for every model family.

## 6. Security, deployment and verification

Follow [security.md](docs/security.md) for receiver trust, bounded workspace access,
approval, corpus permissions and zero-public-egress evidence. The worker API is
the LAN boundary; model servers stay on loopback. Kubernetes and Redis internals
are not public product endpoints. Generated-code validation gets no network or
host-secret access, even if its supervisor needs infrastructure connectivity.

Ship OS/architecture-specific packages with the application runtime, qualified
native libraries and relevant engine. Users explicitly select models or import a
complete verified offline bundle. Updates use explicit connected check/download
or authenticated offline import, with a recovery path preserving user data.
Drivers, platform permissions and sandbox virtualisation requirements must be
surfaced honestly;
normal end users should not debug them with terminal commands.

The existing Docker/K3s backend remains useful for managed compute and sandbox
Jobs. Native Windows/macOS peers instead participate through Refinix's application
protocol. A server can use the same worker service without Kubernetes if its
qualified execution/isolation profile does not need it.

The [release contract](docs/releases.md) adds a qualified existing updater and
platform installer tooling, not Kubernetes for desktop packaging. Start with
full packages; delta updates are optional after measured need. Sparkle on macOS
and TUF-style signed metadata are candidates, not adopted dependencies; Windows
and Linux mechanisms must meet the same explicit-network and recovery contract.
GitHub Releases is the initial artifact-hosting candidate, subject to package
size, access and availability checks. Current CI does not implement this pipeline.

## 7. Devices and rollout

[devicespecifications.md](docs/devicespecifications.md) records historical test
hardware, not permanent production roles. Publish a tested OS/version/architecture,
CPU/GPU backend and capability matrix. Windows, macOS and Linux must each be
qualified as requester and execution target, with a same-OS peer configuration
showing there is no hidden Linux dependency. The recorded Windows inventory
includes Home editions, so Windows Sandbox alone cannot cover the supported fleet.

Follow [outcome-based gates](tasks.md#numbered-execution-tasks). No dates, named
implementers or exclusive module ownership are implied by this technology guide.

## 8. Versions, licences and adoption

Candidate names/URLs are not approved download manifests. Before adoption record
source, exact revision, licences including bundled assets, hashes, supported
platform/backend and observed checks. Preserve historical runtime and image pins
in [architecture.md](docs/architecture.md#81-od-08--resolved-infrastructure-pins)
and [model-catalog.md](docs/model-catalog.md); do not silently upgrade them.

The repository licence is unchanged. An open-source core and specialised paid
offering share the same architecture; commercial distribution of each dependency
and corpus still needs compatible rights. Do not include proprietary documents,
weights or release binaries in Git.
