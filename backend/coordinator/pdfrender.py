"""Rendering one PDF page to pixels on the macOS coordinator.

C08 needs an image before anything can read a *scanned* report: a raster scan
has no text layer, so there is nothing to parse. This module is the whole
rendering boundary, and it is deliberately small.

**Quartz, and nothing else.** The desktop environment already ships PyObjC, so
`Quartz.CGPDFDocument` renders the page with a framework that is present and
pinned. No PDF library is added, no binary is shelled out to, and no second
image stack appears. Where PyObjC is absent — the plain coordinator virtual
environment, or any non-Apple computer — `probe()` says so and `documents.py`
keeps reporting PDF unavailable rather than half-reading the file.

**Nothing touches the disk.** The PDF arrives as bytes the caller already
verified against the intake digest, and the page leaves as PNG bytes built in
memory. There is no temporary image to clean up, no path for a caller to
influence, and no URL: `CGPDFDocumentCreateWithURL` is never used, so a remote
or local path can never be opened from here.

**Every bound is checked before the work, not after.** Input bytes, page count,
pixels per page and encoded output size each have a ceiling, and the whole
render has a wall-clock deadline that is re-checked between pages. A malformed,
encrypted or unrenderable document raises `RenderError`; it never returns a
blank page that a later stage would read as "the scan said nothing".

Standard library plus the already-installed PyObjC Quartz framework.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

# Bounds. Visible in the refusals, so a stop explains itself.
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PAGES = 40
# The longest edge of the rendered page, in pixels. 1600 keeps a 200 dpi A4
# scan legible while staying far below the pixel ceiling below.
TARGET_LONG_EDGE = 1600
MAX_PIXELS_PER_PAGE = 4_000_000          # ~2000x2000; a 4-byte RGBA row buffer
MAX_IMAGE_BYTES = 8 * 1024 * 1024        # encoded PNG per page
MAX_RENDER_SECONDS = 120.0

# One deterministic pixel format for every page, so two runs of the same scan
# produce the same bytes and the model never sees a format that varies by page.
IMAGE_MEDIA_TYPE = "image/png"
IMAGE_UTI = "public.png"


class RenderError(ValueError):
    """A refusal the interface can show, with a code a check can assert."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RenderedPage:
    """One page, numbered by the coordinator that rendered it."""

    number: int                # 1-based, as a reader would count
    image: bytes               # PNG
    width: int
    height: int
    media_type: str = IMAGE_MEDIA_TYPE


def _quartz():
    """Import Quartz on demand, and never as a side effect of importing this.

    A lazy import keeps `documents.py` importable on the Ubuntu worker and in
    the plain coordinator environment, where PyObjC is not installed. It also
    means a capability probe costs nothing until something actually asks.
    """
    try:
        import Quartz                                        # noqa: PLC0415
    except Exception as exc:                                 # noqa: BLE001
        raise RenderError(
            "no_renderer",
            "PDF rendering needs the macOS Quartz framework (PyObjC), which is "
            "not available in this environment.") from exc
    return Quartz


def probe() -> dict:
    """What this computer can actually render. An observation, not a default.

    Importing a framework starts no service, opens no socket and loads no
    model; it only answers whether the code path exists at all.
    """
    try:
        quartz = _quartz()
    except RenderError as exc:
        return {"available": False, "module": None, "detail": str(exc)}
    required = ("CGPDFDocumentCreateWithProvider", "CGBitmapContextCreate",
                "CGImageDestinationCreateWithData", "CGPDFPageGetDrawingTransform")
    missing = [name for name in required if not hasattr(quartz, name)]
    if missing:
        return {"available": False, "module": "Quartz",
                "detail": ("This build of PyObjC Quartz is missing "
                           + ", ".join(missing) + ".")}
    return {
        "available": True, "module": "Quartz",
        "detail": ("Rendered with the macOS Quartz framework (PyObjC). Pages "
                   f"are drawn in memory as {IMAGE_MEDIA_TYPE} at up to "
                   f"{TARGET_LONG_EDGE}px on the long edge."),
        "max_pages": MAX_PAGES, "max_bytes": MAX_PDF_BYTES,
    }


def available() -> bool:
    return probe()["available"]


def _document(quartz, data: bytes):
    provider = quartz.CGDataProviderCreateWithCFData(data)
    if provider is None:
        raise RenderError("malformed", "That PDF could not be opened for reading.")
    document = quartz.CGPDFDocumentCreateWithProvider(provider)
    if document is None:
        raise RenderError("malformed", "That file is not a readable PDF.")
    # An encrypted document can be *opened* and then render every page blank.
    # Refusing here is what keeps "the scan said nothing" from being a possible
    # outcome of a document nobody could actually read.
    if quartz.CGPDFDocumentIsEncrypted(document) and \
            not quartz.CGPDFDocumentIsUnlocked(document):
        raise RenderError(
            "encrypted",
            "That PDF is password-protected. Refinix does not unlock documents.")
    return document


def _page_size(quartz, page) -> tuple[int, int]:
    """Target pixel size for one page, scaled to the long edge and bounded."""
    box = quartz.CGPDFPageGetBoxRect(page, quartz.kCGPDFCropBox)
    width, height = float(box.size.width), float(box.size.height)
    rotation = int(quartz.CGPDFPageGetRotationAngle(page)) % 360
    if rotation in (90, 270):
        width, height = height, width
    if width <= 0 or height <= 0:
        raise RenderError("malformed", "A page in that PDF has no usable size.")
    scale = TARGET_LONG_EDGE / max(width, height)
    pixels_w = max(1, int(round(width * scale)))
    pixels_h = max(1, int(round(height * scale)))
    if pixels_w * pixels_h > MAX_PIXELS_PER_PAGE:
        raise RenderError(
            "too_large",
            f"A page in that PDF renders to more than {MAX_PIXELS_PER_PAGE} pixels.")
    return pixels_w, pixels_h


def _encode(quartz, image) -> bytes:
    data = quartz.CFDataCreateMutable(None, 0)
    destination = quartz.CGImageDestinationCreateWithData(data, IMAGE_UTI, 1, None)
    if destination is None:
        raise RenderError("encode", "That page could not be encoded as an image.")
    quartz.CGImageDestinationAddImage(destination, image, None)
    if not quartz.CGImageDestinationFinalize(destination):
        raise RenderError("encode", "That page could not be encoded as an image.")
    encoded = bytes(data)
    if not encoded:
        raise RenderError("encode", "That page produced no image data.")
    if len(encoded) > MAX_IMAGE_BYTES:
        raise RenderError(
            "too_large",
            f"A rendered page exceeded {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    return encoded


def page_count(data: bytes) -> int:
    """How many pages the document states. Never inferred, never defaulted."""
    if len(data) > MAX_PDF_BYTES:
        raise RenderError("too_large", "That PDF is larger than Refinix renders.")
    quartz = _quartz()
    document = _document(quartz, data)
    count = int(quartz.CGPDFDocumentGetNumberOfPages(document))
    if count <= 0:
        raise RenderError("malformed", "That PDF declares no pages.")
    return count


def render_pages(data: bytes, *, max_pages: int = MAX_PAGES,
                 should_cancel=None, deadline_seconds: float = MAX_RENDER_SECONDS):
    """Yield `RenderedPage` in document order, one page at a time.

    A generator on purpose: the caller sends each page to the model and drops
    the pixels before the next page is drawn, so peak memory is one page rather
    than a whole scan. `should_cancel` is polled between pages, which is the
    only place a partially rendered document can be abandoned cleanly.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise RenderError("unreadable", "A PDF must be supplied as bytes.")
    data = bytes(data)
    if not data:
        raise RenderError("empty", "That PDF is empty.")
    if len(data) > MAX_PDF_BYTES:
        raise RenderError(
            "too_large",
            f"That PDF is larger than {MAX_PDF_BYTES // (1024 * 1024)} MB.")

    quartz = _quartz()
    document = _document(quartz, data)
    declared = int(quartz.CGPDFDocumentGetNumberOfPages(document))
    if declared <= 0:
        raise RenderError("malformed", "That PDF declares no pages.")
    limit = min(declared, max(1, int(max_pages)), MAX_PAGES)
    if declared > limit:
        raise RenderError(
            "too_many_pages",
            f"That PDF has {declared} pages. Refinix reads up to {limit} in one "
            "request.")

    expires = time.monotonic() + max(1.0, float(deadline_seconds))
    for number in range(1, limit + 1):
        if should_cancel is not None and should_cancel():
            raise RenderError("cancelled", "Rendering was stopped.")
        if time.monotonic() > expires:
            raise RenderError(
                "timeout", "Rendering that PDF took longer than Refinix allows.")
        page = quartz.CGPDFDocumentGetPage(document, number)
        if page is None:
            raise RenderError("malformed", f"Page {number} could not be read.")
        width, height = _page_size(quartz, page)
        colour_space = quartz.CGColorSpaceCreateDeviceRGB()
        # kCGImageAlphaNoneSkipLast: no alpha channel to vary between runs.
        context = quartz.CGBitmapContextCreate(
            None, width, height, 8, 0, colour_space,
            quartz.kCGImageAlphaNoneSkipLast)
        if context is None:
            raise RenderError("encode", f"Page {number} could not be drawn.")
        # A white ground, so a transparent scan does not become a black page.
        quartz.CGContextSetRGBFillColor(context, 1.0, 1.0, 1.0, 1.0)
        quartz.CGContextFillRect(context, ((0, 0), (width, height)))
        # The drawing transform applies the page's own rotation and fits the
        # crop box to the bitmap, so a rotated scan is not read sideways.
        transform = quartz.CGPDFPageGetDrawingTransform(
            page, quartz.kCGPDFCropBox, ((0, 0), (width, height)), 0, True)
        quartz.CGContextConcatCTM(context, transform)
        quartz.CGContextDrawPDFPage(context, page)
        image = quartz.CGBitmapContextCreateImage(context)
        if image is None:
            raise RenderError("encode", f"Page {number} could not be captured.")
        yield RenderedPage(number=number, image=_encode(quartz, image),
                           width=width, height=height)
