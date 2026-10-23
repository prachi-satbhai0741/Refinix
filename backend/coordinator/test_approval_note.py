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

import ast
import json
import pathlib
import unittest
from unittest.mock import patch

from backend.coordinator import context, db, docflow, docgen, retrieval, runtime
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


def conditioned_note(report_id, sop_id=None, *, report_page=1, sop_page=1):
    """The same evidence as `grounded_note`, stated the way an unestablished
    reference allows: the supplied procedure's value is reported as a fact
    about that file, and nothing is judged settled against it."""
    cited = [{"source_id": report_id, "page": report_page}]
    if sop_id:
        cited.append({"source_id": sop_id, "page": sop_page})
    return json.dumps({
        "title": "Approval note — transfer pump P-204",
        "summary": {
            "text": ("Routine mechanical inspection NG-2026-0417 of transfer "
                     "pump P-204 recorded a drive-end vibration of 7.9 mm/s "
                     "RMS and two loose baseplate anchor bolts."),
            "citations": cited},
        "findings": [
            {"text": ("Drive-end vibration was recorded at 7.9 mm/s RMS. The "
                      "supplied procedure states a value of 7.1 mm/s RMS."),
             "citations": cited},
            {"text": "Two of four baseplate anchor bolts were found loose.",
             "citations": [{"source_id": report_id, "page": report_page}]},
        ],
        "recommendation": {
            "text": ("The pump remains in service pending corrective action. "
                     "Re-inspection is required within 14 days."),
            "citations": cited},
        "unresolved": [
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
        report = {"source_id": "report", "filename": "report.txt",
                  "pages": [{"number": 1, "text": "x" * 100_000}]}
        passages = [retrieval.Passage(
            source_id="sop", filename="sop.txt", page=index + 1,
            text="y" * retrieval.MAX_PASSAGE_CHARS, rank=float(index))
            for index in range(retrieval.MAX_PASSAGES)]
        built, selected, pages, *_rest = self.c._approval_prompt(
            "draft the approval note", report, [], passages)
        self.assertTrue(selected)
        self.assertTrue(pages)
        self.assertLessEqual(
            context.estimate_messages(built),
            context.input_budget(runtime.NUM_CTX,
                                 docflow.APPROVAL_NUM_PREDICT))

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


# ---------------------------------------------------------------------------
# Cross-source reference identity
# ---------------------------------------------------------------------------

def governing(value, *, filename="inspection-report.pdf"):
    """The report detail `report_evidence` extracts for the governing standard."""
    return [{"text": f"{docflow.GOVERNING_DETAIL}: {value}",
             "citations": [{"source_id": "report", "filename": filename,
                            "page": 1, "label": f"{filename} p.1"}]}]


def reference(text, *, filename="sop-mech-014.txt", page=1):
    return [{"source_id": "sop", "filename": filename,
             "pages": [{"number": page, "text": text}]}]


class ReferenceIdentity(unittest.TestCase):
    """Which document governs, when two selected sources disagree about it.

    A packaged run read the scan as citing SOP-MECH-814, the attached procedure
    calls itself SOP-MECH-014, and the note used the attached procedure's 7.1
    mm/s limit as the acceptance limit. Every citation in it resolved: the page
    existed, the document was selected, the number was really on that page.
    Citation resolution was never the thing that could have caught it, because
    nothing in it asks whether the cited procedure is the one that applies.
    """

    def test_two_sources_naming_the_same_document_raise_nothing(self):
        self.assertEqual(
            docflow.reference_conflicts(governing("SOP-MECH-014 rev 3"),
                                        reference("SOP-MECH-014 rev 3\nSCOPE")),
            [])

    def test_a_different_identifier_is_reported_and_never_reconciled(self):
        conflicts = docflow.reference_conflicts(
            governing("SOP-MECH-814 REV 3"),
            reference("SOP-MECH-014 rev 3\nROUTINE MECHANICAL INSPECTION"))
        self.assertEqual(len(conflicts), 1)
        text = conflicts[0]["text"]
        # Both survive, spelled as each source spelled them.
        self.assertIn("SOP-MECH-814", text)
        self.assertIn("SOP-MECH-014", text)
        self.assertIn("not established", text)

    def test_a_different_revision_of_the_same_document_is_reported(self):
        conflicts = docflow.reference_conflicts(
            governing("SOP-MECH-014 rev 2"), reference("SOP-MECH-014 rev 3"))
        self.assertEqual(len(conflicts), 1)
        self.assertIn("revision 2", conflicts[0]["text"])
        self.assertIn("revision 3", conflicts[0]["text"])

    def test_a_revision_only_one_side_states_is_not_a_conflict(self):
        """A revision the report omits is a silence, not a disagreement."""
        self.assertEqual(
            docflow.reference_conflicts(governing("SOP-MECH-014"),
                                        reference("SOP-MECH-014 rev 3")),
            [])

    def test_a_report_that_names_no_standard_invents_no_conflict(self):
        details = [{"text": "Report number: NG-2026-0417", "citations": []}]
        self.assertEqual(
            docflow.reference_conflicts(details, reference("SOP-MECH-014 rev 3")),
            [])

    def test_a_reference_that_names_no_identifier_invents_no_conflict(self):
        self.assertEqual(
            docflow.reference_conflicts(
                governing("SOP-MECH-014 rev 3"),
                reference("A procedure with no code in its header at all.")),
            [])

    def test_an_ocr_like_near_match_is_a_conflict_not_an_equivalence(self):
        """`0` read as `8` is exactly why this cannot resolve itself. The
        similarity earns a more useful sentence and nothing else: treating two
        identifiers as one because they look alike is the silent
        reconciliation this check exists to prevent."""
        for misread in ("SOP-MECH-814 rev 3", "SOP-MECH-0I4 rev 3",
                        "SOP-MECH-O14 rev 3"):
            with self.subTest(read_as=misread):
                conflicts = docflow.reference_conflicts(
                    governing(misread), reference("SOP-MECH-014 rev 3"))
                self.assertEqual(len(conflicts), 1)
                self.assertIn("may be a misreading", conflicts[0]["text"])
                self.assertIn("not established", conflicts[0]["text"])

    def test_a_wholly_different_document_is_not_called_a_misreading(self):
        conflicts = docflow.reference_conflicts(
            governing("SOP-ELEC-220 rev 1"), reference("SOP-MECH-014 rev 3"))
        self.assertEqual(len(conflicts), 1)
        self.assertNotIn("misreading", conflicts[0]["text"])

    def test_the_conflict_cites_both_sources_that_disagree(self):
        conflicts = docflow.reference_conflicts(
            governing("SOP-MECH-814 REV 3"), reference("SOP-MECH-014 rev 3"))
        cited = {(c["filename"], c["page"]) for c in conflicts[0]["citations"]}
        self.assertEqual(cited, {("inspection-report.pdf", 1),
                                 ("sop-mech-014.txt", 1)})

    def test_only_the_references_selected_for_this_request_are_compared(self):
        """Nothing else in the workspace is consulted, so an unrelated
        procedure sitting in history cannot manufacture a disagreement."""
        selected = reference("SOP-MECH-014 rev 3")
        conflicts = docflow.reference_conflicts(
            governing("SOP-MECH-014 rev 3"), selected)
        self.assertEqual(conflicts, [])

    def test_an_asset_tag_or_report_number_is_not_read_as_a_procedure(self):
        """`P-204` and `NG-2026-0417` have an identifier's shape and are not
        claims about which procedure governs anything."""
        conflicts = docflow.reference_conflicts(
            governing("SOP-MECH-014 rev 3"),
            reference("Transfer pump P-204, report NG-2026-0417.\n"
                      "SOP-MECH-014 rev 3"))
        self.assertEqual(conflicts, [],
                         "the first code in the header is the one that counts")

    def test_the_model_is_told_it_may_quote_but_not_promote_the_limit(self):
        conflicts = docflow.reference_conflicts(
            governing("SOP-MECH-814 REV 3"), reference("SOP-MECH-014 rev 3"))
        messages = docflow.approval_note_messages(
            "draft the approval note", [], [], [], conflicts)
        system = messages[0]["content"]
        self.assertIn(docflow.APPROVAL_CONFLICT_RULE, system)
        self.assertIn("state what that reference says as a fact", system)
        self.assertIn("do not call its value the governing", system)
        self.assertIn("SOP-MECH-814", messages[1]["content"])

    def test_a_note_without_a_conflict_carries_no_such_rule(self):
        messages = docflow.approval_note_messages(
            "draft the approval note", [], [], [], [])
        self.assertNotIn(docflow.APPROVAL_CONFLICT_RULE, messages[0]["content"])

    def test_no_identifier_from_the_observed_failure_is_written_into_the_source(self):
        """The guard is generic. A branch on these codes would pass the one run
        that found the problem and nothing else.

        Executable constants only: comments and docstrings name the run this
        came from, which is worth keeping, and neither can steer a comparison.
        A hardcoded branch would need a literal the interpreter can see.
        """
        tree = ast.parse(pathlib.Path(docflow.__file__).read_text(encoding="utf-8"))
        documented = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                     ast.AsyncFunctionDef)):
                continue
            first = node.body[0] if node.body else None
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                documented.add(id(first.value))
        constants = [node.value for node in ast.walk(tree)
                     if isinstance(node, ast.Constant)
                     and id(node) not in documented]
        for literal in ("SOP-MECH-814", "SOP-MECH-014", "P-204",
                        "NG-2026-0417", "7.1", 7.1):
            with self.subTest(literal=literal):
                self.assertFalse(
                    [c for c in constants
                     if c == literal
                     or (isinstance(c, str) and isinstance(literal, str)
                         and literal in c)],
                    f"{literal!r} is reachable by the comparison")


class ReferenceConflictInTheArtifact(GroundedHarness):
    """The conflict has to reach the document, not only the log."""

    # Exactly what the packaged run produced: the scan read with one digit
    # wrong. The canonical fixture is untouched; this is a variant of its bytes
    # attached under its own name.
    MISREAD = REPORT.read_bytes().replace(b"SOP-MECH-014 rev 3",
                                          b"SOP-MECH-814 REV 3")

    def run_pack(self, report_bytes):
        report = self.attach("inspection-report.txt", report_bytes)
        sop = self.attach("sop-mech-014.txt", SOP.read_bytes())
        job = self.send("draft the approval note", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        self.bind(job, report)
        self.bind(job, sop)
        stream = scripted_stream(
            conditioned_note(report["attachment_id"], sop["attachment_id"]))
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        return job

    def test_the_matching_pack_produces_no_mismatch_section(self):
        job = self.run_pack(REPORT.read_bytes())
        self.assertEqual(self.job_state(job), "completed")
        text, _row = self.artifact_text()
        self.assertNotIn("Reference identity not established", text)

    def test_the_misread_standard_reaches_the_document(self):
        job = self.run_pack(self.MISREAD)
        self.assertEqual(self.job_state(job), "completed")
        text, _row = self.artifact_text()
        self.assertIn("Reference identity not established", text)
        self.assertIn("SOP-MECH-814", text)
        self.assertIn("SOP-MECH-014", text)

    def test_the_recommendation_carries_the_unresolved_applicability(self):
        """Attached by the coordinator, so it does not depend on the model
        having taken the instruction. The scripted note recommends continued
        service without qualifying it; the artifact still qualifies it."""
        self.run_pack(self.MISREAD)
        text, _row = self.artifact_text()
        self.assertIn(docflow.REFERENCE_QUALIFIER, text)
        self.assertIn("applies only once that identity is confirmed", text)

    def test_the_conflict_is_recorded_with_the_citations_it_rests_on(self):
        self.run_pack(self.MISREAD)
        _text, row = self.artifact_text()
        cited = json.loads(row["citations_json"])
        filenames = {c["filename"] for c in cited}
        self.assertIn("inspection-report.txt", filenames)
        self.assertIn("sop-mech-014.txt", filenames)

    def test_the_conflict_does_not_cost_the_evidence_already_preserved(self):
        """Everything the accepted run got right stays right."""
        self.run_pack(self.MISREAD)
        text, _row = self.artifact_text()
        for kept in ("7.9 mm/s RMS",              # the observed reading
                     "7.1 mm/s RMS",              # the supplied SOP's limit
                     "Report number: NG-2026-0417",
                     "Transfer pump P-204",
                     "anchor bolts",
                     "Suction pressure",
                     "A person must check it before it is used."):
            with self.subTest(kept=kept):
                self.assertIn(kept, text)

    def test_no_suction_pressure_value_is_invented_under_a_conflict(self):
        self.run_pack(self.MISREAD)
        text, _row = self.artifact_text()
        self.assertNotIn("Suction pressure: 0", text)
        self.assertRegex(text, r"[Ss]uction pressure[^\n]*"
                               r"(not recorded|llegible|could not)")

    def test_the_document_still_opens_and_reads_back(self):
        self.run_pack(self.MISREAD)
        text, row = self.artifact_text()
        self.assertEqual(row["workflow"], docflow.WORKFLOW_APPROVAL_NOTE)
        self.assertTrue(text.strip())


class ReferenceIdentityIsCaseInsensitive(unittest.TestCase):
    """Found in review: matching upper case only made a lowercase header
    declare no identity at all, which skipped the comparison silently. A missed
    conflict is the dangerous direction; a noisy one is merely annoying."""

    def test_a_lowercase_header_still_matches_its_upper_case_report(self):
        self.assertEqual(
            docflow.reference_conflicts(governing("SOP-MECH-014 rev 3"),
                                        reference("sop-mech-014 rev 3\nSCOPE")),
            [])

    def test_a_lowercase_header_that_disagrees_is_still_caught(self):
        conflicts = docflow.reference_conflicts(
            governing("SOP-MECH-814 REV 3"), reference("sop-mech-014 rev 3"))
        self.assertEqual(len(conflicts), 1)
        self.assertIn("SOP-MECH-814", conflicts[0]["text"])
        self.assertIn("SOP-MECH-014", conflicts[0]["text"])

    def test_case_differs_but_the_document_does_not(self):
        for spelling in ("sop-mech-014 Rev 3", "Sop-Mech-014 REV 3",
                         "SOP-mech-014 rev 3"):
            with self.subTest(spelling=spelling):
                self.assertEqual(
                    docflow.reference_conflicts(governing(spelling),
                                                reference("SOP-MECH-014 rev 3")),
                    [])

    def test_an_ordinary_hyphenated_word_is_not_a_document_number(self):
        """Case-insensitivity without the digit rule would have read
        `drive-end` at the head of a line as the document's identity."""
        for prose in ("drive-end vibration readings and limits\n"
                      "SOP-MECH-014 rev 3",
                      "re-inspection intervals\nSOP-MECH-014 rev 3",
                      "non-drive end bearings\nSOP-MECH-014 rev 3"):
            with self.subTest(head=prose.splitlines()[0]):
                self.assertEqual(
                    docflow.reference_conflicts(governing("SOP-MECH-014 rev 3"),
                                                reference(prose)),
                    [])

    def test_an_asset_tag_beginning_a_line_is_not_the_documents_identity(self):
        """A line-start anchor alone was not enough: an asset tag can begin a
        line too. A document states its own number with its revision, so the
        line carrying one wins."""
        self.assertEqual(
            docflow.declared_identity("P-204 transfer pump\nSOP-MECH-014 rev 3"),
            ("SOP-MECH-014", "3"))
        self.assertEqual(
            docflow.reference_conflicts(
                governing("SOP-MECH-014 rev 3"),
                reference("P-204 transfer pump\nSOP-MECH-014 rev 3")),
            [])


class AnUnestablishedReferenceCannotSettleTheOutcome(GroundedHarness):
    """The conflict has to constrain the note, not sit beside it.

    Found in review: the mismatch was rendered in its own section while the
    note it accompanied still said "above the alarm limit" and "against an
    alarm limit of 7.1". A warning elsewhere in the same file does not unmake
    a sentence that reads as settled, so the model's claim was still the claim
    the guard existed to prevent.
    """

    MISREAD = REPORT.read_bytes().replace(b"SOP-MECH-014 rev 3",
                                          b"SOP-MECH-814 REV 3")

    def sources(self):
        return [{"source_id": "report", "filename": "report.pdf",
                 "pages": [{"number": 1}]},
                {"source_id": "sop", "filename": "sop-mech-014.txt",
                 "pages": [{"number": 1}]}]

    def conflict(self):
        return docflow.reference_conflicts(governing("SOP-MECH-814 REV 3"),
                                           reference("SOP-MECH-014 rev 3"))

    def test_the_noncompliant_note_the_run_produced_is_refused(self):
        """`grounded_note` is the scripted reply the earlier regressions used:
        it calls 7.1 an alarm limit outright. Unchanged, it must now fail."""
        with self.assertRaises(docflow.WorkflowError) as caught:
            docflow.parse_approval_note(grounded_note("report", "sop"),
                                        self.sources(), self.conflict())
        self.assertEqual(caught.exception.code, "unresolved_reference")

    def test_the_same_note_is_accepted_when_identity_is_not_in_doubt(self):
        note = docflow.parse_approval_note(grounded_note("report", "sop"),
                                           self.sources(), [])
        self.assertTrue(note["findings"])

    def test_a_settled_judgement_is_caught_singular_or_plural(self):
        """Found in probing: `\blimit\b` does not match "limits", so "the
        reading is within limits" walked straight through the guard."""
        for settled in ("The reading is within limits.",
                        "The reading is within the limit.",
                        "The vibration is above the alarm limits.",
                        "The asset meets the acceptance criteria.",
                        "The result is out of specification."):
            with self.subTest(claim=settled):
                self.assertTrue(
                    docflow.reference_applicability_judgement(settled))

    def test_a_fact_about_the_supplied_file_is_not_a_judgement(self):
        for stated in ("The supplied procedure states a value of 7.1 mm/s RMS.",
                       "The attached procedure states a 7.1 mm/s RMS limit.",
                       "Drive-end vibration was recorded at 7.9 mm/s RMS.",
                       "Two of four anchor bolts were found loose.",
                       "Re-inspection is required within 14 days."):
            with self.subTest(claim=stated):
                self.assertFalse(
                    docflow.reference_applicability_judgement(stated))

    def test_the_refusal_is_never_repaired_into_shape(self):
        self.assertNotIn("unresolved_reference", docflow.REPAIRABLE_CODES)

    def test_stating_what_the_reference_says_stays_allowed(self):
        """The distinction the whole guard turns on: a fact about a file is
        not a judgement about this inspection."""
        allowed = json.dumps(json.loads(grounded_note("report", "sop")) | {
            "summary": {"text": ("Inspection NG-2026-0417 recorded a drive-end "
                                 "vibration of 7.9 mm/s RMS. The supplied "
                                 "procedure states a value of 7.1 mm/s RMS."),
                        "citations": [{"source_id": "report", "page": 1}]},
            "findings": [{"text": ("Drive-end vibration was recorded at 7.9 "
                                   "mm/s RMS."),
                          "citations": [{"source_id": "report", "page": 1}]}],
            "recommendation": {
                "text": ("Re-inspection is required within 14 days."),
                "citations": [{"source_id": "report", "page": 1}]}})
        note = docflow.parse_approval_note(allowed, self.sources(),
                                           self.conflict())
        self.assertIn("7.1", note["summary"]["text"])

    def test_a_condition_does_not_authorise_a_settled_conclusion(self):
        """A warning and the unsafe conclusion in one claim is still unsafe."""
        contradictory = json.dumps(
            json.loads(conditioned_note("report", "sop")) | {
                "summary": {
                    "text": ("Applicability is not established. Nevertheless, "
                             "the asset exceeds the governing limit and is "
                             "noncompliant."),
                    "citations": [{"source_id": "report", "page": 1}]}})
        with self.assertRaises(docflow.WorkflowError) as caught:
            docflow.parse_approval_note(contradictory, self.sources(),
                                        self.conflict())
        self.assertEqual(caught.exception.code, "unresolved_reference")

    def test_every_claim_is_checked_not_only_the_recommendation(self):
        for field in ("summary", "recommendation"):
            with self.subTest(field=field):
                reply = json.loads(grounded_note("report", "sop"))
                reply["findings"] = [
                    {"text": "Two anchor bolts were found loose.",
                     "citations": [{"source_id": "report", "page": 1}]}]
                reply["summary"] = {
                    "text": "Two anchor bolts were found loose.",
                    "citations": [{"source_id": "report", "page": 1}]}
                reply["recommendation"] = {
                    "text": "Re-inspection is required within 14 days.",
                    "citations": [{"source_id": "report", "page": 1}]}
                reply[field] = {
                    "text": "The asset is compliant with the governing limit.",
                    "citations": [{"source_id": "report", "page": 1}]}
                with self.assertRaises(docflow.WorkflowError) as caught:
                    docflow.parse_approval_note(json.dumps(reply),
                                                self.sources(), self.conflict())
                self.assertEqual(caught.exception.code, "unresolved_reference")

    def test_the_noncompliant_run_writes_no_document_at_all(self):
        """End to end: refused before the artifact, not annotated after it."""
        report = self.attach("inspection-report.txt", self.MISREAD)
        sop = self.attach("sop-mech-014.txt", SOP.read_bytes())
        job = self.send("draft the approval note", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        self.bind(job, report)
        self.bind(job, sop)
        stream = scripted_stream(
            grounded_note(report["attachment_id"], sop["attachment_id"]))
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        self.assertEqual(self.job_state(job), "failed")
        self.assertEqual(self.artifacts(), [])

    def test_the_chat_answer_carries_the_conflict_above_the_summary(self):
        """The person reads this before opening the document, so a summary
        that arrives without the conflict is the same settled sentence."""
        note = docflow.parse_approval_note(
            json.dumps(json.loads(grounded_note("report", "sop")) | {
                "summary": {"text": "Vibration of 7.9 mm/s RMS was recorded.",
                            "citations": [{"source_id": "report", "page": 1}]},
                "findings": [{"text": "Two anchor bolts were loose.",
                              "citations": [{"source_id": "report", "page": 1}]}],
                "recommendation": {"text": "Re-inspect within 14 days.",
                                   "citations": [{"source_id": "report", "page": 1}]}}),
            self.sources(), self.conflict())
        note["reference_conflicts"] = self.conflict()
        answer = docflow.artifact_answer(
            note, {"validation": {"paragraphs": 9}, "filename": "note.docx",
                   "byte_size": 1024},
            docflow.Prepared(), [])
        self.assertIn("Reference identity not established", answer)
        self.assertIn("SOP-MECH-814", answer)
        self.assertLess(answer.index("Reference identity not established"),
                        answer.index("Vibration of 7.9"))
