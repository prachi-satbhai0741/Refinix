"""Automatic local task-to-model assignment.

The coordinator is the orchestrator: it reads what the task needs, removes
every installed model that cannot do it, and ranks the rest. Deterministic
rules are enough for these classes of task (`docs/PROJECT.md` 7.0, 9.1); no
model is asked to choose a model, and nothing here can change a permission.

Task needs come from the workflow (Chat, Code, Documents, page reading), the
attachments (a picture sent natively needs `vision`) and three constrained
prompt labels: code-like text, reasoning-heavy wording and an input too long
for the default window.

Ranking uses only recorded facts: task strengths the publisher's model card
states (never the model's name), whether the model is already loaded, the
estimated fit on this computer, and whether a measured profile exists. Ties
break deterministically so the same request does not flap between models.
Two models may well get the same choice; the reason says why.

Pure: no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.contracts import profiles as inference_profiles

CODE_HINT, VISION_HINT, REASONING_HINT, GENERAL_HINT = "code", "vision", "reasoning", "general"

_CODE_PATTERNS = re.compile(
    r"```|\bdef \w+\(|\bfunction \w*\(|\bclass \w+[:(]|Traceback \(most recent call|"
    r"\b(?:SyntaxError|TypeError|NullPointerException|segmentation fault)\b|"
    r"\b\w+\.(?:py|js|ts|tsx|java|go|rs|cpp|c|cs|rb|php|kt|swift|sql)\b|"
    r"\b(?:compile|refactor|stack trace|unit test|regex)\b", re.I)
_REASONING_PATTERNS = re.compile(
    r"\b(?:prove|proof|step[- ]by[- ]step|derive|derivation|reason through|"
    r"solve|calculate|compute|why does|why is|logic puzzle|theorem)\b|"
    r"\d+\s*[-+*/^]\s*\d+\s*[=?]", re.I)


@dataclass(frozen=True)
class Task:
    workflow: str
    needs_vision: bool = False
    labels: tuple[str, ...] = ()
    estimated_tokens: int = 0


def classify(text: str, *, workflow: str, needs_vision: bool = False,
             prefers_vision: bool = False,
             estimated_tokens: int = 0, default_budget: int = 6000) -> Task:
    """Constrained labels from the request text; never a permission.

    `needs_vision` removes models that cannot take images (page reading).
    `prefers_vision` only ranks them first: a picture sent with a Chat request
    can still be read through text extraction by a model without vision.
    """
    labels = ["image"] if prefers_vision else []
    text = text or ""
    if workflow == inference_profiles.CHAT and _CODE_PATTERNS.search(text):
        labels.append(CODE_HINT)
    if _REASONING_PATTERNS.search(text):
        labels.append(REASONING_HINT)
    if estimated_tokens > default_budget:
        labels.append("long")
    return Task(workflow, needs_vision, tuple(labels), estimated_tokens)


def wanted_hint(task: Task) -> str:
    if task.needs_vision or task.workflow == inference_profiles.OCR \
            or "image" in task.labels:
        return VISION_HINT
    if task.workflow == inference_profiles.CODE or CODE_HINT in task.labels:
        return CODE_HINT
    if REASONING_HINT in task.labels:
        return REASONING_HINT
    return GENERAL_HINT


@dataclass
class Candidate:
    key: str
    model_id: str
    origin: str
    profile: object                       # v1.ExecutionProfile for task.workflow
    capabilities: list | None = None
    hints: tuple[str, ...] = ()
    resident: bool = False
    fit: str = "unknown"
    measured: bool = False
    display: str = ""
    blocked: str | None = None            # an actual reason it cannot run


@dataclass
class Choice:
    candidate: Candidate | None
    reason: str
    skipped: list[tuple[str, str]] = field(default_factory=list)


FIT_RANK = {"good": 0, "marginal": 1, "unknown": 2, "too_large": 3}
ORIGIN_LABEL = {"ollama": "Ollama", "llama.cpp": "Refinix engine"}
WORKFLOW_LABEL = {inference_profiles.CHAT: "Chat", inference_profiles.CODE: "Code",
                  inference_profiles.DOCUMENTS: "Documents",
                  inference_profiles.OCR: "page reading"}


def _hint_rank(candidate: Candidate, hint: str) -> int:
    if hint in candidate.hints:
        return 0
    if hint == VISION_HINT and "vision" in (candidate.capabilities or []):
        return 0
    if not candidate.hints or GENERAL_HINT in candidate.hints:
        return 1
    return 2


def choose(task: Task, candidates: list[Candidate]) -> Choice:
    """The best installed model for this task, with the reason and what was skipped."""
    skipped, eligible = [], []
    for item in candidates:
        if item.blocked:
            skipped.append((item.key, item.blocked))
        elif item.profile is None:
            skipped.append((item.key, f"cannot run {WORKFLOW_LABEL.get(task.workflow, task.workflow)} here"))
        elif task.needs_vision and "vision" not in (item.capabilities or []):
            skipped.append((item.key, "does not accept images"))
        else:
            eligible.append(item)
    if not eligible:
        need = WORKFLOW_LABEL.get(task.workflow, task.workflow)
        if task.needs_vision:
            need += " with an image"
        names = {item.key: item.display or item.model_id for item in candidates}
        why = "; ".join(f"{names.get(key, key)} {reason}" for key, reason in skipped[:3])
        return Choice(None, (f"No installed local model can do {need} on this computer"
                             + (f": {why}." if why else ".")), skipped)
    hint = wanted_hint(task)
    window_needed = task.estimated_tokens

    def rank(item: Candidate):
        too_small = int(bool(window_needed) and
                        item.profile.qualified_context_tokens < window_needed)
        return (_hint_rank(item, hint), too_small, int(not item.resident),
                FIT_RANK.get(item.fit, 2), int(not item.measured), item.key)

    eligible.sort(key=rank)
    best = eligible[0]
    why = []
    accepts_images = "vision" in (best.capabilities or [])
    if hint == VISION_HINT and (accepts_images or VISION_HINT in best.hints):
        why.append("it accepts images")
    elif hint in best.hints:
        why.append({CODE_HINT: "its publisher lists coding as a strength",
                    REASONING_HINT: "its publisher lists reasoning as a strength",
                    GENERAL_HINT: "a general-purpose model"}[hint])
    if best.resident:
        why.append("already loaded")
    if best.measured:
        why.append("measured here")
    if best.fit in ("good", "marginal"):
        why.append("fits this computer (estimated)" if best.fit == "good"
                   else "may be slow here (estimated)")
    if len(eligible) == 1:
        why.append("the only model here that can")
    label = WORKFLOW_LABEL.get(task.workflow, task.workflow)
    origin = ORIGIN_LABEL.get(best.origin, best.origin)
    reason = (f"Auto: {label} → {best.display or best.model_id} ({origin})"
              + (f" — {', '.join(why)}" if why else ""))
    for item in eligible[1:]:
        skipped.append((item.key, "ranked lower for this task"))
    return Choice(best, reason[:256], skipped)
