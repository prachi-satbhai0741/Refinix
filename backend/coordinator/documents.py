"""Reading documents the user attached to one request.

Execution 3's extraction boundary. What it can honestly do is decided by what
is actually installed, not by what the interface would like to offer:

* **text** — `.txt`, `.md`, `.csv`, `.json`. Strict UTF-8, one page.
* **Word** — `.docx`. A `.docx` is a ZIP of OOXML, so the standard library
  reads it: `zipfile` plus `xml.etree`. Paragraphs and table cells, split into
  pages at explicit page breaks.
* **Excel** — `.xlsx`. Also a ZIP of OOXML, read by `xlsx.py`, one page per
  worksheet so a cell reference resolves. No formula is ever calculated.
* **PDF** — the text layer is read first with the bundled PDFium engine, which
  needs no model. Only a PDF whose pages carry no usable text is a scan: it is
  rendered page by page by whichever renderer this computer has, and read by
  the local vision model (`pdfrender.py` and `ocr.py`). The portable
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
          ocr_model: str | None = ocr.runtime.OCR_MODEL,
          ocr_profile=None) -> dict:
    """What this module can actually extract, not merely what is importable.

    `runtime_state` is an already-observed `runtime.probe()`. Passing it keeps
    a status page from re-probing the model runtime once per capability row;
    omitting it makes one fresh observation. Either way the answer describes
    what was observed, never a configured default.
    """
    if ocr_model is None:
        model = {"state": "disabled", "model": None,
                 "detail": ocr.no_profile_detail(None)}
        scan = {"available": False, "renderer": pdfrender.probe(),
                "model": model, "detail": model["detail"]}
        image = {"available": False, "model": model,
                 "detail": model["detail"]}
    elif ocr_profile is None:
        # No qualified profile: the answer is the same whether or not the
        # runtime was already observed, and it is reached without asking it.
        model = ocr.profile_state(ocr_model, ocr_profile)
        scan = {"available": False, "renderer": pdfrender.probe(),
                "model": model, "detail": model["detail"]}
        image = {"available": False, "model": model, "detail": model["detail"]}
    else:
        scan = (ocr.probe(ocr_model, profile=ocr_profile) if runtime_state is None
                else _scan_capability(runtime_state, ocr_model, ocr_profile))
        image = (ocr.image_probe(ocr_model, profile=ocr_profile)
                 if runtime_state is None
                 else _image_capability(runtime_state, ocr_model, ocr_profile))
    layer = pdfrender.text_probe()
    text_layer = {"available": layer["available"],
                  "formats": ["pdf"] if layer["available"] else [],
                  "module": layer["module"], "detail": layer["detail"]}
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
        # Text-layer PDFs need only PDFium, never a model. `pdf` below is the
        # scanned-page path, which needs a qualified reading profile as well.
        "pdf_text": text_layer,
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


def _observed_capabilities(runtime_state: dict, model: str | None) -> list | None:
    """What the runtime reported this model can do, from the observation first.

    Asking the runtime is what keeps OCR from being advertised because a tag
    has "VL" in its name; a probe that already carried the answer is reused.
    """
    if not model or not runtime_state.get("reachable"):
        return None
    entry = ocr.runtime.find(runtime_state, model)
    if entry is None:
        return None
    if entry.get("capabilities") is not None:
        return list(entry["capabilities"])
    return ocr.runtime.model_capabilities(entry["key"])


def _scan_capability(runtime_state: dict,
                     ocr_model: str = ocr.runtime.OCR_MODEL,
                     ocr_profile=None) -> dict:
    """`ocr.probe()` against a runtime observation someone else already made."""
    render = pdfrender.probe()
    if ocr_profile is None:
        model = ocr.profile_state(ocr_model, ocr_profile)
        return {"available": False, "renderer": render, "model": model,
                "detail": model["detail"]}
    caps = _observed_capabilities(runtime_state, ocr_model)
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
                      ocr_model: str = ocr.runtime.OCR_MODEL,
                      ocr_profile=None) -> dict:
    """`ocr.image_probe()` against a runtime observation someone else made.

    The renderer is deliberately absent: a supplied image needs the model and
    nothing else, so a missing PyObjC must not hide a capability that works.
    """
    if ocr_profile is None:
        model = ocr.profile_state(ocr_model, ocr_profile)
        return {"available": False, "model": model, "detail": model["detail"]}
    caps = _observed_capabilities(runtime_state, ocr_model)
    model = ocr.runtime.model_state_from(
        runtime_state, ocr_model,
        requires=ocr.runtime.VISION_CAPABILITY, capabilities=caps)
    if model["state"] != "installed":
        return {"available": False, "model": model, "detail": model["detail"]}
    return {"available": True, "model": model,
            "detail": (f"Supplied images are read by {model['model']} on the "
                       f"local runtime. " + ocr.STANDALONE_NOTE)}


def supported_suffixes(runtime_state: dict | None = None,
                       ocr_model: str = ocr.runtime.OCR_MODEL,
                       ocr_profile=None) -> list[str]:
    """Exactly what `extract` implements on this computer, right now."""
    capability = probe(runtime_state, ocr_model, ocr_profile)
    suffixes = [*TEXT_SUFFIXES, WORD_SUFFIX, SHEET_SUFFIX]
    if capability["pdf_text"]["available"] or capability["pdf"]["available"]:
        suffixes.append(PDF_SUFFIX)
    if capability["ocr"]["formats"]:
        suffixes.extend(IMAGE_SUFFIXES)
    return sorted(suffixes)


def capability_summary(runtime_state: dict | None = None,
                       ocr_model: str | None = ocr.runtime.OCR_MODEL,
                       ocr_profile=None) -> dict:
    """One shape the surfaces and the capability rows both read."""
    capability = probe(runtime_state, ocr_model, ocr_profile)
    # The `pdf` entry is the scanned-page path. Reported as `pdf_scan` so a
    # computer that reads text-layer PDFs is not listed as unable to read PDFs.
    unavailable = [
        {"kind": "pdf_scan" if kind == "pdf" else kind, "detail": entry["detail"]}
        for kind, entry in capability.items() if not entry["available"]
    ]
    reads_pdf = capability["pdf_text"]["available"] or capability["pdf"]["available"]
    return {
        "supported": [s.lstrip(".") for s in
                      sorted([*TEXT_SUFFIXES, WORD_SUFFIX]
                             + ([PDF_SUFFIX] if reads_pdf else []))],
        "unavailable": unavailable,
        "reads_pdf": reads_pdf,
        "reads_pdf_text": capability["pdf_text"]["available"],
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


#: Every prerequisite the reading path can be missing, and the code each one
#: is reported as. Kept in one place because the whole point is that they are
#: different fixes: qualify the model, start the runtime, install the model,
#: choose another model, or install a renderer.
_OCR_MODEL_STATE_CODES = {
    ocr.NO_PROFILE_STATE: "no_ocr_profile",
    "runtime_unavailable": "runtime_unavailable",
    "absent": "no_ocr_model",
    "missing_capability": "model_cannot_read_images",
    "capability_unknown": "model_capability_unknown",
}


def _reading_failure(exc: Exception, filename: str) -> "DocumentError":
    """Turn any reading failure into a document refusal a surface can show.

    `OcrError` is the expected shape and keeps its own code. Anything else —
    most usefully a `TypeError` from a runtime call that no longer matches its
    caller — is a defect in this build, not something the person did. It
    becomes a named internal refusal rather than escaping as a raw exception
    into an interface, which is exactly how a signature mismatch once reached
    a user as `TypeError: stream_chat() got an unexpected keyword argument`.
    """
    if isinstance(exc, ocr.OcrError):
        return DocumentError(exc.code, str(exc))
    return DocumentError(
        "reading_failed",
        f"{filename} could not be read: this build's reading path failed "
        "before producing any text. Nothing was transcribed or saved.")


def _extract_pdf_text(data: bytes, filename: str, *, should_cancel=None):
    """Read a PDF's own text layer, or return None when it has none to read.

    Deterministic and model-free. A page with no usable text is kept, empty and
    numbered, and named in `uncertain`, so a mixed document is never reported
    as read whole. A page over the per-page ceiling is read up to it and named
    as partially read. None means every page lacked usable text: the file is a
    scan, and only the vision path could read it.
    """
    try:
        read = pdfrender.text_pages(data, should_cancel=should_cancel)
    except pdfrender.RenderError as exc:
        raise DocumentError(exc.code, f"{filename}: {exc}") from exc
    usable = {page.number for page in read
              if any(ch.isalnum() for ch in page.text)}
    if not usable:
        return None
    pages, unread, partial = [], [], []
    for page in read:
        note = None
        if page.number not in usable:
            unread.append(page.number)
            note = "No usable text layer on this page; it was not read."
        elif page.truncated:
            partial.append(page.number)
            note = (f"Only the first {pdfrender.MAX_TEXT_CHARS_PER_PAGE} of "
                    f"{page.chars} characters on this page were read.")
        pages.append(Page(page.number,
                          _clean(page.text) if page.number in usable else "",
                          note=note))
    uncertain = []
    if unread:
        uncertain.append(
            f"{_page_list(unread)} {'has' if len(unread) == 1 else 'have'} "
            "no usable text layer (scanned) and "
            f"{'was' if len(unread) == 1 else 'were'} not read.")
    if partial:
        uncertain.append(
            f"{_page_list(partial)} {'was' if len(partial) == 1 else 'were'} "
            f"only partly read: at most {pdfrender.MAX_TEXT_CHARS_PER_PAGE} "
            "characters are read from one page.")
    return pages, "pdf text layer (pypdfium2)", uncertain, len(read)


def _page_list(numbers: list[int]) -> str:
    return (f"Page {numbers[0]}" if len(numbers) == 1
            else "Pages " + ", ".join(str(n) for n in numbers))


def _reader(ocr_model, ocr_profile, ocr_reader):
    """The page reader, chosen now that a page needs reading.

    `ocr_reader`, when given, is the coordinator's callback that picks and
    admits a reader; it is called only here, so text, Word, workbook and
    text-layer PDF reading never wait for a page-reading model.
    """
    return ocr_reader() if ocr_reader is not None else (ocr_model, ocr_profile)


def _extract_pdf(data: bytes, filename: str, *, should_cancel=None,
                 ocr_model: str | None = ocr.runtime.OCR_MODEL,
                 ocr_profile=None, ocr_chat=None, ocr_reader=None):
    """Read the text layer; render and read pages with a model only for a scan.

    The text layer comes first and needs no model. Only when no page carries
    usable text is the file treated as a scan. The scan capability is re-checked
    here rather than trusted from an earlier probe: a runtime that stopped
    answering between the status poll and this request must refuse, not
    half-read. A scanned page that cannot be read fails the whole extraction —
    a document silently missing a page would be worse than no document at all.
    """
    scanned = ""
    if pdfrender.text_probe()["available"]:
        text = _extract_pdf_text(data, filename, should_cancel=should_cancel)
        if text is not None:
            return text
        # Said only when the text layer was actually checked and found empty.
        scanned = f"{filename} has no usable text layer (scanned pages). "
    ocr_model, ocr_profile = _reader(ocr_model, ocr_profile, ocr_reader)
    if ocr_model is None:
        raise DocumentError(
            "model_disabled",
            scanned + ocr.no_profile_detail(None))
    scan = ocr.probe(ocr_model, profile=ocr_profile)
    if not scan["available"]:
        # Several prerequisites, several codes. Collapsing them would send
        # someone to install PyObjC when the model is what is unqualified.
        # The unqualified profile is checked first because it is true
        # regardless of the renderer.
        state = scan["model"]["state"]
        code = (_OCR_MODEL_STATE_CODES[state] if state == ocr.NO_PROFILE_STATE
                else "no_pdf_parser" if not scan["renderer"]["available"]
                else _OCR_MODEL_STATE_CODES.get(state, "no_ocr_model"))
        raise DocumentError(code, scanned + scan["detail"])
    try:
        read = ocr.extract_pdf(data, filename=filename, profile=ocr_profile,
                               should_cancel=should_cancel, model=ocr_model,
                               chat=ocr_chat)
    except Exception as exc:
        # `cancelled` keeps its own code so the workflow can tell a stop from a
        # failure; everything else is a refusal with the extractor's reason.
        raise _reading_failure(exc, filename) from exc
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
                   ocr_model: str | None = ocr.runtime.OCR_MODEL,
                   ocr_profile=None, ocr_chat=None, ocr_reader=None):
    """Send one supplied image to the local vision model, as page 1.

    No renderer at all: the file already is a page image. The method string says
    exactly that, so a reader is never told a PDF was rendered when none was.
    """
    ocr_model, ocr_profile = _reader(ocr_model, ocr_profile, ocr_reader)
    if ocr_model is None:
        raise DocumentError(
            "model_disabled", ocr.no_profile_detail(None))
    state = ocr.image_probe(ocr_model, profile=ocr_profile)
    if not state["available"]:
        code = _OCR_MODEL_STATE_CODES.get(state["model"]["state"], "no_ocr_model")
        raise DocumentError(code, state["detail"])
    try:
        read = ocr.extract_image(data, filename=filename, media_type=media_type,
                                 profile=ocr_profile,
                                 should_cancel=should_cancel, model=ocr_model,
                                 chat=ocr_chat)
    except Exception as exc:
        raise _reading_failure(exc, filename) from exc
    pages = [Page(number=page["number"], text=_clean(page["text"]),
                  confidence=None, note=page["note"])
             for page in read["pages"]]
    return pages, read["method"], list(read["uncertain"]), read["page_count"]


def verified_bytes(path: Path, *, filename: str, expected_sha256: str) -> bytes:
    """Open one private attachment and prove it is the accepted file."""
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
    return data


def extract(path: Path, *, source_id: str, filename: str, media_type: str,
            expected_sha256: str, should_cancel=None,
            ocr_model: str | None = ocr.runtime.OCR_MODEL,
            ocr_profile=None, ocr_chat=None, ocr_reader=None) -> Extraction:
    """Read one attachment, after proving it is the file that was accepted.

    `ocr_chat` is the page-reading call (the runtime's own when omitted); the
    coordinator passes one that holds a memory reservation for each page.
    """
    data = verified_bytes(path, filename=filename,
                          expected_sha256=expected_sha256)
    actual = expected_sha256

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
            ocr_model=ocr_model, ocr_profile=ocr_profile, ocr_chat=ocr_chat,
            ocr_reader=ocr_reader)
    elif suffix == PDF_SUFFIX:
        pages, method, uncertain, declared_pages = _extract_pdf(
            data, filename, should_cancel=should_cancel, ocr_model=ocr_model,
            ocr_profile=ocr_profile, ocr_chat=ocr_chat, ocr_reader=ocr_reader)
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
