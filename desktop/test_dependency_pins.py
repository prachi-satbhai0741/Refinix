"""Declared Python pins and the hash-pinned locks that ship them stay in step.

Dependabot proposes version updates for the declarations it can read
(`backend/requirements.txt`, `desktop/requirements-desktop.txt`). The packages
are actually built from hand-curated, multi-platform `--require-hashes` locks,
which Dependabot is not expected to rewrite. A pull request that bumps a
declaration alone would therefore leave every shipped lock on the old
version; this check fails it until a maintainer updates the locks too (every
platform's wheel hashes, and for the worker image a rebuild with its
`provenance.json`).

Standard library only, so CI runs it before any dependency is installed.

    python -m unittest discover -s desktop -p 'test_dependency_pins.py'
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DECLARATIONS = (REPO / "backend" / "requirements.txt",
                REPO / "desktop" / "requirements-desktop.txt")
# Every desktop package installs every declared pin.
DESKTOP_LOCKS = tuple(REPO / "desktop" / f"requirements-{name}.lock"
                      for name in ("macos", "windows", "linux"))
# Shares the contract pins it lists; a package it does not list is not required.
SHARED_LOCKS = (REPO / "backend" / "worker-image" / "requirements.lock",)
ALL_LOCKS = tuple(sorted({*DESKTOP_LOCKS, *SHARED_LOCKS,
                          *REPO.glob("backend/requirements-*.lock"),
                          *REPO.glob("desktop/requirements-build-*.lock")}))

_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)")
_HASH = re.compile(r"--hash=sha256:([0-9a-f]+)")


def _name(raw: str) -> str:
    return re.sub(r"[-_.]+", "-", raw).lower()


def logical_lines(path: Path) -> list[str]:
    """Lines with comments removed and backslash continuations joined."""
    joined, current = [], ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split(" #", 1)[0] if not line.lstrip().startswith("#") else ""
        if line.rstrip().endswith("\\"):
            current += line.rstrip()[:-1] + " "
            continue
        current += line
        if current.strip():
            joined.append(current.strip())
        current = ""
    if current.strip():
        joined.append(current.strip())
    return joined


def pins(path: Path, *, follow: bool = True, seen=None) -> dict[str, tuple[str, list[str]]]:
    """`{name: (version, hashes)}` for a requirement file and what it includes."""
    seen = set() if seen is None else seen
    path = path.resolve()
    if path in seen:
        return {}
    seen.add(path)
    found = {}
    for line in logical_lines(path):
        if line.startswith("-r "):
            if follow:
                found.update(pins(path.parent / line[3:].strip(), seen=seen))
            continue
        match = _PIN.match(line)
        if match:
            found[_name(match.group(1))] = (match.group(2), _HASH.findall(line))
    return found


class TestPinsStayInStep(unittest.TestCase):
    def declared(self) -> dict[str, str]:
        result = {}
        for path in DECLARATIONS:
            # Each declaration's own pins; its `-r` includes are declarations
            # in their own right and are listed above.
            result.update({name: version for name, (version, _h)
                           in pins(path, follow=False).items()})
        return result

    def test_every_desktop_lock_ships_every_declared_pin_at_its_version(self):
        declared = self.declared()
        self.assertIn("pydantic", declared)
        for lock in DESKTOP_LOCKS:
            shipped = pins(lock)
            for name, version in declared.items():
                with self.subTest(lock=lock.name, package=name):
                    self.assertIn(name, shipped, f"{lock.name} does not ship {name}")
                    self.assertEqual(shipped[name][0], version,
                                     f"{lock.name} ships {name} {shipped[name][0]}, "
                                     f"but the declaration says {version}")

    def test_shared_pins_match_wherever_a_lock_lists_them(self):
        declared = self.declared()
        for lock in SHARED_LOCKS:
            for name, (version, _hashes) in pins(lock).items():
                if name in declared:
                    with self.subTest(lock=lock.name, package=name):
                        self.assertEqual(version, declared[name])

    def test_every_lock_line_is_exact_and_hash_pinned(self):
        for lock in ALL_LOCKS:
            for line in logical_lines(lock):
                if line.startswith("-r "):
                    continue
                with self.subTest(lock=lock.name, line=line[:60]):
                    self.assertRegex(line, _PIN, "an exact name==version pin")
                    hashes = _HASH.findall(line)
                    self.assertTrue(hashes, "at least one --hash=sha256")
                    self.assertTrue(all(len(h) == 64 for h in hashes))

    def test_a_declaration_only_bump_is_caught(self):
        """The failure this file exists for, reproduced on a copy."""
        import tempfile
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / "requirements.txt").write_text("pydantic==99.0.0\n", encoding="utf-8")
            lock = root / "requirements-test.lock"
            lock.write_text("pydantic==2.13.5 --hash=sha256:" + "a" * 64 + "\n",
                            encoding="utf-8")
            declared = pins(root / "requirements.txt")["pydantic"][0]
            shipped = pins(lock)["pydantic"][0]
            self.assertNotEqual(declared, shipped)


if __name__ == "__main__":
    unittest.main(verbosity=2)
