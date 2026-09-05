"""Generate the synthetic raster scan fixture. Standard library only.

C07 owes C08 a *scan*: an image of a page with no text layer, so the extraction
pipeline has to actually read pixels. `inspection-report.txt` is the ground
truth; this renders the same words as bitmaps and wraps them in a PDF whose
pages contain one image each and no text operators at all.

**Why this is generated rather than downloaded or drawn by a library.** A real
scan cannot be committed — it would be someone's document. A rendering
dependency (Pillow, reportlab) would be a new pinned wheel, new provenance and
a new image build for a fixture, which `docs/c08-dependency-plan.md` argues
against for the OCR path and would be no better here. Everything below is
`zlib`, `struct` and arithmetic: a 5x7 bitmap font, a deterministic speckle, and
a hand-written PDF.

**Determinism is the point.** The speckle uses a fixed linear congruential
generator with a fixed seed, so the same input produces byte-identical output
and the recorded SHA-256 stays meaningful. There is no timestamp, no PDF `/ID`
and no creation date in the output for the same reason.

    python3 fixtures/c07/make_scan.py

Regenerating rewrites the PDF and nothing else; run
`python3 -m fixtures.c07.rehash` afterwards to update the provenance manifest.
"""

from __future__ import annotations

import pathlib
import re
import zlib

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "documents" / "inspection-report.txt"
TARGET = HERE / "documents" / "inspection-report-scan.pdf"

# 150 DPI A4-ish. Big enough that OCR is a fair test, small enough to commit.
WIDTH, HEIGHT = 1240, 1754
MARGIN_X, MARGIN_Y = 90, 110
SCALE = 2                      # each font pixel becomes SCALE x SCALE
LINE_HEIGHT = 9 * SCALE
CHAR_WIDTH = 6 * SCALE
SPECKLE_SEED = 20260905
SPECKLE_RATE = 900             # roughly one speckle per this many pixels

# A 5x7 font: fourteen hex digits per glyph, seven rows of one byte, with the
# low five bits of each byte carrying that row's five columns (bit 4 leftmost).
# Fixed width so a malformed entry fails loudly instead of rendering half a
# glyph. Only the characters the fixture uses; anything else renders blank,
# which is visible on the page rather than silently dropped.
FONT = {
    ' ': "00000000000000", '%': "191A0204080B13", "'": "0C0C0000000000",
    '(': "02040808080402", ')': "08040202020408", ',': "000000000C0408",
    '-': "0000000E000000", '.': "00000000000C0C", '/': "01010204081010",
    '0': "0E11131519110E", '1': "040C040404040E", '2': "0E11010204081F",
    '3': "1F02040201110E", '4': "02060A121F0202", '5': "1F101E0101110E",
    '6': "0608101E11110E", '7': "1F010204080808", '8': "0E11110E11110E",
    '9': "0E11110F01020C", ':': "000C0C000C0C00", 'A': "0E11111F111111",
    'B': "1E111E1111111E", 'C': "0E11101010110E", 'D': "1E11111111111E",
    'E': "1F10101E10101F", 'F': "1F10101E101010", 'G': "0E11101711110F",
    'H': "1111111F111111", 'I': "0E04040404040E", 'J': "0702020202120C",
    'K': "11121418141211", 'L': "1010101010101F", 'M': "111B1515111111",
    'N': "11191513111111", 'O': "0E11111111110E", 'P': "1E11111E101010",
    'Q': "0E11111115120D", 'R': "1E11111E141211", 'S': "0F10100E01011E",
    'T': "1F040404040404", 'U': "1111111111110E", 'V': "11111111110A04",
    'W': "11111115151B11", 'X': "11110A040A1111", 'Y': "11110A04040404",
    'Z': "1F01020408101F",
}


def _glyph(char: str) -> list[int]:
    """Seven row bitmaps for one character, or a blank cell."""
    raw = FONT.get(char.upper())
    if raw is None:
        return [0] * 7
    if len(raw) != 14:
        raise ValueError(f"glyph {char!r} is not seven rows of one byte")
    return [int(raw[i:i + 2], 16) for i in range(0, 14, 2)]


class Page:
    """One greyscale page. 255 is paper, 0 is ink."""

    def __init__(self):
        self.rows = [bytearray(b"\xff" * WIDTH) for _ in range(HEIGHT)]

    def draw(self, x: int, y: int, char: str) -> None:
        for row, bits in enumerate(_glyph(char)):
            for column in range(5):
                if not bits & (1 << (4 - column)):
                    continue
                for dy in range(SCALE):
                    for dx in range(SCALE):
                        px, py = x + column * SCALE + dx, y + row * SCALE + dy
                        if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                            self.rows[py][px] = 0

    def text(self, lines: list[str]) -> None:
        y = MARGIN_Y
        for line in lines:
            x = MARGIN_X
            for char in line[:((WIDTH - 2 * MARGIN_X) // CHAR_WIDTH)]:
                self.draw(x, y, char)
                x += CHAR_WIDTH
            y += LINE_HEIGHT

    def speckle(self, seed: int) -> int:
        """Deterministic scanner dirt.

        Without it the pages are perfectly clean bitmaps, which is not what an
        OCR pipeline meets and would make the fixture easier than the real
        thing. A fixed LCG rather than `random`: the sequence must not depend on
        the interpreter's seeding.
        """
        state = seed
        marks = (WIDTH * HEIGHT) // SPECKLE_RATE
        for _ in range(marks):
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            x = state % WIDTH
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            y = state % HEIGHT
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            shade = 120 + (state % 100)
            self.rows[y][x] = min(self.rows[y][x], shade)
        return state

    def data(self) -> bytes:
        return b"".join(bytes(row) for row in self.rows)


def source_pages() -> list[list[str]]:
    """Split the ground-truth text on its own page markers."""
    text = SOURCE.read_text(encoding="utf-8")
    parts = re.split(r"^--- PAGE (\d+) ---$", text, flags=re.M)
    return [parts[i + 1].strip("\n").splitlines()
            for i in range(1, len(parts), 2)]


def build_pdf(pages: list[bytes]) -> bytes:
    """A minimal PDF: one image XObject per page, and no text operators.

    Hand-written because the structure is a handful of objects and an xref
    table. No `/Producer`, no `/CreationDate` and no `/ID`, so the bytes depend
    only on the pixels.
    """
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    kids, page_objects = [], []
    for raw in pages:
        stream = zlib.compress(raw, 9)
        image = add(
            b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
            b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode "
            b"/Length %d >>\nstream\n" % (WIDTH, HEIGHT, len(stream))
            + stream + b"\nendstream")
        # The ONLY content operator is a single image draw. No BT/ET, no /Font,
        # so there is no text layer for an extractor to shortcut through.
        content = b"q %d 0 0 %d 0 0 cm /Im0 Do Q" % (WIDTH, HEIGHT)
        contents = add(b"<< /Length %d >>\nstream\n" % len(content)
                       + content + b"\nendstream")
        page_objects.append((image, contents))

    pages_id = len(objects) + len(page_objects) + 1
    for image, contents in page_objects:
        kids.append(add(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] "
            b"/Resources << /XObject << /Im0 %d 0 R >> >> /Contents %d 0 R >>"
            % (pages_id, WIDTH, HEIGHT, image, contents)))
    tree = add(b"<< /Type /Pages /Kids [" +
               b" ".join(b"%d 0 R" % kid for kid in kids) +
               b"] /Count %d >>" % len(kids))
    assert tree == pages_id, "the page tree object number must match /Parent"
    catalogue = add(b"<< /Type /Catalog /Pages %d 0 R >>" % tree)

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += b"%010d 00000 n \n" % offset
    out += (b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, catalogue, xref))
    return bytes(out)


def main() -> int:
    rendered = []
    seed = SPECKLE_SEED
    for index, lines in enumerate(source_pages()):
        page = Page()
        page.text([f"SYNTHETIC SCAN - PAGE {index + 1} - NOT A REAL DOCUMENT", ""]
                  + lines)
        seed = page.speckle(seed)
        rendered.append(page.data())
    TARGET.write_bytes(build_pdf(rendered))
    print(f"{TARGET.name}: {len(rendered)} pages, {TARGET.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
