"""Reading documents the user attached to one request.

Execution 3's extraction boundary. What it can honestly do is decided by what
is actually installed, not by what the interface would like to offer:

* **text** — `.txt`, `.md`, `.csv`, `.json`. Strict UTF-8, one page.
* **Word** — `.docx`. A `.docx` is a ZIP of OOXML, so the standard library
  reads it: `zipfile` plus `xml.etree`. Paragraphs and table cells, split into
  pages at explicit page breaks.
* **PDF** — refused. There is no PDF parser in this environment and the
  standard library has none, so `probe()` reports it unavailable with the
  prerequisite rather than half-reading the file.
* **scanned pages and images (OCR)** — refused. No OCR engine is installed.
  Nothing here invents text for an image, and no text extractor is described
  as OCR.

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

# Formats a parser exists for, and the ones that need something this computer
# does not have. Neither list is guessed: `probe()` derives both.
NEEDS_PDF_PARSER = {".pdf"}
NEEDS_OCR = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic", ".webp"}


class DocumentError(ValueError):
    """A refusal the interface can show, with a code a test can assert."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------
# Capability probe
# --------------------------------------------------------------------------

def probe() -> dict:
    """What this module can actually extract, not merely what is importable."""
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
            "available": False, "formats": [], "module": None,
            "detail": ("PDF extraction is not implemented in this Refinix "
                       "build. Missing prerequisite: a reviewed PDF text adapter."),
        },
        "ocr": {
            "available": False, "formats": [], "module": None,
            "detail": ("OCR extraction is not implemented in this Refinix "
                       "build. Refinix does not guess at words in a picture. "
                       "Missing prerequisite: a reviewed OCR adapter and engine."),
        },
    }


def supported_suffixes() -> list[str]:
    """Exactly what `extract` implements."""
    return sorted([*TEXT_SUFFIXES, WORD_SUFFIX])


def capability_summary() -> dict:
    """One shape the surfaces and the capability rows both read."""
    capability = probe()
    unavailable = [
        {"kind": kind, "detail": entry["detail"]}
        for kind, entry in capability.items() if not entry["available"]
    ]
    return {
        "supported": [s.lstrip(".") for s in supported_suffixes()],
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


def extract(path: Path, *, source_id: str, filename: str, media_type: str,
            expected_sha256: str) -> Extraction:
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
    capability = probe()
    if suffix in NEEDS_PDF_PARSER and not capability["pdf"]["available"]:
        raise DocumentError("no_pdf_parser", capability["pdf"]["detail"])
    if suffix in NEEDS_OCR and not capability["ocr"]["available"]:
        raise DocumentError("no_ocr", capability["ocr"]["detail"])

    declared_pages: int | None = None
    if suffix in TEXT_SUFFIXES:
        pages, method, uncertain = _extract_text(data, filename, media_type)
        declared_pages = 1
    elif suffix == WORD_SUFFIX:
        pages, method, uncertain, declared_pages = _extract_docx(data, filename)
    else:
        raise DocumentError(
            "unsupported",
            f"Refinix cannot read {suffix or 'a file without an extension'} yet. "
            f"It reads: {', '.join(s.lstrip('.') for s in supported_suffixes())}.")

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
