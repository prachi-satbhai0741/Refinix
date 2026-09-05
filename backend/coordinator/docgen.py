"""Writing a real Word document, and proving it is one.

A `.docx` is a ZIP holding OOXML parts, so `zipfile` and careful XML produce a
genuine one — Word, Pages and LibreOffice open the result. Nothing here writes
HTML or text and renames it: if a real `.docx` could not be produced, the
capability would be reported unavailable instead.

`validate` reopens what was written and checks the structure the format
requires, so "a document was generated" is an observation rather than a hope.

Standard library only.
"""

from __future__ import annotations

import hashlib
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MAX_PARAGRAPHS = 400
MAX_PARAGRAPH_CHARS = 8000

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORD_NS = f"{{{W}}}"

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

_DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>"""

REQUIRED_PARTS = ("[Content_Types].xml", "_rels/.rels", "word/document.xml",
                  "word/_rels/document.xml.rels", "docProps/core.xml",
                  "docProps/app.xml")


class ArtifactError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Block:
    """One paragraph. `style` picks a built-in Word style, nothing custom."""

    text: str
    style: str = "Body"     # Body | Title | Heading1 | Heading2 | Quote

    STYLES = {"Body": None, "Title": "Title", "Heading1": "Heading1",
              "Heading2": "Heading2", "Quote": "Quote"}


def _escape(text: str) -> str:
    """XML-escape, and drop the characters XML 1.0 cannot carry at all.

    Document and model text arrives here as untrusted data; it becomes text
    inside `<w:t>` and can never become markup or an instruction.
    """
    text = "".join(ch for ch in text if (
        ch in "\t\n\r" or 0x20 <= ord(ch) <= 0xD7FF
        or 0xE000 <= ord(ch) <= 0xFFFD or 0x10000 <= ord(ch) <= 0x10FFFF))
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _paragraph(block: Block) -> str:
    style = Block.STYLES.get(block.style)
    properties = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    lines = block.text.split("\n")
    runs = []
    for index, line in enumerate(lines):
        if index:
            runs.append("<w:r><w:br/></w:r>")
        # xml:space preserve keeps leading and trailing spaces intact.
        runs.append(f'<w:r><w:t xml:space="preserve">{_escape(line)}</w:t></w:r>')
    return f"<w:p>{properties}{''.join(runs)}</w:p>"


def _document_xml(blocks: list[Block]) -> str:
    body = "".join(_paragraph(block) for block in blocks)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:document xmlns:w="{W}"><w:body>{body}'
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/>'
            '</w:sectPr></w:body></w:document>')


def _core_xml(title: str, created: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{_escape(title)}</dc:title>'
            '<dc:creator>Refinix</dc:creator>'
            '<cp:lastModifiedBy>Refinix</cp:lastModifiedBy>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>'
            '</cp:coreProperties>')


def _app_xml(paragraphs: int) -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties '
            'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            '<Application>Refinix</Application>'
            f'<Paragraphs>{paragraphs}</Paragraphs>'
            '</Properties>')


def safe_filename(title: str, fallback: str = "approval-note") -> str:
    name = re.sub(r"[^0-9A-Za-z _-]+", " ", title or "").strip()
    name = re.sub(r"\s+", " ", name)[:60].strip()
    return f"{name or fallback}.docx"


def write_docx(target: Path, *, title: str, blocks: list[Block]) -> dict:
    """Write one .docx atomically inside `target`'s directory.

    A same-directory temporary file is written, flushed and moved into place,
    so a reader never sees a half-written archive and a failure leaves no
    partial artifact behind. The target is created fresh; an existing file at
    that path is never overwritten.
    """
    if not blocks:
        raise ArtifactError("empty", "There was nothing to put in the document.")
    if len(blocks) > MAX_PARAGRAPHS:
        raise ArtifactError(
            "too_long", f"A generated document holds at most {MAX_PARAGRAPHS} paragraphs.")
    for block in blocks:
        if len(block.text) > MAX_PARAGRAPH_CHARS:
            raise ArtifactError("too_long", "One paragraph is longer than Refinix writes.")

    target = Path(target)
    directory = target.parent
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        directory.chmod(0o700)
    except OSError:
        pass
    if target.exists():
        raise ArtifactError(
            "exists", "A document already exists at that name. Nothing was overwritten.")

    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    temporary = directory / f".refinix-{os.getpid()}-{os.urandom(6).hex()}.tmp"
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            # [Content_Types].xml must be the first entry in the package.
            archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
            archive.writestr("_rels/.rels", _ROOT_RELS)
            archive.writestr("word/_rels/document.xml.rels", _DOCUMENT_RELS)
            archive.writestr("word/document.xml", _document_xml(blocks))
            archive.writestr("docProps/core.xml", _core_xml(title, created))
            archive.writestr("docProps/app.xml", _app_xml(len(blocks)))
        with open(temporary, "rb") as handle:
            os.fsync(handle.fileno())
        data = temporary.read_bytes()
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return {"path": str(target), "filename": target.name,
            "media_type": "application/vnd.openxmlformats-officedocument"
                          ".wordprocessingml.document",
            "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "created_at": created, "paragraphs": len(blocks)}


def validate(path: Path) -> dict:
    """Reopen the file and check it really is a readable Word document.

    Structure only. It says the package is well formed and the text is where
    Word looks for it; it says nothing about whether the content is correct.
    """
    path = Path(path)
    problems: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            for part in REQUIRED_PARTS:
                if part not in names:
                    problems.append(f"missing {part}")
            damaged = archive.testzip()
            if damaged:
                problems.append(f"damaged entry {damaged}")
            document = archive.read("word/document.xml") if "word/document.xml" in names else b""
    except (zipfile.BadZipFile, OSError, KeyError) as exc:
        return {"readable": False, "problems": [f"not a readable package: {exc}"],
                "paragraphs": 0, "characters": 0}

    paragraphs = characters = 0
    if document:
        try:
            root = ET.fromstring(document)
        except ET.ParseError as exc:
            problems.append(f"document.xml is not valid XML: {exc}")
        else:
            body = root.find(f"{WORD_NS}body")
            if body is None:
                problems.append("document.xml has no body")
            else:
                for paragraph in body.iter(f"{WORD_NS}p"):
                    paragraphs += 1
                    for run in paragraph.iter(f"{WORD_NS}t"):
                        characters += len(run.text or "")
                if paragraphs == 0:
                    problems.append("the document has no paragraphs")
    return {"readable": not problems, "problems": problems,
            "paragraphs": paragraphs, "characters": characters}


def read_text(path: Path) -> list[str]:
    """Paragraph text back out of a generated file, for checks and preview."""
    with zipfile.ZipFile(Path(path)) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(f"{WORD_NS}body")
    lines = []
    for paragraph in (body.iter(f"{WORD_NS}p") if body is not None else []):
        text = "".join(run.text or "" for run in paragraph.iter(f"{WORD_NS}t"))
        lines.append(text)
    return lines
