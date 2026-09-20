"""Which document route a request takes, and what actually reaches the model.

Write Document has three destinations and only one of them may call a model:

    conversion   the previous answer, copied. No model, ever.
    general      a new document written by the model from the request.
    approval     the fixed grounded workflow, when files are attached.

A real request — "Create a document for your entire output", with a long
finished answer above it — took the *general* route and produced a few lines of
generic filler. Two defects did it, and this module exists so neither can come
back quietly:

* the route was chosen from the document verb, and `create` was missing from the
  verb list. The repair keys on the reference to earlier output instead, which is
  the only thing that actually separates "put what you said in a file" from
  "write me something new";
* `general_document_messages` read `content` from rows that carry `text`, so the
  conversation silently vanished from every general document. The old check for
  it asserted a length bound on a hand-built `content` row — the one shape
  production never supplies — so it passed while production was broken. These
  checks assert the history **text** is in the prompt, and drive the real
  coordinator rather than the helper.

Synthetic only: a temporary database, a stubbed runtime, no model and no network.

    python3 -m unittest backend.coordinator.test_document_intent -v
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from backend.coordinator import db, docflow, docgen, runtime
from backend.coordinator.test_documents import fake_stream
from backend.coordinator.test_execution4a import Harness

# ---------------------------------------------------------------------------
# The phrase matrix. One table, so a new phrase is one line and the expected
# route is stated beside it rather than implied by which test it sits in.
# ---------------------------------------------------------------------------

CONVERSION = "conversion"
GENERAL = "general"

PHRASES = [
    # The reported request, and the variants a person actually types.
    ("Create a document for your entire output", CONVERSION),
    ("Create a PDF of your previous answer", CONVERSION),
    ("Put your previous answer in a Word document", CONVERSION),
    ("Save this as a PDF", CONVERSION),
    ("Export the answer above as DOCX", CONVERSION),
    ("Turn your last response into a document", CONVERSION),
    ("Make a Word file from what you just wrote", CONVERSION),
    # Same intent, other wordings.
    ("Create a document of your entire output", CONVERSION),
    ("Save that response as a document", CONVERSION),
    ("Make a DOCX of everything you just wrote", CONVERSION),
    ("Export the above response to Word", CONVERSION),
    ("Put all of that into a document", CONVERSION),
    ("Save your last answer as Word", CONVERSION),
    ("Turn the previous response into a DOCX", CONVERSION),
    ("Convert your reply to a file", CONVERSION),
    ("Save it as a PDF", CONVERSION),
    ("Convert it to a Word file", CONVERSION),
    # Historically supported; must not regress.
    ("save this as a pdf", CONVERSION),
    ("export that to pdf", CONVERSION),
    ("save that as a docx", CONVERSION),

    # New subject matter. These share every verb and format word with the
    # conversion rows above; only the missing reference separates them.
    ("Create a document explaining machine learning", GENERAL),
    ("Write me a document explaining machine learning", GENERAL),
    ("Write a report about pump maintenance", GENERAL),
    ("Create a risk memo for Project Atlas", GENERAL),
    ("Generate a report with three sections", GENERAL),
    ("Produce a maintenance checklist for Pump P-204", GENERAL),
    ("Write a document summarising these requirements", GENERAL),
    ("write me a document about pumps", GENERAL),
    ("Draft a new Word document about cavitation", GENERAL),
    ("Prepare a two-page note about bearing failures", GENERAL),
    ("Create a document describing the inspection process", GENERAL),
    ("Generate a summary of pump cavitation", GENERAL),
    # A pointer word and an output noun in the same sentence, but not a
    # reference to a reply. A rule that allowed any word or two between them
    # read every one of these as "copy the previous answer".
    ("Create a report on your findings and response times", GENERAL),
    ("Write a document about the last inspection response time", GENERAL),
    ("Write a report on your team message to staff", GENERAL),
    # A demonstrative inside a request for something new.
    ("Write a document listing the parts and where to find it", GENERAL),
    ("Create a document with three sections and number it", GENERAL),
    ("Generate a checklist for the pump and attach it", GENERAL),
]


class PhraseMatrix(unittest.TestCase):
    """Every phrase, both directions, with nothing attached."""

    def test_every_phrase_takes_its_stated_route(self):
        for request, expected in PHRASES:
            with self.subTest(request=request, expected=expected):
                chose = docflow.looks_like_conversion(
                    request, has_attachments=False)
                self.assertEqual(CONVERSION if chose else GENERAL, expected)

    def test_an_attachment_always_wins(self):
        """An attached file is what the person means when they attach one, so
        no phrasing may turn the request into a copy of the previous answer."""
        for request, _expected in PHRASES:
            with self.subTest(request=request):
                self.assertFalse(docflow.looks_like_conversion(
                    request, has_attachments=True))

    def test_an_attachment_request_is_never_a_conversion(self):
        for request in ("Create a report from this PDF",
                        "Summarise this document",
                        "Compare this SOP and inspection report"):
            with self.subTest(request=request):
                self.assertFalse(docflow.looks_like_conversion(
                    request, has_attachments=True))

    def test_a_request_with_no_document_verb_is_not_a_conversion(self):
        for request in ("What did your previous answer say?",
                        "your previous answer", "", "   ", None):
            with self.subTest(request=request):
                self.assertFalse(docflow.looks_like_conversion(
                    request, has_attachments=False))


class ClassifierRule(unittest.TestCase):
    """The two defects, named, so a future edit cannot reintroduce either."""

    def convert(self, request):
        return docflow.looks_like_conversion(request, has_attachments=False)

    def test_create_is_a_document_verb(self):
        """The reported regression: `create` was absent from the verb list, so
        the most natural phrasing fell through to generation."""
        for verb in ("Create", "Generate", "Produce", "Make", "Save", "Export",
                     "Turn", "Put", "Convert", "Write", "Render", "Download"):
            with self.subTest(verb=verb):
                self.assertTrue(self.convert(f"{verb} a file of your previous answer"))

    def test_a_document_verb_alone_never_chooses_conversion(self):
        """Why completing the verb list is safe: the reference decides. Adding
        `create` without this would have sent every "Create a document
        explaining X" into the copy path."""
        for request in ("Create a document explaining machine learning",
                        "Generate a report with three sections",
                        "Produce a maintenance checklist for Pump P-204",
                        "Write a document about pumps"):
            with self.subTest(request=request):
                self.assertFalse(self.convert(request))

    def test_inflected_subject_words_still_block_the_weak_branch(self):
        """`explain` did not match "explaining" and `summar(y|ise|ize) of` did
        not match "summarising", which is how a new-document request could be
        answered with a copy of the previous answer."""
        for request in ("Save this document explaining machine learning",
                        "Make this a file summarising the requirements",
                        "Turn this into a document describing the pump",
                        "Save this as a file covering bearing failures"):
            with self.subTest(request=request):
                self.assertFalse(self.convert(request))

    def test_an_explicit_reference_outranks_a_subject_word(self):
        """A named reference is the strong signal: the person pointed at
        something that already exists, so it is copied rather than rewritten."""
        self.assertTrue(self.convert(
            "Save your previous answer about pump maintenance as a docx"))

    def test_a_plural_demonstrative_points_at_subject_matter(self):
        """"these requirements" is a topic; "this" with a format word is the
        answer just given."""
        self.assertFalse(self.convert(
            "Write a document summarising these requirements"))
        self.assertTrue(self.convert("Save this as a PDF"))

    def test_a_bare_demonstrative_needs_a_format_word(self):
        self.assertTrue(self.convert("Save this as a document"))
        self.assertFalse(self.convert("Save this for later"))

    def test_only_known_modifiers_may_sit_between_pointer_and_noun(self):
        """Found in self-review. Allowing any word or two in that gap made
        "your findings and response times" read as a reference to a reply, so a
        plain request for a new report was answered with an old one."""
        for request in ("Create a report on your findings and response times",
                        "Write a document about the last inspection response time",
                        "Write a report on your team message to staff",
                        "Create a file on your client response process"):
            with self.subTest(request=request):
                self.assertFalse(self.convert(request))

    def test_a_named_modifier_still_reaches_the_noun(self):
        for request in ("Save your previous answer as a docx",
                        "Export your very last answer to Word",
                        "Create a document for your entire output",
                        "Turn the above response into a file"):
            with self.subTest(request=request):
                self.assertTrue(self.convert(request))

    def test_a_demonstrative_only_counts_for_a_transformation_verb(self):
        """Also found in self-review. `create`/`generate`/`write` ask for
        something new, so a stray "it" in one of those must not file the
        previous answer instead."""
        for request in ("Write a document listing the parts and where to find it",
                        "Create a document with three sections and number it",
                        "Generate a checklist for the pump and attach it"):
            with self.subTest(request=request):
                self.assertFalse(self.convert(request))
        for request in ("Save it as a PDF", "Convert it to a Word file",
                        "Turn this into a document",
                        "Put all of that into a document"):
            with self.subTest(request=request):
                self.assertTrue(self.convert(request))


# ---------------------------------------------------------------------------
# What reaches the model on the general route
# ---------------------------------------------------------------------------

class HistoryBinding(unittest.TestCase):
    """The conversation must be in the prompt, whichever shape it arrived in."""

    ANSWER = "Deep learning stacks differentiable layers."

    def prompt(self, history):
        built = docflow.general_document_messages("write a report", [], history)
        return built[-1]["content"]

    def test_a_production_database_row_reaches_the_prompt(self):
        """`chat_messages` returns `messages` rows, which carry `text`. Reading
        only `content` is what made every general document historyless."""
        prompt = self.prompt([{"role": "assistant", "text": self.ANSWER,
                               "message_id": "m1", "chat_id": "c",
                               "created_at": "now", "job_id": "j"}])
        self.assertIn(self.ANSWER, prompt)
        self.assertIn("EARLIER IN THIS CONVERSATION", prompt)

    def test_a_model_facing_message_still_reaches_the_prompt(self):
        """`context.select` hands back `content`. Both shapes are legitimate."""
        prompt = self.prompt([{"role": "assistant", "content": self.ANSWER}])
        self.assertIn(self.ANSWER, prompt)

    def test_both_shapes_together_are_carried(self):
        prompt = self.prompt([{"role": "user", "text": "explain deep learning"},
                              {"role": "assistant", "content": self.ANSWER}])
        self.assertIn("explain deep learning", prompt)
        self.assertIn(self.ANSWER, prompt)

    def test_the_request_is_always_present(self):
        self.assertIn("write a report", self.prompt([]))

    def test_no_history_adds_no_earlier_block(self):
        self.assertNotIn("EARLIER IN THIS CONVERSATION", self.prompt([]))

    def test_a_row_with_no_usable_body_is_skipped_not_rendered_as_none(self):
        prompt = self.prompt([{"role": "assistant", "text": ""},
                              {"role": "assistant", "text": None},
                              {"role": "assistant"}])
        self.assertNotIn("None", prompt)
        self.assertNotIn("EARLIER IN THIS CONVERSATION", prompt)

    def test_only_conversation_roles_are_carried(self):
        prompt = self.prompt([{"role": "system", "text": "a system rule"},
                              {"role": "assistant", "text": self.ANSWER}])
        self.assertNotIn("a system rule", prompt)
        self.assertIn(self.ANSWER, prompt)

    def test_the_history_is_still_bounded(self):
        history = [{"role": "user", "text": "history " * 4000}]
        blocks = self.prompt(history).partition("\n\n")[2]
        self.assertLessEqual(len(blocks), docflow.MAX_CONTEXT_CHARS)
        self.assertIn("history", blocks)


# ---------------------------------------------------------------------------
# The real orchestration decision
# ---------------------------------------------------------------------------

class CoordinatorRouting(Harness):
    """The reported request, driven through a real coordinator and database.

    The classifier checks above would still have passed with the production
    wiring broken. These run `Coordinator._run`, which is what actually chose
    the wrong route.
    """

    ANSWER = ("# Deep machine learning\n\nDeep learning uses layered neural "
              "networks trained by gradient descent.\n\n## Backpropagation\n\n"
              "Gradients flow backwards through every layer.")

    def artifact_text(self):
        rows = self.artifacts()
        self.assertEqual(len(rows), 1, "exactly one artifact was expected")
        root = db.artifacts_root(self.c.state_path)
        return "\n".join(docgen.read_text(root / rows[0]["stored_name"])), rows[0]

    def job_state(self, job):
        return self.c.conn.execute(
            "SELECT state FROM jobs WHERE job_id=?", (job,)).fetchone()["state"]

    def test_the_reported_request_copies_the_previous_answer(self):
        """"Create a document for your entire output" — the exact request that
        produced a few lines of generic filler."""
        self.completed_answer(self.ANSWER)
        job = self.send("Create a document for your entire output",
                        skill_id=docflow.WRITE_SKILL,
                        output_format=docflow.FORMAT_DOCX)
        with patch.object(runtime, "stream_chat") as never:
            self.c._run(job, self.chat, docflow.WRITE_SKILL)

        # 1. no model was asked to write the document
        never.assert_not_called()
        # 2. the job finished
        self.assertEqual(self.job_state(job), "completed")
        text, row = self.artifact_text()
        # 3. the artifact records the deterministic route
        self.assertEqual(row["workflow"], docflow.WORKFLOW_CONVERSION)
        # 4. the previous answer is in the file, wording intact
        self.assertIn("Deep learning uses layered neural networks", text)
        self.assertIn("Gradients flow backwards through every layer.", text)
        # 5. and none of the filler the broken route produced
        self.assertNotIn("No external data or instructions were provided", text)

    def test_a_new_document_request_reaches_generation_with_the_history(self):
        """The other direction: a subject was named, so the model writes, and
        the conversation it needs is actually in the prompt."""
        self.completed_answer(self.ANSWER)
        job = self.send("Create a document explaining machine learning",
                        skill_id=docflow.WRITE_SKILL,
                        output_format=docflow.FORMAT_DOCX)
        reply = json.dumps({"title": "Machine learning", "sections": [
            {"heading": "Overview", "paragraphs": ["A written explanation."]}]})
        stream = fake_stream(reply)
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)

        # 1. the model was asked to write it
        self.assertIsNotNone(stream.messages, "the model was never called")
        prompt = stream.messages[-1]["content"]
        self.assertIn("Create a document explaining machine learning", prompt)
        # 2. the earlier conversation reached the prompt — the defect that made
        #    the model answer "no external data was provided"
        self.assertIn("Deep learning uses layered neural networks", prompt)
        self.assertIn("EARLIER IN THIS CONVERSATION", prompt)
        # 3. the artifact is the new document, not a copy of the answer
        self.assertEqual(self.job_state(job), "completed")
        text, row = self.artifact_text()
        self.assertEqual(row["workflow"], docflow.WORKFLOW_GENERAL)
        self.assertIn("A written explanation.", text)
        self.assertNotIn("Gradients flow backwards", text)

    def test_the_reported_request_without_an_answer_refuses_honestly(self):
        """No completed answer to copy must not become a generated document."""
        job = self.send("Create a document for your entire output",
                        skill_id=docflow.WRITE_SKILL)
        with patch.object(runtime, "stream_chat") as never:
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        never.assert_not_called()
        self.assertEqual(self.artifacts(), [])
        self.assertEqual(self.job_state(job), "failed")
        self.assertEqual(self.artifact_files(), [])

    def test_a_pdf_conversion_request_also_takes_the_copy_route(self):
        """Routing is decided before the format, so "Create a PDF of your
        previous answer" must not depend on PDF output being available."""
        self.completed_answer(self.ANSWER)
        job = self.send("Create a PDF of your previous answer",
                        skill_id=docflow.WRITE_SKILL)
        _messages, _prepared, extra = self.c._document_stage(
            job, self.chat, docflow.WRITE_SKILL, [],
            ocr_model=self.c.model_for("documents.ocr"))
        self.assertEqual(extra["workflow"], docflow.WORKFLOW_CONVERSION)
        self.assertIn("Deep learning uses layered neural networks",
                      extra["conversion"]["text"])

    def test_the_answer_being_requested_is_never_its_own_source(self):
        self.completed_answer("the finished answer")
        job = self.send("Create a document for your entire output",
                        skill_id=docflow.WRITE_SKILL)
        _messages, _prepared, extra = self.c._document_stage(
            job, self.chat, docflow.WRITE_SKILL, [],
            ocr_model=self.c.model_for("documents.ocr"))
        self.assertEqual(extra["conversion"]["text"], "the finished answer")
        self.assertNotEqual(extra["conversion"]["job_id"], job)


if __name__ == "__main__":
    unittest.main()
