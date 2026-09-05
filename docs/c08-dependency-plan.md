# C08 dependency plan — what Documents needs that this build does not have

**Status: plan, not an installation.** Nothing here has been downloaded,
installed or run. C07 owes C08 an honest list of what is missing and why; the
install itself is a device checkpoint that happens after C06 passes.

Every version below is a **pin to be confirmed at the checkpoint**, not a
verified fact. Licences are recorded from each project's own repository and must
be re-read at install time — a licence in a plan is a claim, and AGENTS.md
treats it as unverified until the artifact is on the machine with its hash.

---

## 1. What already works, and therefore needs nothing

`backend/coordinator/documents.py` reads `.txt`, `.md`, `.csv`, `.json` and
`.docx` with the standard library, keeps pages separate, and re-verifies the
intake digest before parsing. `docgen.py` writes a real OOXML `.docx` with
`zipfile`. `retrieval.py` searches SQLite FTS5.

**So C08 does not need:** a document parser, a Word writer, a search engine, or
an embedding model. Adding any of them would replace working code with a
dependency.

The C07 fixture pack in [`fixtures/c07/`](../fixtures/c07/) is deliberately
plain text for this reason: it exercises page mapping, citation resolution,
missing values and the SOP traps **through the code that already exists**, with
no install at all.

---

## 2. What is genuinely missing

Two capabilities, and only two.

### 2.1 Rendering a PDF page to an image

**Why the existing components are insufficient.** `documents.py` has no PDF
reader at all, and a text-layer PDF reader would not help with the case C08
exists for: a *scanned* report is a raster image inside a PDF, with no text
layer to extract. There is nothing to parse. The page must be rendered to
pixels before anything can read it.

| | |
|---|---|
| Component | `pypdfium2` (Python binding to PDFium, the renderer in Chromium) |
| Version to pin | to be fixed at the checkpoint from the project's PyPI releases |
| Source | PyPI wheel, `--require-hashes`, same discipline as `backend/worker-image/requirements.lock` |
| Licence to confirm | Apache-2.0 / BSD-3-Clause (PDFium itself is BSD-3-Clause) |
| Wheel size | ~3 MB per platform wheel, plus the bundled PDFium binary |
| Runs offline | yes — it is a local rendering library and opens no network connection |
| Storage | inside the coordinator venv; no model weights, no cache directory |

**The alternative considered and rejected:** `pdf2image` plus a system
`poppler-utils` install. Rejected because it needs a system package manager on
two different operating systems, which is a larger host change than a pinned
wheel, and because it shells out to a binary rather than linking a library.

### 2.2 Reading text out of that image

**Why the existing components are insufficient.** There is no OCR anywhere in
the repository. `documents.py` already reports this rather than approximating
it — its probe returns PDF and OCR as unavailable with the exact missing
prerequisite, which is the honest state and must stay honest until something
real is installed.

| | |
|---|---|
| Component | Tesseract OCR, via the `pytesseract` binding **or** the `tesserocr` binding |
| Version to pin | Tesseract 5.x, exact patch fixed at the checkpoint |
| Source | the OS package for the engine (`apt` on Ubuntu, Homebrew on macOS) plus a pinned PyPI wheel for the binding |
| Licence to confirm | Apache-2.0 (engine); binding licences differ and must be read separately |
| Language data | `eng.traineddata`, ~4 MB for the fast model or ~15 MB for the best model — **a downloaded artifact that needs a recorded source, SHA-256 and storage location** |
| Runs offline | yes, once the engine and the language data are installed |
| Storage | engine in the OS prefix; language data under the recorded `TESSDATA_PREFIX` |

**Why not a vision-language model instead.** The worker already runs a local
model, so "just ask the model to read the scan" looks cheaper than an OCR
install. It is not, for C08's purpose: a VLM produces a plausible reading with
no per-word confidence and no page coordinates, which makes the two things this
workflow is judged on — an honest **uncertainty** signal and a **page-linked
citation** — unavailable. `expected.json`'s `must_not_be` list exists precisely
to catch a confident, fluent, invented measurement. OCR gives a confidence score
per word; a VLM gives a sentence. If a VLM is used later it is an addition, not
a replacement, and it needs its own recorded model provenance.

---

## 3. What each device needs

| Device | Needs | Does not need |
|---|---|---|
| macOS coordinator | Both components. Documents runs locally: `documents.py`, `retrieval.py` and `docgen.py` are coordinator modules, and the C08 acceptance step is opening the Word output on this machine. | Redis, the executor, the worker image |
| Ubuntu worker | Neither, for C08 as scoped. The worker advertises `text.generate` only; `document.extract` is not a capability it offers, and C06 routing will not dispatch a document skill to it. | Both components, unless C12 later moves Documents onto the worker — which is a separate decision with its own checkpoint |

This asymmetry is deliberate and worth stating: **C08 does not need the cluster.**
It needs two installs on one Mac.

---

## 4. What the checkpoint must produce

For each of the four artifacts — two Python packages, one OCR engine, one
language-data file:

1. the exact version installed, from the tool itself, not from this plan;
2. the SHA-256 of every downloaded file;
3. the licence text as shipped, read on the machine;
4. where it was installed and how to remove it;
5. one bounded offline run proving it works: render page 1 of a test PDF, OCR
   it, and compare against known text.

Until those five exist, `docs/model-catalog.md` and `docs/evaluation.md` record
nothing about OCR, and `documents.py` keeps reporting it unavailable.

---

## 5. Explicitly not in this plan

- No model weights, and no change to the OD-05 model choice.
- No cloud OCR, no hosted document API, no telemetry. The offline-runtime
  invariant applies to C08 exactly as it applies to everything else.
- No new dependency for C09. The Code fixture's validation command is
  `python3 -m unittest`, standard library only, by design.
- No installation performed by this change. The exact commands belong in the
  C07 device handoff, written when C06 has passed.
