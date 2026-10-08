#!/bin/sh
# Prepare the public GitHub Pages bundle. This does not publish it.
#
# With a release's release.json (written by scripts/release_assemble.py), the
# download cards are rendered into index.html and release.json is copied beside
# it; without one, the page says no tester preview is published yet.
set -eu
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    printf 'Usage: sh %s NEW_OUTPUT_DIRECTORY [RELEASE_JSON]\n' "$0" >&2
    exit 2
fi
SITE_SOURCE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 - "$SITE_SOURCE_ROOT" "$1" "${2:-}" <<'PY'
import html
import json
import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

source = Path(sys.argv[1]) / "frontend/design"
output = Path(sys.argv[2]).resolve()
release_file = Path(sys.argv[3]) if sys.argv[3] else None
if output.exists():
    raise SystemExit(f"Refusing to overwrite existing output: {output}")

REPOSITORY = "https://github.com/prachi-satbhai0741/Refinix"
LANES = ("linux-x64", "macos-arm64", "windows-x64")
START, END = "<!-- refinix-downloads -->", "<!-- /refinix-downloads -->"


def download_cards(release: dict) -> str:
    """The download section for one release, every value checked and escaped.

    A file is offered only from this release's own GitHub download folder, by a
    plain file name, with a full SHA-256: release.json is data, and a wrong or
    hostile value stops the export instead of reaching the page."""
    version = release.get("version", "")
    if not re.fullmatch(r"\d+\.\d+\.\d+(-(preview|beta)\.\d+)?", version):
        raise SystemExit(f"release.json: not a release version: {version!r}")
    folder = f"{REPOSITORY}/releases/download/v{version}/"
    if release.get("release_page") != f"{REPOSITORY}/releases/tag/v{version}" \
            or release.get("checksums") != folder + "SHA256SUMS":
        raise SystemExit("release.json: release page or checksum link is not this release's")
    preview = release.get("maturity") == "preview"
    lanes = release.get("lanes") or {}
    if set(lanes) - set(LANES):
        raise SystemExit(f"release.json: unknown platform lanes {sorted(set(lanes) - set(LANES))}")
    cards = []
    for lane in LANES:
        entry = lanes.get(lane)
        if not entry:
            continue
        title = html.escape(f"{entry.get('platform', lane)}")
        arch = html.escape(str(entry.get("architecture", "")))
        if entry.get("status") != "available":
            reason = html.escape(str(entry.get("reason") or "not in this release"))
            cards.append(f'''        <article class="build" data-status="unavailable">
          <h3>{title}</h3>
          <span class="req">{arch}</span>
          <p class="dl-status">Unavailable: {reason}</p>
        </article>''')
            continue
        links = []
        for item in entry.get("files") or []:
            name, digest = item.get("name", ""), item.get("sha256", "")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._~+-]*", name) \
                    or item.get("url") != folder + name:
                raise SystemExit(f"release.json: {name!r} is not offered from this release")
            if not re.fullmatch(r"[0-9a-f]{64}", digest) or not isinstance(item.get("size"), int):
                raise SystemExit(f"release.json: {name} has no valid SHA-256 and size")
            label = html.escape(str(item.get("label", name)))
            size = f"{item['size'] / 1_000_000:.0f} MB"
            links.append(f'''          <a class="btn btn-primary" href="{html.escape(folder + name)}">{label} · {size}</a>
          <p class="dl-sum">{html.escape(name)}<br>SHA-256 {digest}</p>''')
        if not links:
            raise SystemExit(f"release.json: {lane} is available with no files")
        status = ("Tester preview — device testing pending" if preview
                  else "Beta release")
        cards.append(f'''        <article class="build" data-status="available">
          <h3>{title}</h3>
          <span class="req">{arch}</span>
          <p class="dl-status">{status}</p>
''' + "\n".join(links) + "\n        </article>")
    if not any('data-status="available"' in card for card in cards):
        raise SystemExit("release.json: nothing in this release is available")
    build = release.get("public_build")
    meta = (f'      <p class="dl-meta">Refinix {html.escape(version)}'
            + (f" · build {int(build)}" if isinstance(build, int) else "")
            + f' · <a href="{html.escape(release["release_page"])}">release page</a>'
            + f' · <a href="{html.escape(release["checksums"])}">SHA256SUMS</a></p>')
    return (f"{START}\n{meta}\n      <div class=\"builds reveal d2\" id=\"downloads\">\n"
            + "\n".join(cards) + f"\n      </div>\n      {END}")

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

index = pages["site.html"]
if release_file is not None:
    release = json.loads(release_file.read_text(encoding="utf-8"))
    if index.count(START) != 1 or index.count(END) != 1:
        raise SystemExit("site.html has no single download section to fill")
    before, rest = index.split(START)
    _old, after = rest.split(END)
    index = before + download_cards(release) + after

output.mkdir(parents=True)
if release_file is None:
    shutil.copyfile(source / "site.html", output / "index.html")
else:
    (output / "index.html").write_text(index, encoding="utf-8")
    shutil.copyfile(release_file, output / "release.json")
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
print(f"Prepared {output}: 2 pages, 2 stylesheets, {len(assets)} assets, CNAME and .nojekyll"
      + (f", downloads for {release['version']}" if release_file is not None else ""))
PY
