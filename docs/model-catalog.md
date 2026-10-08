# Model Catalogue and Provisioning

## Status and evidence rule

The selected Qwen3.5-4B/Ollama prototype baseline and its dated evidence are recorded below.
Candidate and measured status describe that evidence; they do not close the local model library.
Recommendations identify source, licence, integrity, format compatibility and the origin of workload
evidence rather than treating model names or hosting as a universal quality/safety guarantee.

[PROJECT.md](PROJECT.md#13-runtime-and-resource-policy) owns the current runtime contract.
The [verbatim user direction](beta-user-direction-2026-10-05.md) requires broad compatible model
choice using existing upstream infrastructure. Source handling, runtime compatibility and published
evidence do not require team measurement of every model before listing, downloading or local use.
Normal customers do not author execution profiles. Dated prototype qualification records below
remain evidence, not the local catalogue's admission allowlist.

The actual fleet and outstanding hardware checks are in
[devicespecifications.md](devicespecifications.md).

## 1. Catalogue purpose

The catalogue exposes model sources, compatible runtime assets and evidence. It lets
onboarding and persistent Settings → Models answer:

- which main engine fits this device;
- whether an installed model can serve more than one agent profile;
- which dependency is mandatory for an enabled capability;
- whether the model is installed, verified, measured, or unavailable;
- how to reproduce or import the exact artifact.

Recommendations provide useful starting choices; Show more, upstream discovery and advanced import
are not restricted to models the team has measured. Reuse official publisher model cards, runtime
metadata and upstream evaluations, with source/format/licence/integrity information. Identify third-party
quantizers/converters. Hosting on Hugging Face is not universal certification. Missing team measurements
alone do not make a model unusable; actual unsupported formats or unrestricted model code are different
limitations. Qwen, Gemma, GLM, DeepSeek and GPT-OSS are examples, not a closed family list.

<a id="persistent-model-management"></a>
### Persistent model management

This is the catalogue lifecycle authority for FR-015. **Settings → Models is
always reachable after onboarding**; it manages local models independently of
chat history and application updates. The same lifecycle serves first-run setup
and later changes, rather than two separate installers/catalogues.

| Operation | Required behaviour |
|---|---|
| Browse | Show existing local Ollama entries and upstream discovery/downloads for compatible managed assets; show publisher/source, licence, revision, format, size, runtime and known capabilities/requirements. Recommendations are not the full library |
| Understand evidence | Separate installation, runtime/task compatibility, published upstream evidence, local observations, estimates and team measurements. Missing team measurements alone do not prevent an otherwise compatible local model from being used |
| Choose or revisit | Default to automatic task-to-model assignment among installed compatible models; preserve optional manual preferences and choices beyond hardware recommendations. Refresh relevant metadata without silent public checks |
| Download later | User starts a download from a recorded upstream source, including choices beyond fit recommendations; show size, format/runtime needs and warnings. Preserve staged progress/cancellation and existing models |
| Import offline | Apply the approved bundle path below, including manifest, provenance/licence, compatibility and integrity; arbitrary files or runtime inventory names never auto-enter the trusted catalogue |
| Verify and self-test | Verify downloaded asset integrity and establish runtime health/locality. Bounded task checks or normal execution record what actually ran; synthetic team certification of every model/version is not mandatory. Keep actual incompatibilities/failures visible and never fabricate measured evidence |
| Enable or disable | Change profile eligibility explicitly; prevent new placement on disabled models and explain affected queued/active jobs. Never silently change the model of an in-flight attempt |
| Remove safely | Preview affected capabilities/defaults, model references and jobs; drain or explicitly cancel affected work before removal. Require confirmation; preserve shared files referenced by other models and do not delete externally owned runtime stores without a supported explicit removal operation |
| Recover | Interrupted provisioning/removal cannot leave false Ready status or corrupt another model. Preserve catalogue/history; clear stale selections and offer compatible alternatives without overriding user choice |

The standalone Beta requires broad compatible local choice and this persistent lifecycle, not a
small measured-only admission list. Demonstrate representative task/model combinations rather than
benchmarking every available model. Initial recommendations may be few while discovery and downloads
remain open. Calibrated scores are later work, not a prerequisite for listing models.
[PROJECT.md](PROJECT.md#5-persistent-model-management) owns interaction and
[tasks.md](../tasks.md) owns active sequencing; [evaluation](evaluation.md#beta-acceptance) records
evidence. Historical P-task labels are not active gates. The current inventory and per-scope selector
do **not** yet implement this lifecycle.

## 2. Baseline and conditional packs

| Pack | Requirement | Notes |
|---|---|---|
| Main engine | Required for local generation; optional for remote-only clients | Chat, planning, tool use, and fallback |
| Documents | Required when Documents is enabled | OCR/vision model or proven equivalent |
| Semantic knowledge | Required when semantic retrieval is enabled | Embedding model plus local index |
| Code | Requires a compatible local generation model for the selected Code workflow | May reuse the main model; preserve proposal parsing, review, approvals and safe validation rather than requiring a team benchmark for every model |
| Voice | Optional | Local transcription; speech output remains later scope |
| Multilingual | Required when FR-019 Indian-language interaction is enabled | Indic speech input, translation, and speech output; text may reuse the main engine |

Do not download a second model solely because a second profile exists. Profiles
may share one compatible model while retaining different tools, instructions,
policies, and validators.

Basic local search may begin with SQLite full-text search. An embedding model
becomes mandatory only for semantic retrieval; RAG is the complete retrieval
pipeline, not the name of a single model.

## 3. Candidate shortlist

| Pack | Candidate | Intended use | Status |
|---|---|---|---|
| Main engine | `qwen3.5:4b-q4_K_M` | General chat, planning, tool use | **Selected for the first path — Integrity verified** on the macOS coordinator (see §3.1) |
| Documents | PaddleOCR-VL-1.6 candidate | OCR, scans, and document layout | Research candidate. **Not** the same artifact as the installed `MedAIBase/PaddleOCR-VL:0.9b` conversion recorded in 3.2, whose provenance is unresolved. |
| Semantic knowledge | Qwen3-Embedding-0.6B candidate | Local embeddings | Research candidate |
| Code | Qwen2.5-Coder-7B-Instruct Q4 candidate | Code generation and patch work | Research candidate |
| Reasoning/vision | Qwen3.5-9B Q4 candidate | Optional stronger or visual fallback | Hardware-dependent hypothesis |
| Voice | Qwen3-ASR-0.6B or evaluated local ASR | Local transcription | Optional research candidate |
| Multilingual ASR | IndicConformer 600M multilingual candidate | Indian-language speech input | Research candidate |
| Multilingual translation | IndicTrans2 distilled 200M candidate | Indic and English text conversion | Research candidate |
| Speech output | Kokoro-82M candidate; Indic-TTS candidate for Indian languages | Local text-to-speech | Research candidate |

The upstream [Qwen3.5-4B model card](https://huggingface.co/Qwen/Qwen3.5-4B)
records a vision encoder. This is candidate capability, not proof that a chosen
Q4 file and local runtime work correctly on the target fleet.

The FR-019 multilingual candidates come from AI4Bharat (IIT Madras).
[IndicConformer 600M](https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual)
is published under MIT and covers the 22 scheduled languages, including Kannada,
Hindi, Malayalam, and Tamil;
[IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) ships a distilled 200M
variant; [Kokoro-82M](https://github.com/PierrunoYT/Kokoro-TTS-Local) is
Apache-2.0. These are optional candidate packs. Exact download/resident memory, CPU support,
language quality and bundled licences require artifact-specific qualification;
their names or parameter counts do not establish fit. Transcripts preserve
uncertainty instead of being treated as verbatim source evidence.

This shortlist is not an installation manifest. No candidate may enter the
onboarding picker until its exact source, licence, version, files, hashes, and
runtime path are reviewed.

## 3.1 OD-05 — the first selected model set

**Historical first model set: one model.** Qwen3.5-4B remains the reuse baseline
for chat, reasoning, code and supported vision/document tasks. Workflows now exist
in source; each capability needs its own evaluation. Do not provision specialist
models merely to give every feature a different model name.

The macOS coordinator reused its copy from 2026-08-08. At the human C02
checkpoint on 2026-09-03, the Ubuntu worker downloaded the same selected model
into `/usr/share/ollama/.ollama/models` using its existing Ollama installation.
Its returned checksum output reports `OK` for the manifest and all four blobs.

| Field | Value |
|---|---|
| Internal ID | `af-main-qwen35-4b-q4km` |
| Upstream identifier | `qwen3.5:4b-q4_K_M` |
| Source | `registry.ollama.ai/library/qwen3.5`, tag `4b-q4_K_M` |
| Manifest SHA-256 | `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd` |
| Format / quantisation | GGUF, `Q4_K_M` (file magic `GGUF` confirmed on the blob) |
| Reported parameter size | `model_type` 4.7B in the image config |
| Weights file | `sha256:81fb60c7daa80fc1123380b98970b320ae233409f0f71a72ed7b9b0d62f40490` — 3,389,971,840 B |
| Config | `sha256:de9fed2251b37295b763727a59ca35cf5cfe5c7379bc3e2104b2ce3c145aa887` — 475 B |
| Licence layer | `sha256:7339fa418c9ad3e8e12e74ad0fd26a9cc4be8703f9c110728a992b193be85cb2` — 11,355 B, **Apache License 2.0** |
| Default params layer | `sha256:9371364b27a52acac9d87f88bd93c9db1174d8d6ec57f6888925cdc1788871ff` — `temperature 1, top_k 20, top_p 0.95, presence_penalty 1.5` |
| Minimum runtime | Ollama `>= 0.17.1` (declared in the image config) |
| Storage | Weights approximately 3.16 GiB; macOS store `~/.ollama/models`, Ubuntu store `/usr/share/ollama/.ollama/models`. Ubuntu also retains its pre-existing `qwen3:4b`. |
| Evidence state | **Integrity verified; bounded inference and local microbenchmark observed** on both devices, 2026-09-03. Coordinator blobs were re-hashed locally; Ubuntu returned manifest/blob checks and the same manifest digest in `/api/ps`. This is a fixed-prompt smoke check, not a scored quality or application acceptance test. |

### Bounded execution settings for the first path

| Setting | Value | Why |
|---|---|---|
| **Thinking** | **`think: false` by default**, changeable per model from the composer (`chat_template_kwargs.enable_thinking: false` on `llama-server`) | **The safe default, no longer a prohibition.** This is a thinking model: left on, it spent the entire output budget reasoning and returned an **empty** answer at `num_predict` 128 *and* 512, both stopping on `length`. With thinking off the same prompt finished in 89 tokens on `stop`. Measured on the macOS coordinator 2026-09-03; that evidence stands and is why the default is off. Execution 2 raised Chat to `num_predict` 2048 and added a per-model Reasoning switch sending the top-level `/api/chat` `think` field; a request that ends with reasoning but no visible content fails with a named reason and saves no blank reply. Smoke-checked on the macOS coordinator 2026-09-05 against Ollama 0.33.3: `think: false` produced 0 thinking chunks and a visible answer on `stop`; `think: true` produced 101 thinking chunks and the same visible answer on `stop`. No Qwen `/think` or `/nothink` prompt suffix is used. |
| Context | `num_ctx` **8192** on the macOS coordinator | Measured 2026-09-04: +220 MiB resident over 4096, warm time-to-first-token unchanged (0.196 s → 0.203 s), and a fact planted at the start of a 3052-token prompt was still retrieved. The Ubuntu worker keeps 4096 until measured at its own checkpoint. |
| Document work | Desktop Execution 3 sends the model only validated extraction and selected passages, fenced as untrusted data, and parses its reply through a strict schema. Retrieval is keyword matching and OD-07 stays unresolved. C08 adds a scan-reading path whose model is recorded in 3.2 below as an **installed candidate**, not a provisioned catalogue entry. |

## 3.2 C08 scan reading — installed candidate, NOT a catalogue entry

**Evidence state: installed and inspected. Source, licence, provenance and
quality all UNRESOLVED. Not verified for any workflow.** Nothing below was
downloaded by AegisForge; the manifest was already present on the macOS
coordinator and was read there on 2026-09-05 with read-only commands.

This entry does not meet §4's manifest requirement and is deliberately not
promoted to §3.1. It is recorded so the fact that it is installed, and the
observed reason it cannot currently be used, are both written down.

| Field | Observed value |
|---|---|
| Upstream identifier | `MedAIBase/PaddleOCR-VL:0.9b` |
| Source | **UNRESOLVED.** A third-party Ollama account name. Who published it, from what, and whether it corresponds to any official release is not established. |
| Licence | **UNRESOLVED.** No licence layer is present in the manifest. The upstream PaddleOCR project's licence must NOT be attributed to this conversion without reading that artifact's own licence. |
| Manifest SHA-256 | `2d9290d5ab53a5eb50ba12903909ae3879408ca7ef0e5361092967c06cfbfdaf` |
| Config | `sha256:e4ecc823369bd984af05fae8d580273e469c5728f8f46e6fd585ee2fef8bfc6c` — 422 B |
| Model layer | `sha256:3ac47f4557c259c4c680c762729fb4b94e9572c9d52f9104c2f00013caaf9b0e` — 935,768,512 B |
| Other layers | system 31 B, params 35 B. **No projector layer.** |
| Architecture | `paddleocr` (from `/api/show`) |
| Parameter count | 466,654,208 — **466.65M**, despite the `0.9b` tag |
| Quantisation | BF16 |
| Declared capabilities | **`["completion"]` only — `vision` is absent** |
| Storage | `~/.ollama/models` on the macOS coordinator |
| Evidence state | **Installed, inspected, and observed NOT to accept image input.** An image request returns HTTP 500 `image input is not supported`. No quality, accuracy, layout or confidence claim is made or implied. |

**Consequence.** C08 asks the runtime what a model can do before sending it a
page, and requires `vision` in the answer. This model does not declare it, so
scan reading reports itself unavailable with the reason, and no page image is
ever sent. See the [archived C08 observation](archive/c08-dependency-plan.md) §3 for
the three observations and the decision this leaves to the human gate.

**A name is not a capability.** The tag contains "VL" and "PaddleOCR"; the
artifact is a 466M-parameter text-only conversion with no projector. Nothing in
this repository may infer modality, provenance or licence from a model name.

### C08 rendering component

| Field | Observed value |
|---|---|
| Component | `Quartz` via PyObjC — a macOS framework binding, not a model |
| Version | `objc.__version__` = 12.2.2, in `desktop/.venv` (Python 3.12.13) |
| Downloaded | **no** — already present in the locked desktop environment |
| Observed behaviour | Renders the C07 scan to 3 pages, 1131×1600 px PNG, byte-identical across two runs (2026-09-05) |
| Output limit | `num_predict` 128 for self-test and comparison runs | Enough for a complete answer with thinking off; keeps a failing run cheap |
| C03 Chat output limit | `num_predict` 2048, raised from 512 on 2026-09-04 | Longer replies remain bounded; the coordinator records the actual stop reason and distinguishes output and context limits. The Mac context is 8192; the historical comparison settings stay unchanged. |
| C03 overflow policy | Request fields `truncate: false`, `shift: false` | Verified on macOS with Ollama 0.32.14 and this GGUF: oversized input rejected, generation stopped at 8042 prompt + 150 output = 8192 tokens. See [repair evidence](evaluation.md#53-c03-review-repairs--macos-coordinator-2026-09-04). Ubuntu remains unverified for this policy. |
| Sampling | `temperature` 0, `seed` 42 for checks | Four runs produced one response SHA-256, so a regression is visible; identity is proven by hash, not inferred from counts |
| Idle residency | Request field `keep_alive: "10m"`; preparation request uses `"0"` | Keeps recorded warm runs resident; no persistent service-setting change was made |
| Bind address | `127.0.0.1:11434` | Observed on the coordinator via `lsof`/`netstat` and in the Ubuntu worker's returned socket snapshot |

### Estimated versus measured

The weight-file size is not runtime RAM or VRAM. Observations from 2026-09-03
are recorded in [evaluation.md §5.1](evaluation.md#51-od-03-runtime-comparison):

| Device / runtime | Cold TTFT including load | Warm median TTFT | Warm generation |
|---|---:|---:|---:|
| macOS coordinator, Ollama 0.32.14 | 2.504 s | 0.225 s | 37.9 tok/s |
| Ubuntu worker, Ollama 0.33.2 | 16.0149 s | 0.3369 s | 10.14 tok/s |
| macOS coordinator, bundled engine direct | Unmeasured | 0.0502 s | 36.5 tok/s |

The Ubuntu follow-up snapshot reports runner RSS **2157.4 MiB** and daemon RSS
**54.7 MiB**, separately. Ollama reports model allocation 3,727,561,846 bytes,
of which 2,217,780,180 bytes are GPU allocation at context 4096; this supports
partial GPU placement, not a layer count or percentage of computation. The
earlier benchmark's `rss_mb: 69.7` matched the daemon only and is invalid as
runner or total runtime RAM. macOS uses unified memory, with no separately
reported VRAM. Historical RSS snapshots are not peak or aggregate RAM evidence.

All four responses were identical within each run set; Ubuntu and Mac hashes
differ. Output quality on either device, workload concurrency, container GPU
access and sustained performance remain unverified. The requester deferred
controlled cold-start and Ubuntu direct-engine comparisons at C02 closeout.

## 4. Required manifest

Every approved entry records:

- stable internal model ID;
- display name and exact upstream identifier;
- official source;
- model, code, tokenizer, and runtime licences;
- pinned version, revision, or commit;
- expected files, sizes, and SHA-256 hashes;
- quantisation and format;
- compatible operating systems and runtimes;
- estimated and measured RAM and VRAM;
- supported capabilities and agent profiles;
- tested context and output-token limits;
- download or offline-import method;
- installation, verification, and benchmark state;
- material local modifications.

<a id="reviewed-presets"></a>
### 4.1 Reviewed hardware and capability presets

The catalogue pairs model entries with precomputed hardware/workflow presets. Engineering prepares
the records from authoritative model/runtime data, reproducible published measurements and
representative Refinix qualification. Setup matches detected facts to these records; it does not
derive a new memory model, run automatic benchmarks or search the public Internet to choose settings.
Use a small table in the existing catalogue/profile boundary, not a second recommendation framework.

| Record group | Required fields |
|---|---|
| Identity and provenance | Preset ID/revision; category/workflow; recommended model ID and component hashes; upstream and quantizer identities; source/revision/licences; exact managed engine/build/configuration identity |
| Hardware match | OS family and minimum supported version/range; architecture; CPU instructions/chip constraints; qualified backend and driver prerequisites; total RAM/unified-memory floor; current available-memory floor; dedicated VRAM where relevant |
| Storage | Exact component/download and installed bytes; minimum free space for staging, import, update/backup and configured working space; shared components counted once; units explicit |
| Execution | Context window; maximum input and output/reasoning budgets; tokenizer/template; K/V cache precision and any recurrent-state setting supported by that engine/model; cache reuse/persistence policy; backend/offload; threads/batch settings when material; resident-model and concurrent-slot limits |
| Capacity and behavior | Reviewed peak RAM/VRAM and safety margin at those settings; current-capacity thresholds; approved lower tier or queue/failure behavior; load/unload policy; tested overflow, cancellation and structured-output behavior |
| Evidence | Source URL/date and exact published hardware, model/quant, engine revision and settings when available; workload/sample size; measured externally, measured in Refinix or estimated values; missing information and derivation; qualification/acceptance references |

Device names and brands such as MacBook, ASUS and HP may label representative examples. Match actual
hardware/backend facts rather than vendor names. Apple M-series denotes chips; the OS field remains
macOS. Linux initially means the supported Ubuntu range, not all distributions. Supported ranges
must be justified; an observed OS version does not automatically become the minimum version.

Maintain a recommended choice for each offered category/tier, and optional compatible alternatives
where evidence exists. Chat, Code and document generation may reuse the same qualified model;
OCR/vision, embeddings, speech and image generation retain separate capability requirements. Optional
packs remain optional and later packs remain planned. A 4B model is a candidate, not a universal best
choice across hardware and categories. Never treat a vision model's existence as document OCR proof.

Perform development-side estimates with upstream metadata/tools where needed, publish the assumptions
and use conservative bounds. Do not use advertised maximum context as a laptop default, model file
size as peak memory, or a generic transformer KV formula for an unverified hybrid architecture.
Public short-prompt speed results cannot establish long-context, OCR or sustained concurrent behavior.
Missing measurements stay estimated/unknown; do not copy old engine qualification to a new build.

At setup, compare the detected hardware to a reviewed tier, then check actual free memory/disk and
backend/engine availability. Recheck capacity when admitting work; queue, unload or use an approved
lower preset rather than silently changing qualified settings. Prefix-cache isolation, bounded
context and refusal of unsafe/unsupported execution remain mandatory. Normal users do not create
profiles or manually retune KV/context settings.

Published evidence can establish a candidate tier without owning that laptop. Execution qualification
still binds the shipped model/engine/workflow and supported class. Research, automatic installation
checks and [package/release acceptance](releases.md#beta-01-publication) are separate states.
Initial published findings and their gaps are in
[the research record](evaluation.md#hardware-presets-20261004); no all-OS minimum matrix is accepted yet.

### 4.2 Reuse before new infrastructure

Integrate existing source and suitable maintained tools before building commodity functionality.
These are options for evaluation, not approved new dependencies or permission to install them:

| Need | Existing path or upstream option | Refinix integration still needed |
|---|---|---|
| Development-side preset preparation | Already-considered `llmfit`; documented [hardware profiles, context caps and JSON plans](https://github.com/AlexsJones/llmfit/blob/main/docs/cli.md) | Review estimates and community provenance, then freeze suitable settings into catalogue records. Internal planning only for Beta; no fit service or automatic benchmarks on customers' machines |
| Hardware/capacity facts | Existing `device.py`; Python platform APIs and [psutil](https://psutil.readthedocs.io/stable/) for supported memory/disk/process metrics | Small backend-specific GPU probe; preset matching and truthful missing-data handling. psutil does not provide a universal GPU/VRAM detector |
| Inference resources | Existing runtime adapter plus [llama-server controls](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) for context, output, KV precision, offload and slots | Explicit qualified settings, scheduling/admission policy and engine ownership. Upstream fit may adjust unset arguments; pin settings and disable it where supported when that would change qualification |
| Model acquisition/cache | Existing model/provisioning boundaries; [Hugging Face Hub download APIs](https://huggingface.co/docs/huggingface_hub/en/guides/download) for pinned revisions and selected files | Review hosts/redirects, cancellation/progress, integrity, staging and offline import. Do not rewrite a download/cache stack without a demonstrated policy gap |
| Update trust/application | Existing package/lifecycle boundary; [python-tuf client](https://theupdateframework.readthedocs.io/en/stable/api/tuf.ngclient.html) and evaluated platform tools such as [Sparkle](https://sparkle-project.org/documentation/) on macOS | TUF verifies update metadata/targets; it is not an installer or state-recovery engine. Compare platform replacement tools before writing swap helpers; preserve explicit checks and compatible-data recovery |

Before adoption, pin and review source, licence, version, local changes and network behavior.
For a Hub integration, evaluate its documented
[offline and telemetry controls](https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables):
disable telemetry and implicit token forwarding, suppress CLI update checks if the CLI is used, and
enforce offline/local-only behavior during normal work. Connected provisioning remains user initiated.
Do not use runtime convenience flags that fetch models automatically during normal offline startup.
For internal research tools, do not enable benchmark sharing/upload or provider downloads as a
side effect of inspection. `llmfit` recommendations are planning inputs, not execution qualification.

The application stores this manifest and a reference to runtime-owned weights.
It does not duplicate weights already managed by Ollama, llama.cpp, MLX, or
another approved runtime.

## 5. Evidence states

The UI uses explicit states:

- Candidate
- Licence reviewed
- Compatible by documentation
- Installed
- Integrity verified
- Self-test passed
- Locally benchmarked
- Rejected
- Unavailable

Hardware presentation uses:

- Supported and measured
- Supported by documentation but unmeasured
- Expected to be slow
- Insufficient memory
- Runtime unavailable
- Installed but unverified

For preset resources/performance, distinguish **Measured externally**, **Measured in Refinix**,
**Estimated** and **Unavailable**, with a source/configuration reference. An externally measured
model is not thereby a qualified Refinix package or workflow.

Reported or estimated values never appear as measured.

## 6. Onboarding selection

Apply the same selection rules during onboarding and every later Settings → Models
visit. **Beta / P05 uses compatibility and evidence-labelled fit; P17 owns
calibrated numerical scores.** Compatibility is an execution constraint, not a
quality claim. Show Compatible / Unsupported (or Unverified when unknown), plus
Good fit / Marginal / Unknown where evidence supports that judgement. Label fit
and performance evidence measured, estimated or unavailable.

Show at most six recommendations for the requested capabilities, with supported,
evidence-backed good fits first and Show more below. Beta requires no numeric
score or artificial ordering where evidence cannot distinguish candidates. Users may
select another compatible model or import supported artifacts. A remote-only
client needs no local weights; the target must have all required models/tools.

For all releases, block known-incompatible local execution and explain missing
runtime/tools or insufficient memory for weights, KV cache and runtime overhead.

**P17 only, after calibration:** a score out of 100 may rank explained fit; it
is not universal accuracy. The following requirements gate enabling that score:

- Hard-filter unsupported architecture/runtime, unavailable required tools and
  known insufficient memory for weights, KV cache, runtime overhead and the
  selected context, concurrency and offload.
- Rank remaining choices using task-specific quality evidence, measured/estimated
  response time, memory headroom and user power preference. Quality is workload
  dependent; hardware specifications alone cannot predict accuracy.
- “Speed” should use time-to-first-token and tokens/second; “completion time”
  includes load, prompt and output size. Avoid counting the same latency twice.
- Battery/thermal estimates require reliable data; unavailable measurements remain
  unknown. Explain the score's inputs, missing evidence and model/runtime versions.
- Publish score weights and benchmark normalization before enabling numeric ranks.
  Until calibrated, show compatibility tiers/estimated fit instead of invented
  precision. Label real benchmark success rates with task set, sample size and date.

Each card shows model/version, supported capabilities, quantisation, source/licence,
download and installed size, expected peak RAM/VRAM for the configured context,
runtime/backend and measured versus estimated status. In P17, a 96/100 suitability score
must never be labelled “96% accuracy”. No “100% speed” claim without a defined
comparison. The screenshot's compact bars are a UI reference, not a benchmark.

Warn visibly for slow or memory-heavy choices without treating estimated fit as a download allowlist.
Users may select larger/different models. Report actual unsupported formats/capabilities, insufficient
disk or failed resource admission precisely; lack of team measurement is not an incompatibility.
Automatic routing handles normal task assignment, with optional manual preferences. Installation,
compatibility, upstream results and team-measured quality remain distinct; Beta does not offer a peer
fallback for a local limitation.

## 7. Provisioning

### Connected setup

1. The user explicitly begins connected setup.
2. The app invokes one approved existing runtime or source.
3. Progress, source, size, and cancellation are visible.
4. The app verifies the manifest and available integrity evidence.
5. The smallest real capability self-test runs.
6. Connected setup ends before offline runtime begins.

### Air-gapped setup

1. The user or authorised administrator obtains the approved bundle outside the environment.
2. The bundle moves through controlled removable media or an internal server.
3. The app reads the manifest before execution.
4. Unexpected files, hashes, licences, or executable code are rejected.
5. The model is imported into the approved runtime.
6. The same self-test and catalogue state apply.

There are no silent downloads, update checks, telemetry, or background model
installation during offline runtime.

## 8. Runtime strategy

Beta supports existing local Ollama via its official API and the Refinix-managed upstream
[llama.cpp llama-server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) path.
Ollama-owned models run in Ollama without copying weights. Compatible managed assets run in the
managed engine. Show model origin/runtime, select the backend internally and preserve separate
identities for matching model names. Do not require a technical runtime chooser or second engine
installation. Reusing Ollama files directly in another engine is deferred.

The managed engine remains pinned/integrity-verified as an application dependency. Its ownership,
update and recovery boundary is separate from the optional externally maintained Ollama connection.
On either path, team-measured profiles are evidence, not a blanket model/device/version allowlist.
Local compatibility follows API/features, supported model formats, declared task capabilities,
health/locality and capacity. Unknown or insufficient evidence is labelled; real failures are reported.

Distinguish **Installed**, **Published upstream evidence**, **Checked/observed here** and
**Measured in Refinix**, with **Not usable for this task** when an actual limitation is found.
These are independent facts, not a ladder every model must climb before admission. An upstream
benchmark does not become a Refinix benchmark; a quick check does not prove general reliability.
Recorded observations identify runtime version, runtime-reported digest and relevant settings.
Runtime-reported identity is not independent verification of weight bytes.

Use lightweight hardware recommendations and bounded runtime settings rather than mandatory model
benchmarks. Context/output defaults are recommendations adapted to model declarations and available
capacity, not universal measured limits. Keep explicit context/output/concurrency control and supported
reasoning settings. More than one model/job may run when resources permit; otherwise queue or release
Refinix-managed resources without stopping another app's work.

Version/model/settings changes refresh compatibility information. A newer Ollama version alone must
not block Chat/Documents/Code. Recommend a supported upstream update for a genuinely missing feature;
maintain necessary feature/security exclusions without claiming every new version is safe. Do not
silently change the host. Model selection never changes the backend of an active attempt implicitly.

Preserve validators, approvals, grounding and safe tool execution on both paths. Local open-model
admission does not relax worker qualification or sandbox controls. Package/workflow checks use
representative fixtures and available devices, not every model/hardware combination. Downloads remain
explicit connected setup and use source/revision/licence/integrity metadata, including documented
publisher/CDN redirects handled by established upstream mechanisms. No broad redirect trust or
inference redirects are implied.

For semantic RAG, qualify [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
with a supported local runtime and [sqlite-vec](https://github.com/asg017/sqlite-vec)
as an embedded vector-index candidate alongside existing FTS5. These are proposals,
not installed or approved versions. Check packaging/extension loading and retrieval
quality on each supported platform; no external vector database is required.

Reuse one model across tasks where appropriate while allowing compatible specialist and larger
models without prior team measurement. Demonstrate automatic selection between model identities
and task types with available models/fixtures; do not claim a mocked route demonstrates real model
quality or fit. Published task evidence can guide routing. Voice, speech and image-generation packs
remain later capabilities; listing model metadata does not implement those workflows.

Refinix supplies the harness. [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)
is not adopted; its developer-preview plugin approach is a research option only
for a specific proven gap. Do not add it, LangChain, another router model or a
plugin framework merely because the application is agentic.

The current orchestration decision and LangGraph evaluation criteria are in
[PROJECT.md](PROJECT.md#70-orchestration-choice-and-alternatives). Keep the existing harness for now.
No dedicated orchestrator model is mandatory for obvious routing, and embeddings are required only
when semantic retrieval is enabled. A workflow framework does not replace the inference runtime.

The OD-03 record below explains the prototype choice. Its restriction to comparison
work is superseded by the production qualification direction above; it does not
mean a migration has happened.

### OD-03 — Ollama is the first runtime

**Decision:** the first validation path uses **Ollama** on both critical-path
devices. One runtime, one adapter. `llama.cpp`'s `llama-server` is retained
**only as a measurement comparison**, not as a second production adapter, and
MLX is not adopted for the alpha.

The first validation path is **macOS arm64 + Ubuntu x86_64**. Windows support is
**explicitly unverified** and is not on this path.

Recorded reasons, each traceable:

| Reason | Evidence |
|---|---|
| Already installed on both critical-path devices | macOS coordinator **0.32.14**; Ubuntu worker client/server **0.33.2**, reported 2026-09-03 |
| Observed loopback bind | Both device snapshots show `127.0.0.1:11434`; this does not prove zero public outbound traffic |
| Licence | MIT (`ollama/ollama`) |
| Already holds the selected model | Content-addressed store, integrity re-verifiable offline (§3.1) |
| One API across both operating systems | Same HTTP surface on macOS arm64 and Linux x86_64 |
| Native per-request timings | The measured `/api/chat` streams return `load_duration`, `prompt_eval_duration`, `eval_count`, `eval_duration` |

**The latency concern is measured within a limited scope.** The macOS bundled
engine's warm fixed-prompt TTFT was lower than the earlier Ollama baseline;
generation was approximately 36–38 tok/s for both. This small sequential sample
does not isolate wrapper overhead or establish a general runtime ranking.
Two risks still matter:

1. **Per-request overhead** from the extra HTTP and scheduling layer.
2. **Silent cold reloads** — a model is unloaded after 5 minutes idle by
   default, so an unpinned `keep_alive` turns a "warm" measurement into a cold
   one without saying so.

The [recorded comparison](evaluation.md#51-od-03-runtime-comparison) reused the
same GGUF and the engine bundled with Ollama; it did not install or qualify a
separate upstream llama.cpp release. On 2026-09-03 the requester retained
Ollama and explicitly deferred controlled cold-start and Ubuntu direct-engine
comparisons. Those results remain unmeasured, without blocking C02 acceptance.

Adopt a second adapter only if that measurement, or a hard macOS/Linux blocker,
forces it. Do not create a runtime plugin framework before two proven adapters
require a shared boundary.

| Runtime | Licence | Bind used for this path | Status |
|---|---|---|---|
| Ollama | MIT | `127.0.0.1:11434` | **Selected for the first path** |
| Ollama-bundled `llama-server` | MIT | `127.0.0.1:8080` on macOS, explicitly configured | Direct Mac comparison observed; bundled Ubuntu runner observed but direct comparison deferred. Temporary Mac server stopped by requester. |
| MLX | — | — | Not adopted for the alpha |

## 9. Hardware policy

The recorded prototype fleet has no discrete GPU above 8 GB; this is a test
inventory constraint, not a limit on production users. Begin evaluation with:

- Q4 quantisation;
- bounded context;
- task-specific output-token limits;
- cold and warm measurements;
- explicit CPU offload where tested.

Advertised maximum context does not establish practical fit on this computer. Use declared runtime
limits, published requirements, current capacity and labelled estimates for recommendations; users
may choose beyond recommended defaults. Record settings with observations and enforce actual bounded
requests. Follow the [KV-cache policy](PROJECT.md#132-resource-and-context-policy): the engine owns
allocation. A missing measured resource profile is not a general admission refusal. PagedAttention
is an optional engine capability, not a custom Refinix requirement.

Use the [reviewed presets](#reviewed-presets) for setup defaults and current-capacity thresholds.
Public research may support conservative candidate bounds; keep estimates and missing configuration
details visible and do not declare a tier release-accepted from research alone.

Historical device assignments remain hypotheses in
[devicespecifications.md](devicespecifications.md). Onboarding must use detected
and published/observed/estimated evidence rather than member names or hard-coded machines.

## 10. Listing, local use and demonstrated evidence

A model may be listed from its runtime or recorded upstream metadata without a team benchmark.
For downloads, identify publisher/converter, source/revision, applicable licence, file format/size
and available integrity metadata. Runtime-owned user assets are reported separately from endorsed
or redistributed catalogue assets. Do not label unknown provenance or upstream results as verified
by Refinix.

Local use needs actual runtime/API/task compatibility, locality and capacity handling, not a prior
measurement on an assigned device. Keep specific runtime failures and missing information visible;
preserve workflow validators and user authority. A synthetic self-test is not required to turn
every model into an approved catalogue entry.

Claim that a workflow was demonstrated only after observing it with recorded model/runtime/settings,
inputs and outcomes. Record limitations and offline evidence; do not infer quality from one successful
reply. Release checks use representative integrated app/workflow examples rather than benchmarking
all downloadable models. Package and tool-security acceptance remain separate.

**Reading scanned pages (OCR) is Beta.** Any installed local model that declares vision and offers
structured output may read page images; the app labels the choice "Document OCR model (Beta)" and
"Page reading (Beta)". Results observed on one computer — including the Mac scan-reading records
in 3.2 — are evidence about that model and setting, never an allow-list that admits or excludes
other models. Each extraction records the exact model tag and renderer in its method line.

## 11. Personalisation and optional model adaptation

Personalisation does not require changing model weights. Use the following order;
this is a planned qualification path, not an installed training service.

| Method | Purpose and release boundary |
|---|---|
| User instructions and curated memory | Core: editable preferences and useful durable context, selected within the prompt budget |
| Local corpus and RAG | Core: retrieve current authorised documents with citations; adding knowledge means indexing, not retraining |
| Supervised LoRA adapters | Optional: evaluate only for a demonstrated task/style gap that instructions and retrieval cannot solve |
| Preference optimisation, such as DPO | Optional: needs reviewed preferred/rejected examples and measured improvement; not continuous per-chat reinforcement learning |
| Reward-based reinforcement learning | Experimental: needs a defensible reward, suitable training hardware and regression evidence; never a public-core release prerequisite |

Feedback may inform an editable preference without authorising weight training.
Collect training examples only with explicit opt-in, visible scope, review/export/
deletion controls and separate retention. Personal, organisation and training
stores remain distinct; pairing a worker does not authorise sharing its user's
corpus or training on another user's requests. Remote training needs separate
permission for the data and compute involved.

Keep the base model immutable and version adapters independently. Record exact
base/tokenizer revisions, training code/configuration, source/data rights,
consent and dataset provenance/version, adapter hash/licence, compatible inference
runtime, resource measurements and evaluation evidence. Store private examples
locally, never in repository manifests or logs. An inference GGUF file is not an
automatically supported training input; training and inference formats, adapter
conversion and deployment compatibility need their own qualification.

Before enabling an adapter, compare against the unchanged base on held-out
representative tasks, including factual accuracy, code correctness, refusal and
privacy leakage, resource cost and unrelated capabilities. Keep a known-good
base fallback and user-visible disable/revert control. A higher training reward
alone is not a quality result. Changing the adapter invalidates incompatible
runtime caches. Deleting a source document does not remove information already
learned into weights; document adapter retirement/retraining requirements.

Use established tooling only when this optional stage is justified. Relevant
upstream references are [LoRA in PEFT](https://huggingface.co/docs/peft/main/en/conceptual_guides/lora),
[DPO in TRL](https://huggingface.co/docs/trl/en/dpo_trainer) and
[GRPO in TRL](https://huggingface.co/docs/trl/en/grpo_trainer); these links do not
select dependencies or authorise downloads/training.
