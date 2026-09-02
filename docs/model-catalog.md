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

Do not download a second model solely because a second profile exists. Profiles
may share one compatible model while retaining different tools, instructions,
policies, and validators.

Basic local search may begin with SQLite full-text search. An embedding model
becomes mandatory only for semantic retrieval; RAG is the complete retrieval
pipeline, not the name of a single model.

## 3. Candidate shortlist

| Pack | Candidate | Intended use | Status |
|---|---|---|---|
| Main engine | Qwen3.5-4B Q4 candidate | General chat, planning, tool use, and native vision | Research candidate |
| Documents | PaddleOCR-VL-1.6 candidate | OCR, scans, and document layout | Research candidate |
| Semantic knowledge | Qwen3-Embedding-0.6B candidate | Local embeddings | Research candidate |
| Code | Qwen2.5-Coder-7B-Instruct Q4 candidate | Code generation and patch work | Research candidate |
| Reasoning/vision | Qwen3.5-9B Q4 candidate | Optional stronger or visual fallback | Hardware-dependent hypothesis |
| Voice | Qwen3-ASR-0.6B or evaluated local ASR | Local transcription | Optional research candidate |
| Speech output | Kokoro-82M candidate | Local text-to-speech | Deferred |

The upstream [Qwen3.5-4B model card](https://huggingface.co/Qwen/Qwen3.5-4B)
records a vision encoder. This is candidate capability, not proof that a chosen
Q4 file and local runtime work correctly on the target fleet.

This shortlist is not an installation manifest. No candidate may enter the
onboarding picker until its exact source, licence, version, files, hashes, and
runtime path are reviewed.

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

Candidates include Ollama, llama.cpp, and MLX, but the first selection remains
open until:

- the Mac and one Windows worker complete real inference;
- the runtime exposes the required local API and streaming behaviour;
- loopback binding is verified;
- licence and redistribution boundaries are recorded;
- model storage, cancellation, and health reporting are observed.

Do not create a runtime plugin framework before two proven adapters require a
shared boundary.

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
