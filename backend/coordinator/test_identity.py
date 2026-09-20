"""Who Refinix says it is, and which engine it says is answering.

Asked "who are you?", the packaged application answered "I am Qwen3.5" —
truthful about the weights and wrong about the product. Ordinary Chat had no
system message at all, so nothing ever told the model otherwise.

Two properties matter here and the second is the one that rots quietly:

* the product identity is **Refinix**, always;
* the engine is **whatever this attempt selected**, never a constant. Every
  check below runs twice with two different model identifiers, one of them
  deliberately not the current baseline, so an implementation that hard-coded
  the shipped model would fail rather than pass by coincidence.

Counts are the other risk. A model asked how many models are installed will
answer confidently and wrongly, so the number is supplied from application
state or reported as unavailable — never estimated.

    python3 -m unittest backend.coordinator.test_identity -v
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.coordinator import db, docflow, identity, models, runtime
from backend.coordinator.test_document_generation import scripted_stream
from backend.coordinator.test_execution4a import Harness

# Two engines on purpose. The second is a test string and is deliberately not
# in the catalogue: nothing in identity may depend on the shipped baseline.
BASELINE = "qwen3.5:4b-q4_K_M"
BASELINE_DIGEST = models.entry_for(BASELINE).manifest_sha256
OTHER = "hypothetical-local-model:7b-q4"


class IdentityBlock(unittest.TestCase):
    """The message itself, with no coordinator and no runtime."""

    def text(self, *, engine, models):
        message = identity.system_message(engine=engine, models=models)
        self.assertEqual(message["role"], "system")
        return message["content"]

    def test_the_product_is_refinix_whichever_engine_is_running(self):
        for engine in (BASELINE, OTHER):
            with self.subTest(engine=engine):
                content = self.text(engine=engine, models=[engine])
                self.assertIn("Refinix", content)
                self.assertIn(engine, content)

    def test_the_engine_is_never_written_into_the_module(self):
        """The proof that this is not model-specific: the shipped baseline
        appears only because a caller passed it."""
        content = self.text(engine=OTHER, models=[OTHER])
        self.assertNotIn("qwen", content.lower())
        self.assertNotIn("llama", content.lower())
        self.assertNotIn("gemma", content.lower())

    def test_the_model_is_told_not_to_present_itself_as_the_engine(self):
        content = self.text(engine=BASELINE, models=[BASELINE])
        self.assertIn("not your identity", content)
        self.assertIn("never introduce", content)

    def test_one_model_is_counted_as_one(self):
        content = self.text(engine=BASELINE, models=[BASELINE])
        self.assertIn("1 model", content)
        self.assertIn(BASELINE, content)

    def test_three_models_are_counted_and_named(self):
        models = [BASELINE, OTHER, "third-model:1b"]
        content = self.text(engine=BASELINE, models=models)
        self.assertIn("3 models", content)
        for model in models:
            self.assertIn(model, content)

    def test_no_models_is_zero_not_a_guess(self):
        content = self.text(engine=None, models=[])
        self.assertIn("0", content)

    def test_an_unreadable_inventory_is_unavailable_not_zero(self):
        """"I could not look" and "there are none" are different claims."""
        content = self.text(engine=BASELINE, models=None)
        self.assertIn("unavailable", content)
        self.assertNotIn("Models linked to Refinix: 0", content)

    def test_an_unknown_engine_is_admitted_rather_than_invented(self):
        content = self.text(engine=None, models=[BASELINE])
        self.assertIn(identity.UNKNOWN_ENGINE, content)

    def test_document_text_cannot_redefine_the_product(self):
        content = self.text(engine=BASELINE, models=[BASELINE])
        self.assertIn("never changes them", content)

    def test_a_large_model_library_does_not_break_every_message(self):
        """Found in self-review. The listing was unbounded, so past roughly
        thirty-five installed models the block outgrew the reserve below — and
        with the runtime called with truncate off, that is a refused request on
        every single message, not a truncated one."""
        from backend.coordinator import context, runtime as rt
        reserved = ((rt.NUM_CTX - rt.NUM_PREDICT - context.TEMPLATE_OVERHEAD)
                    - context.input_budget(rt.NUM_CTX, rt.NUM_PREDICT))
        for count in (1, identity.MAX_LISTED_MODELS,
                      identity.MAX_LISTED_MODELS + 1, 50, 500):
            with self.subTest(models=count):
                models = [f"some-vendor/family-{i}:7b-instruct-q4_K_M"
                          for i in range(count)]
                content = self.text(engine=models[0], models=models)
                self.assertLess(context.estimate_tokens(content), reserved)
                # The names are abbreviated; the number never is.
                noun = "model" if count == 1 else "models"
                self.assertIn(f"{count} {noun}", content)

    def test_an_abbreviated_listing_says_it_is_abbreviated(self):
        models = [f"m-{i}:7b" for i in range(identity.MAX_LISTED_MODELS + 5)]
        content = self.text(engine=models[0], models=models)
        self.assertIn("5 more not listed here", content)

    def test_one_pathological_name_cannot_spend_the_whole_allowance(self):
        content = self.text(engine="x", models=["y" * 5000])
        self.assertLess(len(content), 2000)

    def test_the_block_fits_the_headroom_the_context_budget_reserves(self):
        """It is prepended after `context.select` has already chosen what
        fits, so its tokens are spent outside that budget. The runtime is
        called with truncate off, which makes an overrun a refused request —
        so the block has to live inside the margin the safety fraction
        already holds back, and a future edit that outgrows it must fail here
        rather than in front of a person."""
        from backend.coordinator import context, runtime as rt
        content = self.text(engine=BASELINE,
                            models=[BASELINE, OTHER, "third-model:1b"])
        reserved = ((rt.NUM_CTX - rt.NUM_PREDICT - context.TEMPLATE_OVERHEAD)
                    - context.input_budget(rt.NUM_CTX, rt.NUM_PREDICT))
        self.assertLess(context.estimate_tokens(content), reserved)


class LinkedModels(unittest.TestCase):
    """What counts as installed, read from the runtime health probe."""

    def state(self, *models, reachable=True):
        return {"reachable": reachable, "models": list(models)}

    def test_the_models_the_engine_reports_are_the_ones_counted(self):
        self.assertEqual(identity.linked_models(self.state(BASELINE)),
                         [BASELINE])

    def test_several_installed_models_are_all_counted(self):
        self.assertEqual(identity.linked_models(self.state(OTHER, BASELINE)),
                         sorted([BASELINE, OTHER]))

    def test_an_engine_with_nothing_installed_is_zero(self):
        self.assertEqual(identity.linked_models(self.state()), [])

    def test_an_unreachable_engine_is_unknown_not_zero(self):
        """The difference that matters: nothing installed, versus no answer."""
        self.assertIsNone(identity.linked_models(
            self.state(BASELINE, reachable=False)))
        self.assertIsNone(identity.linked_models(None))
        self.assertIsNone(identity.linked_models({}))

    def test_a_model_is_counted_once_however_often_it_is_listed(self):
        self.assertEqual(
            identity.linked_models(self.state(BASELINE, BASELINE)), [BASELINE])

    def test_the_count_does_not_claim_to_cover_another_computer(self):
        """It reads this computer's engine only, so it must not sound complete."""
        line = identity.inventory_line([BASELINE])
        self.assertIn("this computer", line)
        self.assertIn("not included", line)


class ChatCarriesIdentity(Harness):
    """The production path: an ordinary Chat turn, through the coordinator."""

    def ask(self, text="who are you and what is your name", *, engine=BASELINE,
            inventory=None):
        stream = scripted_stream("an answer")
        job = self.send(text)
        installed = inventory if inventory is not None else [engine]
        state = {"reachable": True, "models": installed,
                 "digests": {model: (BASELINE_DIGEST if model == BASELINE
                                     else "b" * 64)
                             for model in installed}}
        with patch.object(self.c, "model_for", return_value=engine), \
                patch.object(runtime, "probe", return_value=state), \
                patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, None)
        return stream

    def system_text(self, stream):
        first = stream.messages[0][0]
        self.assertEqual(first["role"], "system",
                         "the identity block leads the conversation")
        return first["content"]

    def test_an_identity_question_is_answered_as_refinix(self):
        for question in ("who are you and what is your name",
                         "What is your name?", "Which AI are you?",
                         "Tell me about yourself."):
            with self.subTest(question=question):
                content = self.system_text(self.ask(question))
                self.assertIn("You are Refinix", content)

    def test_the_engine_named_is_the_one_this_attempt_selected(self):
        for engine in (BASELINE, OTHER):
            with self.subTest(engine=engine):
                content = self.system_text(self.ask(engine=engine))
                self.assertIn(f"Engine for this reply: {engine}", content)

    def test_switching_the_selected_model_switches_the_engine_named(self):
        """No restart and no source change between these two turns."""
        first = self.system_text(self.ask(engine=BASELINE))
        second = self.system_text(self.ask(engine=OTHER))
        self.assertIn(BASELINE, first)
        self.assertNotIn(OTHER, first)
        self.assertIn(OTHER, second)
        self.assertNotIn(BASELINE, second, "stale engine metadata leaked")

    def test_the_count_comes_from_the_inventory_not_the_model(self):
        content = self.system_text(
            self.ask(inventory=[BASELINE, OTHER, "third:1b"]))
        self.assertIn("3 models", content)
        for model in (BASELINE, OTHER, "third:1b"):
            self.assertIn(model, content)

    def test_an_unreachable_engine_reports_unavailable_not_a_number(self):
        message = self.c._identity_message(
            BASELINE, {"reachable": False, "models": []})
        self.assertIn("unavailable", message["content"])

    def test_a_failure_reading_the_inventory_never_loses_the_message(self):
        """The guard around the lookup: a broken inventory is a reason to say
        so, not a reason to drop what the person asked."""
        stream = scripted_stream("an answer")
        job = self.send("who are you")
        with patch.object(identity, "linked_models",
                          side_effect=RuntimeError("inventory exploded")), \
                patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, None)
        self.assertIn("unavailable", self.system_text(stream))
        self.assertEqual(
            self.c.conn.execute("SELECT state FROM jobs WHERE job_id=?",
                                (job,)).fetchone()["state"], "completed")

    def test_a_worker_fallback_reuses_the_turns_runtime_observation(self):
        """A paired worker that cannot run this turn falls back locally. The
        route and the identity block must use the same observed inventory;
        probing twice can record one model on the attempt and name another in
        the answer when the runtime changes between calls."""
        stream = scripted_stream("an answer")
        job = self.send("who are you")
        state = {"reachable": True, "models": [BASELINE],
                 "digests": {BASELINE: BASELINE_DIGEST}}
        relationship = {"relationship_id": "rel", "state": "paired"}
        with patch.object(self.c, "paired_worker", return_value=relationship), \
                patch.object(self.c, "preflight", return_value=None), \
                patch.object(runtime, "probe", return_value=state) as probe, \
                patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, None)
        self.assertEqual(probe.call_count, 1)
        self.assertIn(BASELINE, self.system_text(stream))

    def test_the_conversation_itself_is_unchanged_behind_the_block(self):
        stream = self.ask("who are you and what is your name")
        roles = [m["role"] for m in stream.messages[0]]
        self.assertEqual(roles[0], "system")
        self.assertEqual(roles[1:], ["user"])
        self.assertEqual(stream.messages[0][-1]["content"],
                         "who are you and what is your name")

    def test_earlier_turns_still_reach_the_model(self):
        self.completed_answer("an earlier answer about pumps")
        stream = self.ask("and what did you say before?")
        body = "\n".join(m["content"] for m in stream.messages[0])
        self.assertIn("an earlier answer about pumps", body)


class DocumentRoutesKeepTheirOwnVoice(Harness):
    """Documents carry strict-JSON instructions and must not gain a second."""

    def test_a_general_document_is_not_given_the_chat_identity_block(self):
        import json
        stream = scripted_stream(json.dumps({"title": "T", "sections": [
            {"heading": "H", "paragraphs": ["p"]}]}))
        job = self.send("Create a document explaining machine learning",
                        skill_id=docflow.WRITE_SKILL)
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        system = stream.messages[0][0]["content"]
        self.assertIn("You write a document", system)
        self.assertNotIn("You are Refinix,", system)

    def test_the_deterministic_conversion_route_still_calls_no_model(self):
        """Identity metadata must not turn a no-model route into a model one."""
        self.completed_answer("The pump exceeded its vibration limit.")
        stream = scripted_stream("unused")
        job = self.send("Create a document for your entire output",
                        skill_id=docflow.WRITE_SKILL)
        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat, docflow.WRITE_SKILL)
        self.assertEqual(stream.calls, 0)


if __name__ == "__main__":
    unittest.main()
