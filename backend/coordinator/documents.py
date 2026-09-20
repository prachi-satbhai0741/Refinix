"""Reading documents the user attached to one request.

Execution 3's extraction boundary. What it can honestly do is decided by what
is actually installed, not by what the interface would like to offer:

* **text** — `.txt`, `.md`, `.csv`, `.json`. Strict UTF-8, one page.
* **Word** — `.docx`. A `.docx` is a ZIP of OOXML, so the standard library
  reads it: `zipfile` plus `xml.etree`. Paragraphs and table cells, split into
  pages at explicit page breaks.
* **Excel** — `.xlsx`. Also a ZIP of OOXML, read by `xlsx.py`, one page per
  worksheet so a cell reference resolves. No formula is ever calculated.
* **PDF** — rendered page by page by whichever renderer this computer has, and
  read by the local vision model (`pdfrender.py` and `ocr.py`). The portable
  PDFium engine is preferred on Windows, macOS and Linux alike, with the macOS
  Quartz framework retained as a fallback. Where no renderer or no model is
  present, `probe()` reports the exact missing prerequisite and the file is
  refused rather than half-read. The method string names the renderer that
  actually drew the pages, never a fixed framework.
* **images** — `.png` and `.jpg`/`.jpeg`, sent straight to the local vision
  model as one page. A supplied image already *is* a page image, so there is
  no renderer in that path and the method string never claims one. Other
  picture formats are refused by name rather than accepted on the strength of
  the transport carrying any bytes.

A vision reading is never described as more than it is: it carries the exact
model tag, no per-word confidence, and no layout detection.

Rules that hold for every source:

* the stored bytes are hashed and compared with the digest recorded at intake
  before a single byte is parsed;
* extracted text stays split by page, with the page number kept beside it;
* what is uncertain is said to be uncertain — a missing page count stays
  missing rather than becoming 1;
* filenames and contents are untrusted data. They are never executed, never
  interpolated into an instruction, and never placed whole into an audit row,
  an error message or a log line.

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from backend.coordinator import ocr, pdfrender, xlsx

# Bounds. Visible in the errors, so a refusal explains itself.
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_PAGES = 400
MAX_PAGE_CHARS = 40_000
MAX_TOTAL_CHARS = 1_500_000
MAX_DOCUMENT_XML_BYTES = MAX_TOTAL_CHARS * 4
MAX_APP_XML_BYTES = 64 * 1024

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

TEXT_SUFFIXES = {".txt": "text/plain", ".md": "text/markdown",
                 ".csv": "text/csv", ".json": "application/json"}
WORD_SUFFIX = ".docx"

SHEET_SUFFIX = ".xlsx"

# Formats a parser exists for, and the ones that need something this computer
# does not have. Neither list is guessed: `probe()` derives both.
PDF_SUFFIX = ".pdf"
NEEDS_PDF_PARSER = {PDF_SUFFIX}

# Images sent straight to the local vision model. The whole path — signature
# check, transport, reply schema — has been exercised for these two.
IMAGE_SUFFIXES = dict(ocr.IMAGE_SUFFIXES)

# Pictures this build will not claim to read. Listing them separately is the
# point: they are refused by name rather than accepted because the transport
# would carry any bytes. Adding one means exercising it first.
NEEDS_OCR = {".tif", ".tiff", ".heic", ".webp"}


class DocumentError(ValueError):
    """A refusal the interface can show, with a code a test can assert."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------
# Capability probe
# --------------------------------------------------------------------------

def probe(runtime_state: dict | None = None,
          ocr_model: str = ocr.runtime.OCR_MODEL) -> dict:
    """What this module can actually extract, not merely what is importable.

    `runtime_state` is an already-observed `runtime.probe()`. Passing it keeps
    a status page from re-probing the model runtime once per capability row;
    omitting it makes one fresh observation. Either way the answer describes
    what was observed, never a configured default.
    """
    scan = (ocr.probe(ocr_model) if runtime_state is None
            else _scan_capability(runtime_state, ocr_model))
    image = (ocr.image_probe(ocr_model) if runtime_state is None
             else _image_capability(runtime_state, ocr_model))
    return {
        "text": {
            "available": True,
            "formats": sorted(s.lstrip(".") for s in TEXT_SUFFIXES),
            "detail": "Read as UTF-8 text on this computer.",
        },
        "word": {
            "available": True,
            "formats": ["docx"],
            "detail": "Read with the standard library: a .docx is a ZIP of XML.",
        },
        "pdf": {
            "available": scan["available"],
            "formats": ["pdf"] if scan["available"] else [],
            "module": scan["renderer"].get("module"),
            "detail": scan["detail"],
        },
        # OCR here means "reading pixels". The PDF path renders first; a
        # supplied image is already a page image and is sent as it is. The two
        # share the model prerequisite but not the renderer, so an image can be
        # readable on a computer where PDF rendering is not.
        "ocr": {
            "available": image["available"] or scan["available"],
            "formats": (sorted(s.lstrip(".") for s in IMAGE_SUFFIXES)
                        if image["available"] else []),
            "module": (image["model"].get("model") if image["available"]
                       else None),
            "detail": (image["detail"] if image["available"] else
                       "Refinix does not guess at words in a picture. "
                       + image["detail"]),
        },
    }


def _scan_capability(runtime_state: dict,
                     ocr_model: str = ocr.runtime.OCR_MODEL) -> dict:
    """`ocr.probe()` against a runtime observation someone else already made."""
    render = pdfrender.probe()
    caps = None
    if runtime_state.get("reachable") and \
            ocr_model in (runtime_state.get("models") or []):
        # A cheap metadata read (~10 ms, no model load). Asking is what keeps
        # this from advertising OCR because a tag has "VL" in its name.
        caps = ocr.runtime.model_capabilities(ocr_model)
    model = ocr.runtime.model_state_from(
        runtime_state, ocr_model,
        requires=ocr.runtime.VISION_CAPABILITY, capabilities=caps)
    if not render["available"]:
        return {"available": False, "renderer": render, "model": model,
                "detail": render["detail"]}
    if model["state"] != "installed":
        return {"available": False, "renderer": render, "model": model,
                "detail": model["detail"]}
    return {"available": True, "renderer": render, "model": model,
            "detail": (f"Pages are rendered with {render['module']} and read by "
                       f"{model['model']} on the local runtime. "
                       + ocr.STANDALONE_NOTE)}


def _image_capability(runtime_state: dict,
                      ocr_model: str = ocr.runtime.OCR_MODEL) -> dict:
    """`ocr.image_probe()` against a runtime observation someone else made.

    The renderer is deliberately absent: a supplied image needs the model and
    nothing else, so a missing PyObjC must not hide a capability that works.
    """
    caps = None
    if runtime_state.get("reachable") and \
            ocr_model in (runtime_state.get("models") or []):
        caps = ocr.runtime.model_capabilities(ocr_model)
    model = ocr.runtime.model_state_from(
        runtime_state, ocr_model,
        requires=ocr.runtime.VISION_CAPABILITY, capabilities=caps)
    if model["state"] != "installed":
        return {"available": False, "model": model, "detail": model["detail"]}
    return {"available": True, "model": model,
            "detail": (f"Supplied images are read by {model['model']} on the "
                       f"local runtime. " + ocr.STANDALONE_NOTE)}


def supported_suffixes(runtime_state: dict | None = None,
                       ocr_model: str = ocr.runtime.OCR_MODEL) -> list[str]:
    """Exactly what `extract` implements on this computer, right now."""
    capability = probe(runtime_state, ocr_model)
    suffixes = [*TEXT_SUFFIXES, WORD_SUFFIX, SHEET_SUFFIX]
    if capability["pdf"]["available"]:
        suffixes.append(PDF_SUFFIX)
    if capability["ocr"]["formats"]:
        suffixes.extend(IMAGE_SUFFIXES)
    return sorted(suffixes)


def capability_summary(runtime_state: dict | None = None,
                       ocr_model: str = ocr.runtime.OCR_MODEL) -> dict:
    """One shape the surfaces and the capability rows both read."""
    capability = probe(runtime_state, ocr_model)
    unavailable = [
        {"kind": kind, "detail": entry["detail"]}
        for kind, entry in capability.items() if not entry["available"]
    ]
    return {
        "supported": [s.lstrip(".") for s in
                      sorted([*TEXT_SUFFIXES, WORD_SUFFIX]
                             + ([PDF_SUFFIX] if capability["pdf"]["available"] else []))],
        "unavailable": unavailable,
        "reads_pdf": capability["pdf"]["available"],
        "reads_scans": capability["ocr"]["available"],
        "detail": capability,
        "max_bytes": MAX_DOCUMENT_BYTES,
    }


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

@dataclass
class Page:
    number: int                       # 1-based, as a reader would count
    text: str
    confidence: float | None = None   # None means "not measured", never 0.0
    note: str | None = None

    def as_dict(self) -> dict:
        return {"number": self.number, "text": self.text,
                "confidence": self.confidence, "note": self.note}


@dataclass
class Extraction:
    source_id: str                    # the attachment id: stable, opaque
    filename: str
    media_type: str
    sha256: str
    byte_size: int
    method: str                       # how it was read; never called OCR unless it was
    pages: list[Page] = field(default_factory=list)
    page_count: int | None = None     # None when the format does not state one
    uncertain: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)

    def as_dict(self) -> dict:
        return {"source_id": self.source_id, "filename": self.filename,
                "media_type": self.media_type, "sha256": self.sha256,
                "byte_size": self.byte_size, "method": self.method,
                "page_count": self.page_count,
                "pages": [page.as_dict() for page in self.pages],
                "uncertain": list(self.uncertain)}


def _clean(text: str) -> str:
    """Normalise without changing what the document says."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Control characters other than tab and newline are not content.
    text = "".join(ch for ch in text
                   if ch in "\t\n" or unicodedata.category(ch)[0] != "C")
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def _bounded(pages: list[Page], filename: str) -> list[Page]:
    if len(pages) > MAX_PAGES:
        raise DocumentError(
            "too_many_pages",
            f"{filename} has more than {MAX_PAGES} pages. Refinix reads up to "
            f"{MAX_PAGES}.")
    total = 0
    for page in pages:
        if len(page.text) > MAX_PAGE_CHARS:
            page.text = page.text[:MAX_PAGE_CHARS]
            page.note = (f"Only the first {MAX_PAGE_CHARS} characters of this "
                         "page were read.")
        total += len(page.text)
    if total > MAX_TOTAL_CHARS:
        raise DocumentError(
            "too_much_text",
            f"{filename} holds more text than Refinix reads in one request.")
    return pages


def _extract_text(data: bytes, filename: str, media_type: str) -> tuple[list[Page], str, list[str]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentError(
            "encoding",
            f"{filename} is not UTF-8 text. Refinix reads UTF-8 files in this "
            "version; save it as UTF-8 and attach it again.") from exc
    if media_type == "application/json":
        try:
            json.loads(text)
        except ValueError:
            # Still readable as text; say so rather than refusing.
            return ([Page(1, _clean(text), note="Not valid JSON; read as plain text.")],
                    "utf-8 text", ["This file is not valid JSON."])
    # A plain text file has no page structure. Saying "page 1" is a convention
    # for citation, not a claim that the file declares pages.
    return [Page(1, _clean(text))], "utf-8 text", []


def _docx_paragraph_parts(node) -> list[str]:
    """Paragraph text split at explicit or rendered page breaks."""
    pages, parts = [], []
    for child in node.iter():
        if child.tag == f"{WORD_NS}t" and child.text:
            parts.append(child.text)
        elif child.tag == f"{WORD_NS}tab":
            parts.append("\t")
        elif (child.tag == f"{WORD_NS}br"
              and child.get(f"{WORD_NS}type") == "page") \
                or child.tag == f"{WORD_NS}lastRenderedPageBreak":
            pages.append("".join(parts))
            parts = []
        elif child.tag in (f"{WORD_NS}br", f"{WORD_NS}cr"):
            parts.append("\n")
    pages.append("".join(parts))
    return pages


def _docx_paragraph_text(node) -> str:
    return "\n".join(_docx_paragraph_parts(node))


def _read_zip_part(archive: zipfile.ZipFile, name: str, limit: int,
                   filename: str) -> bytes:
    try:
        info = archive.getinfo(name)
    except KeyError:
        raise
    if info.file_size > limit:
        raise DocumentError("too_much_text",
                            f"{filename} holds more text than Refinix reads.")
    try:
        with archive.open(info) as handle:
            raw = handle.read(limit + 1)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise DocumentError("malformed", f"{filename} has a damaged Word part.") from exc
    if len(raw) > limit:
        raise DocumentError("too_much_text",
                            f"{filename} holds more text than Refinix reads.")
    return raw


def _extract_docx(data: bytes, filename: str) -> tuple[list[Page], str, list[str], int | None]:
    """Read a .docx with the standard library.

    A .docx is a ZIP holding `word/document.xml`. Only that part is read, and
    it is parsed as data: no external entities, no relationship following, no
    embedded object is opened or executed.
    """
    import io
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as exc:
        raise DocumentError(
            "malformed", f"{filename} is not a readable Word file.") from exc
    with archive:
        try:
            info = archive.getinfo("word/document.xml")
        except KeyError as exc:
            raise DocumentError(
                "malformed",
                f"{filename} does not contain a Word document part.") from exc
        raw = _read_zip_part(archive, info.filename, MAX_DOCUMENT_XML_BYTES,
                             filename)
        declared_pages = _docx_declared_pages(archive, filename)

    try:
        # ET does not resolve external entities, which is what matters here.
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise DocumentError(
            "malformed", f"{filename} has a damaged Word document part.") from exc

    body = root.find(f"{WORD_NS}body")
    if body is None:
        raise DocumentError("malformed", f"{filename} has no document body.")

    pages: list[Page] = []
    current: list[str] = []
    for block in body:
        if block.tag == f"{WORD_NS}p":
            for index, line in enumerate(_docx_paragraph_parts(block)):
                if index:
                    pages.append(Page(len(pages) + 1,
                                      _clean("\n".join(current))))
                    current = []
                if line.strip():
                    current.append(line)
        elif block.tag == f"{WORD_NS}tbl":
            for row in block.findall(f"{WORD_NS}tr"):
                cells = [_docx_paragraph_text(cell).strip()
                         for cell in row.findall(f"{WORD_NS}tc")]
                if any(cells):
                    current.append(" | ".join(cells))
    if current or not pages:
        pages.append(Page(len(pages) + 1, _clean("\n".join(current))))

    uncertain = []
    if declared_pages is None:
        uncertain.append(
            "Word does not store a final page count; pages here are split at "
            "explicit page breaks and may not match a printed copy.")
    if not any(page.text for page in pages):
        uncertain.append("No text was found. The file may hold only images, "
                         "which Refinix cannot read without OCR.")
    return pages, "docx (openxml)", uncertain, declared_pages


def _docx_declared_pages(archive: zipfile.ZipFile, filename: str) -> int | None:
    """The page count Word last wrote, when it wrote one. Never invented."""
    try:
        raw = _read_zip_part(archive, "docProps/app.xml", MAX_APP_XML_BYTES,
                             filename)
    except KeyError:
        return None
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    for element in root:
        if element.tag.rsplit("}", 1)[-1] == "Pages" and (element.text or "").strip():
            try:
                value = int(element.text.strip())
            except ValueError:
                return None
            return value if value > 0 else None
    return None


def _extract_pdf(data: bytes, filename: str, *, should_cancel=None,
                 ocr_model: str = ocr.runtime.OCR_MODEL):
    """Render each page and read it with the local vision model.

    The capability is re-checked here rather than trusted from an earlier
    probe: a runtime that stopped answering between the status poll and this
    request must refuse, not half-read. A page that cannot be read fails the
    whole extraction — a document silently missing a page would be worse than
    no document at all.
    """
    scan = ocr.probe(ocr_model)
    if not scan["available"]:
        # Three prerequisites, three codes. Collapsing them would send someone
        # to install PyObjC when the model is what is missing.
        code = ("no_pdf_parser" if not scan["renderer"]["available"] else
                {"runtime_unavailable": "runtime_unavailable",
                 "absent": "no_ocr_model",
                 "missing_capability": "model_cannot_read_images",
                 "capability_unknown": "model_capability_unknown",
                 }.get(scan["model"]["state"], "no_ocr_model"))
        raise DocumentError(code, scan["detail"])
    try:
        read = ocr.extract_pdf(data, filename=filename, should_cancel=should_cancel,
                               model=ocr_model)
    except ocr.OcrError as exc:
        # `cancelled` keeps its own code so the workflow can tell a stop from a
        # failure; everything else is a refusal with the extractor's reason.
        raise DocumentError(exc.code, str(exc)) from exc
    pages = [Page(number=page["number"], text=_clean(page["text"]),
                  # Not measured by this component, so it stays unmeasured.
                  confidence=None, note=page["note"])
             for page in read["pages"]]
    return pages, read["method"], list(read["uncertain"]), read["page_count"]


def _extract_xlsx(data: bytes, filename: str) -> tuple[list[Page], str, list[str], int | None]:
    """Read an .xlsx with the standard library, one page per worksheet.

    A worksheet is the natural page here: it is what a person points at when
    they say where a value is, and it makes `Sheet2!B7` resolvable. Nothing is
    calculated — a formula cell reports its formula and any cached value Excel
    left behind, labelled as cached.
    """
    try:
        book = xlsx.read(data, filename)
    except xlsx.SheetError as exc:
        raise DocumentError(exc.code, str(exc)) from exc

    pages = [Page(number=index, text=_clean(xlsx.as_text([sheet])),
                  note=f"worksheet {sheet['name']}")
             for index, sheet in enumerate(book["sheets"], start=1)]
    uncertain = [
        "Cell values are read as the workbook stores them. No formula was "
        "calculated: a formula cell reports its formula and, where Excel left "
        "one, its cached value marked as cached rather than recomputed.",
    ]
    if book["skipped"]:
        uncertain.append("Not read: " + ", ".join(book["skipped"]) + ".")
    return pages, "xlsx (OOXML, standard library)", uncertain, len(pages)


def _extract_image(data: bytes, filename: str, media_type: str, *,
                   should_cancel=None,
                   ocr_model: str = ocr.runtime.OCR_MODEL):
    """Send one supplied image to the local vision model, as page 1.

    No renderer at all: the file already is a page image. The method string says
    exactly that, so a reader is never told a PDF was rendered when none was.
    """
    state = ocr.image_probe(ocr_model)
    if not state["available"]:
        code = {"runtime_unavailable": "runtime_unavailable",
                "absent": "no_ocr_model",
                "missing_capability": "model_cannot_read_images",
                "capability_unknown": "model_capability_unknown",
                }.get(state["model"]["state"], "no_ocr_model")
        raise DocumentError(code, state["detail"])
    try:
        read = ocr.extract_image(data, filename=filename, media_type=media_type,
                                 should_cancel=should_cancel, model=ocr_model)
    except ocr.OcrError as exc:
        raise DocumentError(exc.code, str(exc)) from exc
    pages = [Page(number=page["number"], text=_clean(page["text"]),
                  confidence=None, note=page["note"])
             for page in read["pages"]]
    return pages, read["method"], list(read["uncertain"]), read["page_count"]


def extract(path: Path, *, source_id: str, filename: str, media_type: str,
            expected_sha256: str, should_cancel=None,
            ocr_model: str = ocr.runtime.OCR_MODEL) -> Extraction:
    """Read one attachment, after proving it is the file that was accepted.

    `expected_sha256` is the digest recorded at intake. Recomputing it here is
    what makes the rest of the pipeline about a known document rather than
    whatever happens to be on disk now.
    """
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        handle = os.open(path, flags)
        try:
            info = os.fstat(handle)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise OSError("not a private regular file")
            chunks, total = [], 0
            while total <= MAX_DOCUMENT_BYTES:
                chunk = os.read(handle, min(1 << 16, MAX_DOCUMENT_BYTES + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            data = b"".join(chunks)
        finally:
            os.close(handle)
    except OSError as exc:
        raise DocumentError(
            "unreadable", f"{filename} could not be read from local storage.") from exc
    if len(data) > MAX_DOCUMENT_BYTES:
        raise DocumentError(
            "too_large",
            f"{filename} is larger than {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB.")
    if not data:
        raise DocumentError("empty", f"{filename} is empty.")

    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise DocumentError(
            "digest_mismatch",
            f"{filename} is not the file Refinix accepted: its contents changed. "
            "Attach it again.")

    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if suffix in NEEDS_OCR:
        # Not "cannot read pictures" — this build reads PNG and JPEG. These
        # formats are refused because their path has not been exercised, and
        # saying so is more use than a generic refusal.
        supported = ", ".join(sorted(s.lstrip(".") for s in IMAGE_SUFFIXES))
        raise DocumentError(
            "unsupported_image",
            f"Refinix reads {supported} images directly, and reads other scans "
            f"inside a PDF. {suffix.lstrip('.')} is not supported here yet.")

    declared_pages: int | None = None
    if suffix in TEXT_SUFFIXES:
        pages, method, uncertain = _extract_text(data, filename, media_type)
        declared_pages = 1
    elif suffix == WORD_SUFFIX:
        pages, method, uncertain, declared_pages = _extract_docx(data, filename)
    elif suffix == SHEET_SUFFIX:
        pages, method, uncertain, declared_pages = _extract_xlsx(data, filename)
    elif suffix in IMAGE_SUFFIXES:
        pages, method, uncertain, declared_pages = _extract_image(
            data, filename, media_type, should_cancel=should_cancel,
            ocr_model=ocr_model)
    elif suffix == PDF_SUFFIX:
        pages, method, uncertain, declared_pages = _extract_pdf(
            data, filename, should_cancel=should_cancel, ocr_model=ocr_model)
    else:
        readable = sorted([*TEXT_SUFFIXES, WORD_SUFFIX, SHEET_SUFFIX,
                           PDF_SUFFIX, *IMAGE_SUFFIXES])
        raise DocumentError(
            "unsupported",
            f"Refinix cannot read {suffix or 'a file without an extension'} yet. "
            f"It reads: {', '.join(item.lstrip('.') for item in readable)}.")

    pages = _bounded(pages, filename)
    if not any(page.text.strip() for page in pages):
        uncertain.append("No readable text was found in this file.")
    return Extraction(
        source_id=source_id, filename=filename, media_type=media_type,
        sha256=actual, byte_size=len(data), method=method, pages=pages,
        # Only what the format actually states. A text file is one page by
        # definition; a Word file keeps None when Word wrote no count.
        page_count=declared_pages, uncertain=uncertain)


def redact(text: str, limit: int = 120) -> str:
    """A short, single-line excerpt for an error or an audit row.

    Full document content never reaches a log, an audit row or an error
    message; a truncated first line is enough to recognise a file by.
    """
    first = _clean(text).splitlines()[0] if _clean(text) else ""
    return first[:limit] + ("…" if len(first) > limit else "")
