#!/usr/bin/env python3
"""Measure Refinix's own overhead on this computer, separately from model time.

Starts the real entry point (`python -m desktop --no-window`) against a
scratch data folder (never the person's own), then records:

    startup           spawn -> first answered /v1/status
    status            /v1/status latency (the page reads it after every action)
    reads             the other GET routes the surfaces load
    idle              CPU and resident memory of the running process at rest
    documents         rendering and text extraction of the fixture PDFs, with
                      peak traced memory (in-process)
    update_verify     offline verification of a staged 256 MB package (in-process)

Every result records the hardware, OS, Python and source commit it came from.
No model is downloaded or run: model time is measured separately, by the
workflows themselves.

    python scripts/measure_performance.py --out perf.json [--label before]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _get(port: int, path: str, timeout: float = 30) -> tuple[float, int]:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                     headers={"Host": f"127.0.0.1:{port}"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    started = time.perf_counter()
    with opener.open(request, timeout=timeout) as response:
        body = response.read()
    return (time.perf_counter() - started) * 1000, len(body)


def _summary(values: list[float]) -> dict:
    ordered = sorted(values)
    return {"n": len(values), "median_ms": round(statistics.median(ordered), 1),
            "p95_ms": round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 1),
            "max_ms": round(ordered[-1], 1)}


def measure_server(work: Path, rounds: int, idle_seconds: int) -> dict:
    import psutil
    port = _free_port()
    state = work / "state" / "coordinator.sqlite3"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    started = time.perf_counter()
    process = subprocess.Popen([sys.executable, "-m", "desktop", "--no-window", "--port",
                                str(port), "--state", str(state)], cwd=str(ROOT),
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env)
    result = {}
    try:
        deadline = time.perf_counter() + 120
        while True:
            try:
                _get(port, "/v1/status", timeout=5)
                break
            except OSError:
                if time.perf_counter() > deadline or process.poll() is not None:
                    raise SystemExit("the coordinator did not start: "
                                     + process.stderr.read().decode()[-800:])
                time.sleep(0.05)
        result["startup_ms"] = round((time.perf_counter() - started) * 1000, 1)
        status = [_get(port, "/v1/status") for _ in range(rounds)]
        result["status"] = {**_summary([s[0] for s in status]),
                            "bytes": status[-1][1]}
        reads = {}
        for path in ("/v1/chats", "/v1/updates", "/v1/capabilities", "/v1/code/conversations"):
            try:
                times = [_get(port, path)[0] for _ in range(max(5, rounds // 3))]
                reads[path] = _summary(times)
            except OSError as exc:
                reads[path] = {"error": str(exc)[:120]}
        result["reads"] = reads
        proc = psutil.Process(process.pid)
        proc.cpu_percent(None)
        time.sleep(idle_seconds)
        result["idle"] = {"seconds": idle_seconds,
                          "cpu_percent": round(proc.cpu_percent(None), 2),
                          "rss_mb": round(proc.memory_info().rss / 1024 ** 2, 1),
                          "threads": proc.num_threads()}
    finally:
        process.terminate()
        try:
            process.wait(20)
        except subprocess.TimeoutExpired:
            process.kill()
    return result


def measure_documents() -> dict:
    """Render every page and extract text from the document fixtures, with the
    OCR step left out (no model): Refinix's own reading cost only.

    Time and memory are measured in separate passes: tracing allocations slows
    allocation-heavy rendering several times over, so a timed pass never runs
    under tracemalloc."""
    import hashlib
    from backend.coordinator import documents, pdfrender

    def read(path, data):
        pages = sum(1 for _page in pdfrender.render_pages(data))
        rendered = time.perf_counter()
        try:
            documents.extract(path, source_id="measure", filename=path.name,
                              media_type="application/pdf",
                              expected_sha256=hashlib.sha256(data).hexdigest(),
                              ocr_model=None)
            outcome = "extracted"
        except documents.DocumentError as exc:
            outcome = f"refused: {str(exc)[:90]}"
        return pages, rendered, outcome

    out = {}
    for path in sorted((ROOT / "fixtures").rglob("*.pdf"))[:6]:
        data = path.read_bytes()
        read(path, data)                               # imports and caches warm
        started = time.perf_counter()
        pages, rendered, outcome = read(path, data)
        finished = time.perf_counter()
        tracemalloc.start()
        read(path, data)
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        out[str(path.relative_to(ROOT))] = {
            "bytes": len(data), "pages": pages,
            "render_ms": round((rendered - started) * 1000, 1),
            "extract_ms": round((finished - rendered) * 1000, 1),
            "outcome": outcome, "peak_traced_mb": round(peak / 1024 ** 2, 1)}
    return out


def measure_update_verify(work: Path) -> dict:
    from backend.coordinator import release, updates
    from scripts import update_repository as repository
    passes = {role: f"measure {role} key" for role in repository.ROLES}
    keys, feed, assets = work / "keys", work / "feed", work / "assets"
    assets.mkdir(parents=True)
    repository.beta_init(keys, feed, passphrases=passes, check_location=False)
    root = (feed / "metadata" / "1.root.json").read_bytes()
    import hashlib
    for number, version in enumerate(("0.1.0-preview.1", "0.1.0-preview.2"), 1):
        name = release.asset_name(version, "linux-x64", "deb")
        with open(assets / name, "wb") as handle:
            for _ in range(256):
                handle.write(os.urandom(1024 * 1024))
        repository.stage(keys, feed, maturity="preview", passphrases=passes, packages=[{
            "path": str(assets / name), "lane": "linux-x64", "version": version,
            "channel": "beta", "maturity": "preview", "build_set": "m", "min_os": "24.04",
            "schema_version": 15, "engine_release": "m", "public_build": number,
            "signing": "unsigned", "install_capability": "preview-test",
            "trust_root": hashlib.sha256(root).hexdigest(), "shared_snapshot_digest": "m"}])
        repository.advance(keys, feed, passphrases=passes)

    class Local:
        def request(self, method, url, preload_content=False, redirect=False):
            class R:
                def __init__(self, body, status=200):
                    self.body, self.status, self.headers = body, status, {}

                def stream(self, size):
                    for start in range(0, len(self.body), size):
                        yield self.body[start:start + size]

                def release_conn(self):
                    pass
            for prefix, folder in (("https://m.invalid/f/", feed),
                                   ("https://m.invalid/r/", assets)):
                if url.startswith(prefix):
                    path = folder / url[len(prefix):]
                    path = path if path.is_file() else folder / Path(url).name
                    return R(path.read_bytes()) if path.is_file() else R(b"", 404)
            return R(b"", 404)

    service = updates.UpdateService(
        work / "data", identity={"version": "0.1.0-preview.1", "channel": "beta",
                                 "maturity": "preview", "lane": "linux-x64",
                                 "install_capability": "preview-test",
                                 "trust_root": hashlib.sha256(root).hexdigest()},
        trust_root=root, feed={"metadata_url": "https://m.invalid/f/metadata/",
                               "targets_url": "https://m.invalid/f/targets/",
                               "packages_url": "https://m.invalid/r/", "package_hosts": []},
        schema_version=15, os_version="24.04", pool=Local(), install_format="deb",
        platform="linux")
    started = time.perf_counter()
    service.check()
    check_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    service.start_download()
    service.wait(600)
    stage_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    service.admit_staged()
    admit_ms = (time.perf_counter() - started) * 1000
    staged = sum(p.stat().st_size for p in (work / "data" / "updates").rglob("*")
                 if p.is_file())
    return {"package_mb": 256, "check_ms": round(check_ms, 1),
            "download_and_stage_ms": round(stage_ms, 1),
            "offline_admission_ms": round(admit_ms, 1),
            "staging_mb": round(staged / 1024 ** 2, 1)}


def host() -> dict:
    import psutil
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip())
    return {"machine": platform.machine(), "processor": platform.processor(),
            "os": platform.platform(), "python": platform.python_version(),
            "cpus": os.cpu_count(), "memory_gb": round(psutil.virtual_memory().total / 1024 ** 3, 1),
            "commit": commit, "uncommitted_changes": dirty}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--idle", type=int, default=20)
    parser.add_argument("--skip", nargs="*", default=[])
    args = parser.parse_args(argv)
    report = {"label": args.label, "host": host(),
              "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with tempfile.TemporaryDirectory(prefix="refinix-measure-") as directory:
        work = Path(directory)
        if "server" not in args.skip:
            report["server"] = measure_server(work, args.rounds, args.idle)
        if "documents" not in args.skip:
            report["documents"] = measure_documents()
        if "updates" not in args.skip:
            report["update_verify"] = measure_update_verify(work / "updates")
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
