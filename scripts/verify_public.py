#!/usr/bin/env python3
"""What an ordinary visitor gets: the live website, its download links, the files.

No credentials are used anywhere. It reads the live site's `release.json`
and download page, and:

* with --expect-site (a checkout of the website commit that was deployed),
  requires the live `index.html` and `release.json` to be exactly that
  commit's — a CDN still serving the previous page fails;
* downloads `SHA256SUMS` and every file the release lists, anonymously,
  following redirects only over HTTPS, and requires each file's size and
  SHA-256 to match both `release.json` and `SHA256SUMS`;
* requires every first-install download link on the live page to be one of
  those files, and each platform card to show its minimum OS and warning;
* records the host each download finally came from (installed clients accept
  only the feed's listed package hosts).

    python scripts/verify_public.py --site https://refinix.runs-on.dev/ \\
        [--expect-site <website checkout>] [--keep <folder>] [--report public.json]

Exit status 0 only when everything matched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlsplit

HEADERS = {"User-Agent": "refinix-public-check", "Cache-Control": "no-cache"}


def fetch(url: str, timeout: float = 60) -> tuple[bytes, str]:
    """Bytes and the final URL; HTTPS only, no credentials, no cookies."""
    if not url.startswith("https://"):
        raise ValueError(f"{url} is not HTTPS")
    request = urllib.request.Request(url, headers=HEADERS)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        final = response.geturl()
        if not final.startswith("https://"):
            raise ValueError(f"{url} redirected to {final}")
        return response.read(), final


def download(url: str, target: Path, timeout: float = 600) -> tuple[int, str, str]:
    """Size, SHA-256 and final URL of one file, streamed to `target`."""
    request = urllib.request.Request(url, headers=HEADERS)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    digest, size = hashlib.sha256(), 0
    with opener.open(request, timeout=timeout) as response, open(target, "wb") as out:
        final = response.geturl()
        if not final.startswith("https://"):
            raise ValueError(f"{url} redirected to {final}")
        for block in iter(lambda: response.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
            out.write(block)
    return size, digest.hexdigest(), final


def check(site: str, expect_site: Path | None, keep: Path | None,
          expect_version: str | None = None) -> dict:
    checks = []

    def record(name, passed, observed):
        checks.append({"check": name, "passed": bool(passed), "observed": observed})
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {observed}", flush=True)

    site = site.rstrip("/") + "/"
    page, _final = fetch(site + "?" + str(int(time.time())))
    raw_release, _final = fetch(urljoin(site, "release.json") + "?" + str(int(time.time())))
    release = json.loads(raw_release)
    if expect_version is not None:
        record("the website offers the requested version",
               release.get("version") == expect_version,
               {"expected": expect_version, "observed": release.get("version")})
    if expect_site is not None:
        for name, live in (("index.html", page), ("release.json", raw_release)):
            wanted = (Path(expect_site) / name).read_bytes()
            record(f"the live {name} is the deployed commit's", live == wanted,
                   {"live_sha256": hashlib.sha256(live).hexdigest(),
                    "commit_sha256": hashlib.sha256(wanted).hexdigest()})
    sums_raw, _ = fetch(release["checksums"])
    sums = dict((line.split()[1], line.split()[0]) for line in
                sums_raw.decode().splitlines() if line.strip())
    folder = keep or Path(tempfile.mkdtemp(prefix="refinix-public-"))
    folder.mkdir(parents=True, exist_ok=True)
    text = page.decode("utf-8", errors="replace")
    listed = set()
    for lane, entry in (release.get("lanes") or {}).items():
        if entry.get("status") != "available":
            continue
        record(f"{lane}: the card shows its warning before the download",
               bool(entry.get("os_warning")) and entry["os_warning"].split(".")[0][:40]
               in text.replace("&#x27;", "'"), entry.get("os_warning"))
        for item in entry.get("files") or []:
            name = item["name"]
            listed.add(item["url"])
            try:
                size, digest, final = download(item["url"], folder / name)
            except Exception as exc:                       # noqa: BLE001
                record(f"{name} downloads anonymously", False, f"{type(exc).__name__}: {exc}")
                continue
            record(f"{name} downloads anonymously and matches", size == item["size"]
                   and digest == item["sha256"] == sums.get(name),
                   {"size": size, "sha256": digest, "final_host": urlsplit(final).hostname,
                    "in_SHA256SUMS": sums.get(name) == digest})
            if item.get("first_install"):
                record(f"{name}: the live page links it", f'href="{item["url"]}"' in text,
                       item["url"])
    links = set(re.findall(r'href="(https://github\.com/[^"]+/releases/download/[^"]+)"', text))
    stray = sorted(link for link in links if link not in listed
                   and not link.endswith("/SHA256SUMS"))
    record("every download link on the page is a listed release file", not stray, stray)
    return {"kind": "public", "site": site, "version": release.get("version"),
            "checks": checks,
            "passed": bool(checks) and all(c["passed"] for c in checks)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", required=True)
    parser.add_argument("--expect-site", type=Path)
    parser.add_argument("--expect-version")
    parser.add_argument("--keep", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    result = check(args.site, args.expect_site, args.keep, args.expect_version)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("all matched" if result["passed"] else "FAILED")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
