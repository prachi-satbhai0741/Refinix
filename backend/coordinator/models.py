"""Which models Refinix supports, and what is actually true of each one here.

Until now the model list was whatever the local runtime happened to report.
That answers "what is installed" and nothing else, so the product could not
tell a person that a model it supports is *missing* — only that a name was
absent from a list — and it could not distinguish a model whose provenance
Refinix has recorded from one someone pulled by hand.

`docs/PROJECT.md` 5 and `docs/model-catalog.md` ask for four separable facts,
and this module is where they live:

* **installed** — the local runtime lists it now;
* **supported but absent** — Refinix records a manifest for it and it is not
  installed here;
* **unlisted** — installed here, with no recorded provenance. 12.4's rule is
  explicit: *installed runtime inventory does not automatically become a
  trusted supported catalogue entry*, so such a model is usable and is plainly
  labelled as unverified rather than quietly promoted;
* **unavailable** — the runtime did not answer, so nothing about any model is
  known. Never reported as "none installed".

Whether Refinix *vouches* for a model is a separate answer, carried by
`provenance`, so an installed model with no recorded source stays usable and
plainly labelled rather than being quietly promoted or silently refused.

**The catalogue is small on purpose.** It holds the one model whose source,
licence, manifest digest, layers and runtime floor were recorded from the
artifact itself. Everything else in `docs/model-catalog.md` is a research
candidate with unresolved provenance, and `model-catalog.md` says those are
not supported download offers — so they are not offered here. A short honest
catalogue is the requirement; a long speculative one would be the failure.

**Nothing in this module downloads, installs, removes or calls a model.** A
missing model produces the exact command the person can run themselves, the
same way the startup sequence already does. Removal is likewise the runtime's
own operation: what Refinix owns is telling the person what a removal would
break before they do it, and never deleting a chat because a model went away.

**A self-test belongs to the exact manifest that passed it.** A result is
stored with the digest it was observed against, so replacing a model's bytes
under the same tag invalidates it rather than inheriting a pass.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

# Workflow scopes a model can be selected for. The same strings `MODEL_DEFAULTS`
# uses, so a catalogue entry and a selection cannot drift apart.
CHAT = "chat"
CODE = "code"
DOCUMENTS_GENERATE = "documents.generate"
DOCUMENTS_OCR = "documents.ocr"

# What the interface may say about one model on this computer.
INSTALLED = "installed"
ABSENT = "absent"
UNLISTED = "unlisted"
UNAVAILABLE = "unavailable"

# Evidence strength, kept as separate words because `docs/model-catalog.md`
# requires measured, documentation-only and unverified to stay distinguishable.
VERIFIED = "verified"
UNVERIFIED = "unverified"
UNRESOLVED = "unresolved"
MISMATCH = "mismatch"
NOT_OBSERVED = "not_observed"


@dataclass(frozen=True)
class ModelFile:
    """One file of a managed-engine model, pinned by size and SHA-256."""

    role: str            # "weights" | "projector"
    name: str
    size: int
    sha256: str
    url: str

    def as_dict(self) -> dict:
        return {"role": self.role, "name": self.name, "size": self.size,
                "sha256": self.sha256, "url": self.url}


def manifest_digest(model_id: str, revision: str | None,
                    files: tuple[ModelFile, ...]) -> str:
    """The Refinix model-manifest identity: exact files, not a name.

    Canonical JSON (sorted keys, no whitespace) of the model id, its pinned
    source revision and every file's role, name, size and SHA-256. The GGUF
    hashes cover the embedded tokenizer and chat template; a template override
    would have to join this list.
    """
    body = {"model_id": model_id, "revision": revision,
            "files": [{"role": f.role, "name": f.name, "size": f.size,
                       "sha256": f.sha256} for f in files]}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Entry:
    """One curated model, with the provenance that was actually recorded.

    Every field here was read from the artifact or its manifest and written
    down in `docs/model-catalog.md`. A field nobody observed is `None`; it is
    never filled in from a model's name, its family or its upstream project.
    """

    id: str
    role: str
    scopes: tuple[str, ...]
    source: str
    licence: str | None
    manifest_sha256: str | None
    format: str | None
    parameters: str | None
    storage_bytes: int | None
    minimum_runtime: str | None
    evidence: str
    evidence_state: str = VERIFIED
    setup_command: str = ""
    # Which engine can run these bytes. The developer baseline is an Ollama
    # registry artifact; the managed engine loads pinned upstream GGUF files.
    engine: str = "ollama"
    files: tuple[ModelFile, ...] = ()
    revision: str | None = None
    display_name: str | None = None
    sampling: tuple[tuple[str, float], ...] = ()

    def as_dict(self) -> dict:
        return {
            "id": self.id, "role": self.role, "scopes": list(self.scopes),
            "source": self.source, "licence": self.licence,
            "manifest_sha256": self.manifest_sha256, "format": self.format,
            "parameters": self.parameters, "storage_bytes": self.storage_bytes,
            "minimum_runtime": self.minimum_runtime,
            "evidence": self.evidence, "evidence_state": self.evidence_state,
            "setup_command": self.setup_command or None,
            "engine": self.engine, "revision": self.revision,
            "display_name": self.display_name or self.id,
            "files": [f.as_dict() for f in self.files],
            "download_bytes": sum(f.size for f in self.files) or None,
        }


# The managed engine's first model: the same Qwen3.5-4B family as the baseline,
# as pinned upstream-format GGUF files. Upstream llama.cpp b11390 refuses the
# Ollama registry blob (`qwen35.rope.dimension_sections has wrong array length`,
# observed 2026-10-04), so the managed engine cannot reuse it. No official Qwen
# or ggml-org GGUF exists; these are the quantizer's files for the official
# Apache-2.0 weights, pinned by repository commit, size and SHA-256 read from
# the Hugging Face API on 2026-10-04.
MANAGED_MAIN_REVISION = "e87f176479d0855a907a41277aca2f8ee7a09523"
_MANAGED_MAIN_BASE = ("https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/"
                      + MANAGED_MAIN_REVISION + "/")
MANAGED_MAIN_FILES = (
    ModelFile("weights", "Qwen3.5-4B-Q4_K_M.gguf", 2_740_937_888,
              "00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4",
              _MANAGED_MAIN_BASE + "Qwen3.5-4B-Q4_K_M.gguf"),
    ModelFile("projector", "mmproj-F16.gguf", 672_423_616,
              "cd88edcf8d031894960bb0c9c5b9b7e1fea6ebee02b9f7ce925a00d12891f864",
              _MANAGED_MAIN_BASE + "mmproj-F16.gguf"),
)
MANAGED_MAIN = "qwen3.5-4b-q4_k_m"

# The supported catalogue. One artifact per engine, each inspected.
CATALOGUE: tuple[Entry, ...] = (
    Entry(
        id="qwen3.5:4b-q4_K_M",
        role="Main engine",
        scopes=(CHAT, CODE, DOCUMENTS_GENERATE),
        source="registry.ollama.ai/library/qwen3.5, tag 4b-q4_K_M",
        licence="Apache-2.0 (licence layer present in the manifest)",
        manifest_sha256=
        "2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd",
        format="GGUF, Q4_K_M",
        parameters="4.7B reported by the image config",
        storage_bytes=3_389_971_840,
        minimum_runtime="Ollama >= 0.17.1",
        evidence=("Integrity verified from the manifest and blobs, with bounded "
                  "inference observed on the qualification devices. That is a "
                  "fixed-prompt smoke check, not a scored quality result."),
        evidence_state=VERIFIED,
        setup_command="ollama pull qwen3.5:4b-q4_K_M",
    ),
    Entry(
        id=MANAGED_MAIN,
        display_name="Qwen3.5 4B (Q4_K_M)",
        role="Main engine",
        scopes=(CHAT, CODE, DOCUMENTS_GENERATE),
        source=("huggingface.co/unsloth/Qwen3.5-4B-GGUF at " + MANAGED_MAIN_REVISION
                + " — a quantization of Qwen/Qwen3.5-4B at "
                "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"),
        licence="Apache-2.0 (base model LICENSE; the quantization repository "
                "declares Apache-2.0)",
        manifest_sha256=manifest_digest(MANAGED_MAIN, MANAGED_MAIN_REVISION,
                                        MANAGED_MAIN_FILES),
        format="GGUF Q4_K_M weights with an F16 vision projector",
        parameters="4B (upstream model card)",
        storage_bytes=sum(f.size for f in MANAGED_MAIN_FILES),
        minimum_runtime="Refinix engine (llama.cpp b11390, pinned)",
        evidence=("Integrity verified: both files were downloaded from the pinned "
                  "revision on 2026-10-04 and re-hashed locally, matching the "
                  "published sizes and SHA-256. Every later download or import is "
                  "re-hashed the same way. Third-party quantization of the official "
                  "weights, because no official GGUF is published. Workflow "
                  "qualification is recorded separately per engine build and "
                  "hardware tier."),
        evidence_state=VERIFIED,
        engine="llama.cpp",
        files=MANAGED_MAIN_FILES,
        revision=MANAGED_MAIN_REVISION,
        # The sampling the baseline ran with (Ollama params layer for this
        # model), so engine parity compares the same decoding.
        sampling=(("temperature", 1.0), ("top_k", 20), ("top_p", 0.95),
                  ("presence_penalty", 1.5)),
    ),
)

# The defaults the managed engine starts with, per workflow scope.
MANAGED_DEFAULTS = {CHAT: MANAGED_MAIN, CODE: MANAGED_MAIN,
                    DOCUMENTS_GENERATE: MANAGED_MAIN, DOCUMENTS_OCR: MANAGED_MAIN}


def entries_for(engine_kind: str) -> tuple[Entry, ...]:
    """Catalogue entries the given engine can run."""
    return tuple(entry for entry in CATALOGUE if entry.engine == engine_kind)

# Models Refinix has looked at and deliberately does **not** offer. Used only
# to annotate one that is already installed, so the interface can say why it is
# not a supported entry instead of saying nothing. Offering these as downloads
# is what `docs/model-catalog.md` forbids.
NOTED: dict[str, str] = {
    "MedAIBase/PaddleOCR-VL:0.9b":
        "Installed candidate only. Who published this conversion, from what, "
        "and under which licence is unresolved, and the manifest carries no "
        "licence layer — so Refinix does not list it as a supported model. It "
        "was also observed to declare no image capability on the device that "
        "inspected it.",
}

BY_ID = {entry.id: entry for entry in CATALOGUE}


@dataclass(frozen=True)
class SelfTest:
    """The smallest representative check for one capability.

    Small on purpose. A self-test answers "can this model do the smallest real
    version of this job on this computer", which is the question setup has to
    pass before a capability is called ready. It is not a quality benchmark and
    must never be presented as one.
    """

    scope: str
    label: str
    needs_model: bool
    needs_vision: bool = False
    writes_artifact: bool = False
    caveat: str = ("A self-test shows the capability ran once here. It says "
                   "nothing about the quality of any answer.")


# The Chat self-test's premise, and the two numbers it turns on.
#
# Every fact it needs is in the prompt. That is the point: a model that fails
# this failed at holding a relation straight, not at knowing something, and a
# domain question would leave those two indistinguishable. It replaces "what is
# 2 + 2?", which a model passed by answering at all — the reply was only
# checked for being non-empty, so a model that writes fluently and reverses
# every comparison it is asked about passed Chat qualification.
CHAT_CHECK_SMALLER = "2.4"
CHAT_CHECK_LARGER = "3.1"
CHAT_CHECK_PROMPT = (
    "Use only the facts in this message.\n"
    f"Available capacity is {CHAT_CHECK_SMALLER}.\n"
    f"Required capacity is {CHAT_CHECK_LARGER}.\n"
    "The operation is unsafe when available capacity is below required "
    "capacity.\n"
    "Reply with one line and nothing else, in this form:\n"
    "<safe or unsafe>; smaller number: <the smaller of the two numbers>")

# The whole reply, or it is not an answer to this question.
#
# `fullmatch`, and no prose fallback. Found in review: searching for a verdict
# token and a number independently passed "not unsafe; smaller number: 2.4" —
# the negation sits outside both patterns — and passed a reply that gave the
# right answer and then contradicted itself. Every other capability's self-test
# already requires an exact shape from the decoder; accepting loose prose here
# bought tolerance for a model that rambles at the cost of the evidence the
# check exists to produce.
#
# A reply in the wrong shape and a reply with the comparison backwards are
# reported as different failures, because they are: one model could not follow
# a one-line instruction, the other could not hold a relation.
_STRICT_REPLY = re.compile(
    r"(unsafe|safe)\s*;\s*smaller number\s*:\s*(\d+(?:\.\d+)?)\.?", re.I)


def chat_relation_failure(reply: str) -> str | None:
    """Why a reply to `CHAT_CHECK_PROMPT` fails, or None if it holds up.

    Returns the sentence a person reads in the self-test result, so it says
    what the model actually did rather than that a check failed.
    """
    text = " ".join((reply or "").split())
    if not text:
        return "answered with nothing visible"
    answer = _STRICT_REPLY.fullmatch(text)
    if answer is None:
        return ("did not answer in the single line it was asked for, so what "
                "it concluded could not be read back without guessing")
    verdict, smaller = answer.group(1).casefold(), answer.group(2)
    if verdict == "safe":
        return (f"called the operation safe although the available capacity "
                f"({CHAT_CHECK_SMALLER}) is below the required capacity "
                f"({CHAT_CHECK_LARGER})")
    if smaller != CHAT_CHECK_SMALLER:
        return (f"named {smaller} as the smaller number when "
                f"{CHAT_CHECK_SMALLER} is")
    return None


SELFTESTS: dict[str, SelfTest] = {
    CHAT: SelfTest(CHAT, "Apply one supplied rule to two numbers",
                   needs_model=True),
    CODE: SelfTest(CODE, "Propose one small change", needs_model=True),
    DOCUMENTS_GENERATE: SelfTest(
        DOCUMENTS_GENERATE, "Write and reopen a Word document",
        needs_model=True, writes_artifact=True),
    DOCUMENTS_OCR: SelfTest(
        DOCUMENTS_OCR, "Read one rendered page", needs_model=True,
        needs_vision=True),
}

PASSED = "passed"
FAILED = "failed"
NOT_RUN = "not_run"

class SelfTestError(RuntimeError):
    """A self-test could not run. Never recorded as a failure of the model."""


def entry_for(model: str) -> Entry | None:
    return BY_ID.get(model)


def provenance(model: str) -> dict:
    """What Refinix records about one model id, whatever its state.

    Three answers, and they are different claims: a recorded manifest, a
    recorded refusal to vouch for it, or nothing recorded at all.
    """
    entry = BY_ID.get(model)
    if entry is not None:
        return {"known": True, **entry.as_dict()}
    if model in NOTED:
        return {"known": False, "id": model, "evidence_state": UNRESOLVED,
                "note": NOTED[model]}
    return {"known": False, "id": model, "evidence_state": UNVERIFIED,
            "note": ("Refinix has no recorded source, licence or manifest for "
                     "this model. It is available because the local engine "
                     "reports it, not because Refinix verified it.")}


def integrity(model: str, digest: str | None) -> dict:
    """Compare observed bytes with the catalogue without trusting the tag."""
    entry = BY_ID.get(model)
    expected = entry.manifest_sha256 if entry else None
    if expected is None:
        return {"state": UNVERIFIED, "expected": None, "observed": digest,
                "eligible": bool(digest)}
    if not digest:
        return {"state": NOT_OBSERVED, "expected": expected, "observed": None,
                "eligible": False}
    matched = digest == expected
    return {"state": VERIFIED if matched else MISMATCH,
            "expected": expected, "observed": digest, "eligible": matched}


def digest_eligible(model: str, digest: str | None) -> bool:
    """Known models must match their recorded manifest; unlisted models do not."""
    return integrity(model, digest)["eligible"]


def lifecycle_state(model: str, *, installed_here: bool, installed_elsewhere: bool,
                    runtime_reachable: bool) -> str:
    """Which of the four states one model is in, from observations only.

    The state answers "is it here", and `provenance` separately answers "does
    Refinix vouch for it". Keeping them apart is what lets a model that is
    installed but unverified stay usable and plainly labelled, and a model
    that is simply not installed say so whether or not Refinix records a
    manifest for it.
    """
    if installed_here or installed_elsewhere:
        return INSTALLED if model in BY_ID else UNLISTED
    if not runtime_reachable:
        # The engine did not answer, so "not installed" is not a thing anyone
        # observed. Absence is unknown, not established.
        return UNAVAILABLE
    return ABSENT


def setup_action(model: str) -> dict | None:
    """What a person can do themselves to install a supported model.

    A command to run, never a download Refinix starts. `docs/PROJECT.md` 21.1
    forbids a runtime model download, and this is the honest alternative: the
    exact step, in the open, performed by the person.
    """
    entry = BY_ID.get(model)
    if entry is not None and entry.files:
        # Refinix's own engine: downloaded by Refinix only when the person
        # confirms, after seeing what, from where and how much; or imported
        # from files they already have.
        size = sum(f.size for f in entry.files)
        return {"kind": "download", "label": "Download",
                "model": entry.id, "download_bytes": size,
                "detail": (f"About {size / 1024 ** 3:.1f} GB from {entry.source}, "
                           "checked against its pinned SHA-256. Or import the same "
                           "files from this computer.")}
    if entry is None or not entry.setup_command:
        return None
    return {"kind": "command", "label": "Install it yourself",
            "command": entry.setup_command,
            "detail": (f"Downloads about "
                       f"{entry.storage_bytes // (1024 ** 3)} GB from "
                       f"{entry.source}. Refinix does not start downloads on "
                       "its own.")}


def removal_impact(model: str, *, selections: dict, enabled: dict) -> dict:
    """What would stop working if this model were no longer available.

    Shown before a removal rather than discovered after one. Refinix never
    deletes anything itself here: chats, artifacts and history belong to the
    workspace and survive any model change, which is the fact this report
    states explicitly so nobody has to guess.
    """
    affected = sorted(scope for scope, chosen in selections.items()
                      if chosen == model)
    return {
        "model": model,
        "selected_for": affected,
        "blocked_capabilities": affected,
        "preserved": ["conversations", "saved messages", "generated artifacts",
                      "approvals", "job history"],
        "detail": (
            ("Removing it would leave "
             + ", ".join(affected)
             + " with no selected model until another is chosen. ")
            if affected else
            "No workflow is currently set to use it. ")
        + "Nothing you have written or generated is deleted by removing a "
          "model; conversations, artifacts and history are kept.",
        # The runtime owns the model store, so removal is its operation and is
        # named rather than performed. The same rule as installation.
        "command": f"ollama rm {model}" if model else None,
        "enabled": bool(enabled.get(model, True)),
    }


def run_selftest(scope: str, model: str, *, generate=None, artifact=None,
                 capabilities=None, vision_capability: str = "vision") -> dict:
    """Run one capability's smallest representative check.

    The callables are supplied by the caller that owns the runtime and the
    document writer, so this stays testable without either. A check that could
    not run at all is `unavailable` with its reason — never `failed`, which
    would blame the model for a missing prerequisite.
    """
    check = SELFTESTS.get(scope)
    if check is None:
        raise SelfTestError(f"there is no self-test for {scope}")
    if check.needs_vision:
        if capabilities is None:
            raise SelfTestError(
                f"The engine did not report what {model} can do, so Refinix "
                "cannot check that it accepts page images.")
        if vision_capability not in capabilities:
            return {"scope": scope, "model": model, "state": FAILED,
                    "detail": (f"{model} does not accept page images on this "
                               "computer, so it cannot read a scan.")}
    if generate is None:
        raise SelfTestError("the local engine was not available to ask.")

    def failed(detail: str) -> dict:
        return {"scope": scope, "model": model, "state": FAILED,
                "detail": detail}

    try:
        if scope == CHAT:
            reply = generate(
                model, [{"role": "user", "content": CHAT_CHECK_PROMPT}],
                scope=scope, num_predict=128)
            wrong = chat_relation_failure(reply)
            if wrong:
                return failed(f"{model} {wrong}. A model that reverses a "
                              "supplied relation can write a fluent technical "
                              "answer that is backwards, so Chat is not "
                              "self-tested on this computer.")
        elif scope == CODE:
            from backend.coordinator import codeflow
            before = "before\n"
            selected = [{"path": "selftest.txt", "text": before,
                         "sha256": hashlib.sha256(before.encode()).hexdigest()}]
            reply = generate(
                model,
                codeflow.build_messages(
                    "Replace the entire file text with the single line: after",
                    selected),
                scope=scope,
                response_format=codeflow.PROPOSAL_SCHEMA, num_predict=512)
            try:
                proposal = codeflow.parse_proposal(reply, selected)
            except codeflow.ProposalError as exc:
                return failed(f"The model did not produce a valid Code proposal: {exc}")
            if not proposal["edits"]:
                return failed("The model produced no edit for the selected test file.")
        elif scope == DOCUMENTS_GENERATE:
            from backend.coordinator import docflow
            reply = generate(
                model,
                docflow.general_document_messages(
                    "Write a one-section document with one short paragraph about Refinix.",
                    []),
                scope=scope,
                response_format=docflow.GENERAL_DOCUMENT_FORMAT,
                num_predict=512)
            try:
                document = docflow.parse_general_document(reply)
            except docflow.WorkflowError as exc:
                return failed(f"The model did not produce a valid document: {exc}")
            if artifact is None:
                raise SelfTestError("no document writer was available to check.")
            written = artifact(title=document["title"],
                               blocks=docflow.general_blocks(document, []))
            if not written.get("valid"):
                return failed(written.get("detail") or
                              "A Word document could not be written and reopened here.")
        elif scope == DOCUMENTS_OCR:
            from backend.coordinator import ocr
            reply = generate(model, ocr.page_messages("image/png"),
                             scope=scope,
                             images=[ocr.selftest_image()],
                             response_format=ocr.PAGE_SCHEMA,
                             num_predict=ocr.PAGE_NUM_PREDICT)
            try:
                reading = ocr.parse_page_reply(reply)
            except ocr.OcrError as exc:
                return failed(f"The model did not produce a valid page reading: {exc}")
            if "refinix" not in reading.lower():
                return failed("The model did not read REFINIX from the test page image.")
    except SelfTestError:
        raise
    except Exception as exc:                                # noqa: BLE001
        raise SelfTestError(str(exc)) from exc
    return {"scope": scope, "model": model, "state": PASSED,
            "detail": f"{check.label} succeeded on this computer. {check.caveat}"}


def selftest_view(records: list[dict], *, model: str,
                  digest: str | None) -> dict:
    """One model's stored self-test results, against what is installed now.

    Three outcomes, kept apart because they are three different claims:

    * **current** — the result was observed against exactly the bytes that are
      installed now. Only this may make a capability look ready.
    * **superseded** — both digests are known and they differ, so the result
      describes a model that is no longer here.
    * **neither** — `digest` could not be observed at all, because the engine
      did not answer or the model is no longer installed. A pass then proves
      nothing about the present, and calling it current would be the exact
      fabrication the rest of this module avoids: it is reported as a pass
      that cannot be confirmed here.

    The record itself is always kept. Deleting it would lose the fact that a
    check was once run, which is true regardless of what is installed today.
    """
    shown = {}
    for record in records:
        if record["model"] != model:
            continue
        recorded = record.get("digest")
        matches = bool(digest and recorded and recorded == digest)
        shown[record["scope"]] = {
            "scope": record["scope"],
            "state": record["state"],
            "detail": record["detail"],
            "ran_at": record["ran_at"],
            "runtime_version": record.get("runtime_version"),
            "superseded": bool(digest and recorded and recorded != digest),
            # A pass is current only when it was observed against the bytes
            # installed now. An unobservable digest is not a match.
            "current": record["state"] == PASSED and matches,
        }
    for scope, check in SELFTESTS.items():
        shown.setdefault(scope, {
            "scope": scope, "state": NOT_RUN,
            "detail": f"{check.label} has not been run on this computer yet.",
            "ran_at": None, "runtime_version": None,
            "superseded": False, "current": False})
    return shown
