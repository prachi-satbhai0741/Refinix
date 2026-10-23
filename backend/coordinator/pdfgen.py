"""Writing a real PDF, and proving it is one.

The companion to `docgen.py`. Where that module builds a `.docx` from OOXML
parts with the standard library, this one draws a PDF with the macOS Quartz
framework that the desktop environment already ships. Nothing here writes text
or HTML and renames it: if a real PDF could not be produced, `probe()` reports
the capability unavailable and the caller offers `.docx` instead.

**Text is drawn through AppKit, not `CGContextShowText`.** The obvious Quartz
call takes a byte string in a `CGTextEncoding`, and the only encoding this
PyObjC build exposes is MacRoman — which silently replaces Devanagari, CJK and
most symbols. `CoreText` is not present in this environment either (no module,
and none of its symbols are re-exported through `Quartz`), so the working path
is an `NSAttributedString` drawn into an `NSGraphicsContext` wrapped around the
PDF context. AppKit picks the fonts and shapes the runs, so Unicode survives.

`validate` reopens what was written with `CGPDFDocumentCreateWithURL` and reads
its real page count, so "a PDF was generated" is an observation rather than a
hope. Structure only: it says the file is a readable PDF with pages, and says
nothing about whether the content is correct.

Standard library plus the already-installed PyObjC Quartz and AppKit
frameworks. No new dependency, and nothing is downloaded.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.coordinator.docgen import Block

MEDIA_TYPE = "application/pdf"

# Bounds, mirroring docgen so a caller can swap formats without new limits.
MAX_BLOCKS = 400
MAX_BLOCK_CHARS = 8000

# A4 in PostScript points, the unit Quartz draws in.
PAGE_WIDTH = 595.0
PAGE_HEIGHT = 842.0
MARGIN = 56.0
TEXT_WIDTH = PAGE_WIDTH - (2 * MARGIN)

# Point size and the space that follows each block, per docgen style name.
STYLE_METRICS = {
    "Title": (22.0, 16.0, True),
    "Heading1": (16.0, 10.0, True),
    "Heading2": (13.0, 8.0, True),
    "Quote": (11.0, 8.0, False),
    "ListNumber": (11.0, 8.0, False),
    "ListBullet": (11.0, 8.0, False),
    "Body": (11.0, 8.0, False),
}


class ArtifactError(ValueError):
    """A refusal the interface can show, with a code a test can assert."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _Frameworks:
    quartz: object
    appkit: object
    foundation: object


def _frameworks() -> _Frameworks:
    """Import the native frameworks on demand, never at module import.

    A lazy import keeps this module importable on the Ubuntu worker and in any
    environment without PyObjC, exactly as `pdfrender` does. `documents.py`
    imports it unconditionally, so an eager import would break the worker.
    """
    try:
        import AppKit                                        # noqa: PLC0415
        import Foundation                                    # noqa: PLC0415
        import Quartz                                        # noqa: PLC0415
    except ImportError as exc:                               # pragma: no cover
        raise ArtifactError(
            "no_pdf_writer",
            "Writing a PDF needs the macOS Quartz and AppKit frameworks "
            "(PyObjC), which are not importable here.") from exc
    return _Frameworks(quartz=Quartz, appkit=AppKit, foundation=Foundation)


def probe() -> dict:
    """What this computer can actually do, checked rather than assumed."""
    try:
        frameworks = _frameworks()
    except ArtifactError as exc:
        return {"available": False, "module": "Quartz+AppKit",
                "media_type": MEDIA_TYPE, "detail": str(exc)}
    missing = [name for name in ("CGPDFContextCreateWithURL",
                                 "CGPDFDocumentCreateWithURL",
                                 "CGContextBeginPage", "CGPDFContextClose")
               if not hasattr(frameworks.quartz, name)]
    if missing:
        return {"available": False, "module": "Quartz+AppKit",
                "media_type": MEDIA_TYPE,
                "detail": ("This build of PyObjC Quartz is missing "
                           + ", ".join(missing) + ".")}
    if not hasattr(frameworks.appkit, "NSGraphicsContext"):
        return {"available": False, "module": "Quartz+AppKit",
                "media_type": MEDIA_TYPE,
                "detail": "This build of PyObjC AppKit has no NSGraphicsContext."}
    return {
        "available": True, "module": "Quartz+AppKit", "media_type": MEDIA_TYPE,
        "detail": ("Written with the macOS Quartz framework (PyObjC) and laid "
                   "out with AppKit, so Unicode text is preserved."),
    }


def available() -> bool:
    return probe()["available"]


def safe_filename(title: str, fallback: str = "document") -> str:
    """The coordinator names the file. Model output never picks an extension."""
    name = re.sub(r"[^0-9A-Za-z _-]+", " ", title or "").strip()
    name = re.sub(r"\s+", " ", name)[:60].strip()
    return f"{name or fallback}.pdf"


def _attributes(frameworks: _Frameworks, style: str):
    """Font and paragraph attributes for one docgen style."""
    appkit = frameworks.appkit
    size, _after, bold = STYLE_METRICS.get(style, STYLE_METRICS["Body"])
    font = (appkit.NSFont.boldSystemFontOfSize_(size) if bold
            else appkit.NSFont.systemFontOfSize_(size))
    paragraph = appkit.NSMutableParagraphStyle.alloc().init()
    paragraph.setLineSpacing_(2.0)
    if style in ("Quote", "ListNumber", "ListBullet"):
        paragraph.setFirstLineHeadIndent_(18.0)
        paragraph.setHeadIndent_(18.0)
    return {appkit.NSFontAttributeName: font,
            appkit.NSParagraphStyleAttributeName: paragraph}


def _visible_text(block: Block) -> str:
    if block.style == "ListNumber" and block.marker:
        return f"{block.marker}. {block.text}"
    if block.style == "ListBullet" and block.marker:
        return f"{block.marker} {block.text}"
    return block.text


def _measured_text(frameworks: _Frameworks, value: str, style: str):
    """Text as an attributed string plus the height it needs.

    Measuring before drawing is what makes pagination honest: a block is only
    placed on a page that can actually hold it.
    """
    appkit, foundation = frameworks.appkit, frameworks.foundation
    text = frameworks.foundation.NSAttributedString.alloc(
        ).initWithString_attributes_(value or " ",
                                     _attributes(frameworks, style))
    bounds = text.boundingRectWithSize_options_(
        foundation.NSMakeSize(TEXT_WIDTH, 1.0e6),
        appkit.NSStringDrawingUsesLineFragmentOrigin)
    _size, after, _bold = STYLE_METRICS.get(style, STYLE_METRICS["Body"])
    return text, float(bounds.size.height), after


def _measured(frameworks: _Frameworks, block: Block):
    return _measured_text(frameworks, _visible_text(block), block.style)


USABLE_HEIGHT = PAGE_HEIGHT - (2 * MARGIN)


def _split_to_pages(frameworks: _Frameworks, block: Block):
    """One block as pieces that each fit a page, in order.

    Character ranges preserve whitespace and also handle one unbroken token.
    Each range is measured before use, so nothing is clipped or rewritten.
    """
    text, height, after = _measured(frameworks, block)
    if height <= USABLE_HEIGHT:
        return [(text, height, after)]

    remaining = _visible_text(block)
    out = []
    while remaining:
        low, high, best = 1, len(remaining), 0
        while low <= high:
            middle = (low + high) // 2
            measured = _measured(
                frameworks, Block(remaining[:middle], block.style))
            if measured[1] <= USABLE_HEIGHT:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        if best == 0:
            raise ArtifactError(
                "layout", "One character could not fit on a PDF page.")
        piece = _measured(frameworks, Block(remaining[:best], block.style))
        out.append((piece[0], piece[1], 0.0))
        remaining = remaining[best:]
    out[-1] = (out[-1][0], out[-1][1], after)
    return out


def write_pdf(target: Path, *, title: str, blocks: list[Block]) -> dict:
    """Write one PDF atomically inside `target`'s directory.

    A same-directory temporary file is written and moved into place, so a
    reader never sees a half-written document and a failure leaves no partial
    artifact behind. The target is created fresh; an existing file at that path
    is never overwritten.
    """
    if not blocks:
        raise ArtifactError("empty", "There was nothing to put in the document.")
    if len(blocks) > MAX_BLOCKS:
        raise ArtifactError(
            "too_long", f"A generated document holds at most {MAX_BLOCKS} paragraphs.")
    for block in blocks:
        if len(block.text) > MAX_BLOCK_CHARS:
            raise ArtifactError("too_long", "One paragraph is longer than Refinix writes.")

    frameworks = _frameworks()
    state = probe()
    if not state["available"]:
        raise ArtifactError("no_pdf_writer", state["detail"])
    quartz, appkit, foundation = (frameworks.quartz, frameworks.appkit,
                                  frameworks.foundation)

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
    pages = 0
    try:
        box = quartz.CGRectMake(0, 0, PAGE_WIDTH, PAGE_HEIGHT)
        url = foundation.NSURL.fileURLWithPath_(str(temporary))
        # docProps equivalents. No creator string that names a person, and no
        # identifier that would follow the file around.
        info = {"kCGPDFContextTitle": title or "Document"}
        context = quartz.CGPDFContextCreateWithURL(url, box, info)
        if context is None:
            raise ArtifactError(
                "no_pdf_writer",
                "Quartz would not open a PDF context for that location.")

        # A block taller than one page is split across pages instead of being
        # moved whole to a fresh page and drawn off the bottom of it. Moving
        # it only hid the loss: the structural check reopens the file and
        # counts pages, so clipped text still validated.
        measured: list[tuple[object, float, float]] = []
        for block in blocks:
            measured.extend(_split_to_pages(frameworks, block))

        cursor = PAGE_HEIGHT - MARGIN
        page_open = False
        for text, height, after in measured:
            if not page_open or (cursor - height) < MARGIN:
                if page_open:
                    appkit.NSGraphicsContext.restoreGraphicsState()
                    quartz.CGContextEndPage(context)
                quartz.CGContextBeginPage(context, box)
                graphics = appkit.NSGraphicsContext.graphicsContextWithCGContext_flipped_(
                    context, False)
                appkit.NSGraphicsContext.saveGraphicsState()
                appkit.NSGraphicsContext.setCurrentContext_(graphics)
                pages += 1
                page_open = True
                cursor = PAGE_HEIGHT - MARGIN
            # Quartz measures from the bottom-left, so a block occupying
            # `height` starts that far below the running cursor.
            text.drawWithRect_options_(
                foundation.NSMakeRect(MARGIN, cursor - height, TEXT_WIDTH, height),
                appkit.NSStringDrawingUsesLineFragmentOrigin)
            cursor -= (height + after)
        if page_open:
            appkit.NSGraphicsContext.restoreGraphicsState()
            quartz.CGContextEndPage(context)
        quartz.CGPDFContextClose(context)

        data = temporary.read_bytes()
        if not data.startswith(b"%PDF-"):
            raise ArtifactError(
                "unreadable_artifact",
                "What Quartz wrote does not begin with a PDF header.")
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
            "media_type": MEDIA_TYPE, "byte_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "created_at": created, "pages": pages, "paragraphs": len(blocks)}


def validate(path: Path) -> dict:
    """Reopen the file and check it really is a readable PDF with pages.

    Shaped like `docgen.validate` so `server.py` records the same fields for
    either format. `paragraphs` is the block count the writer reported; a PDF
    has no paragraph structure to read back, so it is not invented here.
    """
    path = Path(path)
    problems: list[str] = []
    try:
        with path.open("rb") as handle:
            head = handle.read(5)
    except OSError as exc:
        return {"readable": False, "problems": [f"not a readable file: {exc}"],
                "pages": 0, "characters": 0}
    if head != b"%PDF-":
        problems.append("the file does not begin with a PDF header")

    pages = 0
    try:
        frameworks = _frameworks()
    except ArtifactError as exc:
        problems.append(f"cannot reopen it here: {exc}")
    else:
        url = frameworks.foundation.NSURL.fileURLWithPath_(str(path))
        document = frameworks.quartz.CGPDFDocumentCreateWithURL(url)
        if document is None:
            problems.append("a PDF reader on this computer could not open it")
        else:
            pages = int(frameworks.quartz.CGPDFDocumentGetNumberOfPages(document))
            if pages < 1:
                problems.append("the document has no pages")
    return {"readable": not problems, "problems": problems,
            "pages": pages, "characters": 0}


def page_count(path: Path) -> int:
    """The real page count, read back from the written file."""
    return int(validate(path).get("pages") or 0)
