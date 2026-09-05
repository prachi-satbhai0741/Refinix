# Model Catalogue and Provisioning

## Status and evidence rule

All named models in this document are research candidates. Names, licences,
files, runtime compatibility, memory use, quality, and performance remain
unverified until the repository records authoritative source evidence and local
results.

The actual fleet and outstanding hardware checks are in
[devicespecifications.md](devicespecifications.md).

## 1. Catalogue purpose

The catalogue converts raw model choices into approved capabilities. It lets
onboarding answer:

- which main engine fits this device;
- whether an installed model can serve more than one agent profile;
- which dependency is mandatory for an enabled capability;
- whether the model is installed, verified, measured, or unavailable;
- how to reproduce or import the exact artifact.

The catalogue is curated. It is not a general Hugging Face browser or universal
model downloader.

## 2. Baseline and conditional packs

| Pack | Requirement | Notes |
|---|---|---|
| Main engine | Required on every interactive installation | Chat, planning, tool use, and fallback |
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
| Documents | PaddleOCR-VL-1.6 candidate | OCR, scans, and document layout | Research candidate |
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
Apache-2.0. Their combined footprint is roughly 1.8 GB and all three are
reported to run on CPU, so this pack does not compete with the main engine for
VRAM on an 8 GB device. Two cautions before any of this is called verified: the
IndicTrans2 and Indic-TTS licences still need review, and published Indic ASR
accuracy is far from perfect, so transcripts must enter the normal confidence
and approval path rather than being treated as verbatim input.

This shortlist is not an installation manifest. No candidate may enter the
onboarding picker until its exact source, licence, version, files, hashes, and
runtime path are reviewed.

## 3.1 OD-05 — the first selected model set

**The first model set is one model.** The two signature workflows have not been
implemented, so a Documents, Code, embedding or voice model would be provisioned
before anything could consume it. Those stay unprovisioned until C07 names the
workflow that needs them.

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
| Document work | Desktop Execution 3 sends the model only validated extraction and selected passages, fenced as untrusted data, and parses its reply through a strict schema. No OCR, vision or embedding model is provisioned; retrieval is keyword matching, and OD-07 stays unresolved. Nothing here was measured — the workflow is implemented in source and untested. |
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

The default picker presents Recommended, Fast, Quality, and Advanced choices.
Recommended is computed only from recorded compatible evidence for the detected
device. When no measured result exists, it must say recommended by current
compatibility evidence, not best or fastest.

Before confirmation, show:

- total download and installed size;
- expected peak RAM and VRAM;
- model source and licence;
- runtime and version;
- enabled profiles;
- whether the result is measured on this hardware;
- the smallest self-test that will run afterward.

The user must select a main engine. Dependencies for an enabled capability
cannot be skipped, but the user may disable that capability or choose another
compatible model.

## 7. Provisioning

### Connected setup

1. The user explicitly begins connected setup.
2. The app invokes one approved existing runtime or source.
3. Progress, source, size, and cancellation are visible.
4. The app verifies the manifest and available integrity evidence.
5. The smallest real capability self-test runs.
6. Connected setup ends before offline runtime begins.

### Air-gapped setup

1. An administrator obtains the approved bundle outside the environment.
2. The bundle moves through controlled removable media or an internal server.
3. The app reads the manifest before execution.
4. Unexpected files, hashes, licences, or executable code are rejected.
5. The model is imported into the approved runtime.
6. The same self-test and catalogue state apply.

There are no silent downloads, update checks, telemetry, or background model
installation during offline runtime.

## 8. Runtime strategy

Use one existing local runtime wherever the target fleet permits it. Add a
second adapter only for a measured hardware or operating-system blocker.

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

The current fleet has no discrete GPU above 8 GB. Begin evaluation with:

- Q4 quantisation;
- bounded context;
- task-specific output-token limits;
- cold and warm measurements;
- explicit CPU offload where tested.

Advertised maximum context is not a supported context. Support comes from local
quality, latency, and memory evidence.

Tentative device assignments remain hypotheses in
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
