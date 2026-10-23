"""Choose which saved messages become one bounded model request.

Saved history and active context are different things. SQLite keeps the whole
conversation for ever; this module decides which part of it fits inside the
runtime's context window for a single inference, and records exactly what it
decided so the choice can be re-read later.

Nothing here deletes, rewrites or summarises a saved message. Omission is
omission: the reply is told, the user is told, and the message stays in history.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

# Character-per-token divisor used for the pre-flight estimate. It is an
# ESTIMATE, never a guarantee: English averages near 4, but code, CJK and
# Devanagari can be far denser. The margin is only a heuristic; runtime.py
# disables truncation and shifting so an underestimate fails visibly.
CHARS_PER_TOKEN = 3.0

# Per-message chat-template overhead (role markers, separators). Measured
# templates cost a handful of tokens per turn; 8 is a deliberate over-estimate.
PER_MESSAGE_OVERHEAD = 8

# Held back for the chat template's own preamble and any system block.
TEMPLATE_OVERHEAD = 64

# Fraction of the computed input budget actually used, so an under-estimate
# does not immediately overflow the window.
SAFETY_FRACTION = 0.85


def estimate_tokens(text: str) -> int:
    """Character-based selection heuristic, never a token-count guarantee."""
    return int(len(text) / CHARS_PER_TOKEN) + 1


def estimate_messages(messages: list[dict]) -> int:
    """Estimate one already-built runtime prompt with role overhead."""
    return sum(estimate_tokens(message.get("content", "")) + PER_MESSAGE_OVERHEAD
               for message in messages)


def input_budget(window: int, output_allowance: int) -> int:
    """Tokens available for the conversation after output and template overhead.

    `num_predict` is an output *maximum*, not something the runtime deducts for
    us, so it is subtracted here explicitly.
    """
    raw = window - output_allowance - TEMPLATE_OVERHEAD
    return max(0, int(raw * SAFETY_FRACTION))


@dataclass
class Selection:
    """What was sent, what was left out, and how that was decided."""

    included_ids: list[str] = field(default_factory=list)
    omitted_ids: list[str] = field(default_factory=list)
    omitted_count: int = 0
    estimated_input_tokens: int = 0
    input_budget_tokens: int = 0
    context_window: int = 0
    output_allowance: int = 0
    counting_method: str = f"estimate: characters / {CHARS_PER_TOKEN}"
    newest_fits: bool = True
    note: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def select(messages: list[dict], *, window: int, output_allowance: int):
    """Return (payload_messages, Selection) for one request.

    `messages` is the saved conversation, oldest first, each a dict with
    `message_id`, `role` and `text`.

    Rules, in order:
      1. The newest user message is always kept.
      2. Older turns are added newest-first while they fit.
      3. A turn is a complete exchange: an assistant reply is never included
         without the user message it answered, so the model never sees an
         orphan reply.
      4. If the newest message alone does not fit, nothing is silently chopped
         — the caller is told to shorten or split it.
    """
    budget = input_budget(window, output_allowance)
    sel = Selection(context_window=window, output_allowance=output_allowance,
                    input_budget_tokens=budget)

    if not messages:
        return [], sel

    system_count = 0
    while (system_count < len(messages)
           and messages[system_count]["role"] == "system"):
        system_count += 1
    required = messages[:system_count]
    if system_count == len(messages):
        used = sum(estimate_tokens(m["text"]) + PER_MESSAGE_OVERHEAD
                   for m in required)
        sel.included_ids = [m["message_id"] for m in required]
        sel.estimated_input_tokens = used
        sel.newest_fits = used <= budget
        return ([{"role": m["role"], "content": m["text"]} for m in required], sel)

    newest = messages[-1]
    newest_cost = (sum(estimate_tokens(m["text"]) + PER_MESSAGE_OVERHEAD
                       for m in required)
                   + estimate_tokens(newest["text"]) + PER_MESSAGE_OVERHEAD)

    if newest_cost > budget:
        sel.newest_fits = False
        sel.omitted_ids = [m["message_id"] for m in messages[system_count:-1]]
        sel.omitted_count = len(sel.omitted_ids)
        sel.estimated_input_tokens = newest_cost
        sel.included_ids = [m["message_id"] for m in [*required, newest]]
        sel.note = (
            f"This message is about {newest_cost} tokens, larger than the "
            f"{budget}-token input budget for a {window}-token window. "
            "Shorten it or split it into parts."
        )
        return [{"role": m["role"], "content": m["text"]}
                for m in [*required, newest]], sel

    # Walk backwards in complete exchanges so an assistant reply always keeps
    # the user message it answered.
    chosen: list[dict] = [newest]
    used = newest_cost
    index = len(messages) - 2
    while index >= system_count:
        if messages[index]["role"] == "assistant" and index > system_count:
            pair = [messages[index - 1], messages[index]]
            step = 2
        else:
            pair = [messages[index]]
            step = 1
        cost = sum(estimate_tokens(m["text"]) + PER_MESSAGE_OVERHEAD for m in pair)
        if used + cost > budget:
            break
        chosen = pair + chosen
        used += cost
        index -= step

    chosen = [*required, *chosen]
    kept = {m["message_id"] for m in chosen}
    sel.included_ids = [m["message_id"] for m in chosen]
    sel.omitted_ids = [m["message_id"] for m in messages if m["message_id"] not in kept]
    sel.omitted_count = len(sel.omitted_ids)
    sel.estimated_input_tokens = used
    if sel.omitted_count:
        sel.note = (
            f"{sel.omitted_count} earlier "
            f"{'message' if sel.omitted_count == 1 else 'messages'} "
            "were left out of this reply. They remain in your chat."
        )
    return [{"role": m["role"], "content": m["text"]} for m in chosen], sel
