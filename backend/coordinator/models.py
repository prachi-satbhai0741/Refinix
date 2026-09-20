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

    def as_dict(self) -> dict:
        return {
            "id": self.id, "role": self.role, "scopes": list(self.scopes),
            "source": self.source, "licence": self.licence,
            "manifest_sha256": self.manifest_sha256, "format": self.format,
            "parameters": self.parameters, "storage_bytes": self.storage_bytes,
            "minimum_runtime": self.minimum_runtime,
            "evidence": self.evidence, "evidence_state": self.evidence_state,
            "setup_command": self.setup_command or None,
        }


# The supported catalogue. One entry, because one artifact has been inspected.
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
)

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


SELFTESTS: dict[str, SelfTest] = {
    CHAT: SelfTest(CHAT, "Answer one short question", needs_model=True),
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
                model, [{"role": "user", "content":
                         "Answer this short question in one sentence: what is 2 + 2?"}],
                num_predict=64)
            if not (reply or "").strip():
                return failed(f"{model} answered with nothing visible, so this "
                              "capability is not usable yet.")
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
