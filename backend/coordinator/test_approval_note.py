"""The fixed grounded workflow: inspection report + SOP -> approval note.

This is Refinix's hero Documents story, and the thing that separates it from an
ordinary generated document is not its prose — it is that every material claim
has to be traceable to a page that was actually supplied.

Two different guarantees are checked here and they must not be confused:

* **the file is well formed** — one JSON object, matching the note's shape.
  Batch 3 gave this route the same runtime-enforced schema the general document
  already had, because it was still asking for JSON in prose alone;
* **the claims are grounded** — every finding cites a document that was
  selected for this request, at a page that exists and was sent to the model.
  A syntactically perfect note that cites a document nobody attached must still
  fail, and a valid DOCX proves nothing about either.

The C07 pack supplies the real material. The text report is used rather than the
scan so extraction is deterministic without a vision model; the scan's own path
is covered in `test_pdfrender` and `test_ocr`.

    python3 -m unittest backend.coordinator.test_approval_note -v
"""

from __future__ import annotations

import json
import pathlib
import unittest
from unittest.mock import patch

from backend.coordinator import db, docflow, docgen, retrieval, runtime
from backend.coordinator.test_document_generation import scripted_stream
from backend.coordinator.test_execution4a import Harness

C07 = pathlib.Path(__file__).resolve().parents[2] / "fixtures/c07/documents"
REPORT = C07 / "inspection-report.txt"
SOP = C07 / "sop-mech-014.txt"

# What the model is scripted to return. Grounded on purpose: the citations name
# sources and pages the test actually supplies, and the unresolved list keeps
# the one value the report says was never recorded.
def grounded_note(report_id, sop_id=None, *, findings=None, unresolved=None,
                  report_page=1, sop_page=1):
    cited = [{"source_id": report_id, "page": report_page}]
    if sop_id:
        cited.append({"source_id": sop_id, "page": sop_page})
    return json.dumps({
        "title": "Approval note — transfer pump P-204",
        "summary": {
            "text": ("Routine mechanical inspection NG-2026-0417 of transfer "
                     "pump P-204 recorded a drive-end vibration above the "
                     "alarm limit and two loose baseplate anchor bolts."),
            "citations": cited},
        "findings": findings if findings is not None else [
            {"text": ("Drive-end vibration was recorded at 7.9 mm/s RMS "
                      "against an alarm limit of 7.1 mm/s RMS."),
             "citations": cited},
            {"text": "Two of four baseplate anchor bolts were found loose.",
             "citations": [{"source_id": report_id, "page": report_page}]},
        ],
        "recommendation": {
            "text": ("The pump remains in service pending corrective action. "
                     "Re-inspection is required within 14 days."),
            "citations": cited},
        "unresolved": unresolved if unresolved is not None else [
            "Suction pressure was not recorded and could not be verified.",
        ],
    })


class GroundedHarness(Harness):
    """A real coordinator holding the C07 report and its procedure."""

    def setUp(self):
        super().setUp()
        if not REPORT.exists() or not SOP.exists():
            self.skipTest("the C07 document fixtures are not present")

    def attach_pack(self, *, with_sop=True):
        """The report first, then the procedure — the order the workflow reads
        as "report, then references"."""
        report = self.attach("inspection-report.txt", REPORT.read_bytes())
        sources = [report]
        if with_sop:
            sources.append(self.attach("sop-mech-014.txt", SOP.read_bytes()))
        return sources

    def run_workflow(self, *replies, with_sop=True, done_reasons=("stop",),
                     request="draft the approval note"):
        sources = self.attach_pack(with_sop=with_sop)
        job = self.send(request, skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        for record in sources:
            self.bind(job, record)
        stream = scripted_stream(*replies, done_reasons=done_reasons)
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        return job, stream, sources

    def source_ids(self, job):
        _message_id, attachments = self.c._request_sources(self.chat, job)
        return [a["attachment_id"] for a in attachments]

    def job_state(self, job):
        return self.c.conn.execute(
            "SELECT state FROM jobs WHERE job_id=?", (job,)).fetchone()["state"]

    def artifact_text(self):
        rows = self.artifacts()
        self.assertEqual(len(rows), 1, "exactly one artifact was expected")
        root = db.artifacts_root(self.c.state_path)
        return "\n".join(docgen.read_text(root / rows[0]["stored_name"])), rows[0]


# ---------------------------------------------------------------------------
# The hero path, end to end
# ---------------------------------------------------------------------------

class HeroWorkflow(GroundedHarness):
    """Report + SOP -> extraction -> retrieval -> note -> citations -> DOCX."""

    def prepared_ids(self, job):
        ids = self.source_ids(job)
        self.assertEqual(len(ids), 2, "report and procedure are both selected")
        return ids

    def run_hero(self):
        report = self.attach("inspection-report.txt", REPORT.read_bytes())
        sop = self.attach("sop-mech-014.txt", SOP.read_bytes())
        job = self.send("draft the approval note", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        self.bind(job, report)
        self.bind(job, sop)
        reply = grounded_note(report["attachment_id"], sop["attachment_id"])
        stream = scripted_stream(reply)
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        return job, stream, report, sop

    def test_the_workflow_completes_and_records_its_identity(self):
        job, stream, _report, _sop = self.run_hero()
        self.assertEqual(self.job_state(job), "completed")
        self.assertEqual(stream.calls, 1, "a grounded reply needs no repair")
        _text, row = self.artifact_text()
        self.assertEqual(row["workflow"], docflow.WORKFLOW_APPROVAL_NOTE)
        self.assertEqual(row["job_id"], job, "the artifact names its origin job")
        self.assertTrue(row["sha256"], "the artifact records a checksum")

    def test_the_report_and_the_procedure_stay_distinct_sources(self):
        job, stream, report, sop = self.run_hero()
        prompt = stream.messages[0][-1]["content"]
        self.assertIn(report["attachment_id"], prompt)
        self.assertIn(sop["attachment_id"], prompt)
        self.assertNotEqual(report["attachment_id"], sop["attachment_id"])
        text, _row = self.artifact_text()
        self.assertIn("inspection-report.txt", text)
        self.assertIn("sop-mech-014.txt", text)

    def test_the_report_reaches_the_model_with_its_pages(self):
        _job, stream, _report, _sop = self.run_hero()
        prompt = stream.messages[0][-1]["content"]
        for marker in ("7.9", "7.1", "anchor bolts"):
            self.assertIn(marker, prompt)

    def test_every_citation_in_the_finished_note_resolves(self):
        job, _stream, _report, _sop = self.run_hero()
        row = self.artifacts()[0]
        citations = json.loads(row["citations_json"])
        self.assertTrue(citations, "a grounded note records its citations")
        selected = set(self.source_ids(job))
        for citation in citations:
            self.assertIn(citation["source_id"], selected)
            self.assertIn("page", citation)

    def test_the_artifact_reopens_and_reads_back(self):
        self.run_hero()
        row = self.artifacts()[0]
        path = db.artifacts_root(self.c.state_path) / row["stored_name"]
        self.assertTrue(docgen.validate(path)["readable"])

    def test_the_source_hashes_travel_into_the_artifact(self):
        self.run_hero()
        text, _row = self.artifact_text()
        for record in self.c.conn.execute(
                "SELECT sha256 FROM attachments WHERE chat_id=?", (self.chat,)):
            self.assertIn(record["sha256"][:16], text)

    def test_report_identity_is_preserved_without_asking_the_model(self):
        self.run_hero()
        text, _row = self.artifact_text()
        for expected in ("Report details", "Report number: NG-2026-0417",
                         "Inspection date: 2026-04-17",
                         "Inspector: A. Okonkwo"):
            self.assertIn(expected, text)

    def test_explicit_open_report_evidence_cannot_be_omitted(self):
        """The scripted model omits the countersignature. The coordinator's
        exact report evidence still has to reach the artifact."""
        self.run_hero()
        text, _row = self.artifact_text()
        self.assertIn("Open items recorded in the report", text)
        self.assertIn("Torque not recorded", text)
        self.assertIn("Countersigned: not countersigned at time of issue", text)

    # -- the C07 facts that must survive ----------------------------------

    def test_the_reading_and_the_alarm_limit_stay_different_numbers(self):
        """7.9 is what the pump did; 7.1 is what it was allowed to do."""
        self.run_hero()
        text, _row = self.artifact_text()
        self.assertIn("7.9", text)
        self.assertIn("7.1", text)

    def test_the_loose_bolts_survive_into_the_note(self):
        self.run_hero()
        text, _row = self.artifact_text()
        self.assertIn("anchor bolts", text.lower())

    def test_the_reinspection_requirement_survives(self):
        self.run_hero()
        text, _row = self.artifact_text()
        self.assertIn("14 days", text)

    def test_the_unrecorded_suction_pressure_stays_unresolved(self):
        self.run_hero()
        text, _row = self.artifact_text()
        self.assertIn("Not established by these documents", text)
        self.assertIn("Suction pressure", text)

    def test_no_suction_pressure_value_is_invented(self):
        """The report says NOT RECORDED. Nothing downstream may supply a bar
        figure for it."""
        self.run_hero()
        text, _row = self.artifact_text()
        suction = [line for line in text.splitlines()
                   if "suction" in line.lower()]
        self.assertTrue(suction)
        for line in suction:
            self.assertNotIn("bar", line.lower(),
                             f"a suction pressure value appeared: {line!r}")


class PageAssociation(GroundedHarness):
    """A three-page scan, so page identity is exercised rather than assumed.

    The C07 text report extracts as a single page — the `--- PAGE n ---`
    markers are a fixture convention, not something plain-text extraction
    honours — so a stub stands in for the scan's three pages. It mirrors what
    `ocr.extract_pdf` returns for the real PDF, which is covered for real in
    `test_pdfrender` and `test_ocr`.
    """

    SCAN_PAGES = [
        (1, "ROUTINE MECHANICAL INSPECTION\nReport number: NG-2026-0417\n"
            "Asset: Transfer pump P-204\nInspection date: 2026-04-17\n"
            "Inspector: A. Okonkwo\nBaseplate anchor bolts: Two of four "
            "found loose. Torque not recorded.\nSuction pressure gauge: "
            "Illegible; reading could not be taken."),
        (2, "Vibration drive end 7.9 MM/S RMS. Non-drive end 4.1 MM/S RMS.\n"
            "Suction pressure: NOT RECORDED (gauge illegible).\n"
            "Vibration alarm limit: 7.1 MM/S RMS."),
        (3, "Pump remains in service pending corrective action. "
            "Re-inspection required within 14 days.\n"
            "Countersigned: not countersigned at time of issue"),
    ]

    def fake_extraction(self, source_id, filename, sha256):
        class Fake:
            @staticmethod
            def as_dict():
                return {"source_id": source_id, "filename": filename,
                        "media_type": "application/pdf", "sha256": sha256,
                        "byte_size": 1234, "page_count": 3,
                        "method": "pdf render (pypdfium2) + vision (stub)",
                        "uncertain": ["Read by a local vision model."],
                        "pages": [{"number": n, "text": text,
                                   "confidence": None, "note": None}
                                  for n, text in self.SCAN_PAGES]}
        return Fake

    def run_scan(self, note_builder):
        record = self.attach("inspection-report-scan.pdf", b"%PDF-1.4 stub")
        job = self.send("draft the approval note", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        self.bind(job, record)
        source_id = record["attachment_id"]
        full = db.attachment_record(self.c.conn, source_id, self.c.workspace_id)
        fake = self.fake_extraction(source_id, full["filename"], full["sha256"])
        stream = scripted_stream(note_builder(source_id))
        with patch.object(docflow.documents, "extract",
                          return_value=fake), \
                patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        return job, stream, source_id

    def test_every_page_of_the_scan_reaches_the_model(self):
        _job, stream, _sid = self.run_scan(lambda sid: grounded_note(sid))
        prompt = stream.messages[0][-1]["content"]
        for marker in ("7.9", "7.1", "NOT RECORDED", "anchor bolts",
                       "14 days"):
            self.assertIn(marker, prompt)

    def test_a_citation_to_a_later_page_resolves(self):
        job, _stream, sid = self.run_scan(
            lambda s: grounded_note(s, report_page=3))
        self.assertEqual(self.job_state(job), "completed")
        citations = json.loads(self.artifacts()[0]["citations_json"])
        self.assertIn(3, [c["page"] for c in citations])

    def test_a_citation_beyond_the_last_page_is_refused(self):
        job, _stream, _sid = self.run_scan(
            lambda s: grounded_note(s, report_page=4))
        self.assertEqual(self.job_state(job), "failed")
        self.assertEqual(self.artifacts(), [])

    def test_the_page_a_finding_cites_is_recorded_with_it(self):
        """Page identity survives into the artifact, not just into the prompt."""
        self.run_scan(lambda s: grounded_note(s, report_page=2))
        text, _row = self.artifact_text()
        self.assertIn("p.2", text)

    def test_the_renderer_provenance_survives_into_the_artifact(self):
        self.run_scan(lambda s: grounded_note(s))
        text, _row = self.artifact_text()
        self.assertIn("pypdfium2", text)

    def test_scan_report_details_and_open_items_keep_their_pages(self):
        self.run_scan(lambda s: grounded_note(s))
        text, _row = self.artifact_text()
        self.assertIn("Report number: NG-2026-0417", text)
        self.assertIn("Countersigned: not countersigned at time of issue", text)
        self.assertIn("p.3", text)

    def test_coordinator_evidence_is_bounded_before_it_reenters_the_prompt(self):
        source = {"source_id": "report", "filename": "report.pdf"}
        pages = [{"number": 1,
                  "text": ("Report number: " + "R" * 500 + "\n"
                           + "Missing field: not recorded " + "x" * 500)}]
        details, open_items = docflow.report_evidence(source, pages)
        self.assertLessEqual(len(details[0]["text"]),
                             docflow.MAX_REPORT_EVIDENCE_CHARS)
        self.assertLessEqual(len(open_items[0]["text"]),
                             docflow.MAX_REPORT_EVIDENCE_CHARS)


class TheWorkflowTheRequestAsksForIsTheOneThatRuns(GroundedHarness):
    """Same files, same words, different `doc_workflow` — different route.

    The composer now offers this choice, and a real run proved why it has to be
    the choice rather than the wording: an inspection report, an SOP and a
    plain-English request for "a grounded inspection approval note" produced a
    general document, because nothing selected the fixed workflow. These drive
    `submit`, so the value travels the way the page sends it.
    """

    REQUEST = ("Create a grounded inspection approval note using the "
               "inspection report and SOP. Preserve unresolved values and "
               "cite the supporting evidence.")

    def run_with(self, workflow, reply_for):
        sources = self.attach_pack()
        job = self.send(self.REQUEST, skill_id=docflow.WRITE_SKILL,
                        doc_workflow=workflow)
        for record in sources:
            self.bind(job, record)
        stream = scripted_stream(reply_for([s["attachment_id"] for s in sources]))
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        return job, stream

    def test_the_approval_note_value_reaches_the_grounded_branch(self):
        job, stream = self.run_with(
            docflow.WORKFLOW_APPROVAL_NOTE,
            lambda ids: grounded_note(ids[0], ids[1]))
        self.assertEqual(self.job_state(job), "completed")
        row = self.artifacts()[0]
        self.assertEqual(row["workflow"], docflow.WORKFLOW_APPROVAL_NOTE)
        self.assertTrue(json.loads(row["citations_json"]),
                        "the grounded route records resolved citations")
        # The prompt is the note's, not the general document's.
        system = stream.messages[0][0]["content"]
        self.assertIn("approval note", system)
        self.assertEqual(stream.formats[0], docflow.APPROVAL_NOTE_FORMAT)

    def test_the_same_request_without_the_value_takes_the_general_route(self):
        """The failure that prompted the change: identical wording, general
        document, and the reply says so."""
        job, stream = self.run_with(
            docflow.WORKFLOW_GENERAL,
            lambda _ids: json.dumps({"title": "Approval note", "sections": [
                {"heading": "Findings", "paragraphs": ["Vibration was high."]}]}))
        self.assertEqual(self.job_state(job), "completed")
        row = self.artifacts()[0]
        self.assertEqual(row["workflow"], docflow.WORKFLOW_GENERAL)
        self.assertEqual(json.loads(row["citations_json"] or "[]"), [])
        self.assertEqual(stream.formats[0], docflow.GENERAL_DOCUMENT_FORMAT)

    def test_the_general_route_says_it_makes_no_page_citations(self):
        """The sentence the requester saw was accurate; it was the route that
        was wrong. It must keep appearing there and nowhere else."""
        self.run_with(
            docflow.WORKFLOW_GENERAL,
            lambda _ids: json.dumps({"title": "T", "sections": [
                {"heading": "H", "paragraphs": ["p"]}]}))
        self.assertIn("no page citations", self.last_answer())

    def test_the_grounded_route_never_says_it_makes_no_page_citations(self):
        self.run_with(docflow.WORKFLOW_APPROVAL_NOTE,
                      lambda ids: grounded_note(ids[0], ids[1]))
        self.assertNotIn("no page citations", self.last_answer())

    def test_an_unknown_workflow_value_is_refused_at_the_boundary(self):
        """The page can only send what the backend accepts, so the two lists
        cannot drift into a silently ignored value."""
        from backend.coordinator.server import RequestError
        with self.assertRaises(RequestError):
            with patch("backend.coordinator.server.threading.Thread.start"):
                self.c.submit(self.chat, "draft it",
                              skill_id=docflow.WRITE_SKILL,
                              doc_workflow="not_a_real_workflow")


# ---------------------------------------------------------------------------
# Grounding — the checks that make it a grounded note rather than a document
# ---------------------------------------------------------------------------

class CitationGrounding(unittest.TestCase):
    """`parse_approval_note` against the sources actually supplied."""

    REPORT = "src-report"
    SOP = "src-sop"

    def sources(self, *, with_sop=True):
        supplied = [{"source_id": self.REPORT, "filename": "report.txt",
                     "pages": [{"number": 1}, {"number": 2}],
                     "page_count": 2, "sha256": "a" * 64, "method": "text",
                     "uncertain": []}]
        if with_sop:
            supplied.append({"source_id": self.SOP, "filename": "sop.txt",
                             "pages": [{"number": 1}], "page_count": 1,
                             "sha256": "b" * 64, "method": "text",
                             "uncertain": []})
        return supplied

    def parse(self, reply, *, with_sop=True):
        return docflow.parse_approval_note(reply, self.sources(with_sop=with_sop))

    def code_for(self, reply, **kwargs):
        with self.assertRaises(docflow.WorkflowError) as caught:
            self.parse(reply, **kwargs)
        return caught.exception.code

    def test_a_grounded_note_is_accepted(self):
        note = self.parse(grounded_note(self.REPORT, self.SOP, report_page=2))
        self.assertEqual(len(note["findings"]), 2)
        self.assertTrue(all(f["citations"] for f in note["findings"]))

    def test_an_invented_source_is_refused(self):
        self.assertEqual(
            self.code_for(grounded_note("src-nobody-attached")),
            "unresolved_citation")

    def test_a_citation_to_an_unselected_source_is_refused(self):
        """The SOP exists on the computer but was not selected for this
        request, so it cannot ground anything in it."""
        self.assertEqual(
            self.code_for(grounded_note(self.REPORT, self.SOP), with_sop=False),
            "unresolved_citation")

    def test_a_page_that_does_not_exist_is_refused(self):
        reply = json.dumps(json.loads(grounded_note(self.REPORT)) | {
            "findings": [{"text": "A claim about page ninety.",
                          "citations": [{"source_id": self.REPORT, "page": 90}]}]})
        self.assertEqual(self.code_for(reply), "unresolved_citation")

    def test_a_finding_with_no_citation_is_refused(self):
        reply = json.dumps(json.loads(grounded_note(self.REPORT)) | {
            "findings": [{"text": "The pump is fine.", "citations": []}]})
        self.assertEqual(self.code_for(reply), "bad_citations")

    def test_a_malformed_citation_is_refused_not_quietly_dropped(self):
        """The dangerous outcome is keeping the claim and losing the citation:
        an unsupported sentence that reads as though it were checked."""
        reply = json.dumps(json.loads(grounded_note(self.REPORT)) | {
            "findings": [{"text": "Vibration exceeded the limit.",
                          "citations": ["report page 2"]}]})
        self.assertEqual(self.code_for(reply), "bad_citations")

    def test_an_unsupported_conclusion_still_needs_a_resolvable_citation(self):
        """Nothing here reads the sentence. What stops "inspection passed" from
        being filed as grounded is that it must cite a supplied page, and a
        fabricated one is refused — so the claim cannot arrive uncited."""
        for claim in ("The equipment is safe and approved for operation.",
                      "All readings are within limits.",
                      "The pump is fully compliant with SOP-MECH-014.",
                      "Inspection passed; no further action required."):
            with self.subTest(claim=claim):
                uncited = json.dumps(json.loads(grounded_note(self.REPORT)) | {
                    "findings": [{"text": claim, "citations": []}]})
                self.assertEqual(self.code_for(uncited), "bad_citations")
                invented = json.dumps(json.loads(grounded_note(self.REPORT)) | {
                    "findings": [{"text": claim,
                                  "citations": [{"source_id": "src-made-up",
                                                 "page": 1}]}]})
                self.assertEqual(self.code_for(invented), "unresolved_citation")

    def test_a_note_with_no_findings_at_all_is_refused(self):
        """Found in self-review. Every finding needing a citation is worth
        nothing if a note may have no findings: the summary and recommendation
        are free text, so an approval note citing *nothing* would have passed
        the grounded workflow."""
        cite = [{"source_id": self.REPORT, "page": 1}]
        reply = json.dumps({
            "title": "Approval note",
            "summary": {"text": "The pump was inspected.", "citations": cite},
            "findings": [],
            "recommendation": {"text": "Approved for continued operation.",
                               "citations": cite},
            "unresolved": []})
        self.assertEqual(self.code_for(reply), "ungrounded_note")

    def test_a_note_that_established_nothing_may_say_so(self):
        """The one legitimate empty-findings case, and it has to be explicit."""
        cite = [{"source_id": self.REPORT, "page": 1}]
        reply = json.dumps({
            "title": "Approval note",
            "summary": {"text": "The scan could not be read.",
                        "citations": cite},
            "findings": [],
            "recommendation": {"text": "Re-scan the report and repeat the "
                                       "inspection.", "citations": cite},
            "unresolved": ["Nothing in the report was legible."]})
        note = self.parse(reply)
        self.assertEqual(note["findings"], [])
        self.assertEqual(len(note["unresolved"]), 1)

    def test_an_ungrounded_note_is_never_repaired(self):
        """Repairing it would ask the model to invent the findings it did not
        make."""
        self.assertNotIn("ungrounded_note", docflow.REPAIRABLE_CODES)

    # -- the summary and the recommendation answer for themselves -----------

    def claim(self, field, text, citations):
        return json.dumps(json.loads(grounded_note(self.REPORT)) | {
            field: {"text": text, "citations": citations}})

    def test_an_unsupported_consequential_recommendation_is_refused(self):
        """The case that stayed open after Batch 3: the finding is grounded,
        the conclusion is not, and the note passed on the finding's citation."""
        reply = self.claim(
            "recommendation",
            "Equipment is fully compliant and approved for unrestricted "
            "continued operation.", [])
        self.assertEqual(self.code_for(reply), "bad_citations")

    def test_a_grounded_recommendation_is_accepted(self):
        reply = self.claim("recommendation",
                           "Re-inspection is required within 14 days.",
                           [{"source_id": self.REPORT, "page": 2}])
        note = self.parse(reply)
        self.assertTrue(note["recommendation"]["citations"])

    def test_an_unsupported_summary_is_refused(self):
        reply = self.claim("summary",
                           "All inspected conditions are satisfactory.", [])
        self.assertEqual(self.code_for(reply), "bad_citations")

    def test_a_recommendation_citation_goes_through_the_same_resolver(self):
        for citations, expected in (
                ([{"source_id": self.SOP, "page": 1}], "unresolved_citation"),
                ([{"source_id": self.REPORT, "page": 90}], "unresolved_citation"),
                ([{"source_id": "src-invented", "page": 1}], "unresolved_citation")):
            with self.subTest(citations=citations):
                reply = self.claim("recommendation", "Approved.", citations)
                self.assertEqual(self.code_for(reply, with_sop=False), expected)

    def test_every_claim_reaches_the_recorded_citation_list(self):
        """The artifact record must show what supported the conclusion, not
        only what supported the findings."""
        note = self.parse(grounded_note(self.REPORT, self.SOP, report_page=2))
        pairs = {(c["source_id"], c["page"]) for c in docflow.citation_list(note)}
        self.assertIn((self.SOP, 1), pairs)
        self.assertIn((self.REPORT, 2), pairs)

    def test_an_unsupported_claim_is_never_repaired_into_shape(self):
        """Adding a citation is substance, not format."""
        self.assertNotIn("bad_claim", docflow.REPAIRABLE_CODES)
        self.assertNotIn("bad_citations", docflow.REPAIRABLE_CODES)

    def test_the_boundary_a_resolvable_citation_does_not_check_the_sentence(self):
        """Recorded deliberately, because it is what this contract does NOT do.

        Grounding here is traceability: the claim must point at a page that was
        supplied. Nothing compares the sentence against that page, so a finding
        that swaps the reading for the limit is accepted when it cites a real
        page. What the contract removes is the *uncited* and the *fabricated*
        claim — the two ways an unsupported sentence could arrive looking
        checked. Closing this gap needs claim-level verification the current
        architecture does not have, and pretending otherwise in a test would be
        worse than saying so here.
        """
        swapped = json.dumps(json.loads(grounded_note(self.REPORT)) | {
            "findings": [{"text": ("The alarm limit is 7.9 mm/s RMS and the "
                                   "reading was 7.1 mm/s RMS."),
                          "citations": [{"source_id": self.REPORT, "page": 1}]}]})
        note = self.parse(swapped)
        self.assertEqual(len(note["findings"]), 1)
        self.assertTrue(note["findings"][0]["citations"],
                        "it is accepted, and it is traceable to the page a "
                        "reviewer must check")

    def test_a_compliance_claim_cannot_cite_a_procedure_never_supplied(self):
        reply = json.dumps(json.loads(grounded_note(self.REPORT)) | {
            "findings": [{"text": "Verified against SOP-MECH-014.",
                          "citations": [{"source_id": self.SOP, "page": 1}]}]})
        self.assertEqual(self.code_for(reply, with_sop=False),
                         "unresolved_citation")


# ---------------------------------------------------------------------------
# The production call boundary and the repair
# ---------------------------------------------------------------------------

class ApprovalCallContract(GroundedHarness):
    def test_the_note_call_enforces_its_own_schema_and_budget(self):
        report = self.attach("inspection-report.txt", REPORT.read_bytes())
        job = self.send("draft the approval note", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        self.bind(job, report)
        stream = scripted_stream(grounded_note(report["attachment_id"]))
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        self.assertEqual(stream.formats[0], docflow.APPROVAL_NOTE_FORMAT)
        self.assertEqual(stream.budgets[0], docflow.APPROVAL_NUM_PREDICT)

    def test_the_budget_covers_a_maximal_note_inside_the_context(self):
        self.assertGreater(docflow.APPROVAL_NUM_PREDICT, runtime.NUM_PREDICT)
        worst_prompt = docflow.MAX_CONTEXT_CHARS // 4
        self.assertLess(worst_prompt + docflow.APPROVAL_NUM_PREDICT,
                        runtime.NUM_CTX)

    def test_the_enforced_schema_matches_what_the_parser_accepts(self):
        schema = docflow.APPROVAL_NOTE_FORMAT
        self.assertEqual(
            set(schema["required"]),
            {"title", "summary", "findings", "recommendation", "unresolved"})
        citation = (schema["properties"]["findings"]["items"]
                    ["properties"]["citations"]["items"])
        self.assertEqual(set(citation["required"]), {"source_id", "page"})
        self.assertEqual(citation["properties"]["page"]["type"], "integer")
        self.assertFalse(citation["additionalProperties"])


class ApprovalRepair(GroundedHarness):
    def fenced(self, report_id, sop_id=None):
        return "```json\n" + grounded_note(report_id, sop_id) + "\n```"

    def test_a_wrapped_but_unchanged_note_is_repaired_once_and_accepted(self):
        sources = self.attach_pack()
        job = self.send("draft the approval note", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        for record in sources:
            self.bind(job, record)
        ids = [s["attachment_id"] for s in sources]
        stream = scripted_stream(self.fenced(*ids), grounded_note(*ids))
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        self.assertEqual(stream.calls, 2)
        self.assertEqual(self.job_state(job), "completed")
        self.assertEqual(self.artifacts()[0]["workflow"],
                         docflow.WORKFLOW_APPROVAL_NOTE)

    def test_a_repair_that_changes_a_citation_is_still_refused(self):
        """The instruction forbids it; validation is what enforces it. The
        repaired note meets the same sources, so a swapped or invented citation
        fails exactly as it would have the first time."""
        sources = self.attach_pack()
        job = self.send("draft the approval note", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        for record in sources:
            self.bind(job, record)
        ids = [s["attachment_id"] for s in sources]
        stream = scripted_stream(self.fenced(*ids),
                                 grounded_note("src-invented-during-repair"))
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        self.assertEqual(stream.calls, 2)
        self.assertEqual(self.job_state(job), "failed")
        self.assertEqual(self.artifacts(), [])
        self.assertEqual(self.artifact_files(), [])

    def test_the_repair_never_resends_the_report_or_the_procedure(self):
        """A model holding the evidence again could redraft a finding or pick a
        different citation and still pass, because the new citation resolves."""
        sources = self.attach_pack()
        job = self.send("draft the approval note", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        for record in sources:
            self.bind(job, record)
        ids = [s["attachment_id"] for s in sources]
        stream = scripted_stream(self.fenced(*ids), grounded_note(*ids))
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        repair = "\n".join(m["content"] for m in stream.messages[1])
        # Markers that appear only in the raw fixtures, never in the note the
        # model wrote — so their absence proves the evidence was not resent
        # rather than merely that the wording differs.
        for marker in ("SYNTHETIC INSPECTION REPORT", "Northgate",
                       "ACCEPTANCE LIMITS", "SOP-MECH-014 rev 3",
                       "--- PAGE 2 ---", "SOP PASSAGES", "DOCUMENT"):
            self.assertNotIn(marker, repair,
                             f"the repair was handed the evidence again: {marker!r}")
        # What it *does* carry is the note it is repairing.
        self.assertIn("Two of four baseplate anchor bolts", repair)

    def test_the_repair_instruction_forbids_touching_substance(self):
        text = docflow.APPROVAL_REPAIR_INSTRUCTION
        for rule in ("Do not add or remove a finding",
                     "never replace one with a different source or page",
                     "Do not supply a measurement",
                     "Do not move anything out of the unresolved list"):
            self.assertIn(rule, text)

    def test_a_grounding_failure_is_never_repaired(self):
        """An unresolved citation is not a format problem. Asking again would
        invite the model to swap it for one that happens to resolve."""
        self.assertNotIn("unresolved_citation", docflow.REPAIRABLE_CODES)
        self.assertNotIn("bad_citations", docflow.REPAIRABLE_CODES)

    def test_a_truncated_repair_writes_nothing(self):
        sources = self.attach_pack()
        job = self.send("draft the approval note", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        for record in sources:
            self.bind(job, record)
        ids = [s["attachment_id"] for s in sources]
        stream = scripted_stream(self.fenced(*ids), grounded_note(*ids)[:50],
                                 done_reasons=("stop", "length"))
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        self.assertEqual(self.job_state(job), "failed")
        self.assertEqual(self.artifacts(), [])
        self.assertEqual(self.artifact_files(), [])

    def test_a_truncated_first_reply_is_refused_before_any_repair(self):
        sources = self.attach_pack()
        job = self.send("draft the approval note", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        for record in sources:
            self.bind(job, record)
        ids = [s["attachment_id"] for s in sources]
        stream = scripted_stream(grounded_note(*ids)[:50], grounded_note(*ids),
                                 done_reasons=("length", "stop"))
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        self.assertEqual(stream.calls, 1)
        self.assertEqual(self.job_state(job), "failed")
        self.assertEqual(self.artifacts(), [])


# ---------------------------------------------------------------------------
# Retrieval scope
# ---------------------------------------------------------------------------

class RetrievalScope(GroundedHarness):
    def test_retrieval_returns_the_procedure_passage_it_was_asked_for(self):
        job, _stream, sources = self.run_workflow(
            grounded_note("unused"), request="vibration alarm limit")
        sop_id = sources[1]["attachment_id"]
        passages = retrieval.search(
            self.c.conn, workspace_id=self.c.workspace_id,
            source_ids=[sop_id], question="vibration alarm limit")
        self.assertTrue(passages, "the procedure has a matching passage")
        for passage in passages:
            self.assertEqual(passage.source_id, sop_id)
            self.assertTrue(passage.citation)
            self.assertIsInstance(passage.page, int)

    def test_retrieval_never_reaches_a_source_it_was_not_given(self):
        _job, _stream, sources = self.run_workflow(
            grounded_note("unused"), request="vibration alarm limit")
        report_id, sop_id = (s["attachment_id"] for s in sources)
        passages = retrieval.search(
            self.c.conn, workspace_id=self.c.workspace_id,
            source_ids=[sop_id], question="vibration")
        self.assertNotIn(report_id, {p.source_id for p in passages})

    def test_no_match_returns_nothing_rather_than_an_invented_passage(self):
        _job, _stream, sources = self.run_workflow(
            grounded_note("unused"), request="draft the approval note")
        sop_id = sources[1]["attachment_id"]
        passages = retrieval.search(
            self.c.conn, workspace_id=self.c.workspace_id,
            source_ids=[sop_id], question="zzzqqq nonexistent terminology")
        self.assertEqual(passages, [])


# ---------------------------------------------------------------------------
# The optional procedure
# ---------------------------------------------------------------------------

class WithoutAProcedure(GroundedHarness):
    """The contract says the reference corpus is optional. What it must never
    do is let an uncited-against-procedure note read as though one was used."""

    def run_report_only(self):
        report = self.attach("inspection-report.txt", REPORT.read_bytes())
        job = self.send("draft the approval note", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        self.bind(job, report)
        stream = scripted_stream(grounded_note(report["attachment_id"]))
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        return job, stream, report

    def test_a_report_on_its_own_still_produces_a_grounded_note(self):
        job, _stream, _report = self.run_report_only()
        self.assertEqual(self.job_state(job), "completed")
        self.assertEqual(self.artifacts()[0]["workflow"],
                         docflow.WORKFLOW_APPROVAL_NOTE)

    def test_the_artifact_says_no_procedure_was_compared_against(self):
        self.run_report_only()
        text, _row = self.artifact_text()
        self.assertIn("Procedure comparison", text)
        self.assertIn("No reference or procedure passage was used", text)

    def test_no_procedure_is_invented_in_the_sources(self):
        self.run_report_only()
        text, _row = self.artifact_text()
        # The report itself names the standard it says was applied, and the
        # traceability block must preserve that fact. What must not appear is
        # a procedure *file* or a quoted procedure passage Refinix never read.
        self.assertIn("Inspection standard: SOP-MECH-014 rev 3", text)
        self.assertNotIn("sop-mech-014.txt", text.lower())
        self.assertNotIn("Passages used", text)

    def test_a_note_with_a_procedure_does_not_carry_the_disclaimer(self):
        report = self.attach("inspection-report.txt", REPORT.read_bytes())
        sop = self.attach("sop-mech-014.txt", SOP.read_bytes())
        job = self.send("vibration alarm limit", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        self.bind(job, report)
        self.bind(job, sop)
        stream = scripted_stream(grounded_note(report["attachment_id"],
                                               sop["attachment_id"]))
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        text, _row = self.artifact_text()
        self.assertIn("Passages used", text)
        self.assertNotIn("No reference or procedure passage was used", text)


if __name__ == "__main__":
    unittest.main()
