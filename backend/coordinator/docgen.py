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
import tempfile
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
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
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
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>"""

_STYLES_XML = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W}">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="10"/><w:qFormat/><w:pPr><w:spacing w:after="220"/><w:keepNext/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="9"/><w:qFormat/><w:pPr><w:spacing w:before="220" w:after="80"/><w:keepNext/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="9"/><w:qFormat/><w:pPr><w:spacing w:before="180" w:after="60"/><w:keepNext/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="29"/><w:qFormat/><w:pPr><w:ind w:left="360"/><w:spacing w:after="100"/></w:pPr><w:rPr><w:color w:val="444444"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="ListNumber"><w:name w:val="List Number"/><w:basedOn w:val="Normal"/><w:next w:val="ListNumber"/><w:uiPriority w:val="99"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/><w:next w:val="ListBullet"/><w:uiPriority w:val="99"/><w:qFormat/></w:style>
</w:styles>"""

_NUMBERING_XML = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="{W}">
<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:tabs><w:tab w:val="num" w:pos="720"/></w:tabs><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>
<w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:pPr><w:tabs><w:tab w:val="num" w:pos="720"/></w:tabs><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
<w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>"""

REQUIRED_PARTS = ("[Content_Types].xml", "_rels/.rels", "word/document.xml",
                  "word/_rels/document.xml.rels", "word/styles.xml",
                  "word/numbering.xml", "docProps/core.xml", "docProps/app.xml")


class ArtifactError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Block:
    """One paragraph. `style` picks a built-in Word style, nothing custom."""

    text: str
    style: str = "Body"
    marker: str | None = None  # PDF-visible marker; DOCX uses native numbering.

    STYLES = {"Body": None, "Title": "Title", "Heading1": "Heading1",
              "Heading2": "Heading2", "Quote": "Quote",
              "ListNumber": "ListNumber", "ListBullet": "ListBullet"}


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
    props = [f'<w:pStyle w:val="{style}"/>'] if style else []
    if block.style in ("ListNumber", "ListBullet"):
        num_id = "1" if block.style == "ListNumber" else "2"
        props.append(f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num_id}"/></w:numPr>')
    properties = f"<w:pPr>{''.join(props)}</w:pPr>" if props else ""
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
            archive.writestr("word/styles.xml", _STYLES_XML)
            archive.writestr("word/numbering.xml", _NUMBERING_XML)
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


MEDIA_TYPE = ("application/vnd.openxmlformats-officedocument"
              ".wordprocessingml.document")

_PROBE: dict | None = None


def selftest() -> dict:
    """Write a real .docx to a temporary folder and reopen it.

    The whole Word path, executed rather than assumed: a package is built, the
    bytes are flushed and moved into place, and the result is reopened and
    parsed. It needs no model and no third-party library, which is why it is
    the one capability check that can run on any computer at any time.

    It proves the writer works here. It says nothing about the content of any
    document Refinix later generates.

    The file holds two fixed sentences and no user content, which is why it
    may use an ordinary temporary folder rather than the workspace's own: a
    capability probe must not need a data root to exist before it can answer,
    and nothing private passes through it.
    """
    with tempfile.TemporaryDirectory(prefix="refinix-docx-") as folder:
        target = Path(folder) / "refinix-self-test.docx"
        try:
            write_docx(target, title="Refinix self-test", blocks=[
                Block("Refinix self-test", style="Title"),
                Block("Refinix wrote this file to check that Word output works "
                      "on this computer, then reopened it to confirm.")])
            result = validate(target)
        except (ArtifactError, OSError, ValueError) as exc:
            return {"valid": False,
                    "detail": f"A Word document could not be written here: {exc}"}
    if not result["readable"]:
        return {"valid": False,
                "detail": ("A Word document was written but could not be "
                           "reopened: " + "; ".join(result["problems"]))}
    return {"valid": True,
            "detail": (f"A {result['paragraphs']}-paragraph Word document was "
                       "written and reopened successfully.")}


def probe() -> dict:
    """Whether real Word output is available here, observed once per process.

    Cached because the answer cannot change while the process runs — it
    depends on the standard library and on being able to use a temporary
    folder — and because the capability summary asks for it on every status
    read. `selftest` runs the same check fresh when a person asks for one.
    """
    global _PROBE
    if _PROBE is None:
        observed = selftest()
        _PROBE = {"available": observed["valid"], "module": "zipfile",
                  "media_type": MEDIA_TYPE, "detail": observed["detail"]}
    return dict(_PROBE)


def available() -> bool:
    return probe()["available"]


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
