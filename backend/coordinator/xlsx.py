"""Reading a spreadsheet, and being honest about what a cell actually holds.

An `.xlsx` is a ZIP of OOXML parts, so the standard library reads one exactly
as `documents._extract_docx` reads a Word file. Only the parts this module
names are opened, and each is parsed as data.

**A formula is not its result.** A cell can carry a formula *and* the value
Excel last cached for it. Nothing here evaluates a formula — there is no
calculation engine in this build and pretending otherwise would put invented
arithmetic into a document. A formula cell is reported as its formula and, if
Excel left one behind, its cached value clearly labelled as cached. A stale
cache is Excel's business, and saying "cached" is what keeps the reader from
mistaking it for a computed answer.

**Nothing outside the archive is followed.** External relationships, absolute
targets and traversal are refused rather than resolved: a workbook that points
at a network share or another file on this computer must not turn a document
read into a fetch. Macros and embedded objects are never opened or executed;
a `.xlsm` is not accepted at all.

Legacy `.xls` is a different, binary format and is not supported.

Standard library only.
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = f"{{{DOC_REL}}}"

# Bounds. Each is applied to the decompressed size before the part is read, so
# a small archive cannot expand into a large read.
MAX_PART_BYTES = 24 * 1024 * 1024
MAX_ENTRIES = 2048
MAX_SHEETS = 64
MAX_ROWS_PER_SHEET = 20_000
MAX_CELLS_PER_SHEET = 200_000
MAX_CELL_CHARS = 4096
MAX_SHARED_STRINGS = 500_000

# Aggregate ceilings. The per-part limits above bound one worksheet; without
# these, sixty-four worksheets of 24 MB each were individually legal, so a
# small archive could still expand into gigabytes and millions of objects.
# Every one is checked against the archive's declared sizes BEFORE anything is
# decompressed, so a bomb is refused rather than survived.
MAX_TOTAL_PART_BYTES = 64 * 1024 * 1024
MAX_TOTAL_CELLS = 400_000
MAX_TOTAL_TEXT_CHARS = 8 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200

CELL_REFERENCE = re.compile(r"^([A-Z]{1,3})([0-9]{1,7})$")


class SheetError(ValueError):
    """A refusal the interface can show, with a code a check can assert."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class Cell:
    """One cell's location and what it really holds.

    `formula` and `value` are separate on purpose. A caller that wants to show
    "what the sheet says" shows `display`; a caller that wants to know whether
    a number was typed or calculated reads the two fields.
    """

    __slots__ = ("sheet", "reference", "column", "row", "value", "formula",
                 "cached")

    def __init__(self, *, sheet, reference, column, row, value, formula, cached):
        self.sheet = sheet
        self.reference = reference
        self.column = column
        self.row = row
        self.value = value
        self.formula = formula
        self.cached = cached

    @property
    def display(self) -> str:
        """What to put in a document block, with cached values labelled."""
        if self.formula is not None:
            if self.value:
                return f"={self.formula} (cached value {self.value}, not recalculated)"
            return f"={self.formula} (no cached value)"
        return self.value

    def as_dict(self) -> dict:
        return {"sheet": self.sheet, "reference": self.reference,
                "column": self.column, "row": self.row, "value": self.value,
                "formula": self.formula, "cached": self.cached}


def _safe_name(name: str, filename: str) -> str:
    """Refuse a part name that leaves the archive before it is opened."""
    if name.startswith("/") or name.startswith("\\") or ".." in name.split("/"):
        raise SheetError(
            "unsafe_part",
            f"{filename} names a part outside the workbook, which Refinix "
            "does not follow.")
    return name


def _read_part(archive: zipfile.ZipFile, name: str, filename: str,
               *, required: bool = True) -> bytes | None:
    """One part, size-checked before and after reading."""
    try:
        info = archive.getinfo(_safe_name(name, filename))
    except KeyError:
        if required:
            raise SheetError(
                "malformed", f"{filename} does not contain {name}.") from None
        return None
    if info.file_size > MAX_PART_BYTES:
        raise SheetError("too_much_text",
                         f"{filename} holds more data than Refinix reads.")
    try:
        with archive.open(info) as handle:
            raw = handle.read(MAX_PART_BYTES + 1)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise SheetError("malformed",
                         f"{filename} has a damaged workbook part.") from exc
    if len(raw) > MAX_PART_BYTES:
        raise SheetError("too_much_text",
                         f"{filename} holds more data than Refinix reads.")
    return raw


def _parse(raw: bytes, filename: str, part: str):
    try:
        # ET does not resolve external entities, which is what matters here.
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SheetError("malformed",
                         f"{filename} has a damaged {part}.") from exc


def _relationships(archive, rels_path: str, filename: str) -> dict:
    """Relationship id to in-archive target, refusing anything external."""
    raw = _read_part(archive, rels_path, filename, required=False)
    if raw is None:
        return {}
    root = _parse(raw, filename, "relationship part")
    mapping = {}
    for item in root.findall(f"{PKG_REL}Relationship"):
        target_mode = (item.get("TargetMode") or "Internal").strip()
        target = (item.get("Target") or "").strip()
        identifier = item.get("Id")
        if not identifier or not target:
            continue
        if target_mode.lower() == "external" or "://" in target:
            # Deliberately dropped, not resolved. A workbook does not get to
            # turn a document read into a network or filesystem fetch.
            continue
        mapping[identifier] = target
    return mapping


def _resolve(base: str, target: str, filename: str) -> str:
    """A relationship target, relative to the part that declared it."""
    if target.startswith("/"):
        return _safe_name(target.lstrip("/"), filename)
    prefix = base.rsplit("/", 1)[0] if "/" in base else ""
    joined = f"{prefix}/{target}" if prefix else target
    parts: list[str] = []
    for piece in joined.split("/"):
        if piece in ("", "."):
            continue
        if piece == "..":
            if not parts:
                raise SheetError(
                    "unsafe_part",
                    f"{filename} names a part outside the workbook.")
            parts.pop()
        else:
            parts.append(piece)
    return _safe_name("/".join(parts), filename)


def _shared_strings(archive, filename: str) -> list[str]:
    raw = _read_part(archive, "xl/sharedStrings.xml", filename, required=False)
    if raw is None:
        return []
    root = _parse(raw, filename, "shared strings part")
    strings: list[str] = []
    for item in root.findall(f"{MAIN}si"):
        # `t` elements anywhere under `si` — a run-formatted string splits its
        # text across several of them.
        text = "".join(node.text or "" for node in item.iter(f"{MAIN}t"))
        strings.append(text[:MAX_CELL_CHARS])
        if len(strings) > MAX_SHARED_STRINGS:
            raise SheetError("too_much_text",
                             f"{filename} holds more text than Refinix reads.")
    return strings


def _column_of(reference: str) -> str:
    match = CELL_REFERENCE.match(reference or "")
    return match.group(1) if match else ""


def _row_of(reference: str, fallback: int) -> int:
    match = CELL_REFERENCE.match(reference or "")
    return int(match.group(2)) if match else fallback


def _cell_value(cell, strings: list[str]) -> str:
    """The cell's own text, by its declared type. Never a calculated number."""
    kind = cell.get("t") or "n"
    if kind == "inlineStr":
        node = cell.find(f"{MAIN}is")
        if node is None:
            return ""
        return "".join(part.text or "" for part in node.iter(f"{MAIN}t"))
    value = cell.find(f"{MAIN}v")
    raw = (value.text or "") if value is not None else ""
    if kind == "s":
        try:
            return strings[int(raw)]
        except (ValueError, IndexError):
            # A shared-string index that does not resolve is reported empty
            # rather than guessed at.
            return ""
    if kind == "b":
        return {"0": "FALSE", "1": "TRUE"}.get(raw.strip(), raw)
    return raw


def read(data: bytes, filename: str) -> dict:
    """Every worksheet's visible cells, in workbook then row-major order.

    Returns the sheets in the order the workbook declares them, each with its
    real name, so a caller can cite "Sheet2!B7" and have it resolve.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as exc:
        raise SheetError(
            "malformed", f"{filename} is not a readable spreadsheet.") from exc

    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ENTRIES:
            raise SheetError("too_many_parts",
                             f"{filename} contains more parts than Refinix opens.")
        declared = 0
        for info in entries:
            _safe_name(info.filename, filename)
            declared += info.file_size
            # Read from the archive's own headers, before a byte is inflated.
            if info.compress_size and \
                    info.file_size / max(1, info.compress_size) > MAX_COMPRESSION_RATIO:
                raise SheetError(
                    "expansion_refused",
                    f"{filename} contains a part that expands more than "
                    f"{MAX_COMPRESSION_RATIO} times, which Refinix does not open.")
        if declared > MAX_TOTAL_PART_BYTES:
            raise SheetError(
                "too_much_text",
                f"{filename} expands to more than "
                f"{MAX_TOTAL_PART_BYTES // (1024 * 1024)} MB, which is more "
                "than Refinix reads.")
        if any(info.filename.startswith("xl/macrosheets/")
               or info.filename == "xl/vbaProject.bin" for info in entries):
            raise SheetError(
                "macros_present",
                f"{filename} contains a macro project. Refinix does not open "
                "or run macros; save it as a plain .xlsx and attach that.")

        root_rels = _relationships(archive, "_rels/.rels", filename)
        workbook_path = next(
            (target for identifier, target in root_rels.items()
             if target.endswith("workbook.xml")), "xl/workbook.xml")
        workbook_path = _resolve("", workbook_path, filename)
        workbook = _parse(_read_part(archive, workbook_path, filename),
                          filename, "workbook part")
        rels_path = (f"{workbook_path.rsplit('/', 1)[0]}/_rels/"
                     f"{workbook_path.rsplit('/', 1)[-1]}.rels"
                     if "/" in workbook_path
                     else f"_rels/{workbook_path}.rels")
        sheet_rels = _relationships(archive, rels_path, filename)

        declared = workbook.find(f"{MAIN}sheets")
        sheets: list[dict] = []
        if declared is None:
            raise SheetError("malformed", f"{filename} declares no worksheets.")
        for element in declared.findall(f"{MAIN}sheet"):
            if len(sheets) >= MAX_SHEETS:
                break
            name = element.get("name") or f"Sheet{len(sheets) + 1}"
            # A hidden sheet is not "visible cell values", so it is skipped
            # and counted rather than silently merged into the readable text.
            hidden = (element.get("state") or "visible").lower() != "visible"
            target = sheet_rels.get(element.get(f"{REL_NS}id") or "")
            sheets.append({"name": name, "hidden": hidden,
                           "path": _resolve(workbook_path, target, filename)
                                   if target else None})

        # Parsed once for the workbook. It used to be re-read and re-parsed
        # for every worksheet, multiplying the cost of a large table by the
        # number of sheets.
        strings = _shared_strings(archive, filename)
        results, skipped = [], []
        budget = {"cells": 0, "chars": 0}
        for sheet in sheets:
            if sheet["hidden"]:
                skipped.append(f"{sheet['name']} (hidden)")
                continue
            if not sheet["path"]:
                skipped.append(f"{sheet['name']} (no readable part)")
                continue
            raw = _read_part(archive, sheet["path"], filename, required=False)
            if raw is None:
                skipped.append(f"{sheet['name']} (missing part)")
                continue
            cells = _sheet_cells(_parse(raw, filename, "worksheet part"),
                                 sheet["name"], strings, filename)
            # Aggregate, across every sheet read so far.
            budget["cells"] += len(cells)
            budget["chars"] += sum(len(c.value) + len(c.formula or "")
                                   for c in cells)
            if budget["cells"] > MAX_TOTAL_CELLS:
                raise SheetError("too_much_text",
                                 f"{filename} holds more cells than Refinix reads.")
            if budget["chars"] > MAX_TOTAL_TEXT_CHARS:
                raise SheetError("too_much_text",
                                 f"{filename} holds more text than Refinix reads.")
            results.append({"name": sheet["name"], "cells": cells})

    if not results:
        raise SheetError(
            "empty",
            f"{filename} has no readable worksheet."
            + (f" Skipped: {', '.join(skipped)}." if skipped else ""))
    return {"sheets": results, "skipped": skipped}


def _sheet_cells(sheet_root, sheet_name: str, strings: list[str],
                 filename: str) -> list[Cell]:
    data = sheet_root.find(f"{MAIN}sheetData")
    if data is None:
        return []
    cells: list[Cell] = []
    for index, row in enumerate(data.findall(f"{MAIN}row"), start=1):
        if index > MAX_ROWS_PER_SHEET:
            raise SheetError("too_much_text",
                             f"{filename} has more rows than Refinix reads.")
        row_number = _row_of(row.get("r") or "", index)
        for cell in row.findall(f"{MAIN}c"):
            if len(cells) >= MAX_CELLS_PER_SHEET:
                raise SheetError("too_much_text",
                                 f"{filename} has more cells than Refinix reads.")
            reference = cell.get("r") or ""
            formula_node = cell.find(f"{MAIN}f")
            formula = None
            if formula_node is not None:
                # The formula text as written. Never evaluated.
                formula = (formula_node.text or "")[:MAX_CELL_CHARS] or None
            value = _cell_value(cell, strings)[:MAX_CELL_CHARS]
            if not value and formula is None:
                continue
            cells.append(Cell(sheet=sheet_name, reference=reference,
                              column=_column_of(reference), row=row_number,
                              value=value, formula=formula,
                              cached=bool(formula and value)))
    return cells


def as_text(sheets: list[dict]) -> str:
    """The workbook as readable lines, one row per line, cells tab-separated.

    Each line carries its worksheet and row so a citation made from this text
    can be checked against the file.
    """
    lines: list[str] = []
    for sheet in sheets:
        lines.append(f"[worksheet: {sheet['name']}]")
        current_row, row_cells = None, []
        for cell in sheet["cells"]:
            if current_row is not None and cell.row != current_row:
                lines.append(f"row {current_row}: " + "\t".join(row_cells))
                row_cells = []
            current_row = cell.row
            row_cells.append(f"{cell.reference}: {cell.display}")
        if row_cells:
            lines.append(f"row {current_row}: " + "\t".join(row_cells))
    return "\n".join(lines)
