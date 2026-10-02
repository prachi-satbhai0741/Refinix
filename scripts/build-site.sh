#!/bin/sh
# Prepare the public GitHub Pages bundle. This does not publish it.
set -eu
if [ "$#" -ne 1 ]; then
    printf 'Usage: sh %s NEW_OUTPUT_DIRECTORY\n' "$0" >&2
    exit 2
fi
SITE_SOURCE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 - "$SITE_SOURCE_ROOT" "$1" <<'PY'
import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

source = Path(sys.argv[1]) / "frontend/design"
output = Path(sys.argv[2]).resolve()
if output.exists():
    raise SystemExit(f"Refusing to overwrite existing output: {output}")

class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.urls.extend(value for key, value in attrs
                         if key in ("src", "poster", "href") and value)

pages = {name: (source / name).read_text(encoding="utf-8")
         for name in ("site.html", "docs.html")}
references = References()
for text in pages.values():
    references.feed(text)
for name in ("site.css", "docs.css"):
    css = (source / name).read_text(encoding="utf-8")
    references.urls.extend(match.strip().strip("\"'")
                           for match in re.findall(r"url\(\s*([^)]*)\)", css))

# These two optional images have an SVG fallback in both source pages.
optional = {"assets/refinix-lockup-h.png", "assets/refinix-lockup-v.png"}
assets = {}
for url in references.urls:
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        continue
    path = unquote(parsed.path)
    if not path.startswith("assets/"):
        continue
    asset = (source / path).resolve()
    if not asset.is_relative_to((source / "assets").resolve()):
        raise SystemExit(f"Asset escapes the website assets folder: {path}")
    if not asset.is_file():
        if path in optional:
            continue
        raise SystemExit(f"Missing referenced website asset: {path}")
    assets[path] = asset

output.mkdir(parents=True)
shutil.copyfile(source / "site.html", output / "index.html")
docs = re.sub(r'(\bhref\s*=\s*[\"\'])site\.html(?=[#?\"\'])',
              r'\1index.html', pages["docs.html"])
(output / "docs.html").write_text(docs, encoding="utf-8")
for name in ("site.css", "docs.css"):
    shutil.copyfile(source / name, output / name)
for path, asset in sorted(assets.items()):
    target = output / path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(asset, target)
(output / "CNAME").write_text("refinix.runs-on.dev\n", encoding="utf-8")
(output / ".nojekyll").touch()
print(f"Prepared {output}: 2 pages, 2 stylesheets, {len(assets)} assets, CNAME and .nojekyll")
PY
