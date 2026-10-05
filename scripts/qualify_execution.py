#!/usr/bin/env python3
"""Run isolated Chat/Code/Documents qualification and write strict evidence.

The runner uses temporary coordinator state and temporary source files.  A
candidate profile is admitted only inside this process so the production paths
can be exercised; the emitted artifact remains non-admissible evidence and is
never loaded into the production registry.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.contracts import profiles, qualification, v1  # noqa: E402
from backend.coordinator import (db, device, docflow, docgen, engine,  # noqa: E402
                                 local_engine, models, runtime)
from backend.coordinator.server import Coordinator  # noqa: E402


WORKFLOWS = (
    (profiles.CHAT, "text"),
    (profiles.CODE, "json_schema"),
    (profiles.DOCUMENTS, "json_schema"),
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _candidate(profile: v1.ExecutionProfile) -> v1.ExecutionProfile:
    return v1.ExecutionProfile.model_validate({
        **profile.model_dump(),
        "qualification_state": "candidate",
        "eligible": False,
        "evidence_kind": "unverified",
        "evidence_ref": "qualification-run:pending-review",
    })


BOTH_REASONING = ("disabled", "enabled")


def _temporary_profile(model: v1.ModelRef, target: str, workflow: str,
                       context: int, output: int, decoder: str,
                       maximum: int | None = None,
                       reasoning_modes: tuple[str, ...] = BOTH_REASONING) \
        -> v1.ExecutionProfile:
    """A process-local profile for one qualification run.

    `output` is the ordinary allowance and `maximum` is the largest this run
    claims. They used to be the same value, which quietly turned "the only
    allowance we probed" into "the maximum this device supports" — the exact
    step that recorded a 2048-token Code ceiling from a run whose largest
    observed reply was 140 tokens. They are separate here so the artifact can
    be checked for evidence AT the maximum before anything is registered.
    """
    values = {
        "model": model.model_dump(),
        "target_profile_id": target,
        "workflow_mode": workflow,
        "qualified_context_tokens": context,
        "default_output_tokens": output,
        "max_output_tokens": maximum if maximum is not None else output,
        "reasoning_modes": list(reasoning_modes),
        "default_reasoning": "disabled" if "disabled" in reasoning_modes else "enabled",
        "decoder_modes": [decoder],
        "qualified_memory_bytes": None,
        # Process-local admission only; the artifact converts this back to a
        # candidate and no product code consumes the artifact.
        "qualification_state": "qualified",
        "eligible": True,
        "evidence_kind": "measured",
        "evidence_ref": "qualification-run:process-local-candidate",
    }
    return v1.ExecutionProfile(
        profile_id=v1.execution_profile_id(values), **values)


def _profiles(model: v1.ModelRef, target: str, context: int,
              outputs: dict[str, int], allow_candidate: bool,
              maxima: dict[str, int] | None = None,
              workflows=WORKFLOWS, reasoning: dict[str, tuple[str, ...]] | None = None) \
        -> tuple[list[v1.ExecutionProfile], bool]:
    """The profile each workflow is qualified under.

    `reasoning` narrows a workflow to the reasoning modes this run claims, so a
    combination that is not offered (for example Documents with reasoning on,
    which exhausts its output allowance) is neither measured nor registered.
    """
    maxima = maxima or {}
    reasoning = reasoning or {}
    selected = []
    for workflow, decoder in workflows:
        maximum = maxima.get(workflow, outputs[workflow])
        modes = tuple(reasoning.get(workflow, BOTH_REASONING))
        match = next((item for item in profiles.PROFILES
                      if item.model == model
                      and item.target_profile_id == target
                      and item.workflow_mode == workflow
                      and item.qualified_context_tokens == context
                      and item.default_output_tokens == outputs[workflow]
                      and item.max_output_tokens == maximum
                      and set(item.reasoning_modes) == set(modes)
                      and item.decoder_modes == [decoder]), None)
        if match is None:
            if not allow_candidate:
                raise RuntimeError(
                    f"no exact registered {workflow} profile; use --candidate "
                    "only for an isolated new-device qualification run")
            match = _temporary_profile(
                model, target, workflow, context, outputs[workflow], decoder,
                maximum, modes)
        selected.append(match)
    transient = any(item not in profiles.PROFILES for item in selected)
    return selected, transient


@contextmanager
def _observe_stream():
    original = runtime.stream_chat
    observed = {"thinking": False, "structured": False, "source_fenced": False}

    def wrapped(messages, **kwargs):
        observed["structured"] |= kwargs.get("response_format") is not None
        joined = "\n".join(str(item.get("content", "")) for item in messages)
        observed["source_fenced"] |= (
            "--- DOCUMENT id=" in joined and "untrusted data" in joined)
        for kind, payload in original(messages, **kwargs):
            if kind == "thinking":
                observed["thinking"] = True
            yield kind, payload

    runtime.stream_chat = wrapped
    try:
        yield observed
    finally:
        runtime.stream_chat = original


def _detail(coordinator: Coordinator, job_id: str) -> dict:
    detail = coordinator.job_detail(job_id)
    if not detail or detail["job"]["state"] != "completed":
        state = (detail or {}).get("job", {}).get("state", "missing")
        attempts = (detail or {}).get("attempts") or []
        error = attempts[-1].get("error_json") if attempts else None
        raise RuntimeError(f"workflow did not complete ({state}): {error or 'no detail'}")
    return detail


def _evidence(profile: v1.ExecutionProfile, detail: dict, output_sha256: str,
              observed: dict, checks: list[str]) -> qualification.RunEvidence:
    attempt = detail["attempts"][-1]
    request = attempt.get("requested_inference") or {}
    actual = attempt.get("actual_profile") or {}
    metrics = attempt.get("metrics") or {}
    reasoning = request.get("reasoning")
    return qualification.RunEvidence(
        reasoning=reasoning,
        decoder=request.get("decoder"),
        requested_profile_id=request.get("profile_id"),
        actual_profile_id=actual.get("profile_id"),
        context_window_tokens=request.get("context_window_tokens"),
        output_allowance_tokens=request.get("output_allowance_tokens"),
        done_reason=metrics.get("done_reason"),
        prompt_tokens=metrics.get("prompt_tokens"),
        output_tokens=metrics.get("output_tokens"),
        total_ms=metrics.get("total_ms"),
        output_sha256=output_sha256,
        thinking_observed=observed["thinking"],
        verifications=[
            "runtime.identity", "profile.identity", "workflow.completed",
            "reasoning.separated" if reasoning == "enabled" else "reasoning.disabled",
            *checks,
        ])


def _submit(coordinator: Coordinator, chat_id: str, text: str, **kwargs) -> str:
    # Stop submit from starting its background thread; qualification invokes
    # the exact same runner synchronously so failures are returned to this CLI.
    with patch("backend.coordinator.server.threading.Thread.start"):
        return coordinator.submit(chat_id, text, **kwargs)


def _chat(coordinator: Coordinator, profile: v1.ExecutionProfile, reasoning: str) \
        -> qualification.RunEvidence:
    db.set_reasoning(coordinator.conn, profile.model.model_id, reasoning == "enabled")
    chat_id = db.create_chat(coordinator.conn, coordinator.workspace_id,
                             f"qualification chat {reasoning}")
    job_id = _submit(
        coordinator, chat_id,
        "Calculate 17 multiplied by 23. State the result as 391 in one short sentence.")
    with _observe_stream() as observed:
        coordinator._run(job_id, chat_id)
    detail = _detail(coordinator, job_id)
    answers = [row["text"] for row in coordinator.chat_messages(chat_id)
               if row["role"] == "assistant"]
    if not answers or "391" not in answers[-1]:
        raise RuntimeError("Chat did not return the required 17 x 23 result")
    return _evidence(profile, detail, _sha(answers[-1]), observed,
                     ["answer.nonempty"])


#: The representative Beta Code workload. A complete C11 program written into
#: an EMPTY file, which is the shape the small `maths.py` edit never exercised:
#: that one measured 140 output tokens against a 2048 allowance and was then
#: recorded as the device maximum. A qualified maximum has to come from a run
#: that actually approaches it.
REPRESENTATIVE_CODE_FILE = "prime_list.c"
REPRESENTATIVE_CODE_WORKLOAD_ID = "prime-list-v1"
REPRESENTATIVE_CODE_REQUEST = (
    "Create a complete C11 program implementing a singly linked list that "
    "stores only prime numbers. Include safe node allocation, primality "
    "checking, insertion at the head and end, deletion of the first matching "
    "value, printing, deterministic prime population, complete list cleanup, "
    "robust input handling, and a usable main demonstration. Return complete "
    "compiling source, not pseudocode.")


def _representative_checks(source_text: str, validator=None) -> list[str]:
    """Require sandbox-bound compile and behaviour proof for generated C."""
    if validator is None:
        raise RuntimeError(
            "the representative Code workload needs compile and behavior "
            "evidence from the qualified no-network sandbox; host execution "
            "is deliberately refused")
    validation = validator(source_text)
    if not isinstance(validation, dict) \
            or validation.get("workload_id") != REPRESENTATIVE_CODE_WORKLOAD_ID \
            or validation.get("source_sha256") != _sha(source_text) \
            or validation.get("compiler") != [
                "cc", "-std=c11", "-Wall", "-Wextra", "-Werror"] \
            or validation.get("sandboxed") is not True \
            or validation.get("network") != "disabled" \
            or validation.get("compiled") is not True \
            or validation.get("behavior_passed") is not True:
        raise RuntimeError(
            "the representative Code workload did not pass bound compile and "
            "behavior checks in the qualified no-network sandbox")
    return ["representative.compile", "representative.behavior"]


def _require_representative_code(default: int, maximum: int,
                                 candidate: bool, enabled: bool,
                                 validator=None, *, proposal_only=False) -> None:
    if proposal_only:
        if maximum != default:
            raise RuntimeError(
                "proposal-only Code qualification cannot claim a larger maximum")
        return
    if (candidate or maximum > default) and not enabled:
        raise RuntimeError(
            "a new Code profile requires --proposal-only-code, or "
            "--representative-code with bound compile and behavior evidence")
    if enabled and validator is None:
        raise RuntimeError(
            "representative Code qualification is unavailable until a qualified "
            "no-network sandbox validator is connected")


def _representative_code(coordinator: Coordinator, profile: v1.ExecutionProfile,
                         reasoning: str, root: Path, validator=None) \
        -> qualification.RunEvidence:
    """The Beta acceptance workload, run through the real strict Code path.

    Deliberately not a Chat turn and not a direct runtime prompt: it goes
    through `code.propose`, so the proposal schema, the path and hash checks
    and the canonical-file protection are all exercised by the same run that
    produces the envelope evidence.
    """
    db.set_reasoning(coordinator.conn, profile.model.model_id, reasoning == "enabled")
    root.mkdir(parents=True)
    source = root / REPRESENTATIVE_CODE_FILE
    source.write_text("", encoding="utf-8")
    repository = coordinator.code.connect(str(root))
    with _observe_stream() as observed:
        proposal = coordinator.code.propose(
            repository["repo_id"], REPRESENTATIVE_CODE_REQUEST,
            [REPRESENTATIVE_CODE_FILE], execution_target="this_device")
    if source.read_text(encoding="utf-8") != "":
        raise RuntimeError("Code qualification changed the canonical source file")
    edits = db.proposal_edit_contents(coordinator.conn, proposal["proposal_id"])
    if len(edits) != 1 or edits[0]["path"] != REPRESENTATIVE_CODE_FILE:
        raise RuntimeError("the representative workload did not return one whole file")
    if not observed["structured"]:
        raise RuntimeError("Code did not use structured decoding")
    representative_checks = _representative_checks(edits[0]["content"], validator)
    payload = json.dumps({"summary": proposal["summary"], "edits": edits},
                         sort_keys=True, separators=(",", ":"))
    return _evidence(
        profile, _detail(coordinator, proposal["job_id"]), _sha(payload), observed,
        ["structured.decoder", "proposal.schema", "canonical.unchanged",
         *representative_checks])


def _code(coordinator: Coordinator, profile: v1.ExecutionProfile, reasoning: str,
          root: Path) -> qualification.RunEvidence:
    db.set_reasoning(coordinator.conn, profile.model.model_id, reasoning == "enabled")
    root.mkdir(parents=True)
    source = root / "maths.py"
    original = "def add(left, right):\n    return left - right\n"
    source.write_text(original, encoding="utf-8")
    repository = coordinator.code.connect(str(root))
    with _observe_stream() as observed:
        proposal = coordinator.code.propose(
            repository["repo_id"],
            "Fix maths.py so add returns the sum by replacing subtraction with addition.",
            ["maths.py"], execution_target="this_device")
    if source.read_text(encoding="utf-8") != original:
        raise RuntimeError("Code qualification changed the canonical source file")
    edits = db.proposal_edit_contents(coordinator.conn, proposal["proposal_id"])
    if len(edits) != 1 or edits[0]["path"] != "maths.py" \
            or "return left + right" not in edits[0]["content"]:
        raise RuntimeError("Code did not produce the required validated replacement")
    if not observed["structured"]:
        raise RuntimeError("Code did not use structured decoding")
    payload = json.dumps({"summary": proposal["summary"], "edits": edits},
                         sort_keys=True, separators=(",", ":"))
    return _evidence(
        profile, _detail(coordinator, proposal["job_id"]), _sha(payload), observed,
        ["structured.decoder", "proposal.schema", "proposal.small_edit",
         "canonical.unchanged"])


def _documents(coordinator: Coordinator, profile: v1.ExecutionProfile,
               reasoning: str) -> qualification.RunEvidence:
    db.set_reasoning(coordinator.conn, profile.model.model_id, reasoning == "enabled")
    chat_id = db.create_chat(coordinator.conn, coordinator.workspace_id,
                             f"qualification documents {reasoning}")
    source = (b"Qualification observation: shaft velocity was 7.9 mm/s. "
              b"The follow-up inspection is due within 24 hours.\n")
    db.add_attachment(
        coordinator.conn, coordinator.attachments_root,
        workspace_id=coordinator.workspace_id, chat_id=chat_id,
        filename="qualification-source.txt", data=source)
    job_id = _submit(
        coordinator, chat_id,
        "Create a concise document. It must preserve these source facts verbatim: "
        "7.9 mm/s and within 24 hours.",
        skill_id=docflow.WRITE_SKILL, output_format=docflow.FORMAT_DOCX,
        doc_workflow=docflow.WORKFLOW_GENERAL)
    with _observe_stream() as observed:
        coordinator._run(job_id, chat_id, docflow.WRITE_SKILL)
    detail = _detail(coordinator, job_id)
    artifacts = db.artifacts_for_chat(
        coordinator.conn, coordinator.workspace_id, chat_id)
    if len(artifacts) != 1 or not artifacts[0]["validation"].get("readable"):
        raise RuntimeError("Documents did not produce one readable artifact")
    artifact = artifacts[0]
    path = db.artifact_path(
        coordinator.conn, db.artifacts_root(coordinator.state_path),
        artifact["artifact_id"], coordinator.workspace_id)
    if path is None or not docgen.validate(path)["readable"]:
        raise RuntimeError("Documents artifact could not be reopened")
    text = "\n".join(docgen.read_text(path)).lower()
    if not all(value in text for value in ("7.9", "mm/s", "24", "hour")):
        raise RuntimeError("Documents artifact did not preserve the required facts")
    if not observed["structured"] or not observed["source_fenced"]:
        raise RuntimeError("Documents did not preserve structured decoding and source fencing")
    return _evidence(
        profile, detail, artifact["sha256"], observed,
        ["structured.decoder", "document.schema", "document.readable",
         "document.required_facts", "source.fenced"])


def verified_model_files(entry: models.Entry, directory: Path) -> list[dict]:
    """Hash every catalogue file in `directory`; refuse any mismatch."""
    files = []
    for item in entry.files:
        path = (directory / item.name).resolve()
        if not path.is_file() or path.stat().st_size != item.size:
            raise RuntimeError(f"{item.name} is missing or has the wrong size")
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != item.sha256:
            raise RuntimeError(f"{item.name} does not match its pinned SHA-256")
        files.append({"role": item.role, "name": item.name, "path": str(path),
                      "size": item.size, "sha256": item.sha256})
    return files


def managed_settings(args) -> engine.LaunchSettings:
    return engine.LaunchSettings(
        context_tokens=args.context_tokens, slots=1, gpu_layers="all",
        cache_type_k="f16", cache_type_v="f16", flash_attention="auto")


def _managed_observation(args):
    selection = engine.select(environ={}, frozen=False,
                              roots=[args.engine_root] if args.engine_root else None)
    if selection.mode != engine.MANAGED or not selection.usable:
        raise RuntimeError("the managed engine is missing or modified: "
                           + "; ".join(selection.problems or ["not fetched"]))
    if args.expect_runtime_version != selection.runtime_version:
        raise RuntimeError(f"engine drift: expected {args.expect_runtime_version}, "
                           f"found {selection.runtime_version}")
    entry = models.BY_ID[args.model or models.MANAGED_MAIN]
    files = verified_model_files(entry, args.model_dir)
    model = v1.ModelRef(model_id=entry.id, manifest_sha256=entry.manifest_sha256,
                        runtime=engine.LLAMA_CPP, runtime_version=selection.runtime_version)
    return selection, entry, files, model


def qualify(args, *, representative_validator=None) \
        -> qualification.QualificationArtifact:
    managed = getattr(args, "engine", "ollama") == "managed"
    if managed:
        selection, entry, managed_files, observed_model = _managed_observation(args)
        facts = device.hardware(engine_devices=engine.list_devices(selection))
        tiers = [tier.tier_id for tier in profiles.matching_tiers(facts)]
        target = args.target_profile_id or (tiers[0] if tiers else None)
    else:
        state = runtime.probe()
        if not state.get("reachable"):
            raise RuntimeError(f"Ollama is unavailable at {runtime.HOST}: {state.get('error')}")
        if state.get("server_version") != args.expect_runtime_version:
            raise RuntimeError(
                f"runtime version drift: expected {args.expect_runtime_version}, "
                f"observed {state.get('server_version') or 'unknown'}")
        digest = (state.get("digests") or {}).get(runtime.MODEL)
        if digest != profiles.MODEL_DIGEST or not models.digest_eligible(runtime.MODEL, digest):
            raise RuntimeError("the installed model digest does not match the qualified manifest")
        observed_model = v1.ModelRef(
            model_id=runtime.MODEL, manifest_sha256=digest,
            runtime=profiles.RUNTIME, runtime_version=state["server_version"])
        target = args.target_profile_id or device.qualified_target_profile()
    if not target:
        raise RuntimeError("this device has no target identity; pass --target-profile-id")
    outputs = {
        profiles.CHAT: args.chat_output_tokens,
        profiles.CODE: args.code_output_tokens,
        profiles.DOCUMENTS: args.documents_output_tokens,
    }
    maxima = {
        profiles.CHAT: args.chat_max_output_tokens or args.chat_output_tokens,
        profiles.CODE: args.code_max_output_tokens or args.code_output_tokens,
        profiles.DOCUMENTS: (args.documents_max_output_tokens
                             or args.documents_output_tokens),
    }
    selected_workflows = tuple(
        item for item in WORKFLOWS
        if not args.workflows or item[0] in args.workflows)
    reasoning = {workflow: tuple(sorted(set(value.split(","))))
                 for workflow, value in (
                     (profiles.CHAT, args.chat_reasoning),
                     (profiles.CODE, args.code_reasoning),
                     (profiles.DOCUMENTS, args.documents_reasoning))}
    selected, transient = _profiles(
        observed_model, target, args.context_tokens, outputs, args.candidate,
        maxima, selected_workflows, reasoning)
    code_profile = next(
        (item for item in selected if item.workflow_mode == profiles.CODE), None)
    if code_profile is not None:
        _require_representative_code(
            outputs[profiles.CODE], maxima[profiles.CODE],
            code_profile not in profiles.PROFILES, args.representative_code,
            representative_validator,
            proposal_only=args.proposal_only_code)
    original_registry = profiles.PROFILES
    if transient:
        profiles.PROFILES = tuple(selected) + original_registry
    try:
        with tempfile.TemporaryDirectory(prefix="refinix-qualification-") as directory:
            temporary = Path(directory)
            coordinator = Coordinator(temporary / "state" / "coordinator.sqlite3")
            coordinator.target_profile_id = target
            coordinator.preflight = lambda relationship=None: None
            backend = None
            if managed:
                # Absolute paths: the files stay where they were verified.
                db.record_model_install(
                    coordinator.conn, model_id=entry.id,
                    manifest_sha256=entry.manifest_sha256, engine=engine.LLAMA_CPP,
                    files=managed_files, source="qualification run")
                backend = local_engine.LocalEngine(
                    selection, temporary / "state", registry=coordinator.installed_models,
                    settings_for=lambda _model: managed_settings(args))
                runtime.configure_managed(backend)
            by_workflow = {item.workflow_mode: item for item in selected}
            results = {workflow: [] for workflow, _decoder in selected_workflows}
            def claimed(workflow, reasoning):
                return workflow in by_workflow \
                    and reasoning in by_workflow[workflow].reasoning_modes

            try:
                for reasoning in ("disabled", "enabled"):
                    if claimed(profiles.CHAT, reasoning):
                        results[profiles.CHAT].append(
                            _chat(coordinator, by_workflow[profiles.CHAT], reasoning))
                    # One Code run per reasoning mode: the artifact contract
                    # allows exactly one evidence entry per reasoning/decoder
                    # pair, and requires it to have been taken AT the claimed
                    # maximum. The representative workload REPLACES the small
                    # edit rather than joining it, because a claimed maximum
                    # has to be justified by the run that approaches it.
                    if claimed(profiles.CODE, reasoning):
                        if args.representative_code:
                            evidence = _representative_code(
                                coordinator, by_workflow[profiles.CODE], reasoning,
                                temporary / f"code-{reasoning}",
                                validator=representative_validator)
                        else:
                            evidence = _code(
                                coordinator, by_workflow[profiles.CODE], reasoning,
                                temporary / f"code-{reasoning}")
                        results[profiles.CODE].append(evidence)
                    if claimed(profiles.DOCUMENTS, reasoning):
                        results[profiles.DOCUMENTS].append(
                            _documents(coordinator, by_workflow[profiles.DOCUMENTS], reasoning))
            finally:
                if backend is not None:
                    backend.stop()
                    runtime.configure_managed(None)
                coordinator.conn.close()
    finally:
        profiles.PROFILES = original_registry

    observed_device = device.describe()
    if observed_device["os_family"] not in ("macos", "windows", "linux") \
            or not observed_device["release"] or not observed_device["machine"]:
        raise RuntimeError("the OS family, version and architecture must all be observable")
    workflows = [qualification.WorkflowQualification(
        profile=_candidate(profile), result="passed",
        evidence=results[profile.workflow_mode]) for profile in selected]
    return qualification.QualificationArtifact(
        artifact_version=qualification.ARTIFACT_VERSION,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        device=qualification.DeviceObservation(
            os_family=observed_device["os_family"],
            os_release=observed_device["release"],
            architecture=observed_device["machine"],
            target_profile_id=target),
        observed_model=observed_model, result="passed", release_accepted=False,
        workflows=workflows)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--validate", type=Path,
                       help="validate an existing artifact and exit")
    value.add_argument("--output", type=Path,
                       help="new artifact path; an existing file is never replaced")
    value.add_argument("--target-profile-id")
    value.add_argument("--engine", choices=["ollama", "managed"], default="ollama",
                       help="qualify the developer Ollama baseline or the managed engine")
    value.add_argument("--model-dir", type=Path,
                       help="managed engine: folder holding the catalogue files")
    value.add_argument("--model", help="managed engine: catalogue id (default: main model)")
    value.add_argument("--engine-root", type=Path,
                       help="managed engine: fetched engine folder (default: this lane)")
    value.add_argument("--expect-runtime-version")
    value.add_argument("--candidate", action="store_true",
                       help="admit unregistered profiles only inside this isolated run")
    value.add_argument("--workflow", dest="workflows", action="append",
                       choices=[workflow for workflow, _decoder in WORKFLOWS],
                       help="workflow to qualify; repeat to select more than one")
    value.add_argument("--context-tokens", type=int, default=8192)
    value.add_argument("--chat-output-tokens", type=int, default=2048)
    value.add_argument("--code-output-tokens", type=int, default=2048)
    value.add_argument("--documents-output-tokens", type=int, default=3072)
    # The ordinary allowance and the largest claimed allowance are separate.
    # Leaving a maximum unset keeps it equal to the allowance, which is the
    # old behaviour and remains the conservative default.
    value.add_argument("--chat-max-output-tokens", type=int, default=None)
    value.add_argument("--code-max-output-tokens", type=int, default=None,
                       help="largest Code allowance this run claims; must be "
                            "exercised by a representative workload")
    value.add_argument("--documents-max-output-tokens", type=int, default=None)
    # Which reasoning modes each workflow claims. Only claimed modes are run
    # and recorded; an unclaimed mode stays unavailable for that workflow.
    for name in ("chat", "code", "documents"):
        value.add_argument(f"--{name}-reasoning", default="disabled,enabled",
                           choices=["disabled,enabled", "disabled", "enabled"])
    code_mode = value.add_mutually_exclusive_group()
    code_mode.add_argument(
        "--representative-code", action="store_true",
        help="run the complete-program Code workload; evidence is refused "
             "unless a qualified no-network sandbox supplies bound compile "
             "and behavior results")
    code_mode.add_argument(
        "--proposal-only-code", action="store_true",
        help="qualify only the fixed small-edit proposal at the unchanged "
             "default limit; this supplies no sandbox or full-program evidence")
    return value


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.validate:
            artifact = qualification.read(args.validate)
            print(json.dumps({
                "artifact": str(args.validate), "result": artifact.result,
                "release_accepted": artifact.release_accepted,
                "target_profile_id": artifact.device.target_profile_id,
                "runtime_version": artifact.observed_model.runtime_version,
                "workflows": [item.profile.workflow_mode for item in artifact.workflows],
            }, indent=2))
            return 0
        if not args.output or not args.expect_runtime_version:
            raise RuntimeError(
                "a qualification run requires --output and --expect-runtime-version")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        artifact = qualify(args)
        qualification.write(args.output, artifact)
        print(json.dumps({
            "artifact": str(args.output), "result": artifact.result,
            "release_accepted": artifact.release_accepted,
            "profile_ids": [item.profile.profile_id for item in artifact.workflows],
        }, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns one safe reason.
        print(f"qualification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
