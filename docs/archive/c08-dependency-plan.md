# C08 dependencies — what Documents needs, and what is actually installed

The old text-only OCR reply schema and model defaults below are historical.
Current typed transcription/unreadable/refusal handling and model-selection gaps
are recorded in [evaluation](../evaluation.md#beta-source-audit).

> Historical prototype record/template. Retained for reproduction and dated evidence.
> Current scope and order are in [tasks.md](../../tasks.md#numbered-execution-tasks);
> refresh source/device facts and obtain applicable authorisation before using old steps.

**Status: implemented against components that were already present. Nothing
was downloaded, installed, pulled or removed by this change.**

This document replaces the earlier Tesseract + `pypdfium2` plan. That plan
proposed two installs; the decision taken instead was to use what the machine
already has, so C08 needs **no new dependency at all**. What follows is the
recorded state of those components on the macOS coordinator on **2026-09-05**,
including one finding that blocks the workflow at runtime.

Every fact below was read from the machine with a read-only command. Nothing
is inferred from a component's name.

---

## 1. What already works, and therefore needs nothing

`backend/coordinator/documents.py` reads `.txt`, `.md`, `.csv`, `.json` and
`.docx` with the standard library, keeps pages separate, and re-verifies the
intake digest before parsing. `docgen.py` writes a real OOXML `.docx` with
`zipfile`. `retrieval.py` searches SQLite FTS5.

**So C08 does not need:** a document parser, a Word writer, a search engine, or
an embedding model. Adding any of them would replace working code with a
dependency.

---

## 2. Rendering a PDF page — PyObjC Quartz, already installed

**Superseded:** the earlier plan named `pypdfium2`, to be downloaded as a
pinned wheel. It was not installed and is not needed.

The desktop environment already ships PyObjC, which binds the macOS Quartz
framework. `CGPDFDocument` renders a page to a bitmap, and `CGImageDestination`
encodes it — both are part of the operating system.

| | |
|---|---|
| Component | `Quartz`, via PyObjC |
| Observed version | `objc.__version__` = **12.2.2**, in `desktop/.venv` (Python 3.12.13) |
| Source | already present in the locked desktop environment; nothing was fetched |
| Downloads required | **none** |
| Runs offline | yes — an operating-system framework, no network path |
| Implemented in | [`backend/coordinator/pdfrender.py`](../../backend/coordinator/pdfrender.py) |

**Observed behaviour**, from `backend.coordinator.test_ocr.TestRealRenderer`
run under `desktop/.venv` on 2026-09-05: `fixtures/c07/documents/inspection-report-scan.pdf`
renders to **3 pages, 1131 × 1600 px**, PNG, ~99–108 KB each, and the same
input produces byte-identical output twice.

**Where it is absent** — the plain `.venv` coordinator environment, the Ubuntu
worker, and any non-Apple computer — `pdfrender.probe()` reports it unavailable
with the exact missing prerequisite, and PDF extraction is refused rather than
half-performed. This was verified: `.venv` has no `Quartz` module and the
capability correctly reports so.

---

## 3. Reading text out of that image — the installed model, and a blocker

**Superseded:** the earlier plan named Tesseract 5.x plus a language-data
download. Neither was installed and neither is proposed now.

### 3.1 What is installed

An Ollama manifest for `MedAIBase/PaddleOCR-VL:0.9b` is present locally. These
are the observed manifest facts, read from
`~/.ollama/models/manifests/.../MedAIBase/PaddleOCR-VL/0.9b`:

| field | observed value |
|---|---|
| manifest digest (`/api/tags`) | `2d9290d5ab53a5eb50ba12903909ae3879408ca7ef0e5361092967c06cfbfdaf` |
| config digest | `sha256:e4ecc823369bd984af05fae8d580273e469c5728f8f46e6fd585ee2fef8bfc6c` (422 bytes) |
| model layer | `sha256:3ac47f4557c259c4c680c762729fb4b94e9572c9d52f9104c2f00013caaf9b0e` |
| model layer size | 935 768 512 bytes |
| other layers | system (31 bytes), params (35 bytes) |
| architecture (`/api/show`) | `paddleocr` |
| parameter count | 466 654 208 (**466.65M**, not 0.9B) |
| quantisation | BF16 |
| Ollama server | 0.33.3 |

**Source, licence and provenance: UNRESOLVED.** This is a third-party
conversion published under an account name. Nothing here establishes who built
it, from what, under what licence, or whether it corresponds to any official
release. It must not be described as "PaddleOCR" without that evidence, and
`docs/model-catalog.md` records it as an **installed candidate only**.

### 3.2 The finding: it does not accept images

**`MedAIBase/PaddleOCR-VL:0.9b` cannot read a scan on this machine.**

Three independent observations, all on 2026-09-05:

1. `/api/show` reports `capabilities: ["completion"]`. It does **not** list
   `vision`. For comparison, `qwen3.5:4b-q4_K_M` on the same runtime reports
   `["completion", "vision", "tools", "thinking"]`.
2. The manifest contains **one** `application/vnd.ollama.image.model` layer and
   **no** `application/vnd.ollama.image.projector` layer. A multimodal Ollama
   model needs a projector; this manifest has none.
3. Sending a rendered page returns:

   ```text
   HTTP 500 image input is not supported - hint: if this is unexpected,
   you may need to provide the mmproj
   ```

So the tag carries "VL" in its name and is, as packaged, a text-only model.
This is exactly the case AGENTS.md means by treating names as unverified.

**What the code does about it.** `runtime.model_state(..., requires="vision")`
asks the runtime what the model can do and requires `vision` in the answer
before a single page image is sent. The state is its own value —
`missing_capability` — separate from `absent` and from `runtime_unavailable`,
because the three need three different fixes. `documents.probe()` therefore
reports PDF and scan reading as **unavailable**, and `extract()` refuses a PDF
with the code `model_cannot_read_images`. Nothing is downloaded and nothing is
guessed.

### 3.3 What the pipeline does once a vision-capable model is configured

The rest of C08 is implemented and was exercised end to end. Using the
`AEGIS_OCR_MODEL` override to point at the **already-installed**
`qwen3.5:4b-q4_K_M` — no download — the full path ran on 2026-09-05:

* page 1 of the C07 scan transcribed in **16.2 s**, 583 characters;
* every `expected_facts` value whose `scan_page` is stated was recovered **on
  the page the fixture names**;
* the illegible gauge came back as `SUCTION PRESSURE: NOT RECORDED (GAUGE
  ILLEGIBLE)` — the `must_not_be` trap was not taken;
* the countersignature was reported absent, not supplied;
* `confidence` stayed `None` on every page.

That is recorded as **local fixture evidence** in
[`docs/evaluation.md`](../evaluation.md#1-evidence-labels) terms: it shows this
machine's renderer, transport and parser recover known facts from pixels. It is
**not** an OCR quality benchmark, it is not evidence about any other scan, and
it is not a decision to change the configured model.

### 3.4 The decision this leaves to the human gate

`AEGIS_OCR_MODEL` exists so the checkpoint can choose, without a code change:

* **point C08 at an already-installed vision-capable model** — no download, and
  `qwen3.5:4b-q4_K_M` is observed to declare `vision`; or
* **install a vision-capable OCR model** — a download, with its own approved
  source, licence, hash and storage, recorded in the model catalogue; or
* **leave it as configured** — C08 reports scan reading unavailable, which is
  honest and fails closed.

This is a requester decision, not an agent one. The default remains the
configured `MedAIBase/PaddleOCR-VL:0.9b`.

---

## 4. Honesty rules the implementation enforces

The earlier plan argued that a VLM cannot supply per-word confidence or page
coordinates, and that this makes uncertainty and page-linked citation
unavailable. That argument was correct, and the code is built around it rather
than around hiding it:

* `Page.confidence` is always `None` on a vision reading. `None` means "not
  measured"; it is never rendered as `0.0` or as a percentage.
* Every such extraction carries a fixed note saying confidence is unavailable
  for it, and that the reading came from a standalone vision-language component
  rather than the complete PaddleOCR document-layout pipeline.
* **The coordinator owns page numbers.** It renders and sends one page at a
  time and numbers them itself; the model is never told which page it is
  looking at and has no field in which to return one. Page mapping is therefore
  an observation, not a model output.
* The reply schema has exactly one field, `text`. A reply containing
  `confidence`, `page`, a source or anything else is refused.
* A malformed reply gets exactly one bounded repair attempt. A second
  malformed reply fails.

---

## 5. What each device needs

| Device | Needs | Does not need |
|---|---|---|
| macOS coordinator | PyObjC Quartz (**present**) and a vision-capable local model (**see 3.2**). Documents runs here: `documents.py`, `pdfrender.py`, `ocr.py`, `retrieval.py` and `docgen.py` are coordinator modules. | Redis, the executor, the worker image |
| Ubuntu worker | Neither. The worker advertises `text.generate`, `code.generate` and `code.validate`; `document.extract` is not offered, and routing will not dispatch a document skill to it. | Both, unless a later decision moves Documents onto the worker |

**C08 still does not need the cluster.** It needs one Mac.

---

## 6. Explicitly not in this plan

- No model weights committed, and no change to the OD-05 chat model.
- No cloud OCR, no hosted document API, no telemetry.
- No new dependency for C09: the validation command is `python3 -m unittest`,
  standard library only, by design.
- No installation, download or model pull performed by this change.
