#!/usr/bin/env python3
"""Derive Refinix application assets from the two brand originals.

The originals in `frontend/design/assets/Brand/` are the design track's masters
and are never modified. This script only crops and rescales them; it does not
redraw, recolour or restyle the mark.

Outputs (all committed, so neither the runtime nor the packaging step needs an
image library):

    frontend/app/assets/refinix-wordmark.png   header logo, symbol + name
    frontend/app/assets/refinix-mark.png       symbol only, small uses
    desktop/icons/Refinix.iconset/             macOS icon slices
    desktop/icons/Refinix.icns                 macOS bundle icon (needs iconutil)
    desktop/icons/Refinix.ico                  Windows icon
    desktop/icons/refinix-<n>.png              Linux hicolor sizes

Build-time dependency: Pillow (HPND licence), already present on the macOS
coordinator at 12.3.0. `iconutil` and `sips` are macOS system tools. Run this
only when the originals change.

    python3 scripts/build-brand-assets.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
BRAND = REPO / "frontend" / "design" / "assets" / "Brand"
STACKED = BRAND / "refinix-logo-stacked.jpeg"
HORIZONTAL = BRAND / "refinix-logo-horizontal.jpeg"
APP_ASSETS = REPO / "frontend" / "app" / "assets"
ICONS = REPO / "desktop" / "icons"

# Measured content bounds, luminance > 60 with a two-pixel column/row floor.
# The stacked master is 1536x1287 and the horizontal master 1536x1024.
SYMBOL_BOX = (409, 146, 1174, 841)        # symbol only; REFINIX lettering excluded
WORDMARK_BOX = (241, 425, 1325, 605)      # symbol and name, outer margin removed

GROUND = (5, 6, 8)                        # the brand ground, matching the masters
ICON_SIZES = (16, 32, 48, 64, 128, 256, 512)


def _open(path: Path) -> Image.Image:
    if not path.is_file():
        sys.exit(f"missing brand original: {path}")
    return Image.open(path).convert("RGB")


def square_symbol(side: int = 1024, content: float = 0.78) -> Image.Image:
    """The symbol centred on the brand ground, aspect ratio preserved."""
    symbol = _open(STACKED).crop(SYMBOL_BOX)
    box = int(side * content)
    scale = min(box / symbol.width, box / symbol.height)
    resized = symbol.resize((round(symbol.width * scale), round(symbol.height * scale)),
                            Image.LANCZOS)
    canvas = Image.new("RGB", (side, side), GROUND)
    canvas.paste(resized, ((side - resized.width) // 2, (side - resized.height) // 2))
    return canvas


def rounded_tile(side: int = 1024) -> Image.Image:
    """macOS-style rounded tile. The mark itself is untouched inside it."""
    art = square_symbol(side)
    tile = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    mask = Image.new("L", (side * 4, side * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, side * 4 - 1, side * 4 - 1), radius=int(side * 4 * 0.2237), fill=255)
    tile.paste(art, (0, 0), mask.resize((side, side), Image.LANCZOS))
    return tile


def build_app_assets() -> list[Path]:
    APP_ASSETS.mkdir(parents=True, exist_ok=True)
    written = []

    wordmark = _open(HORIZONTAL).crop(WORDMARK_BOX)
    # 3x of the 32px header slot, so the metal survives a Retina panel.
    height = 96
    wordmark = wordmark.resize(
        (round(wordmark.width * height / wordmark.height), height), Image.LANCZOS)
    pad = 8
    plate = Image.new("RGB", (wordmark.width + pad * 2, height + pad * 2), GROUND)
    plate.paste(wordmark, (pad, pad))
    out = APP_ASSETS / "refinix-wordmark.png"
    plate.save(out, optimize=True)
    written.append(out)

    out = APP_ASSETS / "refinix-mark.png"
    square_symbol(128).save(out, optimize=True)
    written.append(out)
    return written


def build_icons() -> list[Path]:
    ICONS.mkdir(parents=True, exist_ok=True)
    written = []
    master = rounded_tile(1024)

    for size in ICON_SIZES:
        out = ICONS / f"refinix-{size}.png"
        master.resize((size, size), Image.LANCZOS).save(out, optimize=True)
        written.append(out)

    out = ICONS / "Refinix.ico"
    master.save(out, sizes=[(s, s) for s in (16, 32, 48, 64, 128, 256)])
    written.append(out)

    # The .iconset is an intermediate iconutil needs; only the .icns is kept.
    with tempfile.TemporaryDirectory() as scratch:
        iconset = Path(scratch) / "Refinix.iconset"
        iconset.mkdir()
        for base in (16, 32, 128, 256, 512):
            for suffix, factor in (("", 1), ("@2x", 2)):
                px = base * factor
                master.resize((px, px), Image.LANCZOS).save(
                    iconset / f"icon_{base}x{base}{suffix}.png", optimize=True)
        icns = ICONS / "Refinix.icns"
        try:
            subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)],
                           check=True, capture_output=True)
            written.append(icns)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            print(f"iconutil unavailable, .icns not built: {exc}", file=sys.stderr)
    return written


if __name__ == "__main__":
    for path in build_app_assets() + build_icons():
        print(path.relative_to(REPO))
