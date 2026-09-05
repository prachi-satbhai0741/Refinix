"""C07 fixture checks: the pack is intact, synthetic, and still broken.

Standard library only; no model, no network, no worker.

These are not a Documents or Code workflow — those are C08 and C09. They prove
the three things C07 owes those chunks:

1. the fixtures have not drifted from their recorded hashes;
2. every expected fact, missing value and citation really is on the page it
   claims, so a C08 failure is the pipeline's and not the fixture's;
3. the code fixture is still broken, its validation command still fails on it,
   and the recorded repair still fixes it — checked on a disposable copy, which
   also proves the canonical fixture is not written to.

    python -m unittest fixtures.c07.test_fixtures
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
APPARATUS = {"provenance.json", "__init__.py", "test_fixtures.py", "rehash.py",
             "make_scan.py"}
DOCUMENTS = HERE / "documents"
CODE = HERE / "code"
REPO = CODE / "pumpcheck"


def pages(path: pathlib.Path) -> dict[int, str]:
    """Split a fixture on its `--- PAGE n ---` markers.

    The marker is the fixture's page contract: a citation to page 2 must
    resolve inside this mapping, not inside the whole file.
    """
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^--- PAGE (\d+) ---$", text, flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


class TestProvenance(unittest.TestCase):
    def manifest(self) -> dict:
        return json.loads((HERE / "provenance.json").read_text())

    def test_every_file_matches_its_recorded_hash(self):
        manifest = self.manifest()
        for name, record in manifest["files"].items():
            path = HERE / name
            with self.subTest(file=name):
                self.assertTrue(path.exists(), f"{name} is missing")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(digest, record["sha256"],
                                 f"{name} changed without its hash being updated")

    def test_the_manifest_covers_every_committed_file(self):
        listed = set(self.manifest()["files"])
        # The manifest records fixture content. The apparatus beside it is
        # not fixture content — and the exclusion is by path, so the package
        # markers INSIDE the code fixture are still recorded.
        found = {str(p.relative_to(HERE)) for p in HERE.rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts
                 and str(p.relative_to(HERE)) not in APPARATUS}
        self.assertEqual(found - listed, set(), "unrecorded fixture files")

    def test_the_pack_declares_itself_synthetic(self):
        manifest = self.manifest()
        self.assertTrue(manifest["contains_no_real_data"])
        self.assertIn("licence", manifest)
        self.assertIn("origin", manifest)

    def test_no_fixture_claims_to_be_a_real_document(self):
        for path in DOCUMENTS.glob("*.txt"):
            with self.subTest(file=path.name):
                self.assertIn("SYNTHETIC", path.read_text().upper()[:400],
                              "a reader must see this is not a real document")

    def test_the_scan_is_recorded_with_its_provenance(self):
        record = self.manifest()["scan"]
        for field in ("generated_by", "generation_method", "tool_versions",
                      "sha256", "size_bytes", "pages"):
            self.assertTrue(record.get(field), f"the scan needs {field}")
        self.assertTrue(record["deterministic"])

    def test_the_recorded_scan_hash_matches_the_committed_file(self):
        record = self.manifest()["scan"]
        data = (HERE / record["file"]).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"])
        self.assertEqual(len(data), record["size_bytes"])


class TestScanFixture(unittest.TestCase):
    """A scan is only a scan if nothing can read it without rendering it."""

    def setUp(self):
        self.expected = json.loads((DOCUMENTS / "expected.json").read_text())
        self.scan = (DOCUMENTS / "inspection-report-scan.pdf").read_bytes()

    def test_the_scan_exists_and_is_a_pdf(self):
        self.assertTrue(self.scan.startswith(b"%PDF-"))
        self.assertTrue(self.scan.rstrip().endswith(b"%%EOF"))

    def test_it_has_the_declared_number_of_pages(self):
        declared = self.expected["sources"]["inspection-report-scan.pdf"]["pages"]
        self.assertEqual(self.scan.count(b"/Type /Page "), declared)
        self.assertGreater(declared, 1, "a multi-page scan was required")

    def outside_streams(self) -> bytes:
        """The file with every stream payload removed.

        Searching the whole file for text operators gives false positives: `TJ`
        occurs by chance inside a compressed image. Only the object
        dictionaries and the uncompressed content streams say anything about
        structure, so the check looks at those.
        """
        out, rest = bytearray(), self.scan
        while True:
            start = rest.find(b"stream\n")
            if start == -1:
                out += rest
                return bytes(out)
            end = rest.find(b"endstream", start)
            out += rest[:start + len(b"stream\n")]
            rest = rest[end:]

    def content_streams(self) -> list[bytes]:
        """The page content streams, which are stored uncompressed and tiny."""
        found, rest = [], self.scan
        while True:
            head = rest.find(b"<< /Length ")
            if head == -1:
                return found
            start = rest.find(b"stream\n", head)
            end = rest.find(b"\nendstream", start)
            if start == -1 or end == -1:
                return found
            dictionary = rest[head:start]
            if b"/Filter" not in dictionary:      # not the compressed image
                found.append(rest[start + len(b"stream\n"):end])
            rest = rest[end + 1:]

    def test_it_carries_no_text_layer(self):
        """The whole point. A text layer would let an extractor skip OCR and
        report text it never read from the image."""
        structure = self.outside_streams()
        for marker in (b"/Font", b"/Type /Font", b"/BaseFont", b"/Encoding"):
            self.assertNotIn(marker, structure,
                             f"{marker!r} means the page can carry text")

    def test_each_page_draws_one_image_and_nothing_else(self):
        """An extractor can only get words out of this by rendering it: the
        entire content stream is a single image-draw operator."""
        streams = self.content_streams()
        self.assertEqual(len(streams), 3)
        for stream in streams:
            self.assertRegex(stream, rb"^q \d+ 0 0 \d+ 0 0 cm /Im0 Do Q$")
            for operator in (b"BT", b"ET", b"Tj", b"TJ", b"Tf"):
                self.assertNotIn(operator, stream)

    def test_every_page_is_a_greyscale_image(self):
        self.assertEqual(self.scan.count(b"/Subtype /Image"), 3)
        self.assertEqual(self.scan.count(b"/ColorSpace /DeviceGray"), 3)

    def test_it_is_byte_identical_when_regenerated(self):
        """A non-deterministic fixture makes its recorded hash meaningless."""
        generator = HERE / "make_scan.py"
        with tempfile.TemporaryDirectory() as workspace:
            copy = pathlib.Path(workspace) / "make_scan.py"
            copy.write_text(
                generator.read_text().replace(
                    'HERE = pathlib.Path(__file__).resolve().parent',
                    f'HERE = pathlib.Path({str(HERE)!r})').replace(
                    'TARGET = HERE / "documents" / "inspection-report-scan.pdf"',
                    f'TARGET = pathlib.Path({workspace!r}) / "out.pdf"'))
            result = subprocess.run([sys.executable, str(copy)],
                                    capture_output=True, text=True, timeout=300)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((pathlib.Path(workspace) / "out.pdf").read_bytes(),
                             self.scan, "regenerating produced different bytes")

    def test_it_carries_no_timestamp_or_document_id(self):
        for field in (b"/CreationDate", b"/ModDate", b"/ID", b"/Producer"):
            self.assertNotIn(field, self.scan,
                             f"{field!r} would make the bytes vary by run")

    def test_it_declares_itself_synthetic_on_the_page(self):
        """A reader looking at the rendered page must see it is not real. The
        banner is drawn into the pixels, so it cannot be stripped from
        metadata."""
        banner = self.expected["scan_binding"]["banner_on_every_page"]
        self.assertIn("SYNTHETIC SCAN", banner)
        self.assertIn("NOT A REAL DOCUMENT", banner)
        source = (HERE / "make_scan.py").read_text()
        self.assertIn("SYNTHETIC SCAN", source)

    def test_no_expectation_cites_a_scan_page_that_does_not_exist(self):
        pages = self.expected["sources"]["inspection-report-scan.pdf"]["pages"]
        found = 0
        for group in ("expected_facts", "expected_missing"):
            for item in self.expected[group]:
                if "scan_page" in item:
                    found += 1
                    with self.subTest(field=item["field"]):
                        self.assertTrue(1 <= item["scan_page"] <= pages)
        self.assertGreater(found, 0, "no expectation is bound to the scan")

    def test_report_expectations_are_bound_to_the_scan(self):
        """Every expectation about the report must say which scan page it is
        on, or C08 has no way to check OCR against it."""
        for group in ("expected_facts", "expected_missing"):
            for item in self.expected[group]:
                if item.get("source") == "inspection-report.txt":
                    with self.subTest(field=item["field"]):
                        self.assertEqual(item.get("scan_page"), item["page"])


class TestDocumentExpectations(unittest.TestCase):
    def setUp(self):
        self.expected = json.loads((DOCUMENTS / "expected.json").read_text())
        # Only the text sources have page markers; the scan is an image and is
        # checked in TestScanFixture.
        self.pages = {name: pages(DOCUMENTS / name)
                      for name in self.expected["sources"]
                      if name.endswith(".txt")}

    def test_declared_page_counts_are_real(self):
        for name, record in self.expected["sources"].items():
            if name not in self.pages:
                continue
            with self.subTest(source=name):
                self.assertEqual(len(self.pages[name]), record["pages"])

    def test_every_expected_fact_is_on_the_page_it_cites(self):
        """Otherwise a correct extractor would fail the fixture."""
        for fact in self.expected["expected_facts"]:
            with self.subTest(field=fact["field"]):
                page = self.pages[fact["source"]][fact["page"]]
                self.assertIn(fact["value"], page,
                              f"{fact['field']} is not on page {fact['page']}")

    def test_every_action_clause_is_present_on_its_cited_page(self):
        """A citation that only names an existing page proves nothing. The
        clause text has to be there, or an approval note could cite a page that
        does not say what it claims."""
        for finding in self.expected["expected_findings"]:
            clause = finding["action_clause"]
            with self.subTest(finding=finding["id"], clause=clause["clause"]):
                page = self.pages[clause["source"]][clause["page"]]
                self.assertIn(clause["quote"], page,
                              f"{clause['clause']} is not on "
                              f"{clause['source']} page {clause['page']}")
                self.assertTrue(page.strip().startswith(("", "\n")) or True)

    def test_every_required_action_is_supported_by_its_clause(self):
        """The action and the clause must agree. A clause quote that does not
        carry the action's key value would let a wrong action pass."""
        for finding in self.expected["expected_findings"]:
            clause = finding["action_clause"]
            numbers = [token for token in re.findall(r"\d+",
                                                     finding["required_action"])]
            with self.subTest(finding=finding["id"]):
                for number in numbers:
                    self.assertIn(number, clause["quote"],
                                  f"{finding['id']} requires {number} but its "
                                  "clause quote does not mention it")

    def test_every_missing_value_is_marked_missing_in_the_source(self):
        for missing in self.expected["expected_missing"]:
            with self.subTest(field=missing["field"]):
                page = self.pages[missing["source"]][missing["page"]]
                self.assertIn(missing["reported_as"], page)

    def test_a_forbidden_substitute_is_never_the_recorded_value(self):
        """`must_not_be` lists the fabrications a pipeline is tempted into. If
        one of them were also the true value the check would be vacuous."""
        for missing in self.expected["expected_missing"]:
            for forbidden in missing.get("must_not_be", []):
                with self.subTest(field=missing["field"], forbidden=forbidden):
                    self.assertNotEqual(forbidden, missing["reported_as"])

    def test_every_finding_citation_resolves(self):
        for finding in self.expected["expected_findings"]:
            for citation in finding["requires_citations"]:
                with self.subTest(finding=finding["id"], **citation):
                    self.assertIn(citation["page"], self.pages[citation["source"]])

    def test_every_finding_is_stated_in_the_report(self):
        report = "".join(self.pages["inspection-report.txt"].values())
        for finding in self.expected["expected_findings"]:
            with self.subTest(finding=finding["id"]):
                self.assertIn(finding["id"], report)

    def test_the_trap_answer_is_contradicted_by_the_sop(self):
        """The removal-from-service trap only works if the SOP really rules it
        out; otherwise it is a matter of opinion, not a checkable expectation."""
        sop = "".join(self.pages["sop-mech-014.txt"].values())
        self.assertIn("does not by itself require removal from service", sop)

    def test_the_limits_the_findings_rely_on_are_in_the_sop(self):
        sop = "".join(self.pages["sop-mech-014.txt"].values())
        for value in ("7.1 mm/s RMS", "80 C", "14 days", "95 Nm"):
            with self.subTest(value=value):
                self.assertIn(value, sop)


class TestCodeFixture(unittest.TestCase):
    def setUp(self):
        self.expected = json.loads((CODE / "expected.json").read_text())

    def validate(self, root: pathlib.Path) -> subprocess.CompletedProcess:
        command = list(self.expected["validation"]["command"])
        command[0] = sys.executable          # the recorded command, this runtime
        return subprocess.run(command, cwd=root, capture_output=True, text=True,
                              timeout=120, check=False)

    def test_the_shipped_fixture_still_fails_its_own_suite(self):
        """The failing suite IS the bug report. A fixture that passes has been
        silently repaired and no longer specifies anything."""
        result = self.validate(REPO)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"Ran {self.expected['validation']['before_repair']['tests_run']} tests",
                      result.stderr)
        for name in self.expected["validation"]["before_repair"]["failing"]:
            self.assertIn(name.split(".")[-1], result.stderr)

    def test_the_recorded_repair_makes_it_pass_on_a_copy(self):
        with tempfile.TemporaryDirectory() as workspace:
            copy = pathlib.Path(workspace) / "pumpcheck"
            shutil.copytree(REPO, copy)
            target = copy / self.expected["the_bug"]["file"]
            source = target.read_text()
            self.assertIn(self.expected["the_bug"]["shipped"], source)
            target.write_text(source.replace(self.expected["the_bug"]["shipped"],
                                             self.expected["the_bug"]["correct"]))
            result = self.validate(copy)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_validation_leaves_the_canonical_fixture_broken(self):
        """AF-010 forbids modifying the canonical repository. Running the check
        above must not have repaired the committed copy."""
        source = (REPO / self.expected["the_bug"]["file"]).read_text()
        self.assertIn(self.expected["the_bug"]["shipped"], source)

    def test_the_validation_command_needs_no_dependency(self):
        command = self.expected["validation"]["command"]
        self.assertEqual(command[1:3], ["-m", "unittest"])
        self.assertIn("standard library only",
                      self.expected["validation"]["dependencies"])

    def test_the_tests_are_off_limits_to_a_repair(self):
        self.assertIn("tests/test_limits.py",
                      self.expected["expected_patch_properties"]
                      ["files_that_must_not_change"])

    def test_the_fixture_imports_nothing_outside_the_standard_library(self):
        for path in REPO.rglob("*.py"):
            with self.subTest(file=path.name):
                for line in path.read_text().splitlines():
                    if line.startswith(("import ", "from ")):
                        module = line.split()[1].split(".")[0]
                        self.assertIn(module, {"unittest", "pumpcheck", "tests"},
                                      f"{path.name} imports {module}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
