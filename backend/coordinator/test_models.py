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

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import db, device, docgen, models, runtime
from backend.coordinator.server import Coordinator

CATALOGUED = models.CATALOGUE[0].id


class TestTheCatalogue(unittest.TestCase):
    def test_it_holds_only_entries_whose_provenance_was_recorded(self):
        for entry in models.CATALOGUE:
            with self.subTest(model=entry.id):
                self.assertTrue(entry.source)
                self.assertTrue(entry.licence)
                self.assertEqual(len(entry.manifest_sha256 or ""), 64)
                self.assertTrue(entry.evidence)
                self.assertEqual(entry.evidence_state, models.VERIFIED)

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
                                     generate=lambda model, prompt: "ready")
        self.assertEqual(result["state"], models.PASSED)
        self.assertIn("nothing about the quality", result["detail"])

    def test_an_empty_answer_is_a_failure_rather_than_a_pass(self):
        result = models.run_selftest(models.CHAT, CATALOGUED,
                                     generate=lambda model, prompt: "   ")
        self.assertEqual(result["state"], models.FAILED)

    def test_a_missing_prerequisite_is_unavailable_not_a_failed_model(self):
        with self.assertRaises(models.SelfTestError):
            models.run_selftest(models.CHAT, CATALOGUED, generate=None)

    def test_a_runtime_error_never_becomes_a_verdict_on_the_model(self):
        def broken(model, prompt):
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
                                     generate=lambda *_: "ready",
                                     artifact=docgen.selftest)
        self.assertEqual(result["state"], models.PASSED)

    def test_a_writer_that_cannot_produce_a_document_fails_the_check(self):
        result = models.run_selftest(
            models.DOCUMENTS_GENERATE, CATALOGUED,
            generate=lambda *_: "ready",
            artifact=lambda: {"valid": False, "detail": "no temporary folder"})
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

    HEALTH = {"reachable": True, "server_version": "0.33.3",
              "models": [CATALOGUED], "digests": {CATALOGUED: "a" * 64},
              "loaded": None, "endpoint": runtime.HOST, "error": None}

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.c = Coordinator(Path(self.scratch.name) / "state.sqlite3")
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
                "digests": {CATALOGUED: "a" * 64,
                            "somebody/random:latest": "b" * 64}}):
            row = self.row("somebody/random:latest")
        self.assertEqual(row["state"], models.UNLISTED)
        self.assertEqual(row["provenance"]["evidence_state"], models.UNVERIFIED)
        # Still usable — it is installed — but never presented as verified.
        self.assertIn("chat", row["eligible_scopes"])


class TestEnablement(CoordinatorBase):
    def test_a_model_arrives_enabled(self):
        self.assertTrue(self.row(CATALOGUED)["enabled"])

    def test_switching_one_off_removes_it_from_new_work_only(self):
        before = len(self.c.jobs(limit=-1))
        self.c.set_model_enabled(CATALOGUED, False)
        row = self.row(CATALOGUED)
        self.assertFalse(row["enabled"])
        self.assertEqual(row["eligible_scopes"], [])
        # It is still installed and still recorded as the chat selection.
        self.assertTrue(row["installed"])
        self.assertIn("chat", row["selected_for"])
        self.assertEqual(len(self.c.jobs(limit=-1)), before)

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
                          lambda model, prompt: "ready"):
            record = self.c.run_model_selftest(models.CHAT)
        self.assertEqual(record["state"], models.PASSED)
        self.assertEqual(record["digest"], "a" * 64)
        self.assertEqual(record["runtime_version"], "0.33.3")
        self.assertTrue(self.row(CATALOGUED)["selftests"][models.CHAT]["current"])

    def test_a_result_is_superseded_when_the_bytes_change_under_the_tag(self):
        with patch.object(self.c, "_selftest_generate",
                          lambda model, prompt: "ready"):
            self.c.run_model_selftest(models.CHAT)
        with patch.object(runtime, "probe", return_value={
                **self.HEALTH, "digests": {CATALOGUED: "c" * 64}}):
            row = self.row(CATALOGUED)
        self.assertTrue(row["selftests"][models.CHAT]["superseded"])
        self.assertFalse(row["selftests"][models.CHAT]["current"])

    def test_uninstalling_a_model_stops_its_pass_reading_as_current(self):
        with patch.object(self.c, "_selftest_generate",
                          lambda model, prompt: "ready"):
            self.c.run_model_selftest(models.CHAT)
        with patch.object(runtime, "probe", return_value={
                **self.HEALTH, "models": [], "digests": {}}):
            row = self.row(CATALOGUED)
        self.assertFalse(row["selftests"][models.CHAT]["current"])

    def test_an_unreachable_engine_records_unavailable_not_failed(self):
        with patch.object(runtime, "probe",
                          return_value={"reachable": False, "models": [],
                                        "digests": {}, "server_version": None}):
            record = self.c.run_model_selftest(models.CHAT)
        self.assertEqual(record["state"], "unavailable")
        self.assertIn("did not answer", record["detail"])

    def test_a_model_that_is_not_installed_records_unavailable(self):
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
                             lambda model, prompt: "ready"):
            self.c.run_model_selftest(models.CHAT)
        self.assertEqual(asked, [], "chat needs no modality answer")

    def test_the_page_check_does_ask_what_the_model_accepts(self):
        asked = []
        with patch.object(runtime, "model_capabilities",
                          lambda m: asked.append(m) or ["completion"]), \
                patch.object(runtime, "probe", return_value={
                    **self.HEALTH, "models": [CATALOGUED, runtime.OCR_MODEL],
                    "digests": {CATALOGUED: "a" * 64,
                                runtime.OCR_MODEL: "b" * 64}}):
            record = self.c.run_model_selftest(models.DOCUMENTS_OCR)
        self.assertEqual(asked, [runtime.OCR_MODEL])
        self.assertEqual(record["state"], models.FAILED)

    def test_quitting_stops_a_self_test_instead_of_waiting_it_out(self):
        seen = {}

        def capture(messages, **kwargs):
            seen.update(kwargs)
            yield "delta", "ready"
            yield "done", {}

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

        def generate(model, prompt):
            calls.append((model, prompt))
            return "ready"
        with patch.object(self.c, "_selftest_generate", generate):
            self.c.run_model_selftest(models.CHAT)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], CATALOGUED)


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
