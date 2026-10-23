"""Rendering one PDF page to pixels, on every operating system Refinix supports.

A raster scan has no text layer, so nothing can read it until a page becomes an
image. This module is the whole rendering boundary, and Phase 1 item E is why it
now has two backends instead of one.

**Portable first, Quartz retained.** `pypdfium2` is the selected renderer
wherever it is installed: it ships a pinned PDFium binary for Windows, macOS and
Linux, needs no system package and reaches no network, so the Beta-critical
reading path is one code path qualified on three OS families rather than an Apple
framework the other two cannot have. The macOS Quartz path stays as a fallback so
an already-installed bundle that predates the dependency keeps reading documents
instead of losing the capability. Where neither is present, `probe()` says so and
`documents.py` keeps reporting PDF unavailable rather than half-reading the file.

**Provenance comes from the renderer, not from a constant.** Each page carries
the name of the backend that produced it, and `ocr.method_label` reads that name.
A fixed "(Quartz)" string would become a fabricated provenance line the moment a
second backend existed.

**Nothing touches the disk.** The PDF arrives as bytes the caller already
verified against the intake digest, and the page leaves as PNG bytes built in
memory. There is no temporary image to clean up and no path for a caller to
influence: neither backend is ever handed a URL or filename, so no local or
remote path can be opened from here. Form environments are deliberately not
initialised, so interactive form content and its scripting are never evaluated.

**Every bound is checked before the work, not after.** Input bytes, page count,
pixels per page and encoded output size each have a ceiling, and the whole render
has a wall-clock deadline re-checked between pages. A malformed, encrypted or
unrenderable document raises `RenderError`; it never returns a blank page that a
later stage would read as "the scan said nothing".

**A text layer is read, not rendered.** `text_pages` reads the words a PDF
already carries through the same PDFium boundary and the same bounds, without
drawing a page. Only a page with no text layer needs pixels at all.

Standard library, plus `pypdfium2` (BSD-3-Clause / Apache-2.0, bundling PDFium)
where installed, plus the already-present PyObjC Quartz framework on macOS.
"""

from __future__ import annotations

import struct
import time
import zlib
from dataclasses import dataclass

# Bounds. Visible in the refusals, so a stop explains itself.
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PAGES = 40
# The longest edge of the rendered page, in pixels. 2200 reads small print on
# an A4 or Letter scan (about 265 dpi) that 1600 blurred: in an earlier run on
# the C07 fixture a 1600-pixel render read NG-2026-0417 as MG-…, while 2200
# read every identifier. That is history, not a measurement of accuracy. A page
# whose shape would exceed the pixel ceiling below at this size is drawn
# smaller to fit it rather than refused.
TARGET_LONG_EDGE = 2200
MAX_PIXELS_PER_PAGE = 4_000_000          # ~2000x2000
MAX_IMAGE_BYTES = 8 * 1024 * 1024        # encoded PNG per page
MAX_RENDER_SECONDS = 120.0
# The most text read from one page's text layer. The same ceiling
# `documents.MAX_PAGE_CHARS` applies to every other format; it is repeated here
# because `documents` imports this module, not the other way round.
MAX_TEXT_CHARS_PER_PAGE = 40_000

# One deterministic pixel format for every page and every backend, so the model
# never sees a format that varies by page or by operating system.
IMAGE_MEDIA_TYPE = "image/png"
IMAGE_UTI = "public.png"                 # Quartz destination type

# Backend names. These reach artifact provenance, so they are stable strings and
# not derived from a module's `__name__`.
PDFIUM = "pypdfium2"
QUARTZ = "Quartz"
# Preference order. Portable first: one qualified path on three OS families is
# worth more than the platform-native one it replaces.
BACKEND_ORDER = (PDFIUM, QUARTZ)


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
    # Which backend drew it. Empty only for a page a caller built itself, which
    # `ocr.method_label` reports as an unnamed renderer rather than guessing.
    renderer: str = ""


@dataclass(frozen=True)
class PageText:
    """The text layer of one page, exactly as far as it was read."""

    number: int                # 1-based, as a reader would count
    text: str
    chars: int                 # characters PDFium reports on the page
    truncated: bool            # True when only the first MAX_TEXT_CHARS_PER_PAGE were read


# --------------------------------------------------------------------------
# Shared bounds and PNG encoding
# --------------------------------------------------------------------------

def _check_input(data) -> bytes:
    if not isinstance(data, (bytes, bytearray)):
        raise RenderError("unreadable", "A PDF must be supplied as bytes.")
    data = bytes(data)
    if not data:
        raise RenderError("empty", "That PDF is empty.")
    if len(data) > MAX_PDF_BYTES:
        raise RenderError(
            "too_large",
            f"That PDF is larger than {MAX_PDF_BYTES // (1024 * 1024)} MB.")
    return data


def _target_size(width: float, height: float) -> tuple[int, int, float]:
    """Pixel size and scale for one page, bounded before anything is drawn."""
    if width <= 0 or height <= 0:
        raise RenderError("malformed", "A page in that PDF has no usable size.")
    scale = TARGET_LONG_EDGE / max(width, height)
    # Fit to the pixel ceiling: a square or unusually wide page is drawn at the
    # largest size the ceiling allows instead of being refused.
    ceiling = (MAX_PIXELS_PER_PAGE / (width * height)) ** 0.5
    if scale > ceiling:
        scale = ceiling * 0.999
    pixels_w = max(1, int(round(width * scale)))
    pixels_h = max(1, int(round(height * scale)))
    if pixels_w * pixels_h > MAX_PIXELS_PER_PAGE:
        raise RenderError(
            "too_large",
            f"A page in that PDF renders to more than {MAX_PIXELS_PER_PAGE} pixels.")
    return pixels_w, pixels_h, scale


def _page_limit(declared: int, max_pages: int) -> int:
    if declared <= 0:
        raise RenderError("malformed", "That PDF declares no pages.")
    limit = min(declared, max(1, int(max_pages)), MAX_PAGES)
    if declared > limit:
        raise RenderError(
            "too_many_pages",
            f"That PDF has {declared} pages. Refinix reads up to {limit} in one "
            "request.")
    return limit


def _check_encoded(encoded: bytes) -> bytes:
    if not encoded:
        raise RenderError("encode", "That page produced no image data.")
    if len(encoded) > MAX_IMAGE_BYTES:
        raise RenderError(
            "too_large",
            f"A rendered page exceeded {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    return encoded


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))


def encode_png(width: int, height: int, rows: list[bytes]) -> bytes:
    """8-bit RGB PNG from raw scanlines. Standard library only.

    Written here rather than pulled in with an imaging library because the only
    authorised dependency is the PDF renderer itself, and because this keeps the
    encoded bytes under Refinix's control: one colour type, no alpha channel to
    vary between runs, and filter 0 on every scanline. Two renders of the same
    page by the same backend therefore produce identical bytes.
    """
    if len(rows) != height:
        raise RenderError("encode", "A page produced the wrong number of rows.")
    stride = width * 3
    for row in rows:
        if len(row) != stride:
            raise RenderError("encode", "A page produced a malformed scanline.")
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    # Filter byte 0 (None) before each scanline: no prediction, so the output
    # depends on the pixels alone.
    raw = b"".join(b"\x00" + row for row in rows)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header)
            + _chunk(b"IDAT", zlib.compress(raw, 6)) + _chunk(b"IEND", b""))


# --------------------------------------------------------------------------
# Backend: pypdfium2 — the portable path
# --------------------------------------------------------------------------

def _pdfium():
    """Import pypdfium2 on demand, and never as a side effect of importing this.

    A lazy import keeps `documents.py` importable on the worker and in any
    environment where the renderer is not installed, and means a capability
    probe costs nothing until something actually asks.
    """
    try:
        import pypdfium2                                     # noqa: PLC0415
        from pypdfium2 import raw                             # noqa: PLC0415
    except Exception as exc:                                 # noqa: BLE001
        raise RenderError(
            "no_renderer",
            "PDF rendering needs the pypdfium2 renderer, which is not "
            "installed in this environment.") from exc
    return pypdfium2, raw


def _pdfium_probe() -> dict:
    try:
        pypdfium2, _raw = _pdfium()
    except RenderError as exc:
        return {"available": False, "module": PDFIUM, "detail": str(exc)}
    try:
        from pypdfium2.version import PDFIUM_INFO, PYPDFIUM_INFO  # noqa: PLC0415
        versions = (f" pypdfium2 {PYPDFIUM_INFO.version}, "
                    f"PDFium {PDFIUM_INFO.version}.")
    except Exception:                                        # noqa: BLE001
        # A build that does not report its versions still renders; the label
        # simply cannot name them, and says nothing rather than inventing one.
        versions = ""
    missing = [name for name in ("PdfDocument", "PdfiumError")
               if not hasattr(pypdfium2, name)]
    if missing:
        return {"available": False, "module": PDFIUM,
                "detail": ("This build of pypdfium2 is missing "
                           + ", ".join(missing) + ".")}
    return {
        "available": True, "module": PDFIUM,
        "detail": ("Rendered with the bundled PDFium engine, which works the "
                   "same way on Windows, macOS and Linux. Pages are drawn in "
                   f"memory as {IMAGE_MEDIA_TYPE} at up to {TARGET_LONG_EDGE}px "
                   "on the long edge." + versions),
        "max_pages": MAX_PAGES, "max_bytes": MAX_PDF_BYTES,
    }


def _pdfium_document(pypdfium2, raw, data: bytes):
    """Open bytes, and turn PDFium's reason into one of ours.

    The error code is used rather than the message text: an encrypted document
    must be refused as encrypted on every PDFium build, and matching on English
    prose would stop being true the first time that prose changed.
    """
    try:
        return pypdfium2.PdfDocument(data)
    except pypdfium2.PdfiumError as exc:
        code = getattr(exc, "err_code", None)
        if code == raw.FPDF_ERR_PASSWORD:
            raise RenderError(
                "encrypted",
                "That PDF is password-protected. Refinix does not unlock "
                "documents.") from exc
        if code == raw.FPDF_ERR_SECURITY:
            raise RenderError(
                "encrypted",
                "That PDF uses a security handler Refinix will not open.") from exc
        raise RenderError(
            "malformed", "That file is not a readable PDF.") from exc
    except Exception as exc:                                 # noqa: BLE001
        raise RenderError(
            "malformed", "That PDF could not be opened for reading.") from exc


def _pdfium_page_count(data: bytes) -> int:
    pypdfium2, raw = _pdfium()
    document = _pdfium_document(pypdfium2, raw, data)
    try:
        count = len(document)
    finally:
        document.close()
    if count <= 0:
        raise RenderError("malformed", "That PDF declares no pages.")
    return count


def _pdfium_render(data: bytes, *, max_pages: int, should_cancel,
                  deadline_seconds: float):
    pypdfium2, raw = _pdfium()
    document = _pdfium_document(pypdfium2, raw, data)
    try:
        limit = _page_limit(len(document), max_pages)
        expires = time.monotonic() + max(1.0, float(deadline_seconds))
        for number in range(1, limit + 1):
            if should_cancel is not None and should_cancel():
                raise RenderError("cancelled", "Rendering was stopped.")
            if time.monotonic() > expires:
                raise RenderError(
                    "timeout",
                    "Rendering that PDF took longer than Refinix allows.")
            yield _pdfium_page(pypdfium2, document, number)
    finally:
        document.close()


def _pdfium_page(pypdfium2, document, number: int) -> RenderedPage:
    try:
        page = document[number - 1]
    except Exception as exc:                                 # noqa: BLE001
        raise RenderError("malformed", f"Page {number} could not be read.") from exc
    try:
        # PDFium's page size already accounts for the page's own /Rotate, and
        # `render` draws in that same orientation. Swapping the edges again here
        # — as the Quartz path must — would turn an upright page sideways.
        width_pt, height_pt = page.get_size()
        # Predicted only, to bound the work before it happens. PDFium rounds a
        # scaled edge up where this rounds to nearest, so the two differ by a
        # pixel on most pages; the bitmap it actually produced is the authority
        # for what gets encoded, and the ceiling is applied to that.
        _predicted_w, _predicted_h, scale = _target_size(float(width_pt),
                                                         float(height_pt))
        bitmap = None
        try:
            # rev_byteorder gives RGB rather than BGR, so no channel swap is
            # needed. A white fill keeps a transparent scan from becoming a
            # black page. Forms are never initialised on the document, so
            # `may_draw_forms` has nothing to draw.
            bitmap = page.render(scale=scale, rev_byteorder=True,
                                 fill_color=(255, 255, 255, 255))
            width, height = int(bitmap.width), int(bitmap.height)
            if width <= 0 or height <= 0:
                raise RenderError("encode", f"Page {number} rendered to nothing.")
            if width * height > MAX_PIXELS_PER_PAGE:
                raise RenderError(
                    "too_large",
                    f"A page in that PDF renders to more than "
                    f"{MAX_PIXELS_PER_PAGE} pixels.")
            if bitmap.mode != "RGB":
                raise RenderError(
                    "encode",
                    f"Page {number} rendered in an unsupported pixel format.")
            rows = _rows(bitmap, width, height)
        finally:
            if bitmap is not None:
                bitmap.close()
    finally:
        page.close()
    return RenderedPage(number=number, image=_check_encoded(
        encode_png(width, height, rows)),
        width=width, height=height, renderer=PDFIUM)


def _rows(bitmap, width: int, height: int) -> list[bytes]:
    """Scanlines without the row padding PDFium may add for alignment."""
    stride, line = bitmap.stride, width * 3
    if stride < line:
        raise RenderError("encode", "A rendered page has a malformed stride.")
    buffer = memoryview(bytes(bitmap.buffer))
    if len(buffer) < stride * height:
        raise RenderError("encode", "A rendered page is shorter than declared.")
    return [bytes(buffer[row * stride:row * stride + line])
            for row in range(height)]


# --------------------------------------------------------------------------
# Backend: Quartz — retained for an installed macOS bundle
# --------------------------------------------------------------------------

def _quartz():
    """Import Quartz on demand, and never as a side effect of importing this."""
    try:
        import Quartz                                        # noqa: PLC0415
    except Exception as exc:                                 # noqa: BLE001
        raise RenderError(
            "no_renderer",
            "PDF rendering with the macOS Quartz framework (PyObjC) is not "
            "available in this environment.") from exc
    return Quartz


def _quartz_probe() -> dict:
    try:
        quartz = _quartz()
    except RenderError as exc:
        return {"available": False, "module": QUARTZ, "detail": str(exc)}
    required = ("CGPDFDocumentCreateWithProvider", "CGBitmapContextCreate",
                "CGImageDestinationCreateWithData", "CGPDFPageGetDrawingTransform")
    missing = [name for name in required if not hasattr(quartz, name)]
    if missing:
        return {"available": False, "module": QUARTZ,
                "detail": ("This build of PyObjC Quartz is missing "
                           + ", ".join(missing) + ".")}
    return {
        "available": True, "module": QUARTZ,
        "detail": ("Rendered with the macOS Quartz framework (PyObjC). Pages "
                   f"are drawn in memory as {IMAGE_MEDIA_TYPE} at up to "
                   f"{TARGET_LONG_EDGE}px on the long edge. This is the macOS "
                   "fallback; the portable renderer is preferred."),
        "max_pages": MAX_PAGES, "max_bytes": MAX_PDF_BYTES,
    }


def _quartz_document(quartz, data: bytes):
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


def _quartz_page_size(quartz, page) -> tuple[int, int]:
    box = quartz.CGPDFPageGetBoxRect(page, quartz.kCGPDFCropBox)
    width, height = float(box.size.width), float(box.size.height)
    rotation = int(quartz.CGPDFPageGetRotationAngle(page)) % 360
    # Quartz reports the unrotated crop box, so the edges are swapped here. The
    # portable backend must not do this; its size is already rotated.
    if rotation in (90, 270):
        width, height = height, width
    pixels_w, pixels_h, _scale = _target_size(width, height)
    return pixels_w, pixels_h


def _quartz_encode(quartz, image) -> bytes:
    data = quartz.CFDataCreateMutable(None, 0)
    destination = quartz.CGImageDestinationCreateWithData(data, IMAGE_UTI, 1, None)
    if destination is None:
        raise RenderError("encode", "That page could not be encoded as an image.")
    quartz.CGImageDestinationAddImage(destination, image, None)
    if not quartz.CGImageDestinationFinalize(destination):
        raise RenderError("encode", "That page could not be encoded as an image.")
    return _check_encoded(bytes(data))


def _quartz_page_count(data: bytes) -> int:
    quartz = _quartz()
    document = _quartz_document(quartz, data)
    count = int(quartz.CGPDFDocumentGetNumberOfPages(document))
    if count <= 0:
        raise RenderError("malformed", "That PDF declares no pages.")
    return count


def _quartz_render(data: bytes, *, max_pages: int, should_cancel,
                   deadline_seconds: float):
    quartz = _quartz()
    document = _quartz_document(quartz, data)
    limit = _page_limit(int(quartz.CGPDFDocumentGetNumberOfPages(document)),
                        max_pages)
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
        width, height = _quartz_page_size(quartz, page)
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
        yield RenderedPage(number=number, image=_quartz_encode(quartz, image),
                           width=width, height=height, renderer=QUARTZ)


# --------------------------------------------------------------------------
# Choosing a backend
# --------------------------------------------------------------------------

_BACKENDS = {
    PDFIUM: {"probe": _pdfium_probe, "render": _pdfium_render,
             "count": _pdfium_page_count},
    QUARTZ: {"probe": _quartz_probe, "render": _quartz_render,
             "count": _quartz_page_count},
}


def backends() -> tuple[dict, ...]:
    """Every backend's own answer, in preference order. A diagnostic: it says
    which renderers this computer has, not which one a render will use."""
    return tuple(_BACKENDS[name]["probe"]() for name in BACKEND_ORDER)


def probe() -> dict:
    """What this computer can actually render. An observation, not a default.

    Importing a renderer starts no service, opens no socket and loads no model;
    it only answers whether the code path exists at all. The first available
    backend in preference order wins, and its name is what artifact provenance
    will carry.
    """
    states = backends()
    for state in states:
        if state["available"]:
            return dict(state, backends=[s["module"] for s in states
                                         if s["available"]])
    # No backend: report every reason, because the fix differs per platform —
    # install the portable renderer, or on macOS restore PyObjC.
    return {
        "available": False, "module": None,
        "backends": [],
        "detail": ("Refinix cannot render PDF pages on this computer. "
                   + " ".join(state["detail"] for state in states)),
    }


def available() -> bool:
    return probe()["available"]


def selected_backend() -> str | None:
    """The backend a render would use right now, or None."""
    return probe()["module"]


def _selected():
    name = selected_backend()
    if name is None:
        raise RenderError("no_renderer", probe()["detail"])
    return _BACKENDS[name]


def page_count(data: bytes) -> int:
    """How many pages the document states. Never inferred, never defaulted."""
    data = _check_input(data)
    return _selected()["count"](data)


def render_pages(data: bytes, *, max_pages: int = MAX_PAGES,
                 should_cancel=None, deadline_seconds: float = MAX_RENDER_SECONDS,
                 backend: str | None = None):
    """Yield `RenderedPage` in document order, one page at a time.

    A generator on purpose: the caller sends each page to the model and drops
    the pixels before the next page is drawn, so peak memory is one page rather
    than a whole scan. `should_cancel` is polled between pages, which is the
    only place a partially rendered document can be abandoned cleanly.

    `backend` names one explicitly. It exists so the two backends can be
    compared on a computer that has both; leave it unset in the application, so
    the preference order decides.
    """
    data = _check_input(data)
    if backend is not None:
        if backend not in _BACKENDS:
            raise RenderError("no_renderer", f"{backend!r} is not a renderer.")
        state = _BACKENDS[backend]["probe"]()
        if not state["available"]:
            raise RenderError("no_renderer", state["detail"])
        chosen = _BACKENDS[backend]
    else:
        chosen = _selected()
    return chosen["render"](data, max_pages=max_pages,
                            should_cancel=should_cancel,
                            deadline_seconds=deadline_seconds)


# --------------------------------------------------------------------------
# Reading the text layer
# --------------------------------------------------------------------------
#
# A PDF written by a program already carries its words. Reading them is
# deterministic and needs no model, so a text-bearing PDF does not wait on an
# OCR qualification it never needed. Only PDFium offers this: Quartz has no
# text API, so a computer with only the Quartz fallback reports it unavailable
# rather than guessing. Nothing is rendered here.

def text_probe() -> dict:
    """Whether this computer can read a PDF's text layer right now."""
    state = _pdfium_probe()
    if not state["available"]:
        return {"available": False, "module": None,
                "detail": ("Refinix cannot read PDF text on this computer. "
                           + state["detail"])}
    return {"available": True, "module": PDFIUM,
            "detail": ("Text-layer PDFs are read on this computer with the "
                       "bundled PDFium engine. Scanned pages have no text "
                       "layer and are not read this way.")}


def text_pages(data: bytes, *, max_pages: int = MAX_PAGES, should_cancel=None,
               deadline_seconds: float = MAX_RENDER_SECONDS) -> list[PageText]:
    """Every page's text layer, in document order, without rendering a page.

    The same bounds as rendering: input bytes, the page limit checked before
    any page is read, a wall-clock deadline and cancellation between pages. A
    page holding more than `MAX_TEXT_CHARS_PER_PAGE` characters is read up to
    that ceiling and marked `truncated`, so the caller can say so; it is never
    cut silently. A page with no text layer comes back empty, never invented.
    """
    data = _check_input(data)
    pypdfium2, raw = _pdfium()
    document = _pdfium_document(pypdfium2, raw, data)
    try:
        limit = _page_limit(len(document), max_pages)
        expires = time.monotonic() + max(1.0, float(deadline_seconds))
        pages = []
        for number in range(1, limit + 1):
            if should_cancel is not None and should_cancel():
                raise RenderError("cancelled", "Reading was stopped.")
            if time.monotonic() > expires:
                raise RenderError(
                    "timeout", "Reading that PDF took longer than Refinix allows.")
            pages.append(_pdfium_page_text(document, number))
        return pages
    finally:
        document.close()


def _pdfium_page_text(document, number: int) -> PageText:
    try:
        page = document[number - 1]
    except Exception as exc:                                 # noqa: BLE001
        raise RenderError("malformed", f"Page {number} could not be read.") from exc
    textpage = None
    try:
        textpage = page.get_textpage()
        chars = int(textpage.count_chars())
        read = min(chars, MAX_TEXT_CHARS_PER_PAGE)
        text = textpage.get_text_range(0, read) if read > 0 else ""
    except RenderError:
        raise
    except Exception as exc:                                 # noqa: BLE001
        raise RenderError(
            "malformed", f"The text on page {number} could not be read.") from exc
    finally:
        if textpage is not None:
            textpage.close()
        page.close()
    return PageText(number=number, text=text, chars=chars,
                    truncated=chars > MAX_TEXT_CHARS_PER_PAGE)
