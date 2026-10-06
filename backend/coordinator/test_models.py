"""The model lifecycle: catalogue, states, self-tests and what a change breaks.

The failures these checks are written against are all ways the product could
look more certain than it is:

* treating "the engine did not answer" as "nothing is installed";
* promoting a model the local runtime happens to list into a supported entry
  with implied provenance;
* letting a self-test observed against one set of bytes vouch for another;
* recording a missing prerequisite as a failure of the model;
* implying that switching a model off, or removing it, takes a person's
  conversations and artifacts with it.

Nothing here downloads, installs, removes or calls a model. The generation
step is supplied by the caller, and every test supplies a fake.

    python3 -m unittest backend.coordinator.test_models -v
"""

import inspect
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from backend.contracts import profiles, v1
from backend.contracts import profiles as inference_profiles
from backend.coordinator import db, device, docgen, models, runtime
from backend.coordinator.server import Coordinator

CATALOGUED = models.CATALOGUE[0].id
CATALOG_DIGEST = models.CATALOGUE[0].manifest_sha256
WORKER_CHAT_PROFILE = next(
    profile for profile in profiles.PROFILES
    if profile.target_profile_id == profiles.UBUNTU_VICTUS_RTX2050
    and profile.workflow_mode == profiles.CHAT
    and profile.model.runtime_version == "0.33.2")


def chat_reply(_model, _messages, **_options):
    """A model that applies the supplied rule and gets the direction right.

    It used to be "Four.", which passed because the check only asked whether
    anything came back. The Chat self-test now applies a supplied comparison,
    so a stand-in for a working model has to hold that comparison.
    """
    return (f"unsafe; smaller number: {models.CHAT_CHECK_SMALLER}")


def reversed_chat_reply(_model, _messages, **_options):
    """Fluent, complete, and with the comparison the wrong way round."""
    return (f"safe; smaller number: {models.CHAT_CHECK_LARGER}")


def document_reply(_model, _messages, **_options):
    return json.dumps({"title": "Refinix", "sections": [
        {"heading": "Overview", "paragraphs": ["Refinix runs locally."]}]})


class TestTheCatalogue(unittest.TestCase):
    def test_it_holds_only_entries_whose_provenance_was_recorded(self):
        for entry in models.CATALOGUE:
            with self.subTest(model=entry.id):
                self.assertTrue(entry.source)
                self.assertTrue(entry.licence)
                self.assertEqual(len(entry.manifest_sha256 or ""), 64)
                self.assertTrue(entry.evidence)
                # Inspected artifacts are VERIFIED; library entries are LISTED:
                # pinned from the publisher's metadata, never measured here.
                self.assertIn(entry.evidence_state, (models.VERIFIED, models.LISTED))
                if entry.evidence_state == models.LISTED:
                    self.assertTrue(entry.files and entry.revision and entry.repo)
                    self.assertTrue(all(len(f.sha256) == 64 and f.size > 0
                                        and f.url.startswith("https://huggingface.co/")
                                        and entry.revision in f.url
                                        for f in entry.files))

    def test_a_research_candidate_is_not_offered_as_a_supported_model(self):
        """`docs/model-catalog.md`: unqualified candidates are not download
        offers. The OCR conversion has unresolved provenance, so it may be
        annotated but never listed."""
        self.assertNotIn("MedAIBase/PaddleOCR-VL:0.9b", models.BY_ID)
        note = models.provenance("MedAIBase/PaddleOCR-VL:0.9b")
        self.assertFalse(note["known"])
        self.assertEqual(note["evidence_state"], models.UNRESOLVED)
        self.assertIn("unresolved", note["note"])

    def test_an_unknown_model_is_reported_as_unverified_rather_than_unknown_quality(self):
        note = models.provenance("somebody/random:latest")
        self.assertFalse(note["known"])
        self.assertEqual(note["evidence_state"], models.UNVERIFIED)
        self.assertIn("no recorded source", note["note"])

    def test_the_setup_action_is_a_command_the_person_runs_themselves(self):
        action = models.setup_action(CATALOGUED)
        self.assertEqual(action["kind"], "command")
        self.assertIn("ollama pull", action["command"])
        self.assertIn("does not start downloads", action["detail"])

    def test_nothing_is_offered_for_a_model_refinix_does_not_vouch_for(self):
        self.assertIsNone(models.setup_action("somebody/random:latest"))


class TestLifecycleStates(unittest.TestCase):
    def test_an_unreachable_engine_is_unknown_not_absent(self):
        self.assertEqual(
            models.lifecycle_state(CATALOGUED, installed_here=False,
                                   installed_elsewhere=False,
                                   runtime_reachable=False),
            models.UNAVAILABLE)

    def test_a_supported_model_the_engine_did_not_list_is_absent(self):
        self.assertEqual(
            models.lifecycle_state(CATALOGUED, installed_here=False,
                                   installed_elsewhere=False,
                                   runtime_reachable=True),
            models.ABSENT)

    def test_an_installed_model_without_provenance_stays_unlisted(self):
        self.assertEqual(
            models.lifecycle_state("somebody/random:latest", installed_here=True,
                                   installed_elsewhere=False,
                                   runtime_reachable=True),
            models.UNLISTED)

    def test_absence_is_absence_whether_or_not_refinix_vouches_for_it(self):
        """The state answers "is it here". Whether Refinix records a manifest
        is `provenance`, and folding the two together made an ordinary missing
        model read as "unknown"."""
        self.assertEqual(
            models.lifecycle_state("somebody/random:latest", installed_here=False,
                                   installed_elsewhere=False,
                                   runtime_reachable=True),
            models.ABSENT)
        self.assertIsNone(models.setup_action("somebody/random:latest"))

    def test_a_model_on_a_peer_counts_as_installed(self):
        self.assertEqual(
            models.lifecycle_state(CATALOGUED, installed_here=False,
                                   installed_elsewhere=True,
                                   runtime_reachable=True),
            models.INSTALLED)


class TestSelfTests(unittest.TestCase):
    def test_a_passing_check_says_what_it_does_not_prove(self):
        result = models.run_selftest(models.CHAT, CATALOGUED,
                                     generate=chat_reply)
        self.assertEqual(result["state"], models.PASSED)
        self.assertIn("nothing about the quality", result["detail"])

    def test_an_empty_answer_is_a_failure_rather_than_a_pass(self):
        result = models.run_selftest(models.CHAT, CATALOGUED,
                                     generate=lambda *_args, **_kwargs: "   ")
        self.assertEqual(result["state"], models.FAILED)

    def test_chat_applies_a_supplied_rule_rather_than_asking_for_any_reply(self):
        """A packaged run answered a pump question fluently with the central
        comparison reversed, and Chat was self-tested at the time — because the
        check was "what is 2 + 2?" and only looked for a non-empty reply. The
        premise lives in the prompt so a failure means the model could not hold
        a relation, not that it did not know something."""
        seen = {}

        def generate(_model, messages, **_options):
            seen["prompt"] = messages[0]["content"]
            return chat_reply(_model, messages)

        result = models.run_selftest(models.CHAT, CATALOGUED, generate=generate)
        self.assertEqual(result["state"], models.PASSED)
        for supplied in (models.CHAT_CHECK_SMALLER, models.CHAT_CHECK_LARGER,
                         "below"):
            self.assertIn(supplied, seen["prompt"])

    def test_a_reversed_relation_fails_chat_however_fluent_it_is(self):
        result = models.run_selftest(models.CHAT, CATALOGUED,
                                     generate=reversed_chat_reply)
        self.assertEqual(result["state"], models.FAILED)
        self.assertIn("safe", result["detail"])

    def test_a_reply_that_never_commits_to_an_ordering_is_not_a_pass(self):
        """Half the check is a coin flip on its own. A verdict with no
        comparison behind it has not been checked against anything."""
        result = models.run_selftest(
            models.CHAT, CATALOGUED,
            generate=lambda *_a, **_k: "The operation is unsafe.")
        self.assertEqual(result["state"], models.FAILED)

    def test_the_exact_line_that_was_asked_for_passes(self):
        for shape in (f"unsafe; smaller number: {models.CHAT_CHECK_SMALLER}",
                      f"Unsafe; Smaller number: {models.CHAT_CHECK_SMALLER}",
                      f"unsafe ; smaller number : {models.CHAT_CHECK_SMALLER}."):
            with self.subTest(reply=shape):
                result = models.run_selftest(
                    models.CHAT, CATALOGUED,
                    generate=lambda *_a, _s=shape, **_k: _s)
                self.assertEqual(result["state"], models.PASSED)

    def test_a_negated_verdict_is_not_read_as_the_verdict(self):
        """Found in review. Searching for the token `unsafe` anywhere in the
        reply passed "not unsafe": the negation sits outside the pattern, and
        the answer it was actually giving was the wrong one."""
        result = models.run_selftest(
            models.CHAT, CATALOGUED,
            generate=lambda *_a, **_k:
                f"not unsafe; smaller number: {models.CHAT_CHECK_SMALLER}")
        self.assertEqual(result["state"], models.FAILED)

    def test_a_reply_that_answers_then_contradicts_itself_fails(self):
        """Found in review. A right answer followed by a reversed one is not a
        model that holds the relation; it is a model that wrote both."""
        result = models.run_selftest(
            models.CHAT, CATALOGUED,
            generate=lambda *_a, **_k:
                (f"unsafe; smaller number: {models.CHAT_CHECK_SMALLER} — but "
                 f"actually {models.CHAT_CHECK_SMALLER} exceeds "
                 f"{models.CHAT_CHECK_LARGER}"))
        self.assertEqual(result["state"], models.FAILED)

    def test_prose_instead_of_the_asked_form_fails_as_a_shape_not_a_reversal(self):
        """Both are failures, and they are different failures: a person reading
        the result should not be told the model reversed a relation when it
        only ignored the format."""
        result = models.run_selftest(
            models.CHAT, CATALOGUED,
            generate=lambda *_a, **_k:
                "The operation is unsafe because 2.4 is less than 3.1.")
        self.assertEqual(result["state"], models.FAILED)
        self.assertIn("single line", result["detail"])
        self.assertNotIn("smaller number when", result["detail"])

    def test_no_reply_is_checked_for_a_pump_or_any_other_subject(self):
        """The fix for the observed failure is a shared reliability boundary,
        not a fact table. A subject-specific branch here would mean Refinix got
        one topic right and every neighbouring one still wrong."""
        source = inspect.getsource(models)
        for trivia in ("npsh", "cavitat", "centrifugal", "pump"):
            self.assertNotIn(trivia, source.casefold())

    def test_code_requires_a_parseable_proposal_not_any_nonempty_reply(self):
        result = models.run_selftest(
            models.CODE, CATALOGUED,
            generate=lambda *_args, **_kwargs: "ready")
        self.assertEqual(result["state"], models.FAILED)
        self.assertIn("valid Code proposal", result["detail"])

    def test_ocr_sends_an_image_and_requires_its_visible_text(self):
        seen = {}

        def generate(_model, _messages, **options):
            seen.update(options)
            return json.dumps({"status": "transcription", "text": "REFINIX"})

        result = models.run_selftest(
            models.DOCUMENTS_OCR, "ocr:1", generate=generate,
            capabilities=[runtime.VISION_CAPABILITY])
        self.assertEqual(result["state"], models.PASSED)
        self.assertTrue(seen["images"][0].startswith(b"\x89PNG"))

    def test_a_missing_prerequisite_is_unavailable_not_a_failed_model(self):
        with self.assertRaises(models.SelfTestError):
            models.run_selftest(models.CHAT, CATALOGUED, generate=None)

    def test_a_runtime_error_never_becomes_a_verdict_on_the_model(self):
        def broken(*_args, **_kwargs):
            raise runtime.RuntimeUnavailable("the engine went away")
        with self.assertRaises(models.SelfTestError) as caught:
            models.run_selftest(models.CHAT, CATALOGUED, generate=broken)
        self.assertIn("went away", str(caught.exception))

    def test_a_model_that_declares_no_vision_fails_the_page_check(self):
        result = models.run_selftest(models.DOCUMENTS_OCR, "ocr:1",
                                     generate=lambda *_: "ready",
                                     capabilities=["completion"])
        self.assertEqual(result["state"], models.FAILED)
        self.assertIn("does not accept page images", result["detail"])

    def test_unknown_capabilities_are_unavailable_rather_than_assumed_missing(self):
        with self.assertRaises(models.SelfTestError):
            models.run_selftest(models.DOCUMENTS_OCR, "ocr:1",
                                generate=lambda *_: "ready", capabilities=None)

    def test_the_document_check_writes_and_reopens_a_real_word_file(self):
        """No model is needed for the artifact half, so it is run for real."""
        observed = docgen.selftest()
        self.assertTrue(observed["valid"], observed["detail"])
        result = models.run_selftest(models.DOCUMENTS_GENERATE, CATALOGUED,
                                     generate=document_reply,
                                     artifact=docgen.selftest)
        self.assertEqual(result["state"], models.PASSED)

    def test_a_writer_that_cannot_produce_a_document_fails_the_check(self):
        result = models.run_selftest(
            models.DOCUMENTS_GENERATE, CATALOGUED,
            generate=document_reply,
            artifact=lambda **_kwargs:
                {"valid": False, "detail": "no temporary folder"})
        self.assertEqual(result["state"], models.FAILED)
        self.assertIn("no temporary folder", result["detail"])

    def test_an_unknown_workflow_has_no_self_test_to_invent(self):
        with self.assertRaises(models.SelfTestError):
            models.run_selftest("nonsense", CATALOGUED)


class TestSelfTestView(unittest.TestCase):
    def record(self, **over):
        base = {"model": CATALOGUED, "scope": models.CHAT, "state": models.PASSED,
                "detail": "ok", "digest": "a" * 64, "runtime_version": "0.33.3",
                "ran_at": "2026-09-20T00:00:00Z"}
        base.update(over)
        return base

    def test_a_result_from_different_bytes_cannot_vouch_for_what_is_installed(self):
        view = models.selftest_view([self.record()], model=CATALOGUED,
                                    digest="b" * 64)
        self.assertTrue(view[models.CHAT]["superseded"])
        self.assertFalse(view[models.CHAT]["current"])
        # The record is kept: that a check was once run is still a fact.
        self.assertEqual(view[models.CHAT]["state"], models.PASSED)

    def test_a_matching_digest_is_current(self):
        view = models.selftest_view([self.record()], model=CATALOGUED,
                                    digest="a" * 64)
        self.assertTrue(view[models.CHAT]["current"])
        self.assertFalse(view[models.CHAT]["superseded"])

    def test_a_pass_cannot_be_current_when_the_installed_bytes_are_unknown(self):
        """The engine is down, or the model is gone. A pass observed against
        bytes nobody can see now proves nothing about the present, and calling
        it current would let an uninstalled model look ready."""
        view = models.selftest_view([self.record()], model=CATALOGUED,
                                    digest=None)
        self.assertEqual(view[models.CHAT]["state"], models.PASSED)
        self.assertFalse(view[models.CHAT]["current"])
        # Not superseded either: nothing was observed to differ from.
        self.assertFalse(view[models.CHAT]["superseded"])

    def test_a_record_with_no_digest_cannot_vouch_for_installed_bytes(self):
        view = models.selftest_view([self.record(digest=None)],
                                    model=CATALOGUED, digest="a" * 64)
        self.assertFalse(view[models.CHAT]["current"])
        self.assertFalse(view[models.CHAT]["superseded"])

    def test_every_workflow_appears_even_when_it_was_never_checked(self):
        view = models.selftest_view([], model=CATALOGUED, digest=None)
        self.assertEqual(set(view), set(models.SELFTESTS))
        self.assertTrue(all(row["state"] == models.NOT_RUN for row in view.values()))

    def test_another_models_result_is_not_borrowed(self):
        view = models.selftest_view([self.record(model="other:1")],
                                    model=CATALOGUED, digest="a" * 64)
        self.assertEqual(view[models.CHAT]["state"], models.NOT_RUN)


class TestRemovalImpact(unittest.TestCase):
    def test_it_names_the_workflows_that_would_lose_their_model(self):
        impact = models.removal_impact(
            CATALOGUED, selections={"chat": CATALOGUED, "code": "other:1"},
            enabled={})
        self.assertEqual(impact["selected_for"], ["chat"])
        self.assertIn("chat", impact["detail"])

    def test_it_states_plainly_that_nothing_a_person_made_is_deleted(self):
        impact = models.removal_impact(CATALOGUED, selections={}, enabled={})
        self.assertIn("conversations", impact["preserved"])
        self.assertIn("generated artifacts", impact["preserved"])
        self.assertIn("are kept", impact["detail"])

    def test_removal_itself_is_named_rather_than_performed(self):
        impact = models.removal_impact(CATALOGUED, selections={}, enabled={})
        self.assertEqual(impact["command"], f"ollama rm {CATALOGUED}")


class CoordinatorBase(unittest.TestCase):
    """The inventory as the interface receives it, against a fake runtime."""

    HEALTH = {"reachable": True, "server_version": "0.32.14",
              "models": [CATALOGUED], "digests": {CATALOGUED: CATALOG_DIGEST},
              "loaded": None, "endpoint": runtime.HOST, "error": None}

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.c = Coordinator(Path(self.scratch.name) / "state.sqlite3")
        self.c.target_profile_id = profiles.MAC_M5_16GB
        self.addCleanup(self.c.conn.close)
        patches = [
            patch.object(runtime, "probe", return_value=dict(self.HEALTH)),
            patch.object(runtime, "model_capabilities", return_value=["completion"]),
            patch.object(self.c, "preflight", return_value=None),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def row(self, model, inventory=None):
        inventory = inventory if inventory is not None else self.c.model_inventory()
        return next(item for item in inventory if item["id"] == model)


class TestInventory(CoordinatorBase):
    def test_an_installed_model_is_located_by_role_not_by_operating_system(self):
        row = self.row(CATALOGUED)
        self.assertEqual(row["locations"], [device.HERE])
        self.assertNotIn("macOS coordinator", row["locations"])

    def test_a_supported_model_that_is_absent_still_appears_with_its_command(self):
        with patch.object(runtime, "probe",
                          return_value={**self.HEALTH, "models": [], "digests": {}}):
            row = self.row(CATALOGUED)
        self.assertEqual(row["state"], models.ABSENT)
        self.assertIn("ollama pull", row["setup"]["command"])
        self.assertEqual(row["eligible_scopes"], [])

    def test_an_unreachable_engine_reports_unknown_rather_than_absent(self):
        with patch.object(runtime, "probe",
                          return_value={"reachable": False, "models": [],
                                        "digests": {}, "server_version": None}):
            row = self.row(CATALOGUED)
        self.assertEqual(row["state"], models.UNAVAILABLE)
        self.assertIsNone(row["setup"])

    def test_an_installed_model_without_provenance_is_marked_unverified(self):
        with patch.object(runtime, "probe", return_value={
                **self.HEALTH, "models": [CATALOGUED, "somebody/random:latest"],
                "digests": {CATALOGUED: CATALOG_DIGEST,
                            "somebody/random:latest": "b" * 64}}):
            row = self.row("somebody/random:latest")
        self.assertEqual(row["state"], models.UNLISTED)
        self.assertEqual(row["provenance"]["evidence_state"], models.UNVERIFIED)
        # A model the team never measured may still run here under its own
        # candidate profile; it never inherits another model's measured one,
        # and its evidence says "compatible", not "measured".
        self.assertEqual(row["eligible_scopes"], ["chat", "code", "documents.generate"])
        for profile in row["execution_profiles"]["local"]:
            self.assertEqual(profile["qualification_state"], "candidate")
            self.assertFalse(profile["eligible"])
            self.assertEqual(profile["model"]["model_id"], "somebody/random:latest")
        self.assertEqual(row["evidence"]["chat"], "compatible")

    def test_an_ollama_copy_with_other_bytes_is_labelled_not_refused(self):
        """Ollama's store is the person's: other bytes under a catalogued tag
        are their own model, visibly differing from Refinix's recorded copy,
        and never presented as that recorded copy or its measured profile."""
        with patch.object(runtime, "probe", return_value={
                **self.HEALTH, "digests": {CATALOGUED: "f" * 64}}):
            row = self.row(CATALOGUED)
        self.assertEqual(row["integrity"]["local"]["state"], models.DIFFERS)
        self.assertTrue(row["integrity"]["local"]["eligible"])
        self.assertIn("chat", row["eligible_scopes"])
        for profile in row["execution_profiles"]["local"]:
            self.assertNotEqual(profile["evidence_kind"], "measured")
        ref = self.c.local_model_ref(
            CATALOGUED, {**self.HEALTH, "digests": {CATALOGUED: "f" * 64}})
        self.assertEqual(ref["manifest_sha256"], "f" * 64)

    def test_a_worker_digest_mismatch_stays_strict(self):
        """The strict check still guards what a paired worker advertises."""
        self.assertFalse(models.digest_eligible(CATALOGUED, "f" * 64))

    def test_a_worker_catalogue_mismatch_falls_back_to_verified_local_bytes(self):
        relationship = {"relationship_id": "rel", "state": "paired"}
        wrong = WORKER_CHAT_PROFILE.model_dump()
        wrong["model"]["manifest_sha256"] = "f" * 64
        wrong["profile_id"] = v1.execution_profile_id(wrong)
        node = {
            "contract_version": v1.CONTRACT_VERSION,
            "node_id": "22222222-2222-4222-8222-222222222222",
            "display_name": "worker", "app_version": "test",
            "platform": "Linux x86_64",
            "supported_contract_versions": [v1.CONTRACT_VERSION],
            "health": "healthy",
            "capabilities": ["text.generate"], "queue_depth": 0,
            "models": [{"model_id": CATALOGUED,
                        "manifest_sha256": "f" * 64,
                        "runtime": "ollama", "runtime_version": "0.33.2"}],
            "inference_profiles": [wrong],
            "observed_at": "2026-09-21T00:00:00Z",
            "available_memory_bytes": None, "loaded_model_id": None,
        }
        with patch.object(self.c, "paired_worker", return_value=relationship), \
                patch.object(self.c, "preflight", return_value=node):
            route = self.c.choose_route(model_id=CATALOGUED,
                                        runtime_state=self.HEALTH)
        self.assertFalse(route.remote)
        self.assertIn("does not match", route.reason)
        self.assertEqual(route.model["manifest_sha256"], CATALOG_DIGEST)


class TestEnablement(CoordinatorBase):
    def test_a_model_arrives_enabled(self):
        self.assertTrue(self.row(CATALOGUED)["enabled"])

    def test_switching_one_off_removes_it_from_new_work_only(self):
        self.c.select_model("chat", CATALOGUED)
        before = len(self.c.jobs(limit=-1))
        self.c.set_model_enabled(CATALOGUED, False)
        row = self.row(CATALOGUED)
        self.assertFalse(row["enabled"])
        self.assertEqual(row["eligible_scopes"], [])
        # It is still installed and still recorded as the chat selection.
        self.assertTrue(row["installed"])
        self.assertIn("chat", row["selected_for"])
        self.assertEqual(len(self.c.jobs(limit=-1)), before)

    def test_a_switched_off_selection_cannot_create_a_chat_job(self):
        chat = db.create_chat(self.c.conn, self.c.workspace_id, "disabled")
        self.c.set_model_enabled(CATALOGUED, False)
        with self.assertRaises(Exception) as caught:
            self.c.submit(chat, "hello")
        self.assertIn("switched off", str(caught.exception))
        self.assertEqual(self.c.jobs(chat, limit=-1), [])

    def test_a_switched_off_model_cannot_be_selected_and_says_why(self):
        self.c.set_model_enabled(CATALOGUED, False)
        with self.assertRaises(Exception) as caught:
            self.c.select_model("chat", CATALOGUED)
        self.assertIn("switched off", str(caught.exception))

    def test_switching_back_on_restores_eligibility(self):
        self.c.set_model_enabled(CATALOGUED, False)
        self.c.set_model_enabled(CATALOGUED, True)
        self.assertIn("chat", self.row(CATALOGUED)["eligible_scopes"])

    def test_an_absent_model_is_refused_as_absent_not_as_switched_off(self):
        """Turning it back on would not make it selectable, so saying "switched
        off" would send the person to the wrong control."""
        self.c.set_model_enabled(CATALOGUED, False)
        with patch.object(runtime, "probe",
                          return_value={**self.HEALTH, "models": [],
                                        "digests": {}}):
            with self.assertRaises(Exception) as caught:
                self.c.select_model("chat", CATALOGUED)
        self.assertIn("not available", str(caught.exception))
        self.assertNotIn("switched off", str(caught.exception))

    def test_an_unknown_model_cannot_be_switched(self):
        with self.assertRaises(Exception):
            self.c.set_model_enabled("nothing:here", False)

    def test_switching_off_does_not_touch_the_reasoning_choice(self):
        db.set_reasoning(self.c.conn, CATALOGUED, True)
        self.c.set_model_enabled(CATALOGUED, False)
        self.assertTrue(db.get_reasoning(self.c.conn, CATALOGUED))

    def test_conversations_survive_a_model_being_switched_off(self):
        chat_id = db.create_chat(self.c.conn, self.c.workspace_id,
                                 "a conversation")
        self.c.set_model_enabled(CATALOGUED, False)
        self.assertTrue(any(row["chat_id"] == chat_id for row in self.c.chats()))


class TestSelfTestRoute(CoordinatorBase):
    def test_a_pass_is_recorded_against_the_manifest_it_was_observed_on(self):
        with patch.object(self.c, "_selftest_generate",
                          chat_reply):
            record = self.c.run_model_selftest(models.CHAT)
        self.assertEqual(record["state"], models.PASSED)
        self.assertEqual(record["digest"], CATALOG_DIGEST)
        self.assertEqual(record["runtime_version"], "0.32.14")
        self.assertTrue(self.row(CATALOGUED)["selftests"][models.CHAT]["current"])

    def test_a_result_is_superseded_when_the_bytes_change_under_the_tag(self):
        with patch.object(self.c, "_selftest_generate",
                          chat_reply):
            self.c.run_model_selftest(models.CHAT)
        with patch.object(runtime, "probe", return_value={
                **self.HEALTH, "digests": {CATALOGUED: "c" * 64}}):
            row = self.row(CATALOGUED)
        self.assertTrue(row["selftests"][models.CHAT]["superseded"])
        self.assertFalse(row["selftests"][models.CHAT]["current"])

    def test_uninstalling_a_model_stops_its_pass_reading_as_current(self):
        with patch.object(self.c, "_selftest_generate",
                          chat_reply):
            self.c.run_model_selftest(models.CHAT)
        with patch.object(runtime, "probe", return_value={
                **self.HEALTH, "models": [], "digests": {}}):
            row = self.row(CATALOGUED)
        self.assertFalse(row["selftests"][models.CHAT]["current"])

    def test_an_unreachable_engine_records_unavailable_not_failed(self):
        db.set_model_selection(self.c.conn, models.CHAT, CATALOGUED)
        with patch.object(runtime, "probe",
                          return_value={"reachable": False, "models": [],
                                        "digests": {}, "server_version": None}):
            record = self.c.run_model_selftest(models.CHAT)
        self.assertEqual(record["state"], "unavailable")
        self.assertIn("did not answer", record["detail"])

    def test_a_model_that_is_not_installed_records_unavailable(self):
        db.set_model_selection(self.c.conn, models.CHAT, CATALOGUED)
        with patch.object(runtime, "probe",
                          return_value={**self.HEALTH, "models": [],
                                        "digests": {}}):
            record = self.c.run_model_selftest(models.CHAT)
        self.assertEqual(record["state"], "unavailable")
        self.assertIn("not installed", record["detail"])

    def test_a_check_that_needs_no_modality_asks_the_engine_for_none(self):
        """`/api/show` is a round trip on a path the person is waiting on."""
        asked = []
        with patch.object(runtime, "model_capabilities",
                          lambda m: asked.append(m) or ["completion"]), \
                patch.object(self.c, "_selftest_generate",
                             chat_reply):
            self.c.run_model_selftest(models.CHAT)
        self.assertEqual(asked, [], "chat needs no modality answer")

    def test_the_page_check_does_ask_what_the_model_accepts(self):
        db.set_model_selection(self.c.conn, models.DOCUMENTS_OCR, runtime.OCR_MODEL)
        asked = []
        with patch.object(runtime, "model_capabilities",
                          lambda m: asked.append(m) or ["completion"]), \
                patch.object(runtime, "probe", return_value={
                **self.HEALTH, "models": [CATALOGUED, runtime.OCR_MODEL],
                    "digests": {CATALOGUED: CATALOG_DIGEST,
                                runtime.OCR_MODEL: "b" * 64}}):
            record = self.c.run_model_selftest(models.DOCUMENTS_OCR)
        self.assertEqual(asked, [runtime.model_key(runtime.OLLAMA, runtime.OCR_MODEL)])
        self.assertEqual(record["state"], models.FAILED)

    def test_quitting_stops_a_self_test_instead_of_waiting_it_out(self):
        seen = {}

        def capture(messages, **kwargs):
            seen.update(kwargs)
            yield "delta", "Four."
            yield "done", {"done_reason": "stop"}

        with patch.object(runtime, "stream_chat", capture):
            self.c.run_model_selftest(models.CHAT)
        self.assertIn("should_cancel", seen)
        self.assertFalse(seen["should_cancel"]())
        self.c.stopping.set()
        self.assertTrue(seen["should_cancel"](),
                        "the coordinator's stopping flag must reach the stream")

    def test_a_workflow_without_a_self_test_is_refused(self):
        with self.assertRaises(Exception):
            self.c.run_model_selftest("nonsense")

    def test_running_one_never_downloads_or_installs(self):
        calls = []

        def generate(model, messages, **options):
            calls.append((model, messages, options))
            return "Four."
        with patch.object(self.c, "_selftest_generate", generate):
            self.c.run_model_selftest(models.CHAT)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], runtime.model_key(runtime.OLLAMA, CATALOGUED))


class TestSelfTestWorkflowSelection(CoordinatorBase):
    """Which qualified workflow each self-test is admitted under.

    The workflow used to be guessed from the response format: anything that
    was not the Code proposal schema became `documents.structured`. Reading a
    page and writing a document both decode JSON, so the OCR self-test was
    admitted under the Documents profile — a different workflow, a different
    envelope and a different schema from the one it actually sends.
    """

    def workflow_for(self, scope):
        """The workflow the coordinator resolves a profile for, per scope."""
        db.set_model_selection(self.c.conn, models.DOCUMENTS_OCR, runtime.OCR_MODEL)
        db.set_model_selection(self.c.conn, scope, CATALOGUED) \
            if scope != models.DOCUMENTS_OCR else None
        seen = {}

        def local_profile(*, workflow, **kwargs):
            seen["workflow"] = workflow
            seen.update(kwargs)
            return None                      # refuse: the resolution is the point

        with patch.object(self.c, "local_profile", local_profile), \
                patch.object(runtime, "model_capabilities",
                             return_value=["completion", "vision"]), \
                patch.object(runtime, "probe", return_value={
                    **self.HEALTH, "models": [CATALOGUED, runtime.OCR_MODEL],
                    "digests": {CATALOGUED: CATALOG_DIGEST,
                                runtime.OCR_MODEL: "b" * 64}}):
            self.c.run_model_selftest(scope)
        return seen

    def test_the_ocr_self_test_asks_for_the_ocr_workflow(self):
        seen = self.workflow_for(models.DOCUMENTS_OCR)
        self.assertEqual(seen["workflow"], inference_profiles.OCR)
        self.assertEqual(seen["model_id"],
                         runtime.model_key(runtime.OLLAMA, runtime.OCR_MODEL))

    def test_the_ocr_self_test_is_not_admitted_as_documents(self):
        seen = self.workflow_for(models.DOCUMENTS_OCR)
        self.assertNotEqual(seen["workflow"], inference_profiles.DOCUMENTS)

    def test_each_other_scope_keeps_its_own_workflow(self):
        for scope, expected in (
                (models.CHAT, inference_profiles.CHAT),
                (models.CODE, inference_profiles.CODE),
                (models.DOCUMENTS_GENERATE, inference_profiles.DOCUMENTS)):
            with self.subTest(scope=scope):
                self.assertEqual(self.workflow_for(scope)["workflow"], expected)

    def test_every_self_test_scope_has_a_mapped_workflow(self):
        """A new scope must not silently inherit another workflow's profile."""
        self.assertEqual(set(models.SELFTESTS),
                         set(self.c.SELFTEST_WORKFLOWS))

    def test_the_ocr_self_test_is_unavailable_while_nothing_qualifies_it(self):
        """A model whose observation does not declare vision gets no page
        profile, whatever a later capability answer says, and no page is sent."""
        db.set_model_selection(self.c.conn, models.DOCUMENTS_OCR, runtime.OCR_MODEL)
        with patch.object(runtime, "model_capabilities",
                          return_value=["completion", "vision"]), \
                patch.object(runtime, "probe", return_value={
                    **self.HEALTH, "models": [CATALOGUED, runtime.OCR_MODEL],
                    "digests": {CATALOGUED: CATALOG_DIGEST,
                                runtime.OCR_MODEL: "b" * 64}}), \
                patch.object(runtime, "stream_chat") as never:
            record = self.c.run_model_selftest(models.DOCUMENTS_OCR)
        self.assertEqual(record["state"], "unavailable")
        self.assertIn("cannot run this check", record["detail"])
        never.assert_not_called()


class TestStatusTruthfulness(CoordinatorBase):
    def test_status_names_this_computer_without_claiming_a_qualified_profile(self):
        state = self.c.status()
        self.assertIn(state["device"]["os_family"],
                      ("macos", "windows", "linux", "other"))
        self.assertIn("code_containment", state["device"])

    def test_the_code_surface_is_reported_from_what_this_computer_can_do(self):
        from backend.coordinator import repo
        with patch.object(repo, "containment_backend", return_value=None):
            state = self.c.status()
        self.assertEqual(state["surfaces"]["code"], "unavailable")
        self.assertIn("Code is unavailable", state["surface_notes"]["code"])
        code = next(row for row in state["capabilities"] if row["id"] == "code")
        self.assertEqual(code["state"], "unavailable")

    def test_a_capability_reports_its_self_test_beside_its_state(self):
        state = self.c.status()
        chat = next(row for row in state["capabilities"] if row["id"] == "chat")
        self.assertEqual(chat["selftest"]["state"], models.NOT_RUN)
        self.assertFalse(chat["selftest"]["current"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
