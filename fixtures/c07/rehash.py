"""Recompute the C07 provenance manifest. Standard library only.

Run after changing any fixture file, and never to "fix" a failing hash check
you did not intend to cause — that check exists to catch a fixture that drifted
away from the expected results recorded against it.

    python3 -m fixtures.c07.rehash
"""

from __future__ import annotations

import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
# The checking apparatus, not fixture content. Matched by path, not by name:
# `code/pumpcheck/pumpcheck/__init__.py` IS fixture content and must be hashed,
# while the package marker beside this file is not.
APPARATUS = {"provenance.json", "__init__.py", "test_fixtures.py", "rehash.py",
             "make_scan.py"}


def files() -> dict:
    out = {}
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if str(path.relative_to(HERE)) in APPARATUS:
            continue
        data = path.read_bytes()
        out[str(path.relative_to(HERE))] = {
            "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
    return out


def main() -> int:
    manifest = json.loads((HERE / "provenance.json").read_text())
    manifest["files"] = files()
    (HERE / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"recorded {len(manifest['files'])} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
