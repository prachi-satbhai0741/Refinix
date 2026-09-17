# Model Catalogue and Provisioning

## Status and evidence rule

The selected Qwen3.5-4B/Ollama prototype baseline and its dated evidence are
recorded below. Other named components remain candidates unless an exact manifest
and qualifying result says otherwise. Production recommendations require source,
licence, integrity, compatibility and workload evidence, not model-name claims.

The actual fleet and outstanding hardware checks are in
[devicespecifications.md](devicespecifications.md).

## 1. Catalogue purpose

The catalogue converts raw model choices into approved capabilities. It lets
onboarding and persistent Settings → Models answer:

- which main engine fits this device;
- whether an installed model can serve more than one agent profile;
- which dependency is mandatory for an enabled capability;
- whether the model is installed, verified, measured, or unavailable;
- how to reproduce or import the exact artifact.

The recommendation catalogue is curated. Show more and advanced import preserve
user choice among supported models; imports still require provenance, integrity,
licence and runtime compatibility. User choice does not promise every model format
or unrestricted executable model code.

<a id="persistent-model-management"></a>
### Persistent model management

This is the catalogue lifecycle authority for FR-015. **Settings → Models is
always reachable after onboarding**; it manages local models independently of
chat history and application updates. The same lifecycle serves first-run setup
and later changes, rather than two separate installers/catalogues.

| Operation | Required behaviour |
|---|---|
| Browse | Distinguish installed models from supported not-installed entries; show capabilities/profiles, exact source, licence, version/revision, quantisation, download/installed size, runtime and expected hardware requirements from the approved manifest |
| Understand evidence | Distinguish measured, estimated, documentation-only and unverified compatibility/performance; installed does not imply supported or self-tested. Unqualified research candidates are not supported download offers |
| Choose or revisit | Select another compatible model for eligible profiles; refresh recommendations when hardware, runtime or enabled capabilities change, on explicit inspection/self-test without silent public checks |
| Download later | User explicitly starts an approved compatible download; show source, size, progress and cancellation. Stage partial files outside active model entries; failure/cancel leaves existing capabilities usable |
| Import offline | Apply the approved bundle path below, including manifest, provenance/licence, compatibility and integrity; arbitrary files or runtime inventory names never auto-enter the trusted catalogue |
| Verify and self-test | Verify exact files after download/import, then run the capability-specific local test; only successful eligible profiles become ready. Keep failure details and incomplete/unverified states visible |
| Enable or disable | Change profile eligibility explicitly; prevent new placement on disabled models and explain affected queued/active jobs. Never silently change the model of an in-flight attempt |
| Remove safely | Preview affected capabilities/defaults, model references and jobs; drain or explicitly cancel affected work before removal. Require confirmation; preserve shared files referenced by other models and do not delete externally owned runtime stores without a supported explicit removal operation |
| Recover | Interrupted provisioning/removal cannot leave false Ready status or corrupt another model. Preserve catalogue/history; clear stale selections and offer compatible alternatives without overriding user choice |

Band A / P04–P05 implements this for a small approved set, including at least two
appropriate task/model combinations. A small supported set is sufficient; there
is no requirement to invent six qualified choices. Additional models and calibrated
scores are P17. [Workflows](workflows.md#models-after-onboarding) owns interaction;
[evaluation](evaluation.md#beta-acceptance) owns evidence. The current inventory and
per-scope selector do **not** yet implement this lifecycle.

## 2. Baseline and conditional packs

| Pack | Requirement | Notes |
|---|---|---|
| Main engine | Required for local generation; optional for remote-only clients | Chat, planning, tool use, and fallback |
| Documents | Required when Documents is enabled | OCR/vision model or proven equivalent |
| Semantic knowledge | Required when semantic retrieval is enabled | Embedding model plus local index |
| Code | Requires a coding-capable verified model when Code is enabled | May reuse the main engine if it passes the code benchmark |
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

Reported or estimated values never appear as measured.

## 6. Onboarding selection

Apply the same selection rules during onboarding and every later Settings → Models
visit. Compatibility tiers suffice for Beta until numerical scores are calibrated.

Show at most six recommendations for the requested capabilities, sorted by
**suitability score descending** (best first), with Show more below. Users may
select another compatible model or import supported artifacts. A remote-only
client needs no local weights; the target must have all required models/tools.

Use a score out of 100 as an explained fit ranking, not universal accuracy:

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
runtime/backend and measured versus estimated status. A 96/100 suitability score
must never be labelled “96% accuracy”. No “100% speed” claim without a defined
comparison. The screenshot's compact bars are a UI reference, not a benchmark.

Warn visibly for slow or memory-heavy advanced choices. Known-incompatible local
execution is blocked with a reason; downloading for a compatible remote target is
a separate valid choice. The user controls the selection and can revisit it without
resetting chats. Installation status, compatibility and quality are distinct states.

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

**Current:** Ollama, as recorded in OD-03 below. **Preferred production candidate:**
a pinned app-managed [llama.cpp llama-server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)
for qualified GGUF models, using Metal/CUDA/Vulkan/CPU builds only where tested.
Provide a safe CPU fallback where it actually meets the supported profile.

Before replacing the default, compare exact model files and settings on supported
OS/architectures: installation/startup, cold/warm latency, memory, cancellation,
structured outputs, context handling, concurrent admission and document/vision
parity. [Multimodal support](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)
requires supported model architecture and any matching projector assets. Record
build/revision, hashes and licences. Existing Ollama results are not proof that a
separate upstream binary is qualified. Preserve rollback and avoid duplicate weight
stores or a permanent requirement for two runtimes.

For semantic RAG, qualify [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
with a supported local runtime and [sqlite-vec](https://github.com/asg017/sqlite-vec)
as an embedded vector-index candidate alongside existing FTS5. These are proposals,
not installed or approved versions. Check packaging/extension loading and retrieval
quality on each supported platform; no external vector database is required.

Keep one baseline model wherever it meets quality requirements. Specialist coding,
OCR/vision or larger reasoning models enter the supported set only after a measured
benefit on representative tasks. Demonstrate auto-selection with at least two
qualified model options and task types; one model serving several profiles alone
does not demonstrate selection between models. Voice, speech and image-generation
engines remain optional future packs.

Refinix supplies the harness. [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)
is not adopted; its developer-preview plugin approach is a research option only
for a specific proven gap. Do not add it, LangChain, another router model or a
plugin framework merely because the application is agentic.

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

Advertised maximum context is not a supported context. Support comes from local
quality, latency, and memory evidence. Record context/output limits, concurrent
slots, cache precision/reuse settings and backend with each measurement. Follow
the [KV-cache policy](architecture.md#kv-cache-and-runtime-resource-policy): the
engine owns allocation; Refinix admits work against a measured resource budget.
PagedAttention is an optional engine capability, not a custom Refinix requirement.

Historical device assignments remain hypotheses in
[devicespecifications.md](devicespecifications.md). Onboarding must use detected
and measured evidence rather than member names or hard-coded machines.

## 10. Acceptance for one catalogue entry

An entry is demo-ready only when:

- authoritative source and all relevant licences are recorded;
- exact revision and files are pinned;
- integrity verification succeeds;
- the selected runtime loads it locally;
- the representative capability self-test passes;
- memory, latency, and quality are recorded on the assigned device;
- offline runtime completes without an external inference call;
- setup instructions reproduce the result.

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
