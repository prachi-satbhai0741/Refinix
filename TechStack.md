# AegisForge technology stack

Updated: **2026-09-03**. Recommended languages and technologies for the offline
workbench, given the current team, hardware and internal-hackathon scope.
“Best” here means the simplest stack that can deliver and verify those workflows;
it does not mean the fastest language in an isolated benchmark.

The [PRD](docs/prd.md) owns scope, [architecture](docs/architecture.md) owns system
boundaries, and [tasks.md](tasks.md#numbered-execution-tasks) owns execution order
and human checkpoints. This guide does not advance a checkpoint or establish
runtime compatibility. **Recommended** means a choice for implementation;
**recorded** means an existing design decision; **implemented** means source
exists; **observed** refers only to the linked evidence; **deferred/conditional**
means outside the currently authorised implementation.

## 1. Language choices

| Section | Recommended language | Why it fits |
|---|---|---|
| Application interface: Chat, Documents, Code, Control Center | **TypeScript**, with HTML and CSS | One typed browser application can share job state, streaming views, approvals and artifact links. |
| Coordinator, worker API, routing and tool orchestration | **Python** | Reuse the existing Python contracts and the local AI/document ecosystem; keep orchestration readable. |
| Document extraction, OCR integration and artifact generation | **Python** | Bind existing native engines and document libraries instead of implementing file formats or OCR. |
| Persistent state and local text search | **SQL**, called through Python | SQLite transactions, constraints and full-text queries suit one coordinator-owned database. |
| Model inference and GPU computation | Existing **C/C++** engines and their CUDA/Metal backends | Use Ollama's supplied native runtime. Python sends requests; it does not implement token generation. |
| Deployment and isolation policy | **YAML** and **Dockerfile** configuration | Describe the existing Docker/K3s design without introducing another application language. |
| Device setup | **Bash** on Ubuntu, shell-compatible commands on macOS, **PowerShell** on Windows | Use each platform's native administration tools. Prefer Python for substantial portable inventory logic. |
| Checks | **Python** for backend checks; **TypeScript** for frontend and browser checks | Test each layer in its implementation language. |

TypeScript checks code before execution; it does not validate incoming JSON at
runtime. Keep validation at API boundaries in the Python contracts and handle
unexpected events in the UI. See the [TypeScript handbook](https://www.typescriptlang.org/docs/handbook/intro.html).
There is no current reason to rewrite orchestration in Go or Rust or create a
separate service for each screen.

## 2. What exists and what is proposed

| Area | Current repository/evidence | Recommended direction |
|---|---|---|
| Contracts | Python/Pydantic source, examples and checks in [backend/contracts](backend/contracts/README.md) | Extend these shared contracts as workflows are implemented. |
| Coordinator and workers | Planned; no implemented application API or executor | Python + FastAPI + Pydantic + Uvicorn, with asynchronous I/O. |
| Frontend | No source or package manifest. The recorded alpha baseline is local HTML/CSS/JavaScript. | **React + TypeScript + Vite** for the four stateful surfaces; ordinary CSS initially. This is a proposed revision to the baseline, not an existing scaffold. |
| Inference | Bounded native Ollama runs reported on macOS and Ubuntu; Mac comparison used Ollama's bundled `llama-server` | **Keep Ollama through the internal hackathon.** Reconsider a direct engine only after selection and representative measurements. |
| State and search | SQLite recorded; full-text retrieval is a candidate; application storage is not implemented | SQLite through Python's standard library, WAL where appropriate, and FTS5 before a semantic index. |
| Distributed infrastructure | Docker/K3s/Redis versions and image digests recorded; worker/cluster path is unverified | Keep the recorded design, proving one Ubuntu worker before expanding. |
| OCR and document libraries | Candidates and workflows documented; no approved working extraction pipeline | Qualify the small set in section 5 on actual document fixtures and the intended device. |

The source of runtime claims is [evaluation evidence](docs/evaluation.md), not
this table. The two runtimes' cold-start comparison and Ubuntu direct-engine
comparison remain **deferred**, not passed. A future switch to llama.cpp depends
on measured latency, output correctness, memory and operating effort; upstream
also offers prebuilt binaries, so manual compilation is not universally required.
See [llama.cpp](https://github.com/ggml-org/llama.cpp).

## 3. Frontend and product surfaces

Use one React/TypeScript application with shared components and job state. React
state and reducers are enough initially; do not add a global state library for
anticipated complexity. [React's state guide](https://react.dev/learn/managing-state)
describes these built-in mechanisms. Vite produces local static assets that the
coordinator can serve; Node.js belongs in the build environment, not necessarily
the installed runtime. See [Vite production builds](https://vite.dev/guide/build)
and [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/).

| Surface/component | Language and technology | Implementation direction |
|---|---|---|
| Chat | TypeScript + React; browser HTTP/SSE client | Stream output and show cancellation, errors, citations and tool approvals from the shared API. |
| Documents | TypeScript + React; native file input and artifact links | Show source pages, extracted text, uncertain fields and citations; Python performs extraction and generation. |
| Code | TypeScript + React; simple file and patch views | Review proposed changes and sandbox results. Add a full editor only when editing requirements justify it. |
| Control Center and onboarding | TypeScript + React | Render reported node capabilities, pairing, model readiness, jobs and evidence; never infer “secure” or “healthy” from a successful connection alone. |
| Styling and accessibility | Semantic HTML + CSS | Use native controls, keyboard access, visible focus and readable layouts. Tailwind is optional if it reduces work for the team; it is not required for functionality. |
| Rich text | TypeScript with a reviewed Markdown renderer when needed | Treat model and document output as untrusted; disable raw HTML or sanitise it before rendering. |

Record adoption of the proposed frontend choice alongside C03 implementation and
its dependency lockfile. Until then, the current architecture's vanilla baseline
remains explicitly recorded. No Next.js server, desktop wrapper, CDN, remote font
or analytics dependency is needed for this first local application.

## 4. Coordinator, workers and data

| Layer | Language and technology | Reason and boundary |
|---|---|---|
| Local coordinator API | Python + FastAPI + Pydantic + Uvicorn | FastAPI defines HTTP routes, Pydantic validates contracts, and Uvicorn serves the application; these are complementary components. |
| Workflow harness and routing | Python; explicit job states and existing contracts | Coordinate steps, approvals, cancellation, retries and capability-based placement in one harness. Add no generic agent framework or plugin system yet. |
| Runtime and worker HTTP calls | Python + an asynchronous HTTP client, such as HTTPX | Use bounded timeouts, streaming and cancellation. Reuse one suitable client across callers. |
| UI job events | Python producer + TypeScript consumer; Server-Sent Events | Match the recorded one-way event stream. Mutating commands remain authenticated API requests. |
| Worker service | Python + the shared FastAPI/Pydantic contracts | Execute bounded tasks in assigned temporary workspaces; return results and artifacts without owning canonical chat history. |
| Persistent application state | SQL + Python `sqlite3`; SQLite | Store jobs, chats, approvals, metadata and audit references on the coordinator. Use transactions and constraints rather than a new persistence service. |
| Database concurrency | SQLite WAL, recommended for concurrent reads | WAL allows readers alongside a writer, but still permits only one writer at a time. Keep writes short and plan checkpointing and consistent backups. |
| Local knowledge search | SQL + SQLite FTS5 | Start with full-text retrieval over extracted text and source/page metadata. Confirm FTS5 is available in the shipped SQLite build. |
| Distributed queue and transient leases | Python Redis client + Redis **Streams** consumer groups and expiring keys | Keep Redis inside the Ubuntu cluster. Acknowledge after handling, recover pending jobs and make retries idempotent. The coordinator uses the worker API. |
| Artifacts and model files | Python `pathlib`, `tempfile`, `hashlib`; local filesystem | Keep binaries outside Git, write artifacts safely, enforce workspace paths and record checksums. Store searchable metadata in SQLite. |

Async I/O overlaps waiting; it does not make CPU-bound OCR non-blocking. Run
heavy work in worker processes or the sandbox, away from the API event loop.
See [FastAPI concurrency](https://fastapi.tiangolo.com/async/) and
[HTTPX async support](https://www.python-httpx.org/async/).

SQLite WAL is for a database on one host, not a shared network-drive database.
Use a consistent backup procedure that accounts for WAL state, such as the
standard-library backup API. See [SQLite WAL](https://sqlite.org/wal.html),
[Python sqlite3](https://docs.python.org/3/library/sqlite3.html) and
[FTS5](https://sqlite.org/fts5.html).

Pub/Sub can lose messages while consumers are disconnected; a plain `BLPOP`
removes a job before processing completes. Neither replaces the recorded Streams
queue. Consumer groups still require explicit acknowledgement and recovery;
they do not automatically give exactly-once execution. Use commands supported by
the pinned Redis 7.2 release. See [Pub/Sub delivery semantics](https://redis.io/docs/latest/develop/pubsub/),
[BLPOP reliability](https://redis.io/docs/latest/commands/blpop/#reliable-queues)
and [Streams consumer groups](https://redis.io/docs/latest/commands/xreadgroup/).

## 5. Inference, documents and code tools

All application adapters here should be Python. Native libraries and model
engines perform the expensive computation. New libraries below are
**recommendations or candidates**, not installed dependencies or accepted models.

| Capability | Recommended technology | Selection rule and limitation |
|---|---|---|
| Chat and reasoning | Ollama's local API through a thin Python adapter | Keep the selected `qwen3.5:4b-q4_K_M` pack and recorded settings for the first path. Bind inference to loopback; preserve errors and streaming completion evidence. |
| Model discovery and provenance | Python + catalogue manifests + SHA-256 | Record source, licence, runtime/version and hashes; do not infer capability from a model name or an executable path. |
| PDF rendering and existing text | **pypdfium2**, candidate | Evaluate its PDFium-backed rendering and text extraction first. Use pinned compatible wheels and review bundled notices; avoid installing several overlapping PDF libraries by default. |
| Printed-text OCR baseline | **Tesseract** with a Python adapter; `pytesseract` if needed | Provision the native executable and required language data offline. Evaluate page layout, field accuracy and latency on the actual fixture set. |
| Complex layouts, scans and vision | Python adapter to a locally qualified OCR/vision model from the [catalogue](docs/model-catalog.md) | Compare catalogue candidates, including PaddleOCR where applicable, against the baseline. A 4 GB GPU does not establish model fit, accuracy or throughput. |
| Citations and extracted fields | Python validation + SQL metadata | Preserve source/page references and uncertainty; do not fabricate missing values or accept model output as validated extraction. |
| Word deliverables | **python-docx**, recommended | Produce `.docx` artifacts from structured results; verify content and layout with representative documents. |
| Code inspection and patch preparation | Python + existing repository tools | Limit context to the selected repository and prepare reviewable patches. Keep approved final writes under coordinator control. |
| Code execution and validation | Python supervisor; the fixture's actual language/toolchain inside an approved sandbox image | A Python project needs Python checks; a TypeScript project needs its own tools. Support an explicit initial toolchain set, not arbitrary package installation during offline jobs. |
| Engineering calculations | Python `decimal`/`math` and explicit input/unit validation | Use deterministic calculations with visible assumptions. Add specialist libraries only for a scoped requirement and verify them against known examples. |
| Spreadsheets, when enabled | Python + **openpyxl**, candidate | Read/write `.xlsx`; do not assume generated formulas have been recalculated by an Excel engine. |
| Presentation files, when enabled | Python + **python-pptx**, candidate | Generate `.pptx` from approved content and templates, then inspect rendered slides. |
| Semantic retrieval, voice and additional languages | Python adapters to separately qualified local models | Conditional on scope, licence, hardware, fixtures and an offline packaging path; no vector database or extra model is required by this guide. |

Library references: [pypdfium2](https://github.com/pypdfium2-team/pypdfium2),
[pytesseract and its engine prerequisite](https://github.com/madmaze/pytesseract),
[python-docx](https://python-docx.readthedocs.io/en/latest/),
[openpyxl](https://openpyxl.readthedocs.io/en/stable/) and
[python-pptx](https://python-pptx.readthedocs.io/en/latest/).

Tesseract is a baseline to test, not a promise of reliable table or drawing
understanding; its documentation identifies table recognition limitations.
See [Tesseract quality guidance](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html#tables-recognition).
PyMuPDF is an alternative only after an explicit licence review: its
[AGPL/commercial licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)
must fit the intended distribution. Do not silently adopt it as a permissive
dependency because the repository itself uses Apache-2.0.

## 6. Security, deployment and verification

| Layer | Language and technology | Required boundary/status |
|---|---|---|
| Pairing and authenticated transport | Python; established TLS and credential-store APIs | Implement the recorded [security policy](docs/security.md): fingerprint verification, scoped credentials, expiry and revocation. Do not invent cryptography. |
| Secrets | OS credential storage and restricted worker credential files, accessed through Python | Keep secrets out of source, request transcripts, logs and command-line arguments. Follow the recorded macOS/worker storage policy. |
| Container build | Dockerfile + pinned Python base image | Build reproducible OCI images with only the required tools; record resulting worker/sandbox digests. |
| Ubuntu orchestration | Kubernetes YAML + single-node K3s/containerd | Run services as Deployments and isolated validation as short-lived Jobs. Docker builds the images; K3s provides orchestration. |
| Sandbox enforcement | Kubernetes security/network policy plus bounded Python process supervision | Enforce non-root execution, no privilege escalation, reduced capabilities, filesystem/workspace bounds and CPU/memory/process/time/output limits. No host Docker socket or unrestricted host mounts. Verify enforcement on the target platform. |
| Network isolation | Default-deny sandbox networking; minimal authenticated worker LAN API | `--network none` alone is not a complete sandbox or proof of host safety. Test escape and egress boundaries required by the security plan. |
| Stronger sandbox runtime | gVisor, conditional | Consider it if the threat model and target-platform proof require additional isolation. It can integrate with Kubernetes; it is not a replacement for the queue or orchestrator. |
| Logs and evidence | Python standard logging + structured job records + TypeScript evidence views | Capture timings, outcomes and redacted errors. Keep model text and credentials out of routine logs. “Zero egress” requires the prescribed network evidence. |
| Backend checks | Python standard-library checks and existing tests | Reuse the current contract/parser checks; add focused checks for new behavior. No extra test framework is required solely for consistency. |
| Frontend/browser checks | TypeScript; Vitest and Playwright when justified | Introduce only with implemented UI behavior and authorised validation. Provision browser binaries before offline use. |
| CI | Existing GitHub Actions YAML | Retain current repository gates; add targeted checks when implementation warrants them. CI is a development service, never a runtime dependency. |
| Packaging | Local static assets + Python service + provisioned runtimes | Bundle required assets and dependencies for offline operation. Defer a desktop wrapper until the demonstration path works. |
| Public website | HTML/CSS; small JavaScript where needed | Keep it separate from the local application and confidential data. It is not an inference or coordination service. |

Containers share important host resources and need more than a networking flag
to isolate untrusted code; see [Docker security](https://docs.docker.com/engine/security/).
For the optional stronger boundary, see [gVisor](https://gvisor.dev/docs/) and its
[Kubernetes integration](https://gvisor.dev/docs/user_guide/quick_start/kubernetes/).
Proposed UI test tools are documented at [Vitest](https://vitest.dev/guide/) and
[Playwright](https://playwright.dev/docs/intro). Their inclusion here does not
mean either has been installed or run.

## 7. Devices and rollout

| Device role | Languages/runtime | Current scope |
|---|---|---|
| macOS coordinator, ARM64 | Browser TypeScript UI; Python coordinator; native Ollama | First application host. Native inference evidence exists; the application and paired-worker acceptance are separate gates. |
| Ubuntu worker, x86_64 | Python worker and tools; native Ollama; planned OCI workloads on K3s | First worker. Native inference and Docker inventory were returned; deployed worker, cluster and sandbox behavior remain to be verified. |
| Later OCR/vision worker, including the Windows laptop discussed for Yug | Python tool adapter plus a qualified native runtime or supported isolated environment | Preserve the intended OCR role, but confirm hardware, storage, runtime and connection method before adding it. Do not assume Windows joins the Linux K3s deployment unchanged. |
| Other laptops or a private server | The same worker contract and eligible tool runtimes | Add capacity only through an authorised checkpoint with evidence of useful task capability. A device role is not exclusive code ownership. |

The first two machines establish the initial path; they do not limit the product
to two machines. Additional workers remain conditional in the current task
board, not automatically scheduled or already verified. If a dedicated OCR
laptop becomes mandatory for the demo, record its setup and acceptance work in
that board. The [device inventory](docs/devicespecifications.md) owns machine
details; this document does not prescribe unverified Windows/WSL setup commands.

## 8. Versions, licences and adoption

Reuse the versions, licences and hashes already recorded in:

- [backend/requirements.txt](backend/requirements.txt) for the implemented
  contract dependencies, including Pydantic 2.13.5.
- [Architecture infrastructure pins](docs/architecture.md#81-od-08--resolved-infrastructure-pins)
  for the Python 3.13 worker image, Redis 7.2.16 and K3s v1.36.4+k3s1.
- [Model catalogue](docs/model-catalog.md) and [evaluation](docs/evaluation.md)
  for model provenance, device runtime versions and bounded measurements.

The host Python versions and the container's Python version currently differ;
this guide does not mandate a host upgrade or claim compatibility across all
three. Check the implemented dependencies on each supported environment.

New frontend, API and document-library versions are **not pinned yet**. At the
relevant implementation chunk, select compatible versions, verify licences and
offline behavior, commit dependency locks/manifests and record required native
packages and integrity data before provisioning. Approved connected setup must
produce a runtime that needs no cloud API, CDN, telemetry or implicit downloads.
No dependency or service is installed by documenting this stack.
