"""General document generation: the structured contract, and how it fails.

Once a request has correctly reached general generation (Batch 1's job), the
model has to come back with one JSON object. Asking for that in prose alone is
what made documents unreliable: a 4B model answered with markdown fences,
preambles and trailing remarks, and every one of those was refused as
unreadable *after* the work had been done.

This module covers the contract that replaced the prose:

* the runtime decodes against an enforced schema, and the call really asks for
  one — asserted at the production boundary, not on the constant;
* a document gets its own output ceiling, larger than a chat reply;
* a wrongly *shaped* reply gets exactly one repair, and a second failure is the
  answer;
* a *truncated* reply is never repaired and never parsed — half a JSON object
  must not become an artifact;
* the parser stays strict. Enforcement plus one repair is the robustness; a
  parser that scavenges JSON out of arbitrary prose is not.

Synthetic only: a temporary database and a scripted runtime. No model, no
network, no real generation.

    python3 -m unittest backend.coordinator.test_document_generation -v
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from backend.coordinator import context, db, docflow, docgen, runtime
from backend.coordinator.test_execution4a import Harness

VALID = {"title": "Machine learning", "sections": [
    {"heading": "Overview", "paragraphs": ["Layered models learn features."]},
    {"heading": "Training", "paragraphs": ["Gradients update the weights."]}]}


def body(document=None) -> str:
    return json.dumps(document if document is not None else VALID)


def scripted_stream(*replies, done_reasons=("stop",)):
    """A `runtime.stream_chat` double that answers differently each call.

    Records every call, so "exactly one repair" and "no repair at all" are
    assertions about what actually happened rather than about intent.
    """
    queue = list(replies)
    reasons = list(done_reasons)

    def stream(messages, *, should_cancel=None, profile=None, inference=None,
               response_format=None, images=None):
        index = stream.calls
        stream.calls += 1
        stream.messages.append(messages)
        stream.formats.append(response_format)
        stream.budgets.append(inference.output_allowance_tokens
                              if inference else None)
        stream.thinking.append(inference.reasoning == "enabled"
                               if inference else None)
        yield "delta", queue[index] if index < len(queue) else ""
        yield "done", {"done_reason": reasons[index] if index < len(reasons)
                       else reasons[-1]}

    stream.calls = 0
    stream.messages = []
    stream.formats = []
    stream.budgets = []
    stream.thinking = []
    return stream


class GenerationHarness(Harness):
    """One general-document request, driven through the real coordinator."""

    REQUEST = "Create a document explaining machine learning"

    def generate(self, *replies, done_reasons=("stop",), request=None):
        stream = scripted_stream(*replies, done_reasons=done_reasons)
        job = self.send(request or self.REQUEST, skill_id=docflow.WRITE_SKILL,
                        output_format=docflow.FORMAT_DOCX)
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        return job, stream

    def job_state(self, job):
        return self.c.conn.execute(
            "SELECT state FROM jobs WHERE job_id=?", (job,)).fetchone()["state"]

    def failure(self, job):
        row = self.c.conn.execute(
            "SELECT a.error_json FROM jobs j JOIN attempts a"
            " ON a.attempt_id = j.active_attempt_id WHERE j.job_id=?",
            (job,)).fetchone()
        return json.loads(row["error_json"]) if row and row["error_json"] else {}

    def written(self):
        rows = self.artifacts()
        self.assertEqual(len(rows), 1, "exactly one artifact was expected")
        root = db.artifacts_root(self.c.state_path)
        return "\n".join(docgen.read_text(root / rows[0]["stored_name"]))


# ---------------------------------------------------------------------------
# A and H — the ordinary case
# ---------------------------------------------------------------------------

class CleanGeneration(GenerationHarness):
    def test_valid_structured_output_is_written_without_a_repair(self):
        job, stream = self.generate(body())
        self.assertEqual(self.job_state(job), "completed")
        self.assertEqual(stream.calls, 1, "a clean reply must not be repaired")
        text = self.written()
        self.assertIn("Layered models learn features.", text)
        self.assertIn("Gradients update the weights.", text)

    def test_the_document_keeps_its_title_and_headings(self):
        self.generate(body())
        text = self.written()
        for expected in ("Machine learning", "Overview", "Training"):
            self.assertIn(expected, text)

    def test_the_artifact_records_the_general_workflow(self):
        self.generate(body())
        self.assertEqual(self.artifacts()[0]["workflow"],
                         docflow.WORKFLOW_GENERAL)


# ---------------------------------------------------------------------------
# B — the production call boundary
# ---------------------------------------------------------------------------

class CallContract(GenerationHarness):
    def test_the_generation_call_asks_the_runtime_to_enforce_the_schema(self):
        """Asserted where the call is made. A constant defined and never passed
        is exactly the defect this replaces."""
        _job, stream = self.generate(body())
        self.assertEqual(stream.formats[0], docflow.GENERAL_DOCUMENT_FORMAT)
        self.assertEqual(stream.formats[0]["type"], "object")
        self.assertEqual(stream.formats[0]["additionalProperties"], False)

    def test_the_generation_call_uses_the_document_output_budget(self):
        _job, stream = self.generate(body())
        self.assertEqual(stream.budgets[0], docflow.DOCUMENT_NUM_PREDICT)

    def test_a_document_may_write_more_than_a_chat_reply(self):
        """1024 — the unused constant this replaced — was below the chat
        default, which would have made documents shorter than an answer."""
        self.assertGreater(docflow.DOCUMENT_NUM_PREDICT, runtime.NUM_PREDICT)

    def test_the_budget_leaves_room_for_the_prompt_inside_the_context(self):
        """The real estimator counts fixed instructions as well as sources."""
        source = {"source_id": "large", "filename": "large.txt",
                  "pages": [{"number": 1, "text": "x" * 100_000}]}
        base = docflow.general_document_messages(self.REQUEST, [])
        messages = self.c._fit_document_prompt(
            base, docflow.DOCUMENT_NUM_PREDICT,
            lambda budget: docflow.general_document_messages(
                self.REQUEST, [source], budget=budget))
        self.assertLessEqual(
            context.estimate_messages(messages),
            context.input_budget(runtime.NUM_CTX, docflow.DOCUMENT_NUM_PREDICT))

    def test_the_enforced_schema_matches_what_the_parser_accepts(self):
        """One representation, not two. A schema that allowed a field the
        parser rejects would fail after generation, every time."""
        schema = docflow.GENERAL_DOCUMENT_FORMAT
        self.assertEqual(set(schema["required"]), {"title", "sections"})
        section = schema["properties"]["sections"]["items"]
        self.assertEqual(set(section["required"]), {"heading", "paragraphs"})
        self.assertFalse(section["additionalProperties"])
        docflow.parse_general_document(body())            # the same shape

    def test_an_ordinary_chat_turn_is_not_constrained(self):
        """Chat is free text. Handing it a document schema would break it."""
        stream = scripted_stream("a plain answer")
        job = self.send("explain the reading")
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, None)
        self.assertEqual(stream.formats, [None])
        self.assertEqual(stream.budgets, [runtime.NUM_PREDICT])


# ---------------------------------------------------------------------------
# C — Batch 1 behaviour is preserved
# ---------------------------------------------------------------------------

class HistoryStillReachesGeneration(GenerationHarness):
    def test_production_shaped_history_is_in_the_generation_prompt(self):
        self.completed_answer("Deep learning stacks differentiable layers.")
        _job, stream = self.generate(body())
        prompt = stream.messages[0][-1]["content"]
        self.assertIn("Deep learning stacks differentiable layers.", prompt)
        self.assertIn("EARLIER IN THIS CONVERSATION", prompt)


# ---------------------------------------------------------------------------
# D and E — the single repair
# ---------------------------------------------------------------------------

class RepairRound(GenerationHarness):
    FENCED = "```json\n" + body() + "\n```"

    def test_a_wrapped_reply_is_repaired_once_and_accepted(self):
        job, stream = self.generate(self.FENCED, body())
        self.assertEqual(stream.calls, 2, "one generation and one repair")
        self.assertEqual(self.job_state(job), "completed")
        self.assertIn("Layered models learn features.", self.written())

    def test_the_repair_turn_carries_the_bad_reply_and_the_shape(self):
        _job, stream = self.generate(self.FENCED, body())
        repair = stream.messages[1]
        self.assertEqual([m["role"] for m in repair], ["system", "user"])
        self.assertIn("Repair the format only", repair[-1]["content"])
        self.assertIn("```json", repair[-1]["content"],
                      "the malformed reply is what is being repaired")

    def test_the_repair_does_not_resend_the_sources_or_the_history(self):
        """A format repair needs the text and the target shape. Handing back the
        sources invites a second draft, and resending a full prompt alongside a
        full-length reply overruns the context the runtime will accept."""
        self.completed_answer("An earlier answer about vibration limits.")
        _job, stream = self.generate(self.FENCED, body())
        repair = "\n".join(m["content"] for m in stream.messages[1])
        self.assertNotIn("An earlier answer about vibration limits.", repair)
        self.assertNotIn("EARLIER IN THIS CONVERSATION", repair)
        self.assertNotIn(self.REQUEST, repair)

    def test_the_whole_malformed_reply_survives_into_the_repair(self):
        """The bug this replaced: the reply was cut to 4,000 characters while the
        instruction promised to keep every paragraph, so a long document came
        back shorter with the rest silently gone — and passed both the schema and
        the parser."""
        big = {"title": "Deep machine learning", "sections": [
            {"heading": f"Section {i}",
             "paragraphs": ["A substantial paragraph of explanation. " * 12]}
            for i in range(8)]}
        fenced = "```json\n" + body(big) + "\n```"
        self.assertGreater(len(fenced), 4000, "the fixture must exceed the old cap")
        _job, stream = self.generate(fenced, body(big))
        carried = stream.messages[1][-1]["content"]
        for index in range(8):
            self.assertIn(f"Section {index}", carried)
        self.assertIn(fenced, carried, "the reply is carried whole")

    def test_the_repair_prompt_fits_the_context_at_full_reply_length(self):
        """Worst case: a reply that used the entire output budget."""
        reply = "x" * (docflow.DOCUMENT_NUM_PREDICT * 4)
        messages = docflow.general_repair_messages(reply)
        estimated = sum(context.estimate_tokens(m["content"]) for m in messages)
        self.assertLess(estimated + docflow.DOCUMENT_NUM_PREDICT, runtime.NUM_CTX)

    def test_a_reply_longer_than_the_budget_could_produce_is_bounded(self):
        """Bounded, not unbounded: the cap is above anything the budget can
        generate, so it only ever trims something pathological."""
        messages = docflow.general_repair_messages("y" * 500_000)
        self.assertLessEqual(len(messages[-1]["content"]),
                             docflow.MAX_REPAIR_REPLY_CHARS + 1_000)

    def test_the_repair_asks_for_the_same_words_not_a_second_draft(self):
        instruction = docflow.GENERAL_REPAIR_INSTRUCTION
        self.assertIn("word for word", instruction)
        self.assertIn("Do not add a section", instruction)

    def test_the_repair_is_also_schema_constrained_and_bounded(self):
        _job, stream = self.generate(self.FENCED, body())
        self.assertEqual(stream.formats[1], docflow.GENERAL_DOCUMENT_FORMAT)
        self.assertEqual(stream.budgets[1], docflow.DOCUMENT_NUM_PREDICT)

    def test_the_repair_does_not_spend_the_budget_on_reasoning(self):
        _job, stream = self.generate(self.FENCED, body())
        self.assertIs(stream.thinking[1], False)

    def test_a_second_malformed_reply_fails_and_is_not_retried(self):
        job, stream = self.generate(self.FENCED, "still not json at all")
        self.assertEqual(stream.calls, 2, "exactly one repair, never two")
        self.assertEqual(self.job_state(job), "failed")
        self.assertEqual(self.artifacts(), [])
        self.assertEqual(self.artifact_files(), [])

    def test_at_most_one_repair_however_many_replies_are_queued(self):
        """No loop. A model that cannot produce the format must not be asked
        again and again on someone's own machine."""
        job, stream = self.generate("nope", "still nope", body(), body())
        self.assertEqual(stream.calls, 2)
        self.assertEqual(self.job_state(job), "failed")

    def test_only_wrongly_shaped_replies_are_repaired(self):
        """A reply with no sections is not a format problem. Repairing it would
        ask the model to invent a document it never wrote."""
        job, stream = self.generate(json.dumps({"title": "T", "sections": []}))
        self.assertEqual(stream.calls, 1, "no repair for missing content")
        self.assertEqual(self.job_state(job), "failed")
        self.assertEqual(self.artifacts(), [])

    def test_the_repairable_set_is_the_shape_codes_only(self):
        self.assertEqual(set(docflow.REPAIRABLE_CODES),
                         {"not_json", "not_object", "unknown_fields"})
        for excluded in ("empty", "bad_sections", "bad_section",
                         "too_many_sections", "incomplete"):
            self.assertNotIn(excluded, docflow.REPAIRABLE_CODES)


# ---------------------------------------------------------------------------
# F — truncation
# ---------------------------------------------------------------------------

class TruncatedGeneration(GenerationHarness):
    def test_a_reply_cut_off_by_the_output_limit_is_refused(self):
        job, stream = self.generate(body()[:60], done_reasons=("length",))
        self.assertEqual(self.job_state(job), "failed")
        self.assertEqual(self.artifacts(), [])
        self.assertEqual(self.artifact_files(), [])

    def test_a_truncated_reply_is_never_repaired(self):
        """Repairing half a document means asking the model to finish it from
        memory, which is how invented content would get in."""
        job, stream = self.generate(body()[:60], body(),
                                    done_reasons=("length", "stop"))
        self.assertEqual(stream.calls, 1, "truncation stops before the repair")
        self.assertEqual(self.job_state(job), "failed")

    def test_the_failure_says_the_reply_was_incomplete(self):
        job, _stream = self.generate(body()[:60], done_reasons=("length",))
        self.assertIn("incomplete", self.failure(job).get("message", "").lower())

    def test_a_complete_reply_that_merely_looks_short_is_still_accepted(self):
        """The stop reason decides, not the length: a short document is a
        legitimate document."""
        small = {"title": "T", "sections": [
            {"heading": "H", "paragraphs": ["One line."]}]}
        job, stream = self.generate(body(small), done_reasons=("stop",))
        self.assertEqual(self.job_state(job), "completed")
        self.assertEqual(stream.calls, 1)

    def test_an_unreported_stop_reason_is_not_assumed_successful(self):
        job, _stream = self.generate(body(), done_reasons=(None,))
        self.assertEqual(self.job_state(job), "failed")
        self.assertEqual(self.artifacts(), [])


# ---------------------------------------------------------------------------
# G — the parser tolerance decision
# ---------------------------------------------------------------------------

class ParserStaysStrict(unittest.TestCase):
    """Enforcement plus one repair is the robustness. The parser is not loosened.

    A parser that hunted for a JSON-looking substring inside arbitrary prose
    would accept a reply the model never meant as a document, and would hide the
    schema not being enforced. Each wrapper below is therefore *rejected here*
    and recovered — if at all — by the repair round.
    """

    def classify(self, reply):
        try:
            docflow.parse_general_document(reply)
            return "accepted"
        except docflow.WorkflowError as exc:
            return ("repaired" if exc.code in docflow.REPAIRABLE_CODES
                    else f"rejected:{exc.code}")

    def test_the_adversarial_matrix_is_classified_as_designed(self):
        expected = [
            ("clean JSON", body(), "accepted"),
            ("whitespace around it", "\n\n  " + body() + "  \n", "accepted"),
            ("markdown-fenced", "```json\n" + body() + "\n```", "repaired"),
            ("explanatory preamble", "Here is your document:\n" + body(), "repaired"),
            ("trailing prose", body() + "\n\nLet me know!", "repaired"),
            ("a JSON array", "[1, 2, 3]", "repaired"),
            ("unknown top-level field",
             json.dumps({"title": "T", "summary": "s", "sections": [
                 {"heading": "H", "paragraphs": ["p"]}]}), "repaired"),
            ("unknown field inside a section",
             json.dumps({"title": "T", "sections": [
                 {"heading": "H", "paragraphs": ["p"], "level": 1}]}),
             "rejected:bad_section"),
            ("truncated JSON", body()[:40], "repaired"),
            ("empty output", "", "rejected:empty"),
            ("no sections", json.dumps({"title": "T", "sections": []}),
             "rejected:bad_sections"),
            ("a section with no paragraphs",
             json.dumps({"title": "T", "sections": [
                 {"heading": "H", "paragraphs": []}]}), "rejected:bad_section"),
        ]
        for label, reply, want in expected:
            with self.subTest(case=label):
                self.assertEqual(self.classify(reply), want)

    def test_a_fence_is_not_silently_stripped(self):
        """Documented decision: the fence is a parse failure, not something the
        parser quietly unwraps. Truncated JSON classifies the same way, which is
        why the *caller* refuses truncation before ever parsing."""
        with self.assertRaises(docflow.WorkflowError) as caught:
            docflow.parse_general_document("```json\n" + body() + "\n```")
        self.assertEqual(caught.exception.code, "not_json")

    def test_semantic_validation_survives_syntactic_enforcement(self):
        """A grammar can promise `sections` is a list of objects. It cannot
        promise the document says anything, so the parser still checks."""
        for reply in (json.dumps({"title": "", "sections": [
                          {"heading": "H", "paragraphs": ["p"]}]}),
                      json.dumps({"title": "T", "sections": [
                          {"heading": "H", "paragraphs": [""]}]})):
            with self.subTest(reply=reply):
                with self.assertRaises(docflow.WorkflowError):
                    docflow.parse_general_document(reply)


# ---------------------------------------------------------------------------
# I — Batch 1 is untouched
# ---------------------------------------------------------------------------

class CancellationDuringRepair(GenerationHarness):
    """The repair adds a second model call inside the validating phase."""

    def test_a_stop_during_the_repair_publishes_nothing(self):
        fenced = "```json\n" + body() + "\n```"
        job = self.send(self.REQUEST, skill_id=docflow.WRITE_SKILL)

        def stream(messages, *, should_cancel=None, profile=None, inference=None,
                   response_format=None, images=None):
            stream.calls += 1
            if stream.calls == 1:
                yield "delta", fenced
                yield "done", {"done_reason": "stop"}
            else:
                yield "cancelled", {}
        stream.calls = 0

        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        self.assertEqual(stream.calls, 2)
        self.assertEqual(self.job_state(job), "cancelled")
        self.assertEqual(self.artifacts(), [])
        self.assertEqual(self.artifact_files(), [])


class RuntimeFailsDuringRepair(GenerationHarness):
    def test_an_unreachable_runtime_during_the_repair_writes_nothing(self):
        """The repair is a second call, so it is a second chance to fail. The
        job must end without an artifact rather than half-written."""
        fenced = "```json\n" + body() + "\n```"
        job = self.send(self.REQUEST, skill_id=docflow.WRITE_SKILL)

        def stream(messages, *, should_cancel=None, profile=None, inference=None,
                   response_format=None, images=None):
            stream.calls += 1
            if stream.calls == 1:
                yield "delta", fenced
                yield "done", {"done_reason": "stop"}
                return
            raise runtime.RuntimeUnavailable("the runtime went away")
        stream.calls = 0

        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        self.assertEqual(stream.calls, 2)
        self.assertEqual(self.job_state(job), "failed")
        self.assertEqual(self.artifacts(), [])
        self.assertEqual(self.artifact_files(), [])


class OtherRoutesUnconstrained(Harness):
    """Only general generation opted into the schema. The other routes must be
    called exactly as they were, because their replies are different shapes."""

    def test_the_approval_note_route_gets_its_own_schema_not_the_documents(self):
        from backend.coordinator.test_documents import fake_stream
        record = self.attach("report.txt", b"page one\nvibration 7.9 mm/s")
        job = self.send("draft the approval note", skill_id=docflow.WRITE_SKILL,
                        doc_workflow=docflow.WORKFLOW_APPROVAL_NOTE)
        self.bind(job, record)
        cite = [{"source_id": record["attachment_id"], "page": 1}]
        reply = json.dumps({
            "title": "Approval note",
            "summary": {"text": "The pump exceeded its limit.",
                        "citations": cite},
            "findings": [{"text": "Vibration 7.9 mm/s.", "citations": cite}],
            "recommendation": {"text": "Re-torque and re-measure.",
                               "citations": cite},
            "unresolved": ["Suction pressure was not recorded."]})
        stream = fake_stream(reply)
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        # Batch 3 gave the approval note its own enforced shape. What must
        # stay true is that it is not handed the *document* one: the two
        # replies are different objects and either grammar would refuse the
        # other's output.
        self.assertIsNotNone(stream.response_format)
        self.assertNotEqual(stream.response_format,
                            docflow.GENERAL_DOCUMENT_FORMAT)
        self.assertEqual(stream.response_format, docflow.APPROVAL_NOTE_FORMAT)
        self.assertEqual(self.artifacts()[0]["workflow"],
                         docflow.WORKFLOW_APPROVAL_NOTE)


class ConversionUnaffected(GenerationHarness):
    def test_the_previous_answer_export_still_calls_no_model(self):
        self.completed_answer("The pump exceeded its vibration limit.")
        stream = scripted_stream(body())
        job = self.send("Create a document for your entire output",
                        skill_id=docflow.WRITE_SKILL)
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        self.assertEqual(stream.calls, 0, "conversion is deterministic")
        self.assertEqual(self.job_state(job), "completed")
        self.assertIn("The pump exceeded its vibration limit.", self.written())
        self.assertEqual(self.artifacts()[0]["workflow"],
                         docflow.WORKFLOW_CONVERSION)


if __name__ == "__main__":
    unittest.main()
