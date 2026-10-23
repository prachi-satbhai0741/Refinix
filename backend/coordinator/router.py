"""Automatic local task-to-model assignment.

The coordinator is the orchestrator: it reads what the task needs, removes
every installed model that cannot do it, and ranks the rest into an ordered
list — the best suitable model first, then the next. Deterministic rules are
enough for these classes of task (`docs/PROJECT.md` 7.0, 9.1); no model is
asked to choose a model, and nothing here can change a permission.

Any compatible installed model on either runtime takes part. Nothing here
knows a model by name: a model is described only by what was recorded about
it and what its runtime reports.

Task needs come from the workflow (Chat, Code, Documents, page reading), the
attachments and a few constrained prompt labels: code-like text,
reasoning-heavy wording, an input too long for the default window, and — for
a picture sent with Chat — whether the question is about the text in it or
about what it shows.

Two kinds of fact decide:

* **Hard requirements** remove a model: no profile for this workflow and
  decoder here, no image input when the step must look at an image, or an
  actual reason it cannot run (locality, integrity, switched off).
* **A documented task limitation** removes a model from Auto for the tasks it
  is documented not to do: an explicit, cited statement such as "for document
  OCR only". Missing evidence is never a limitation; a model nobody described
  is *unknown* and stays a candidate.

Everything else is a preference: documented task strengths (published claims,
not measurements), a current self-test on this computer, how credible the
evidence is, whether the window fits, whether the model is already loaded,
the estimated fit, and whether a measured profile exists. Ties break
deterministically so the same request does not flap between models.

A model the person pinned is never swapped and never skipped for a
preference: it still has to meet the hard requirements, and a documented
limitation or a weak fit becomes a warning in its reason.

Pure: no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.contracts import profiles as inference_profiles

# Task strengths, as recorded evidence names them. The same words the
# catalogue's `hints` and `limited_to` use.
GENERAL, CODE, VISION, REASONING, OCR = "general", "code", "vision", "reasoning", "ocr"

_CODE_PATTERNS = re.compile(
    r"```|\bdef \w+\(|\bfunction \w*\(|\bclass \w+[:(]|Traceback \(most recent call|"
    r"\b(?:SyntaxError|TypeError|NullPointerException|segmentation fault)\b|"
    r"\b\w+\.(?:py|js|ts|tsx|java|go|rs|cpp|c|cs|rb|php|kt|swift|sql)\b|"
    r"\b(?:compile|refactor|stack trace|unit test|regex)\b", re.I)
_REASONING_PATTERNS = re.compile(
    r"\b(?:prove|proof|step[- ]by[- ]step|derive|derivation|reason through|"
    r"solve|calculate|compute|why does|why is|logic puzzle|theorem)\b|"
    r"\d+\s*[-+*/^]\s*\d+\s*[=?]", re.I)

# --------------------------------------------------------------------------
# A picture sent with Chat: text in it, or what it shows?
# --------------------------------------------------------------------------
#
# Page reading transcribes the visible text of a page (`ocr.SYSTEM_INSTRUCTION`)
# and nothing else. Its output can answer a request for that text, or a
# question whose answer is a piece of that text — never a question about
# objects, colours, people, handwriting, signatures, stamps, whether something
# is genuine, or where things are. So a picture only takes the
# read-the-text-then-answer route when the request is clearly about its text;
# anything visual, mixed or unclear needs a model that looks at the picture.
# English only, and conservative on purpose: words like "document",
# "signature" or "summarise" do not by themselves make a request text-only.

TRANSCRIPTION, TEXT_QUESTION, VISUAL = "transcription", "text_question", "visual"

# Anything that needs the picture itself. One match makes the request visual,
# whatever else it asks.
_VISUAL_WORDS = re.compile(
    r"\b(?:colou?rs?|colou?red|describe|look(?:s|ing)?\s+like|appear(?:s|ance)?|"
    r"what(?:'s|\s+is)\s+(?:in|on|shown\s+in)\s+(?:this|the|my)\s+(?:image|picture|photo|pic|"
    r"screenshot)|(?:image|picture|photo)\s+of|"
    r"who\s+is|who's|wearing|faces?|people|persons?|animals?|objects?|shapes?|"
    r"how\s+many|where\s+is|(?:on|to|at)\s+the\s+(?:left|right|top|bottom)|above|below|"
    r"behind|in\s+front\s+of|next\s+to|background|foreground|scene|position|layout|"
    r"charts?|graphs?|diagrams?|plots?|logos?|icons?|drawings?|sketch(?:es)?|"
    r"handwriting|handwritten|signatures?|signed|"
    r"stamps?|seals?|genuine|authentic(?:ity)?|fake|forged|forgery|tamper(?:ed|ing)?|"
    r"edited|real\s+or|compare|comparison|similar|differen(?:t|ce)|match(?:es|ing)?|"
    r"style|font|quality|blurry|damaged|condition)\b", re.I)
# A clearly text-only request is one of these forms and nothing else: the
# WHOLE request must match. "Transcribe the text and explain the gesture"
# has a second clause the text cannot answer, so it needs vision.
_POLITE = r"(?:please\s+)?(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?"
_ABOUT = (r"(?:\s+(?:in|from|on|of)\s+(?:this|the|that|my|attached)\s+"
          r"(?:image|picture|photo|pic|page|scan|screenshot|document|file|receipt|"
          r"invoice|letter|form|sign|note|label|card))?")
_TAIL = r"(?:\s+(?:for\s+me|please))?\s*[.!?]*"
_TRANSCRIPTION_FORMS = (
    r"(?:(?:perform|do|run)\s+(?:an?\s+)?ocr|ocr|transcribe)(?:\s+(?:this|it|that|the\s+text|"
    r"all\s+the\s+text|the\s+words|everything))?",
    r"extract\s+(?:the\s+|all\s+(?:the\s+)?)?(?:text|words|wording)",
    r"(?:read|copy|type)\s+(?:out\s+)?(?:the\s+|all\s+(?:the\s+)?)?(?:text|words|wording)",
    r"what\s+does\s+(?:it|this|that|(?:the|this|that|my)\s+\w+)\s+say",
    r"what(?:'s|\s+is)\s+written(?:\s+(?:on|in)\s+(?:it|this|that|(?:the|this|that|my)\s+\w+))?",
)
_TEXT_FORMS = (
    r"(?:summari[sz]e|translate|proofread|spell[- ]?check)\s+(?:the\s+|this\s+|its\s+)?"
    r"(?:text|words|wording)(?:\s+(?:into|to)\s+[a-z]+)?",
    r"what\s+(?:is|are)\s+the\s+(?:total|subtotal|amount|amount\s+due|due\s+date|"
    r"invoice\s+number|reference(?:\s+number)?|account\s+number|phone\s+number|"
    r"e-?mail(?:\s+address)?|address|order\s+number)\s+(?:on|in|of)\s+"
    r"(?:this|the|that|my)\s+\w+",
)


def _whole(forms) -> re.Pattern:
    return re.compile(rf"\s*{_POLITE}(?:{'|'.join(forms)}){_ABOUT}{_TAIL}", re.I)


_TRANSCRIPTION_REQUEST = _whole(_TRANSCRIPTION_FORMS)
_TEXT_REQUEST = _whole(_TEXT_FORMS)


def image_intent(text: str) -> str:
    """What a question sent with a picture asks of it: one of three labels.

    Only a request that is, as a whole, one clearly text-based form takes the
    text route. A visual word, a second clause, or anything these forms do not
    cover — including no question at all — needs a model that sees.
    """
    text = (text or "").strip()
    if _VISUAL_WORDS.search(text):
        return VISUAL
    if _TRANSCRIPTION_REQUEST.fullmatch(text):
        return TRANSCRIPTION
    if _TEXT_REQUEST.fullmatch(text):
        return TEXT_QUESTION
    return VISUAL


@dataclass(frozen=True)
class Task:
    workflow: str
    needs_vision: bool = False
    labels: tuple[str, ...] = ()
    estimated_tokens: int = 0
    # For a picture sent with Chat: transcription, text_question or visual.
    image: str | None = None


def classify(text: str, *, workflow: str, needs_vision: bool = False,
             prefers_vision: bool = False, images: bool = False,
             estimated_tokens: int = 0, default_budget: int = 6000) -> Task:
    """Constrained labels from the request text; never a permission.

    `needs_vision` removes models that cannot take images (page reading).
    `prefers_vision` only ranks them first. `images` says ordinary Chat was
    sent a picture: a question about what it shows then needs vision, while a
    request for its text only prefers it, because page reading can supply
    that text to a model without vision.
    """
    labels = ["image"] if prefers_vision else []
    intent = None
    text = text or ""
    if images and workflow == inference_profiles.CHAT:
        intent = image_intent(text)
        if intent == VISUAL:
            needs_vision = True
        if "image" not in labels:
            labels.append("image")
    if workflow == inference_profiles.CHAT and _CODE_PATTERNS.search(text):
        labels.append(CODE)
    if _REASONING_PATTERNS.search(text):
        labels.append(REASONING)
    if estimated_tokens > default_budget:
        labels.append("long")
    return Task(workflow, needs_vision, tuple(labels), estimated_tokens, intent)


def wanted(task: Task) -> str:
    """The strength this task asks of the model that answers it."""
    if task.workflow == inference_profiles.OCR or task.image == TRANSCRIPTION:
        return OCR
    if task.image == TEXT_QUESTION:
        return GENERAL
    if task.needs_vision or "image" in task.labels:
        return VISION
    if task.workflow == inference_profiles.CODE or CODE in task.labels:
        return CODE
    if REASONING in task.labels:
        return REASONING
    return GENERAL



@dataclass
class Candidate:
    key: str
    model_id: str
    origin: str
    profile: object                       # v1.ExecutionProfile for task.workflow
    capabilities: list | None = None
    hints: tuple[str, ...] = ()           # documented task strengths
    resident: bool = False
    fit: str = "unknown"
    measured: bool = False
    display: str = ""
    blocked: str | None = None            # an actual reason it cannot run
    # Documented task limitation: the model is described as doing only these.
    limited_to: tuple[str, ...] = ()
    # How credible the strengths/limitation are: 3 the publisher's card,
    # 2 the repository's own metadata, 1 runtime-reported metadata, 0 none.
    evidence: int = 0
    evidence_source: str = ""
    # This workflow's self-test on this computer, only when it still matches
    # the installed bytes and check settings: "passed", "failed" or None.
    check: str | None = None
    check_kind: str | None = None          # why a current check failed, when known
    # Documents only: False when this model runs Documents as limited Chat.
    structured: bool = True


@dataclass
class Choice:
    candidate: Candidate | None
    reason: str
    skipped: list[tuple[str, str]] = field(default_factory=list)
    # Every model that may do this task, best first; the first is `candidate`.
    ranked: list[Candidate] = field(default_factory=list)
    # "unsuitable" when models could run it but each one's documentation
    # says it does not do this kind of task.
    code: str | None = None


FIT_RANK = {"good": 0, "marginal": 1, "unknown": 2, "too_large": 3}
ORIGIN_LABEL = {"ollama": "Ollama", "llama.cpp": "Refinix engine"}
WORKFLOW_LABEL = {inference_profiles.CHAT: "Chat", inference_profiles.CODE: "Code",
                  inference_profiles.DOCUMENTS: "Documents",
                  inference_profiles.OCR: "page reading"}
STRENGTH_WORDS = {GENERAL: "general use", CODE: "coding", VISION: "images",
                  REASONING: "reasoning", OCR: "page reading"}
EVIDENCE_WORDS = {3: "its publisher's card", 2: "its repository's metadata",
                  1: "what its runtime reports"}


def task_fit(candidate: Candidate, want: str) -> int:
    """0 documented for this task · 1 documented general · 2 other documented
    strengths, still a capable fallback · 3 nothing documented."""
    strengths = set(candidate.hints)
    if want in strengths:
        return 0
    if want == OCR and VISION in strengths:
        return 1
    if GENERAL in strengths:
        return 1
    if strengths:
        return 2
    return 3


def limitation(candidate: Candidate, task: Task) -> str | None:
    """Why this model's documentation rules it out of this task, if it does."""
    if not candidate.limited_to or wanted(task) in candidate.limited_to:
        return None
    what = ", ".join(STRENGTH_WORDS.get(item, item) for item in candidate.limited_to)
    source = EVIDENCE_WORDS.get(candidate.evidence, "its documentation")
    return f"is documented for {what} only ({source})"


INCOMPLETE = "incomplete"


def demonstrated(candidate: Candidate) -> str | None:
    """A limitation this computer observed for this task, while it still applies.

    Only one kind counts: this workflow's own check, run against the model,
    runtime and check settings in place now, reached its output limit without
    finishing the answer. A formatting failure, a wrong answer, a crash or a
    check that could not run ranks the model lower at most; a stale or missing
    result counts for nothing. Passing the check again removes it.
    """
    if candidate.check == "failed" and candidate.check_kind == INCOMPLETE:
        return ("did not finish its answer within this task's check limit here "
                "(current model, runtime and check settings)")
    return None


def _vision_missing(candidate: Candidate, task: Task) -> int:
    prefers = task.needs_vision or "image" in task.labels or task.workflow == inference_profiles.OCR
    return int(prefers and "vision" not in (candidate.capabilities or []))


def _check_rank(candidate: Candidate) -> int:
    return {"passed": 0, "failed": 2}.get(candidate.check or "", 1)


def _hard(item: Candidate, task: Task) -> str | None:
    if item.blocked:
        return item.blocked
    if item.profile is None:
        return f"cannot run {WORKFLOW_LABEL.get(task.workflow, task.workflow)} here"
    if task.needs_vision and "vision" not in (item.capabilities or []):
        return "does not accept images"
    return None


def choose(task: Task, candidates: list[Candidate], *, auto: bool = True) -> Choice:
    """The installed models that may do this task, best first, with reasons.

    `auto=False` is a model the person pinned: only the hard requirements
    apply, and a documented limitation becomes a warning in the reason.
    """
    skipped, eligible, limited = [], [], []
    for item in candidates:
        why = _hard(item, task)
        if why:
            skipped.append((item.key, why))
            continue
        documented = limitation(item, task) or demonstrated(item)
        if documented and auto:
            skipped.append((item.key, documented))
            limited.append(item)
            continue
        eligible.append(item)
    need = WORKFLOW_LABEL.get(task.workflow, task.workflow)
    if task.needs_vision:
        need += " with an image"
    names = {item.key: item.display or item.model_id for item in candidates}
    if not eligible:
        why = "; ".join(f"{names.get(key, key)} {reason}" for key, reason in skipped[:3])
        code = "unsuitable" if limited and len(limited) == len(
            [c for c in candidates if not _hard(c, task)]) else None
        if code == "unsuitable":
            return Choice(None, (f"No installed local model is suitable for {need}: "
                                 f"{why}. Choose a model yourself, or set up one that "
                                 "does this kind of task."), skipped, [], code)
        return Choice(None, (f"No installed local model can do {need} on this computer"
                             + (f": {why}." if why else ".")), skipped, [], None)
    want = wanted(task)
    window_needed = task.estimated_tokens

    def rank(item: Candidate):
        too_small = int(bool(window_needed) and
                        item.profile.qualified_context_tokens < window_needed)
        return (int(not item.structured), _vision_missing(item, task), task_fit(item, want),
                _check_rank(item), -item.evidence, too_small, int(not item.resident),
                FIT_RANK.get(item.fit, 2), int(not item.measured), item.key)

    eligible.sort(key=rank)
    best = eligible[0]
    label = WORKFLOW_LABEL.get(task.workflow, task.workflow)
    origin = ORIGIN_LABEL.get(best.origin, best.origin)
    name = best.display or best.model_id
    why = describe(best, task)
    if len(eligible) == 1:
        why.append("the only model here that can")
    if auto:
        reason = f"Auto: {label} → {name} ({origin})"
    else:
        reason = f"Chosen by you: {name}"
        warning = limitation(best, task) or demonstrated(best)
        if warning:
            why = [f"note: it {warning}"]
        elif task_fit(best, want) >= 2 and want != GENERAL:
            why = [f"note: it is not documented for {STRENGTH_WORDS.get(want, want)}"]
        else:
            why = []
    reason += f" — {', '.join(why)}" if why else ""
    for item in eligible[1:]:
        skipped.append((item.key, "ranked lower for this task"))
    return Choice(best, reason[:256], skipped, eligible, None)


def describe(item: Candidate, task: Task) -> list[str]:
    """Why this model ranks where it does, in plain words, strongest first."""
    want = wanted(task)
    fit = task_fit(item, want)
    source = EVIDENCE_WORDS.get(item.evidence)
    why = []
    if want in (VISION, OCR) and "vision" in (item.capabilities or []):
        why.append("it accepts images")
    if fit == 0 and want != GENERAL:
        why.append(f"documented for {STRENGTH_WORDS.get(want, want)}"
                   + (f" ({source})" if source else ""))
    elif fit in (0, 1) and GENERAL in item.hints:
        why.append("a general-purpose model" + (f" ({source})" if source else ""))
    elif fit == 2:
        why.append("documented for other tasks; no better-documented model is available")
    else:
        why.append("its strengths are not documented")
    if item.check == "passed":
        why.append("passed this check here")
    elif item.check == "failed":
        formatting = item.check_kind in ("empty", "multi_line", "extra_text")
        why.append("its check here failed on formatting only" if formatting
                   else "failed this check here")
    if not item.structured:
        why.append("as limited plain Chat")
    if item.resident:
        why.append("already loaded")
    if item.measured:
        why.append("measured here")
    if item.fit in ("good", "marginal"):
        why.append("fits this computer (estimated)" if item.fit == "good"
                   else "may be slow here (estimated)")
    return why
