#!/usr/bin/env python3
"""Measure the managed engine against the parity rule (P-1) and write evidence.

Runs only on loopback, through the production adapters and prompt builders:

* the managed `llama-server` with the pinned model files, and optionally
* the developer baseline, Ollama, on the *same model bytes*, imported into a
  temporary private store so the user's own Ollama store is never touched.

Workflow trials use the real prompt builders and strict parsers (Chat relation
check, Code proposal, general document, approval note, page reading of the C07
synthetic scan). It also measures Stop during prompt processing and during
generation, context-overflow refusal, loopback-only binding, sampled outbound
connections, cold/warm time to first token, throughput and peak resident memory.

The output is evidence for review, not a qualification record and not release
acceptance. It never downloads anything.

    python scripts/engine_parity.py --model-dir <dir> --output <file.json> \\
        [--trials 3] [--ollama /usr/local/bin/ollama]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.contracts import profiles, v1  # noqa: E402
from backend.coordinator import (codeflow, device, docflow, engine,  # noqa: E402
                                 local_engine, models, ocr, pdfrender, retrieval,
                                 runtime)

FIXTURES = ROOT / "fixtures" / "c07" / "documents"


# --------------------------------------------------------------------------
# Profiles and one measured call
# --------------------------------------------------------------------------

def make_profile(model: v1.ModelRef, workflow: str, decoder: str, context: int,
                 output: int) -> v1.ExecutionProfile:
    values = {"model": model.model_dump(), "target_profile_id": "parity-run",
              "workflow_mode": workflow, "qualified_context_tokens": context,
              "default_output_tokens": output, "max_output_tokens": output,
              "reasoning_modes": ["disabled", "enabled"], "default_reasoning": "disabled",
              "decoder_modes": [decoder], "qualified_memory_bytes": None,
              "qualification_state": "qualified", "eligible": True,
              "evidence_kind": "measured", "evidence_ref": "parity-run:process-local"}
    return v1.ExecutionProfile(profile_id=v1.execution_profile_id(values), **values)


class Caller:
    def __init__(self, model: v1.ModelRef, context: int):
        self.model, self.context = model, context

    def __call__(self, messages, *, workflow, reasoning="disabled", response_format=None,
                 images=None, output=2048, should_cancel=None):
        decoder = "json_schema" if response_format else "text"
        profile = make_profile(self.model, workflow, decoder, self.context, output)
        inference = profiles.request(
            profile, reasoning=reasoning, decoder=decoder,
            decoder_schema_sha256=(profiles.schema_sha256(response_format)
                                   if response_format else None))
        started = time.monotonic()
        first = None
        text, thinking, done = [], 0, None
        for kind, payload in runtime.stream_chat(
                messages, profile=profile, inference=inference,
                should_cancel=should_cancel, images=images,
                response_format=response_format):
            if kind in ("delta", "thinking") and first is None:
                first = time.monotonic() - started
            if kind == "delta":
                text.append(payload)
            elif kind == "thinking":
                thinking += len(payload)
            elif kind == "cancelled":
                return {"cancelled": True, "elapsed_s": time.monotonic() - started,
                        "ttft_s": first}
            elif kind == "done":
                done = payload
        return {"text": "".join(text), "thinking_chars": thinking, "ttft_s": first,
                "elapsed_s": time.monotonic() - started, "metrics": done}


# --------------------------------------------------------------------------
# Workflow trials (production builders and strict parsers)
# --------------------------------------------------------------------------

def _pages(text: str) -> list[dict]:
    pages, current, number = [], [], 0
    for line in text.splitlines():
        if line.startswith("--- PAGE ") and line.endswith("---"):
            if number:
                pages.append({"number": number, "text": "\n".join(current).strip()})
            number = int(line.split()[2])
            current = []
        elif number:
            current.append(line)
    if number:
        pages.append({"number": number, "text": "\n".join(current).strip()})
    return pages


def trial_chat(call, reasoning):
    result = call([{"role": "user", "content": models.CHAT_CHECK_PROMPT}],
                  workflow=profiles.CHAT, reasoning=reasoning, output=2048)
    failure = models.chat_relation_failure(result.get("text", ""))
    return result, failure


def trial_code(call, reasoning):
    before = "def add(left, right):\n    return left - right\n"
    selected = [{"path": "maths.py", "text": before,
                 "sha256": hashlib.sha256(before.encode()).hexdigest()}]
    result = call(codeflow.build_messages(
        "Fix maths.py so add returns the sum by replacing subtraction with addition.",
        selected), workflow=profiles.CODE, reasoning=reasoning,
        response_format=codeflow.PROPOSAL_SCHEMA, output=2048)
    try:
        proposal = codeflow.parse_proposal(result.get("text", ""), selected)
    except codeflow.ProposalError as exc:
        return result, f"proposal rejected: {exc}"
    edits = proposal.get("edits") or []
    if not edits or "return left + right" not in edits[0].get("content", ""):
        return result, "proposal did not contain the required fix"
    return result, None


def trial_general(call, reasoning):
    source = {"source_id": str(uuid.uuid4()), "filename": "observation.txt",
              "pages": [{"number": 1, "text": "Shaft velocity was 7.9 mm/s. The "
                         "follow-up inspection is due within 24 hours."}]}
    result = call(docflow.general_document_messages(
        "Create a concise document that preserves 7.9 mm/s and within 24 hours.",
        [source]), workflow=profiles.DOCUMENTS, reasoning=reasoning,
        response_format=docflow.GENERAL_DOCUMENT_FORMAT, output=3072)
    try:
        document = docflow.parse_general_document(result.get("text", ""))
    except docflow.WorkflowError as exc:
        return result, f"document rejected: {exc}"
    flat = json.dumps(document).lower()
    if "7.9" not in flat or "24" not in flat:
        return result, "document dropped a required fact"
    return result, None


def trial_approval(call, reasoning):
    report_pages = _pages((FIXTURES / "inspection-report.txt").read_text(encoding="utf-8"))
    sop_pages = _pages((FIXTURES / "sop-mech-014.txt").read_text(encoding="utf-8"))
    report = {"source_id": str(uuid.uuid4()), "filename": "inspection-report.txt",
              "pages": report_pages}
    sop = {"source_id": str(uuid.uuid4()), "filename": "sop-mech-014.txt",
           "pages": sop_pages}
    passages = [retrieval.Passage(sop["source_id"], sop["filename"], page["number"],
                                  page["text"], 1.0) for page in sop_pages[:2]]
    result = call(docflow.approval_note_messages(
        "Draft the approval note for this inspection report.", passages,
        [(report, report_pages)]), workflow=profiles.DOCUMENTS, reasoning=reasoning,
        response_format=docflow.APPROVAL_NOTE_FORMAT, output=docflow.APPROVAL_NUM_PREDICT)
    try:
        docflow.parse_approval_note(result.get("text", ""), [report, sop])
    except docflow.WorkflowError as exc:
        return result, f"approval note rejected: {exc}"
    return result, None


def trial_page(call, reasoning, *, page_png: bytes):
    result = call(ocr.page_messages("image/png"), workflow=profiles.OCR,
                  reasoning=reasoning, response_format=ocr.PAGE_SCHEMA,
                  images=[page_png], output=ocr.PAGE_NUM_PREDICT)
    try:
        reading = ocr.parse_page_reply(result.get("text", ""))
    except ocr.OcrError as exc:
        return result, f"page reading rejected: {exc}"
    wanted = ("NG-2026-0417", "P-204", "SOP-MECH-014")
    missing = [w for w in wanted if w.lower() not in reading.lower()]
    result["reading_chars"] = len(reading)
    return result, (f"page reading missed {missing}" if missing else None)


TRIALS = {"chat": trial_chat, "code": trial_code, "general_document": trial_general,
          "approval_note": trial_approval}


def run_trials(call, trials: int, *, page_png: bytes | None) -> dict:
    results = {}
    for name, function in TRIALS.items():
        for reasoning in ("disabled", "enabled"):
            key = f"{name}/{reasoning}"
            runs = []
            for _ in range(trials):
                try:
                    result, failure = function(call, reasoning)
                except runtime.RuntimeUnavailable as exc:
                    result, failure = {}, f"runtime refused: {exc}"
                metrics = result.get("metrics") or {}
                runs.append({"passed": failure is None, "failure": failure,
                             "done_reason": metrics.get("done_reason"),
                             "prompt_tokens": metrics.get("prompt_tokens"),
                             "output_tokens": metrics.get("output_tokens"),
                             "ttft_s": result.get("ttft_s"),
                             "elapsed_s": round(result.get("elapsed_s") or 0, 3),
                             "tokens_per_s": metrics.get("tokens_per_s")})
            results[key] = {"passed": sum(r["passed"] for r in runs), "of": len(runs),
                            "runs": runs}
    if page_png is not None:
        runs = []
        for _ in range(trials):
            try:
                result, failure = trial_page(call, "disabled", page_png=page_png)
            except runtime.RuntimeUnavailable as exc:
                result, failure = {}, f"runtime refused: {exc}"
            metrics = result.get("metrics") or {}
            runs.append({"passed": failure is None, "failure": failure,
                         "done_reason": metrics.get("done_reason"),
                         "output_tokens": metrics.get("output_tokens"),
                         "elapsed_s": round(result.get("elapsed_s") or 0, 3)})
        results["page_reading/disabled"] = {"passed": sum(r["passed"] for r in runs),
                                            "of": len(runs), "runs": runs}
    return results


# --------------------------------------------------------------------------
# Behaviour checks
# --------------------------------------------------------------------------

def stop_checks(call) -> dict:
    out = {}
    essay = [{"role": "user", "content": "Write a detailed 1500-word essay on pump "
              "maintenance, with many numbered sections."}]
    first_delta = threading.Event()
    cancel = threading.Event()

    def watcher():
        first_delta.wait(60)
        time.sleep(1.0)
        cancel.set()

    stamp = {}
    original = runtime.stream_chat

    def mark(messages, **kw):
        for kind, payload in original(messages, **kw):
            if kind == "delta" and not first_delta.is_set():
                first_delta.set()
            if kind == "cancelled":
                stamp["cancelled_at"] = time.monotonic()
            yield kind, payload

    runtime.stream_chat = mark
    try:
        threading.Thread(target=watcher, daemon=True).start()
        result = call(essay, workflow=profiles.CHAT, output=2048,
                      should_cancel=lambda: (cancel.is_set() and stamp.setdefault(
                          "requested_at", time.monotonic())) or cancel.is_set())
    finally:
        runtime.stream_chat = original
    out["during_generation"] = {
        "cancelled": bool(result.get("cancelled")),
        "stop_latency_s": (round(stamp["cancelled_at"] - stamp["requested_at"], 3)
                           if "cancelled_at" in stamp and "requested_at" in stamp else None)}
    long_prompt = [{"role": "user", "content": ("The pump inspection record continues. "
                                                * 900) + "\nSummarise in one line."}]
    asked = time.monotonic()
    result = call(long_prompt, workflow=profiles.CHAT, output=256,
                  should_cancel=lambda: time.monotonic() - asked > 0.3)
    out["during_prompt_processing"] = {
        "cancelled": bool(result.get("cancelled")),
        "returned_after_s": round(result.get("elapsed_s") or 0, 3)}
    follow = call([{"role": "user", "content": "Reply with the single word: ready"}],
                  workflow=profiles.CHAT, output=64)
    out["engine_usable_after_stop"] = {"ttft_s": follow.get("ttft_s"),
                                       "text": (follow.get("text") or "")[:40]}
    return out


def overflow_check(call, context: int) -> dict:
    words = "pressure " * int(context * 1.4)
    try:
        call([{"role": "user", "content": words}], workflow=profiles.CHAT, output=256)
    except runtime.RuntimeUnavailable as exc:
        return {"refused": True, "message": str(exc)[:200]}
    return {"refused": False, "message": "the engine answered an overflowing prompt"}


def performance(call, *, cold_started: float | None) -> dict:
    prompt = [{"role": "user", "content": "In two sentences, explain why pumps need "
               "regular bearing inspection."}]
    runs = [call(prompt, workflow=profiles.CHAT, output=128) for _ in range(4)]
    ttfts = [r["ttft_s"] for r in runs if r.get("ttft_s")]
    speeds = [(r.get("metrics") or {}).get("tokens_per_s") for r in runs]
    return {"engine_start_to_ready_s": cold_started,
            "first_request_ttft_s": runs[0].get("ttft_s"),
            "warm_median_ttft_s": round(statistics.median(ttfts[1:]), 4) if len(ttfts) > 1 else None,
            "median_tokens_per_s": statistics.median([s for s in speeds if s]) if any(speeds) else None}


class Sampler:
    """Resident memory and socket snapshots of one process tree."""

    def __init__(self, pid_source, interval=0.25):
        self.pid_source, self.interval = pid_source, interval
        self.peak_rss = 0
        self.listen, self.remote, self.samples, self.errors = set(), set(), 0, 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join(5)

    def _run(self):
        import psutil
        while not self._stop.wait(self.interval):
            pid = self.pid_source()
            if not pid:
                continue
            try:
                process = psutil.Process(pid)
                self.peak_rss = max(self.peak_rss, process.memory_info().rss)
                for conn in process.net_connections(kind="inet"):
                    if conn.status == psutil.CONN_LISTEN:
                        self.listen.add(f"{conn.laddr.ip}:{conn.laddr.port}")
                    elif conn.raddr and conn.raddr.ip not in ("127.0.0.1", "::1"):
                        self.remote.add(f"{conn.raddr.ip}:{conn.raddr.port}")
                self.samples += 1
            except Exception:                              # noqa: BLE001
                self.errors += 1

    def report(self) -> dict:
        return {"method": "psutil per-process socket snapshot",
                "interval_s": self.interval, "samples": self.samples,
                "observer_errors": self.errors, "peak_rss_bytes": self.peak_rss,
                "listening": sorted(self.listen),
                "loopback_only": all(a.startswith(("127.0.0.1:", "[::1]:", "::1:"))
                                     for a in self.listen) if self.listen else None,
                "non_loopback_connections_seen": sorted(self.remote),
                "coverage_note": "Snapshots can miss a connection opened and closed "
                                 "between samples; this is observation, not "
                                 "enforcement."}


# --------------------------------------------------------------------------
# Engines under test
# --------------------------------------------------------------------------

def managed_setup(model_dir: Path, engine_root: Path | None, context: int, data: Path):
    selection = engine.select(environ={}, frozen=False,
                              roots=[engine_root] if engine_root else None)
    if selection.mode != engine.MANAGED or not selection.usable:
        raise RuntimeError("managed engine missing or modified")
    entry = models.BY_ID[models.MANAGED_MAIN]
    files = {f.role: (model_dir / f.name) for f in entry.files}
    components = tuple(local_engine.ModelComponent(f.role, model_dir / f.name, f.size,
                                                   f.sha256) for f in entry.files)
    record = local_engine.InstalledModel(entry.id, entry.manifest_sha256, files["weights"],
                                         files.get("projector"), dict(entry.sampling),
                                         components)
    settings = engine.LaunchSettings(context_tokens=context)
    backend = local_engine.LocalEngine(selection, data, registry=lambda: {entry.id: record},
                                       settings_for=lambda _m: settings)
    model = v1.ModelRef(model_id=entry.id, manifest_sha256=entry.manifest_sha256,
                        runtime=engine.LLAMA_CPP, runtime_version=selection.runtime_version)
    return selection, backend, model


def ollama_baseline(binary: str, model_dir: Path, context: int, trials: int,
                    work: Path, page_png) -> dict:
    """Same bytes in a temporary private Ollama store; never the user's store."""
    entry = models.BY_ID[models.MANAGED_MAIN]
    weights = model_dir / next(f.name for f in entry.files if f.role == "weights")
    store = work / "ollama-store"
    store.mkdir()
    host = "127.0.0.1:11521"
    env = {"PATH": "/usr/bin:/bin", "HOME": str(work), "OLLAMA_HOST": host,
           "OLLAMA_MODELS": str(store), "OLLAMA_NOPRUNE": "1"}
    serve = subprocess.Popen([binary, "serve"], env=env, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        version = None
        for _ in range(60):
            time.sleep(0.5)
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                        f"http://{host}/api/version", timeout=2) as response:
                    version = json.load(response).get("version")
                    break
            except OSError:
                continue
        if version is None:
            return {"available": False, "reason": "private Ollama did not start"}
        params = "\n".join(f"PARAMETER {k} {v}" for k, v in entry.sampling)
        modelfile = work / "Modelfile"
        modelfile.write_text(f"FROM {weights}\nRENDERER qwen3.5\nPARSER qwen3.5\n{params}\n",
                             encoding="utf-8")
        created = subprocess.run([binary, "create", "refinix-parity", "-f", str(modelfile)],
                                 env=env, capture_output=True, text=True, timeout=900)
        if created.returncode != 0:
            return {"available": False, "ollama_version": version,
                    "reason": (created.stderr or created.stdout).strip()[-400:]}
        original_host = runtime.HOST
        runtime.HOST = f"http://{host}"
        try:
            state = runtime.probe()
            digest = (state.get("digests") or {}).get("refinix-parity:latest")
            model = v1.ModelRef(model_id="refinix-parity:latest",
                                manifest_sha256=digest or "0" * 64, runtime="ollama",
                                runtime_version=version)
            call = Caller(model, context)
            perf = performance(call, cold_started=None)
            results = run_trials(call, trials, page_png=None)
            # Same-bytes generation must actually generate: an engine that
            # loads but cannot run the architecture is not a baseline.
            return {"available": True, "ollama_version": version,
                    "imported_manifest": digest, "performance": perf, "trials": results}
        finally:
            runtime.HOST = original_host
    finally:
        serve.terminate()
        try:
            serve.wait(10)
        except subprocess.TimeoutExpired:
            serve.kill()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--engine-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--context", type=int, default=8192)
    parser.add_argument("--ollama", help="ollama binary for the same-bytes baseline")
    args = parser.parse_args(argv)
    if args.output.exists():
        print("refusing to replace an existing evidence file", file=sys.stderr)
        return 1
    first = next(iter(pdfrender.render_pages(
        (FIXTURES / "inspection-report-scan.pdf").read_bytes())), None)
    page_png = first.image if first is not None else None
    with tempfile.TemporaryDirectory(prefix="refinix-parity-") as work:
        work = Path(work)
        selection, backend, model = managed_setup(args.model_dir, args.engine_root,
                                                  args.context, work / "data")
        runtime.configure_managed(backend)
        call = Caller(model, args.context)
        evidence = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "kind": "engine-parity-evidence", "release_accepted": False,
                    "engine": selection.describe(),
                    "model": model.model_dump(),
                    "device": {k: v for k, v in device.hardware(
                        engine_devices=engine.list_devices(selection)).items()
                        if k != "memory_available_bytes"},
                    "settings": {"context_tokens": args.context, "trials": args.trials}}
        try:
            with Sampler(lambda: backend.engine.process.pid
                         if backend.engine.running else None) as sampler:
                started = time.monotonic()
                warm = call([{"role": "user", "content": "Reply: ok"}],
                            workflow=profiles.CHAT, output=16)
                evidence["cold_first_request_s"] = round(time.monotonic() - started, 3)
                evidence["cold_first_request_ttft_s"] = warm.get("ttft_s")
                evidence["performance"] = performance(call, cold_started=None)
                evidence["trials"] = run_trials(call, args.trials, page_png=page_png)
                evidence["stop"] = stop_checks(call)
                evidence["overflow"] = overflow_check(call, args.context)
            evidence["observer"] = sampler.report()
        finally:
            backend.stop()
            runtime.configure_managed(None)
        if args.ollama:
            evidence["ollama_same_bytes"] = ollama_baseline(
                args.ollama, args.model_dir, args.context, args.trials, work, page_png)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output),
                      "trials": {k: f"{v['passed']}/{v['of']}"
                                 for k, v in evidence["trials"].items()},
                      "stop": evidence["stop"], "overflow": evidence["overflow"]["refused"],
                      "observer": {k: evidence["observer"][k] for k in
                                   ("loopback_only", "non_loopback_connections_seen",
                                    "peak_rss_bytes")},
                      "ollama": (evidence.get("ollama_same_bytes") or {}).get("available")},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
