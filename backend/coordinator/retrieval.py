"""Finding passages in the documents the user selected, with real citations.

Keyword retrieval over SQLite FTS5, scoped to one request's sources. It is
called keyword retrieval because that is what it is: there is no embedding
model provisioned, OD-07 is unresolved, and nothing here is described as
semantic search.

What makes a citation trustworthy here:

* a passage can only come from a source the user selected for this request;
* every passage carries the source id and the page number it was extracted
  from, taken from the extraction record rather than from the model;
* `resolve` re-checks each citation against the selected sources before it is
  shown, so a citation the model invented cannot be rendered;
* one source cannot fill the whole context — passages are taken round-robin
  across sources, so a long document does not crowd out a short one;
* ordering is deterministic, including the tie-break, so the same question
  over the same documents produces the same passages.

Standard library only.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from unicodedata import category

MAX_PASSAGES = 12
MAX_PASSAGE_CHARS = 900
MAX_PER_SOURCE = 4
MIN_TERM_LENGTH = 2

METHOD = "keyword (SQLite FTS5)"
METHOD_NOTE = (
    "Passages are found by matching words, not meaning. No embedding model is "
    "installed, so this is keyword search and is labelled as such.")


class RetrievalError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fts_available(conn: sqlite3.Connection) -> bool:
    """Whether the coordinator created its FTS5 index. Read-only."""
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table'"
        " AND name='document_pages_fts'").fetchone() is not None


@dataclass(frozen=True)
class Passage:
    source_id: str
    filename: str
    page: int
    text: str
    rank: float

    def as_dict(self) -> dict:
        return {"source_id": self.source_id, "filename": self.filename,
                "page": self.page, "text": self.text, "rank": self.rank}

    @property
    def citation(self) -> str:
        return f"{self.filename} p.{self.page}"


# --------------------------------------------------------------------------
# Query handling
# --------------------------------------------------------------------------

def _words(text: str) -> list[str]:
    words, current = [], []
    for character in text or "":
        if character == "_" or character.isalnum() or category(character).startswith("M"):
            current.append(character)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    return words

def build_match(question: str) -> str:
    """Turn a person's words into a safe FTS5 MATCH expression.

    Every term is quoted, so FTS5 operators a user or a document happened to
    type — `NEAR`, `*`, `^`, `OR` — are searched for as words instead of
    changing the query.
    """
    words = _words(question)
    terms = [w for w in words if len(w) >= MIN_TERM_LENGTH][:24]
    if not terms:
        raise RetrievalError(
            "no_terms",
            "That question has no words to search for. Try naming something "
            "that appears in the documents.")
    return " OR ".join(f'"{term}"' for term in terms)


def search(conn: sqlite3.Connection, *, workspace_id: str, source_ids: list[str],
           question: str, limit: int = MAX_PASSAGES) -> list[Passage]:
    """Bounded passages from exactly these sources, deterministically ordered."""
    if not source_ids:
        raise RetrievalError("no_sources", "No documents were selected to search.")
    if not fts_available(conn):
        raise RetrievalError(
            "no_fts",
            "This computer's SQLite build has no full-text search, so Refinix "
            "cannot look inside documents. Missing prerequisite: SQLite with FTS5.")
    match = build_match(question)
    placeholders = ",".join("?" for _ in source_ids)
    rows = conn.execute(
        f"SELECT p.source_id, p.filename, p.page, p.text, bm25(document_pages_fts) AS rank"
        f" FROM document_pages_fts f"
        f" JOIN document_pages p ON p.rowid = f.rowid"
        f" WHERE document_pages_fts MATCH ? AND p.workspace_id = ?"
        f"   AND p.source_id IN ({placeholders})"
        # bm25 is ascending-best. Source and page break ties, so the order is
        # the same every time rather than whatever the table returns.
        f" ORDER BY rank ASC, p.source_id ASC, p.page ASC"
        f" LIMIT ?",
        (match, workspace_id, *source_ids, limit * 4)).fetchall()

    # Round-robin across sources so one long document cannot take every slot.
    by_source: dict[str, list[Passage]] = {}
    for row in rows:
        passage = Passage(
            source_id=row["source_id"], filename=row["filename"],
            page=row["page"], text=_excerpt(row["text"], question),
            rank=float(row["rank"]))
        bucket = by_source.setdefault(row["source_id"], [])
        if len(bucket) < MAX_PER_SOURCE:
            bucket.append(passage)

    chosen: list[Passage] = []
    order = sorted(by_source, key=lambda sid: (by_source[sid][0].rank, sid))
    depth = 0
    while len(chosen) < limit and any(len(by_source[s]) > depth for s in order):
        for source_id in order:
            if len(chosen) >= limit:
                break
            bucket = by_source[source_id]
            if len(bucket) > depth:
                chosen.append(bucket[depth])
        depth += 1
    return chosen


def _excerpt(text: str, question: str) -> str:
    """A bounded window around the first matching word, or the opening."""
    if len(text) <= MAX_PASSAGE_CHARS:
        return text.strip()
    words = [w for w in _words(question) if len(w) >= MIN_TERM_LENGTH]
    lowered = text.lower()
    position = -1
    for word in words:
        found = lowered.find(word.lower())
        if found != -1 and (position == -1 or found < position):
            position = found
    if position == -1:
        return text[:MAX_PASSAGE_CHARS].strip() + "…"
    start = max(0, position - MAX_PASSAGE_CHARS // 3)
    window = text[start:start + MAX_PASSAGE_CHARS].strip()
    return ("…" if start else "") + window + ("…" if start + MAX_PASSAGE_CHARS < len(text) else "")


# --------------------------------------------------------------------------
# Citations
# --------------------------------------------------------------------------

def resolve(citations, *, sources: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split citations into ones that resolve and ones that do not.

    A citation resolves only when its source was selected for this request and
    its page exists in that source's extraction. Anything else is returned as
    unresolved so the interface can say so, rather than being rendered as
    though it pointed somewhere.
    """
    by_id = {source["source_id"]: source for source in sources}
    resolved, unresolved = [], []
    for raw in citations if isinstance(citations, list) else []:
        if not isinstance(raw, dict):
            unresolved.append({"raw": str(raw)[:120],
                               "reason": "That citation was not in the expected shape."})
            continue
        source_id = raw.get("source_id")
        page = raw.get("page")
        source = by_id.get(source_id) if isinstance(source_id, str) else None
        if source is None:
            unresolved.append({"raw": str(source_id)[:120],
                               "reason": "That document was not selected for this request."})
            continue
        pages = source.get("pages") or []
        numbers = {p["number"] if isinstance(p, dict) else p for p in pages}
        if not isinstance(page, int) or page not in numbers:
            unresolved.append({
                "raw": f"{source['filename']} p.{page}",
                "reason": f"{source['filename']} has no page {page}."})
            continue
        resolved.append({"source_id": source_id, "filename": source["filename"],
                         "page": page, "label": f"{source['filename']} p.{page}"})
    return resolved, unresolved


def no_result_note(question: str, sources: list[dict]) -> str:
    names = ", ".join(source["filename"] for source in sources[:4])
    return (f"Nothing in {names or 'the selected documents'} matched those words. "
            "Refinix searches for the words you used, not their meaning, so a "
            "different wording may find it.")
