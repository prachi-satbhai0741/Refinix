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

This entry was **not downloaded for this task**. It was already present in the
macOS coordinator's Ollama store from 2026-08-08 and is reused.

| Field | Value |
|---|---|
| Internal ID | `af-main-qwen35-4b-q4km` |
| Upstream identifier | `qwen3.5:4b-q4_K_M` |
| Source | `registry.ollama.ai/library/qwen3.5`, tag `4b-q4_K_M` |
| Format / quantisation | GGUF, `Q4_K_M` (file magic `GGUF` confirmed on the blob) |
| Reported parameter size | `model_type` 4.7B in the image config |
| Weights file | `sha256:81fb60c7daa80fc1123380b98970b320ae233409f0f71a72ed7b9b0d62f40490` — 3,389,971,840 B |
| Config | `sha256:de9fed2251b37295b763727a59ca35cf5cfe5c7379bc3e2104b2ce3c145aa887` — 475 B |
| Licence layer | `sha256:7339fa418c9ad3e8e12e74ad0fd26a9cc4be8703f9c110728a992b193be85cb2` — 11,355 B, **Apache License 2.0** |
| Default params layer | `sha256:9371364b27a52acac9d87f88bd93c9db1174d8d6ec57f6888925cdc1788871ff` — `temperature 1, top_k 20, top_p 0.95, presence_penalty 1.5` |
| Minimum runtime | Ollama `>= 0.17.1` (declared in the image config) |
| Store total | 3.2 GB under `~/.ollama/models` |
| Evidence state | **Integrity verified** — all four blobs re-hashed on the coordinator 2026-09-03 and matched their content-addressed names. **Not** self-test passed; **not** locally benchmarked. |

### Bounded execution settings for the first path

| Setting | Value | Why |
|---|---|---|
| **Thinking** | **`think: false`** (`chat_template_kwargs.enable_thinking: false` on `llama-server`) | **Required, not a preference.** This is a thinking model: left on, it spent the entire output budget reasoning and returned an **empty** answer at `num_predict` 128 *and* 512, both stopping on `length`. With thinking off the same prompt finished in 89 tokens on `stop`. Measured on the macOS coordinator 2026-09-03. |
| Context | `num_ctx` 4096 | Ollama's documented default; an advertised maximum is not a supported context |
| Output limit | `num_predict` 128 for self-test and comparison runs | Enough for a complete answer with thinking off; keeps a failing run cheap |
| Sampling | `temperature` 0, `seed` 42 for checks | Four runs produced one response SHA-256, so a regression is visible; identity is proven by hash, not inferred from counts |
| Idle residency | `OLLAMA_KEEP_ALIVE` explicit rather than the 5-minute default | Otherwise a "warm" measurement silently becomes a cold reload |
| Bind address | `127.0.0.1:11434` | Confirmed loopback-only on the coordinator via `lsof`/`netstat`, per the offline-runtime invariant |

### Estimated versus measured

**Estimated only, from file sizes — not measured anywhere yet:** ~3.2 GiB of
weights plus KV cache and runtime overhead.

- **macOS coordinator** — 16 GiB unified memory. The weights fit with headroom;
  Metal shares unified memory, so there is no separate VRAM ceiling.
- **Ubuntu worker** — RTX 2050 with **4096 MiB VRAM**. 3.2 GiB of weights plus
  KV cache and CUDA context will **not** fit fully in 4 GiB, so expect partial
  CPU offload. 15 GiB of system RAM makes that workable but slower. This is a
  prediction from arithmetic; the measured split must come from the checkpoint
  run, not from this table.

**Measured on the macOS coordinator, 2026-09-03** (see
[evaluation.md §5.1](evaluation.md#51-od-03-runtime-comparison)): cold time to
first token 2.504 s, warm median 0.225 s, ~37.9 tok/s, process RSS 3.83–3.90 GB,
with all four responses sharing one SHA-256. Unified memory means there is no
separate VRAM figure to report on this device.

**Not measured anywhere:** anything on the Ubuntu worker, any VRAM/CPU-offload
split, and output quality on either device. Do not present those until a named
device produces them.

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
| Already installed on both critical-path devices | macOS coordinator client **0.32.14** measured 2026-09-03; Ubuntu worker binary on `PATH` at C01, version to be reported at C02 |
| Loopback by default | Ollama binds `127.0.0.1:11434` unless `OLLAMA_HOST` changes it — the offline-runtime invariant holds with no extra configuration |
| Licence | MIT (`ollama/ollama`) |
| Already holds the selected model | Content-addressed store, integrity re-verifiable offline (§3.1) |
| One API across both operating systems | Same HTTP surface on macOS arm64 and Linux x86_64 |
| Native per-request timings | `/api/generate` returns `load_duration`, `prompt_eval_duration`, `eval_count`, `eval_duration`, so latency evidence needs no extra harness |

**The latency concern is not dismissed.** Ollama wraps `llama.cpp`, so it can
only be slower than calling `llama.cpp` directly; the open questions are *how
much* and *whether it matters at this scale*. Two specific risks:

1. **Per-request overhead** from the extra HTTP and scheduling layer.
2. **Silent cold reloads** — a model is unloaded after 5 minutes idle by
   default, so an unpinned `keep_alive` turns a "warm" measurement into a cold
   one without saying so.

The comparison that settles it is specified in
[evaluation.md](evaluation.md#51-od-03-runtime-comparison). It runs on one
device against the *same GGUF file* — the Ollama blob is a real GGUF, so
`llama-server -m <blob path>` loads the identical weights with no second
download. Until that runs, this decision is **recorded, not proven**.

Adopt a second adapter only if that measurement, or a hard macOS/Linux blocker,
forces it. Do not create a runtime plugin framework before two proven adapters
require a shared boundary.

| Runtime | Licence | Default bind | Status |
|---|---|---|---|
| Ollama | MIT | `127.0.0.1:11434` | **Selected for the first path** |
| `llama.cpp` / `llama-server` | MIT | `127.0.0.1:8080` | Comparison only; **not installed** on either critical-path device |
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
