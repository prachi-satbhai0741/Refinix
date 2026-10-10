"""Offline checks for broad local model use, two runtimes and Auto routing.

No model, no network, no real Ollama: fake runtime observations, a loopback
stand-in for Ollama's identity reads, and temporary SQLite stores.

    python3 -m unittest backend.coordinator.test_model_runtime -v
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.contracts import profiles, v1
from backend.coordinator import (admission, capacity, code_service, db, docflow, engine, fake_ollama, hub,
                                 local_engine, models, ocr, provisioning, router,
                                 runtime)
from backend.coordinator.server import Coordinator, RequestError

GEMMA = models.entry_for("gemma-3-4b-it-q4_k_m")
CODER = models.entry_for("qwen2.5-coder-7b-instruct-q4_k_m")
OLLAMA_QWEN = runtime.MODEL
OLLAMA_DIGEST = models.entry_for(runtime.MODEL).manifest_sha256


def managed_state(*entries, capabilities=None):
    capabilities = capabilities or {}
    return {"reachable": True, "server_version": "b11390-metal", "runtime": "llama.cpp",
            "models": [e.id for e in entries],
            "digests": {e.id: e.manifest_sha256 for e in entries},
            "capabilities": {e.id: capabilities.get(e.id, ["completion"]) for e in entries},
            "context_lengths": {e.id: e.context_length for e in entries},
            "file_checks": {e.id: {"state": "verified", "detail": ""} for e in entries},
            "loaded": None, "error": None}


def ollama_state(models_=None, *, version="0.34.2", remote=(), capabilities=None,
                 model_tags=None, context_lengths=None):
    models_ = models_ if models_ is not None else {OLLAMA_QWEN: OLLAMA_DIGEST}
    return {"reachable": True, "server_version": version, "runtime": "ollama",
            "models": list(models_), "digests": dict(models_), "remote": list(remote),
            "capabilities": dict(capabilities or {}), "tags_read": True,
            "model_tags": dict(model_tags or {}),
            "context_lengths": dict(context_lengths or {}),
            "loaded": None, "loaded_all": [], "error": None}


class CoordinatorCase(unittest.TestCase):
    STATE: dict = {}

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.c = Coordinator(Path(self.scratch.name) / "state.sqlite3")
        self.addCleanup(self.c.conn.close)
        self.c.target_profile_id = profiles.MAC_M5_16GB
        for item in (patch.object(runtime, "probe", side_effect=lambda: self.STATE),
                     patch.object(self.c, "preflight", return_value=None)):
            item.start()
            self.addCleanup(item.stop)


# --------------------------------------------------------------------------
# A. Both runtimes in one process
# --------------------------------------------------------------------------

class TestRuntimeView(unittest.TestCase):
    def test_the_ollama_baseline_is_a_feature_floor_not_an_allowlist(self):
        self.assertFalse(runtime.ollama_baseline_met("0.12.5"))
        self.assertTrue(runtime.ollama_baseline_met("0.12.6"))
        self.assertTrue(runtime.ollama_baseline_met("0.99.0"))
        self.assertTrue(runtime.ollama_baseline_met("v1.2.0-rc1"))
        self.assertIsNone(runtime.ollama_baseline_met("not a version"))

    def test_one_name_in_both_runtimes_is_two_identities(self):
        state = runtime.merge({
            runtime.LLAMA_CPP: {**managed_state(GEMMA), "models": ["same"],
                                "digests": {"same": "a" * 64}},
            runtime.OLLAMA: ollama_state({"same": "b" * 64})})
        found = runtime.entries(state)
        self.assertEqual(set(found), {"llama.cpp|same", "ollama|same"})
        self.assertIsNone(runtime.find(state, "same"), "a bare name is ambiguous here")
        self.assertEqual(runtime.find(state, "ollama|same")["digest"], "b" * 64)

    def test_locality_comes_from_the_v12_fields_and_unknown_is_not_local(self):
        cloud = runtime.entries(ollama_state({"a:1": "a" * 64, "b:cloud": "b" * 64},
                                             remote=["b:cloud"]))
        self.assertEqual(cloud["ollama|a:1"]["locality"], runtime.LOCAL)
        self.assertEqual(cloud["ollama|b:cloud"]["locality"], runtime.REMOTE)
        old = runtime.entries(ollama_state(version="0.11.0"))
        self.assertEqual(old[f"ollama|{OLLAMA_QWEN}"]["locality"], runtime.UNKNOWN)
        unread = runtime.entries(ollama_state(version="garbled"))
        self.assertEqual(unread[f"ollama|{OLLAMA_QWEN}"]["locality"], runtime.UNKNOWN)

    def test_the_refinix_engine_is_local_by_construction(self):
        found = runtime.entries(managed_state(GEMMA))
        self.assertEqual(found[f"llama.cpp|{GEMMA.id}"]["locality"], runtime.LOCAL)

    def test_a_profile_is_dispatched_by_its_recorded_runtime(self):
        profile = admission.candidate(
            {"model_id": "m", "digest": "a" * 64, "origin": "llama.cpp",
             "runtime_version": "b1", "locality": "local", "capabilities": None,
             "context_length": None}, profiles.CHAT)
        request = profiles.request_local(profile, reasoning="disabled", decoder="text")
        runtime.configure_managed(None)
        with self.assertRaisesRegex(runtime.RuntimeUnavailable, "not part of"):
            list(runtime.stream_chat([{"role": "user", "content": "x"}],
                                     profile=profile, inference=request))


class _IdentityServer:
    """Answers Ollama's identity reads for one model; records what was asked."""

    def __init__(self, model, *, remote=False, capabilities=("completion",)):
        server_model, flags = model, {"remote": remote, "capabilities": capabilities}
        asked = self.asked = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def do_GET(self):
                asked.append(self.path)
                fake_ollama.answer(self, server_model.model, **flags)

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                asked.append(self.path)
                fake_ollama.answer(self, server_model.model, **flags)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.host = f"http://127.0.0.1:{self.httpd.server_port}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class TestPreSendConfirmation(unittest.TestCase):
    PROFILE = next(p for p in profiles.PROFILES if p.model.runtime == "ollama")

    def confirm(self, model, served=None, **flags):
        server = _IdentityServer(SimpleNamespace(model=served or model), **flags)
        try:
            with patch.object(runtime, "HOST", server.host):
                return runtime.confirm_ollama(model), server.asked
        finally:
            server.close()

    def test_the_digest_comes_from_tags_and_locality_from_show(self):
        facts, asked = self.confirm(self.PROFILE.model)
        self.assertEqual(facts["locality"], runtime.LOCAL)
        self.assertEqual(asked, ["/api/version", "/api/tags", "/api/show"])

    def test_changed_bytes_are_never_sent_input(self):
        changed = self.PROFILE.model.model_copy(update={"manifest_sha256": "e" * 64})
        with self.assertRaisesRegex(runtime.RuntimeUnavailable, "changed"):
            self.confirm(self.PROFILE.model, served=changed)

    def test_a_cloud_model_is_never_sent_input(self):
        with self.assertRaisesRegex(runtime.RuntimeUnavailable, "another host"):
            self.confirm(self.PROFILE.model, remote=True)

    def test_a_runtime_change_after_admission_is_refused(self):
        newer = self.PROFILE.model.model_copy(update={"runtime_version": "0.99.0"})
        with self.assertRaisesRegex(runtime.RuntimeUnavailable, "changed from"):
            self.confirm(self.PROFILE.model, served=newer)

    def test_an_ollama_below_the_baseline_asks_for_an_update(self):
        old = self.PROFILE.model.model_copy(update={"runtime_version": "0.11.0"})
        with self.assertRaisesRegex(runtime.RuntimeUnavailable, "ollama.com/download"):
            self.confirm(old)


# --------------------------------------------------------------------------
# B. Local admission and the remote boundary
# --------------------------------------------------------------------------

def observation(**overrides):
    values = {"model_id": "somebody/model:7b", "digest": "c" * 64, "origin": "ollama",
              "runtime_version": "0.34.2", "locality": "local",
              "capabilities": ["completion"], "context_length": 32768}
    values.update(overrides)
    return values


class TestLocalCandidates(unittest.TestCase):
    def test_a_candidate_is_never_presented_as_measured_or_qualified(self):
        profile = admission.candidate(observation(), profiles.CHAT)
        self.assertEqual((profile.qualification_state, profile.eligible,
                          profile.evidence_kind), ("candidate", False, "documented"))
        self.assertEqual(profile.qualified_context_tokens, admission.DEFAULT_WINDOW)

    def test_bounds_follow_what_the_model_declares(self):
        small = admission.candidate(observation(context_length=4096), profiles.CHAT)
        self.assertEqual(small.qualified_context_tokens, 4096)
        unknown = admission.candidate(observation(context_length=None), profiles.CHAT)
        self.assertEqual(unknown.evidence_kind, "estimated")
        wide = admission.candidate(observation(), profiles.CHAT, window=16384)
        self.assertEqual(wide.qualified_context_tokens, 16384)
        capped = admission.candidate(observation(context_length=12000), profiles.CHAT,
                                     window=32768)
        self.assertEqual(capped.qualified_context_tokens, 12000)

    def test_page_reading_needs_vision_and_runs_reasoning_off(self):
        self.assertIsNone(admission.candidate(observation(), profiles.OCR))
        ocr = admission.candidate(observation(capabilities=["completion", "vision"]),
                                  profiles.OCR)
        self.assertEqual((ocr.decoder_modes, ocr.reasoning_modes),
                         (["json_schema"], ["disabled"]))

    def test_reasoning_is_offered_only_where_the_model_has_a_switch(self):
        plain = admission.candidate(observation(), profiles.CHAT)
        thinking = admission.candidate(
            observation(capabilities=["completion", "thinking"]), profiles.CHAT)
        documents = admission.candidate(
            observation(capabilities=["completion", "thinking"]), profiles.DOCUMENTS)
        self.assertEqual(plain.reasoning_modes, ["disabled"])
        self.assertEqual(thinking.reasoning_modes, ["disabled", "enabled"])
        self.assertEqual(documents.reasoning_modes, ["disabled"])

    def test_a_model_elsewhere_or_of_unknown_locality_gets_no_profile(self):
        for locality in ("remote", "unknown"):
            self.assertIsNone(admission.candidate(observation(locality=locality),
                                                  profiles.CHAT))

    def test_an_exact_measured_profile_wins_over_a_candidate(self):
        measured = next(p for p in profiles.PROFILES if p.model.runtime == "ollama"
                        and p.workflow_mode == profiles.CHAT)
        found = admission.profiles_for(observation(
            model_id=measured.model.model_id, digest=measured.model.manifest_sha256,
            runtime_version=measured.model.runtime_version),
            [measured.target_profile_id])
        chat = [p for p in found if p.workflow_mode == profiles.CHAT]
        self.assertEqual(chat, [measured])


class TestRemoteBoundariesStayStrict(unittest.TestCase):
    """A local candidate can never cross to another computer."""

    def setUp(self):
        self.candidate = admission.candidate(observation(), profiles.CHAT)

    def test_strict_checks_refuse_a_candidate(self):
        self.assertFalse(profiles.compatible(
            self.candidate, model_id=self.candidate.model.model_id,
            workflow=profiles.CHAT, reasoning="disabled", decoder="text"))
        with self.assertRaises(ValueError):
            profiles.request(self.candidate, reasoning="disabled", decoder="text")
        local = profiles.request_local(self.candidate, reasoning="disabled",
                                       decoder="text")
        with self.assertRaises(ValueError):
            profiles.validate_request(self.candidate, local, self.candidate.model)

    def test_a_node_may_not_advertise_a_candidate(self):
        with self.assertRaisesRegex(ValueError, "measured qualified"):
            v1.Node(contract_version=v1.CONTRACT_VERSION,
                    node_id="11111111-1111-4111-8111-111111111111",
                    display_name="worker", app_version="0.1", platform="linux",
                    supported_contract_versions=[v1.CONTRACT_VERSION],
                    capabilities=["text.generate"], models=[self.candidate.model],
                    inference_profiles=[self.candidate], health="unknown",
                    observed_at=None, queue_depth=None, available_memory_bytes=None,
                    loaded_model_id=None)

    def test_the_worker_registry_never_returns_a_candidate(self):
        self.assertEqual(profiles.for_observation(
            target_profile_id=[admission.LOCAL_TARGET],
            models=[self.candidate.model]), [])

    def test_the_worker_runtime_rejects_a_candidate(self):
        from backend.worker import runtime as worker_runtime
        source = Path(worker_runtime.__file__).read_text()
        self.assertIn("validate_request", source)
        self.assertNotIn("validate_local", source)
        self.assertNotIn("request_local", source)

    def test_local_validation_still_binds_identity_and_bounds(self):
        local = profiles.request_local(self.candidate, reasoning="disabled",
                                       decoder="text")
        other = self.candidate.model.model_copy(update={"manifest_sha256": "d" * 64})
        with self.assertRaises(ValueError):
            profiles.validate_local(self.candidate, local, other)
        with self.assertRaises(ValueError):
            profiles.request_local(self.candidate, reasoning="enabled", decoder="text")
        with self.assertRaises(ValueError):
            profiles.request_local(self.candidate, reasoning="disabled", decoder="text",
                                   context_window=self.candidate.qualified_context_tokens + 1)


# --------------------------------------------------------------------------
# D. Automatic routing
# --------------------------------------------------------------------------

class TestRouter(unittest.TestCase):
    def candidate(self, key, *, hints=(), capabilities=("completion",), resident=False,
                  blocked=None, profile=True):
        return router.Candidate(key=key, model_id=key, origin="ollama",
                                profile=SimpleNamespace(qualified_context_tokens=8192)
                                if profile else None,
                                capabilities=list(capabilities), hints=tuple(hints),
                                resident=resident, blocked=blocked)

    def test_prompt_labels_are_constrained(self):
        self.assertIn("code", router.classify("fix this TypeError in app.py",
                                              workflow=profiles.CHAT).labels)
        self.assertIn("reasoning", router.classify("prove that 2+2=4 step by step",
                                                   workflow=profiles.CHAT).labels)
        self.assertEqual(router.classify("hello", workflow=profiles.CHAT).labels, ())

    def test_a_code_task_prefers_a_published_coding_model(self):
        choice = router.choose(router.Task(profiles.CODE),
                               [self.candidate("general", hints=("general",)),
                                self.candidate("coder", hints=("code",))])
        self.assertEqual(choice.candidate.key, "coder")
        self.assertIn("coding", choice.reason)

    def test_two_models_may_get_the_same_choice_and_ties_are_stable(self):
        a, b = self.candidate("a"), self.candidate("b")
        first = router.choose(router.Task(profiles.CHAT), [b, a]).candidate.key
        again = router.choose(router.Task(profiles.CHAT), [a, b]).candidate.key
        self.assertEqual(first, again)

    def test_page_reading_removes_models_without_vision(self):
        choice = router.choose(router.Task(profiles.OCR, needs_vision=True),
                               [self.candidate("text")])
        self.assertIsNone(choice.candidate)
        self.assertIn("does not accept images", choice.reason)

    def test_a_picture_in_chat_prefers_vision_without_requiring_it(self):
        task = router.classify("what is this?", workflow=profiles.CHAT, prefers_vision=True)
        seen = router.choose(task, [self.candidate("text"),
                                    self.candidate("eyes", capabilities=("completion",
                                                                         "vision"))])
        self.assertEqual(seen.candidate.key, "eyes")
        alone = router.choose(task, [self.candidate("text")])
        self.assertEqual(alone.candidate.key, "text")

    def test_a_loaded_model_breaks_a_tie(self):
        choice = router.choose(router.Task(profiles.CHAT),
                               [self.candidate("a"), self.candidate("b", resident=True)])
        self.assertEqual(choice.candidate.key, "b")
        self.assertIn("already loaded", choice.reason)

    def test_the_refusal_names_why_each_model_was_skipped(self):
        choice = router.choose(router.Task(profiles.CHAT),
                               [self.candidate("a", blocked="switched off for new work")])
        self.assertIn("a switched off for new work", choice.reason)


class TestModelAgnosticRouting(unittest.TestCase):
    """Routing for any compatible model: made-up identities, evidence only."""

    def c(self, key, *, hints=(), limited=(), evidence=None, caps=("completion",),
          check=None, resident=False, fit="good", structured=True, blocked=None):
        return router.Candidate(
            key=key, model_id=key, origin="ollama",
            profile=SimpleNamespace(qualified_context_tokens=8192),
            capabilities=list(caps), hints=tuple(hints), resident=resident, fit=fit,
            blocked=blocked, limited_to=tuple(limited),
            evidence=(3 if (hints or limited) else 0) if evidence is None else evidence,
            check=check, structured=structured)

    CHAT = router.Task(profiles.CHAT)

    def test_names_do_not_route_evidence_does(self):
        for documented, unknown in (("zz-model", "aa-model"), ("aa-model", "zz-model")):
            with self.subTest(documented=documented):
                choice = router.choose(self.CHAT, [self.c(unknown),
                                                   self.c(documented, hints=("general",))])
                self.assertEqual(choice.candidate.key, documented)

    def test_each_task_gets_its_documented_strength(self):
        eyes = ("completion", "vision")
        pool = [self.c("g", hints=("general",)), self.c("k", hints=("code",)),
                self.c("r", hints=("reasoning",)),
                self.c("v", hints=("general", "vision"), caps=eyes),
                self.c("o", hints=("ocr",), caps=eyes)]
        cases = [
            (self.CHAT, "g"),
            (router.Task(profiles.CODE), "k"),
            (router.classify("prove this step by step", workflow=profiles.CHAT), "r"),
            (router.classify("what colour is the car?", workflow=profiles.CHAT,
                             images=True), "v"),
            (router.Task(profiles.OCR, needs_vision=True), "o"),
            (router.classify("transcribe this", workflow=profiles.CHAT, images=True), "o"),
            (router.classify("summarise the text", workflow=profiles.CHAT,
                             images=True), "v"),
        ]
        for task, expected in cases:
            with self.subTest(task=task):
                self.assertEqual(router.choose(task, pool).candidate.key, expected)

    def test_the_preferred_model_missing_means_the_next_capable_one(self):
        choice = router.choose(router.Task(profiles.CODE),
                               [self.c("plain", hints=("general",)), self.c("mystery")])
        self.assertEqual(choice.candidate.key, "plain")
        self.assertIn("general-purpose", choice.reason)
        self.assertEqual([c.key for c in choice.ranked], ["plain", "mystery"])

    def test_a_coding_specialist_is_a_capable_chat_fallback(self):
        choice = router.choose(self.CHAT, [self.c("mystery"), self.c("coder", hints=("code",))])
        self.assertEqual(choice.candidate.key, "coder")
        self.assertIn("no better-documented model is available", choice.reason)

    def test_only_unknown_models_still_route_with_a_caution(self):
        choice = router.choose(self.CHAT, [self.c("mystery")])
        self.assertEqual(choice.candidate.key, "mystery")
        self.assertIn("not documented", choice.reason)
        self.assertIsNone(choice.code)

    def test_a_documented_limitation_excludes_from_auto_but_not_from_a_pin(self):
        reader = self.c("reader", hints=("ocr",), limited=("ocr",),
                        caps=("completion", "vision"))
        both = router.choose(self.CHAT, [reader, self.c("plain", hints=("general",))])
        self.assertEqual(both.candidate.key, "plain")
        self.assertIn(("reader", "is documented for page reading only (its publisher's card)"),
                      both.skipped)
        alone = router.choose(self.CHAT, [reader])
        self.assertIsNone(alone.candidate)
        self.assertEqual(alone.code, "unsuitable")
        self.assertIn("page reading only", alone.reason)
        self.assertEqual(router.choose(router.Task(profiles.OCR, needs_vision=True),
                                       [reader]).candidate.key, "reader")
        pinned = router.choose(self.CHAT, [reader], auto=False)
        self.assertEqual(pinned.candidate.key, "reader")
        self.assertIn("note: it is documented for page reading only", pinned.reason)

    def test_missing_evidence_is_never_a_limitation(self):
        choice = router.choose(self.CHAT, [self.c("no-template-no-card")])
        self.assertEqual(choice.candidate.key, "no-template-no-card")

    def test_a_hard_requirement_names_what_is_missing(self):
        task = router.classify("who is in this photo?", workflow=profiles.CHAT, images=True)
        choice = router.choose(task, [self.c("plain", hints=("general",))])
        self.assertIsNone(choice.candidate)
        self.assertIsNone(choice.code)
        self.assertIn("does not accept images", choice.reason)

    def test_a_current_self_test_ranks_but_never_gates(self):
        failed = router.choose(self.CHAT, [self.c("a", hints=("general",), check="failed"),
                                           self.c("b", hints=("general",))])
        self.assertEqual(failed.candidate.key, "b")
        alone = router.choose(self.CHAT, [self.c("a", hints=("general",), check="failed")])
        self.assertEqual(alone.candidate.key, "a")
        self.assertIn("failed this check here", alone.reason)
        passed = router.choose(self.CHAT, [self.c("z", hints=("general",), check="passed"),
                                           self.c("a", hints=("general",))])
        self.assertEqual(passed.candidate.key, "z")

    def test_the_ranked_list_is_every_suitable_model_best_first(self):
        choice = router.choose(self.CHAT, [
            self.c("mystery"), self.c("coder", hints=("code",)),
            self.c("plain", hints=("general",)),
            self.c("off", hints=("general",), blocked="switched off for new work")])
        self.assertEqual([c.key for c in choice.ranked], ["plain", "coder", "mystery"])
        self.assertIn(("off", "switched off for new work"), choice.skipped)

    def test_structured_documents_rank_before_limited_chat(self):
        task = router.Task(profiles.DOCUMENTS)
        choice = router.choose(task, [self.c("a-limited", hints=("general",), structured=False),
                                      self.c("z-structured", hints=("general",))])
        self.assertEqual([c.key for c in choice.ranked], ["z-structured", "a-limited"])

    def test_picture_questions_are_classified_conservatively(self):
        cases = {
            "transcribe this": router.TRANSCRIPTION,
            "What does it say?": router.TRANSCRIPTION,
            "please extract the text": router.TRANSCRIPTION,
            "summarise the text": router.TEXT_QUESTION,
            "what is the total on this invoice": router.TEXT_QUESTION,
            "transcribe the text in this image": router.TRANSCRIPTION,
            "what does this sign say": router.TRANSCRIPTION,
            "Is this signature genuine?": router.VISUAL,
            "Compare the handwriting in this document": router.VISUAL,
            "summarise this document": router.VISUAL,
            "summarise this receipt": router.VISUAL,
            "who signed this letter": router.VISUAL,
            "is this stamp authentic": router.VISUAL,
            # Mixed requests: a text clause plus anything else needs vision.
            "Transcribe the text and explain the gesture": router.VISUAL,
            "transcribe this and tell me who wrote it": router.VISUAL,
            "What does it say, and is it real?": router.VISUAL,
            "extract the text then describe the layout": router.VISUAL,
            "read the text, also what mood does it convey": router.VISUAL,
            "transcribe this. Is it friendly?": router.VISUAL,
            "summarise this PDF": router.VISUAL,
            # Whole requests in a clearly text-only form.
            "Could you read out the text from this page?": router.TRANSCRIPTION,
            "Perform OCR on this image": router.TRANSCRIPTION,
            "translate the text into French": router.TEXT_QUESTION,
            "what colour is the car?": router.VISUAL,
            "who is in this photo": router.VISUAL,
            "describe the image": router.VISUAL,
            "how many people are there?": router.VISUAL,
            "transcribe the text on the left": router.VISUAL,
            "what is this?": router.VISUAL,
            "": router.VISUAL,
        }
        for text, intent in cases.items():
            with self.subTest(text=text):
                self.assertEqual(router.image_intent(text), intent)

    def test_a_visual_question_needs_vision_and_a_text_request_only_prefers_it(self):
        visual = router.classify("what colour is the car", workflow=profiles.CHAT, images=True)
        self.assertTrue(visual.needs_vision)
        self.assertEqual(visual.image, router.VISUAL)
        text = router.classify("transcribe this", workflow=profiles.CHAT, images=True)
        self.assertFalse(text.needs_vision)
        self.assertIn("image", text.labels)
        self.assertEqual(router.wanted(text), router.OCR)
        plain = router.classify("hello", workflow=profiles.CHAT)
        self.assertIsNone(plain.image)


ACME_HELPER, ACME_READER = "acme/helper:1", "acme/reader:1"


class TestRoutingAcrossRuntimes(CoordinatorCase):
    """Made-up models on both runtimes: evidence, fallback and agreement."""

    STATE = runtime.merge({
        runtime.LLAMA_CPP: managed_state(
            GEMMA, CODER, capabilities={GEMMA.id: ["completion", "vision"]}),
        runtime.OLLAMA: ollama_state(
            {ACME_HELPER: "1" * 64, ACME_READER: "2" * 64},
            capabilities={ACME_HELPER: ["completion"],
                          ACME_READER: ["completion", "vision"]},
            model_tags={ACME_HELPER: ["conversational", "text-generation"]})})
    GEMMA_KEY, CODER_KEY = f"llama.cpp|{GEMMA.id}", f"llama.cpp|{CODER.id}"
    HELPER_KEY, READER_KEY = f"ollama|{ACME_HELPER}", f"ollama|{ACME_READER}"

    def test_one_resolver_describes_both_runtimes(self):
        observed = self.c.observations()
        self.assertEqual(observed[self.GEMMA_KEY]["evidence_level"], models.EVIDENCE_CARD)
        self.assertEqual(observed[self.HELPER_KEY]["hints"], ("general",))
        self.assertEqual(observed[self.HELPER_KEY]["evidence_level"], models.EVIDENCE_RUNTIME)
        self.assertEqual(observed[self.READER_KEY]["hints"], ())
        self.assertEqual(observed[self.READER_KEY]["limited_to"], ())

    def test_the_next_suitable_model_takes_over_as_models_go_away(self):
        self.assertEqual(self.c.choose_model("chat")["key"], self.GEMMA_KEY)
        db.set_model_enabled(self.c.conn, self.GEMMA_KEY, False)
        self.assertEqual(self.c.choose_model("chat")["key"], self.HELPER_KEY)
        db.set_model_enabled(self.c.conn, self.HELPER_KEY, False)
        self.assertEqual(self.c.choose_model("chat")["key"], self.CODER_KEY)
        self.assertEqual(self.c.choose_model("code")["key"], self.CODER_KEY)
        db.set_model_enabled(self.c.conn, self.CODER_KEY, False)
        db.set_model_enabled(self.c.conn, self.GEMMA_KEY, True)
        code = self.c.choose_model("code")
        self.assertEqual(code["key"], self.GEMMA_KEY)
        self.assertIn("general-purpose", code["reason"])

    def test_a_stopped_runtime_drops_out_and_the_other_runtime_serves(self):
        stopped = runtime.merge({
            runtime.LLAMA_CPP: {**managed_state(GEMMA), "reachable": False},
            runtime.OLLAMA: self.STATE["runtimes"][runtime.OLLAMA]})
        choice = self.c.choose_model("chat", observed=self.c.observations(stopped))
        self.assertEqual(choice["key"], self.HELPER_KEY)

    def test_auto_offers_an_ordered_list_and_a_pin_offers_none(self):
        choice = self.c.choose_model("chat")
        self.assertEqual(choice["alternatives"][0], self.HELPER_KEY)
        self.assertNotIn(choice["key"], choice["alternatives"])
        self.c.select_model("chat", self.READER_KEY)
        pinned = self.c.choose_model("chat")
        self.assertEqual((pinned["key"], pinned["alternatives"]), (self.READER_KEY, []))

    def test_preview_precheck_and_run_build_the_same_task(self):
        observed = self.c.observations()
        preview = self.c._choices(observed)["chat"]["key"]
        run = self.c.choose_model("chat", observed=observed,
                                  task=self.c.request_task("chat", "hello"))["key"]
        self.assertEqual(preview, run)
        self.c._precheck("chat", self.c.request_task("chat", "hello"))
        visual = self.c.request_task("chat", "what colour is this?", images=True)
        self.assertTrue(visual.needs_vision)
        self.assertEqual(self.c.choose_model("chat", observed=observed, task=visual)["key"],
                         self.GEMMA_KEY)

    def test_a_first_choice_refused_by_memory_falls_back_before_any_attempt(self):
        chat = db.create_chat(self.c.conn, self.c.workspace_id, "fallback")
        with patch("backend.coordinator.server.threading.Thread.start"):
            job = self.c.submit(chat, "hello there")
        real_admit = self.c._admit

        def admit(token, item, window, **kwargs):
            if item and item["key"] == self.GEMMA_KEY:
                return capacity.Decision("refuse", "Not enough free memory (test).")
            return real_admit(token, item, window, **kwargs)

        def stream(_messages, **_kwargs):
            yield "delta", "Hello."
            yield "done", {"done_reason": "stop"}

        with patch.object(self.c, "_admit", side_effect=admit), \
                patch.object(runtime, "stream_chat", stream):
            self.c._run(job, chat)
        detail = self.c.job_detail(job)
        self.assertEqual(detail["job"]["state"], "completed")
        self.assertEqual(len(detail["attempts"]), 1, "fallback happens before an attempt")
        attempt = detail["attempts"][0]
        self.assertIn(ACME_HELPER, attempt["model_json"])
        self.assertIn("skipped", attempt["route_reason"])
        self.assertIn("next suitable model", attempt["route_reason"])

    def test_a_pinned_model_refused_by_memory_is_not_swapped(self):
        self.c.select_model("chat", self.GEMMA_KEY)
        chat = db.create_chat(self.c.conn, self.c.workspace_id, "pinned")
        with patch("backend.coordinator.server.threading.Thread.start"):
            job = self.c.submit(chat, "hello there")
        with patch.object(self.c, "_admit",
                          return_value=capacity.Decision("refuse", "Not enough memory.")):
            self.c._run(job, chat)
        detail = self.c.job_detail(job)
        self.assertEqual(detail["job"]["state"], "failed")
        self.assertIn("Not enough memory", json.loads(
            detail["attempts"][0]["error_json"])["message"])


OCR_ONLY = "acme/page-reader:1"


class TestDemonstratedLimitation(CoordinatorCase):
    """D9: only an observed, current, task-specific failure to finish removes a
    model from Auto. Tags, missing tags and other failures only rank it."""

    STATE = runtime.merge({
        runtime.LLAMA_CPP: managed_state(),
        runtime.OLLAMA: ollama_state(
            {ACME_HELPER: "1" * 64, OCR_ONLY: "3" * 64},
            capabilities={ACME_HELPER: ["completion"], OCR_ONLY: ["completion"]},
            model_tags={ACME_HELPER: ["conversational"],
                        OCR_ONLY: ["image-to-text", "ocr", "document-parse"]})})
    HELPER_KEY, READER_KEY = f"ollama|{ACME_HELPER}", f"ollama|{OCR_ONLY}"

    def record(self, key, *, state="failed", kind=models.INCOMPLETE, fingerprint=None,
               digest=None, scope="chat"):
        observed = self.c.observations()
        db.record_selftest(
            self.c.conn, model=key, scope=scope, state=state, detail="recorded",
            digest=digest or observed[key]["digest"], runtime_version="0.34.2",
            check_fingerprint=fingerprint or self.c.check_fingerprints(key, observed)[scope],
            failure_kind=kind, reply_excerpt="It is my understanding that")

    def test_tags_alone_never_exclude_a_model(self):
        db.set_model_enabled(self.c.conn, self.HELPER_KEY, False)
        choice = self.c.choose_model("chat")
        self.assertEqual(choice["key"], self.READER_KEY, "a capable fallback, ranked low")
        self.assertIn("no better-documented model", choice["reason"])

    def test_a_current_incomplete_check_excludes_it_for_that_task_only(self):
        self.record(self.READER_KEY)
        db.set_model_enabled(self.c.conn, self.HELPER_KEY, False)
        chat = self.c.choose_model("chat")
        self.assertIsNone(chat["key"])
        self.assertEqual(chat["code"], "unsuitable")
        self.assertIn("did not finish its answer", chat["refusal"])
        # Code has no such evidence, so it stays a candidate there.
        self.assertEqual(self.c.choose_model("code")["key"], self.READER_KEY)
        row = next(r for r in self.c.model_inventory() if r["key"] == self.READER_KEY)
        self.assertEqual(list(row["auto_excluded"]), ["chat"])

    def test_stale_formatting_wrong_or_unavailable_results_never_exclude(self):
        db.set_model_enabled(self.c.conn, self.HELPER_KEY, False)
        for label, kwargs in (
                ("stale settings", {"fingerprint": "f" * 64}),
                ("replaced bytes", {"digest": "9" * 64}),
                ("formatting", {"kind": models.EXTRA_TEXT}),
                ("wrong answer", {"kind": models.WRONG_VERDICT}),
                ("could not run", {"state": "unavailable", "kind": None})):
            with self.subTest(label):
                self.record(self.READER_KEY, **kwargs)
                self.assertEqual(self.c.choose_model("chat")["key"], self.READER_KEY)

    def test_passing_again_restores_it(self):
        self.record(self.READER_KEY)
        self.record(self.READER_KEY, state="passed", kind=None)
        db.set_model_enabled(self.c.conn, self.HELPER_KEY, False)
        self.assertEqual(self.c.choose_model("chat")["key"], self.READER_KEY)

    def test_a_person_may_still_choose_it_with_the_reason_said(self):
        self.record(self.READER_KEY)
        self.c.select_model("chat", self.READER_KEY)
        pinned = self.c.choose_model("chat")
        self.assertEqual(pinned["key"], self.READER_KEY)
        self.assertIsNone(pinned["refusal"])
        self.assertIn("note: it did not finish its answer", pinned["reason"])

    def test_only_an_output_limit_stop_is_recorded_as_incomplete(self):
        key = self.HELPER_KEY

        def stops(reason, limit):
            def stream(_messages, **_kwargs):
                yield "delta", "It is my understanding"
                yield "done", {"done_reason": reason, "limit_reason": limit}
            return stream

        cases = (("length", "output", "failed", models.INCOMPLETE),
                 ("length", "context", "unavailable", None),
                 ("length", "unknown", "unavailable", None),
                 ("error", None, "unavailable", None))
        for reason, limit, state, kind in cases:
            with self.subTest(reason=reason, limit=limit):
                with patch.object(runtime, "stream_chat", stops(reason, limit)):
                    result = self.c.run_model_selftest("chat", model=key)
                self.assertEqual((result["state"], result["failure_kind"]), (state, kind))


BIG, SMALL = "acme/big-window:1", "acme/small-window:1"


class TestFallbackBeforeTheAttempt(CoordinatorCase):
    """Review finding: a request the first model's window cannot hold, or a
    proposal its budget cannot hold, was refused without trying the next."""

    STATE = runtime.merge({
        runtime.LLAMA_CPP: managed_state(GEMMA, CODER,
                                         capabilities={GEMMA.id: ["completion", "vision"]}),
        runtime.OLLAMA: ollama_state(
            {SMALL: "4" * 64, BIG: "5" * 64},
            capabilities={SMALL: ["completion"], BIG: ["completion"]},
            model_tags={SMALL: ["conversational"]},
            context_lengths={SMALL: 4096, BIG: 32768})})
    SMALL_KEY, BIG_KEY = f"ollama|{SMALL}", f"ollama|{BIG}"

    def setUp(self):
        super().setUp()
        for key in (f"llama.cpp|{GEMMA.id}", f"llama.cpp|{CODER.id}"):
            db.set_model_enabled(self.c.conn, key, False)
        self.chat = db.create_chat(self.c.conn, self.c.workspace_id, "long")

    def run_long(self):
        with patch("backend.coordinator.server.threading.Thread.start"):
            job = self.c.submit(self.chat, "Please check this text. " + "word " * 2600)

        def stream(_messages, **_kwargs):
            yield "delta", "Checked."
            yield "done", {"done_reason": "stop"}

        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, self.chat)
        return self.c.job_detail(job)

    def test_a_request_the_first_window_cannot_hold_goes_to_the_next_model(self):
        self.assertEqual(self.c.choose_model("chat")["key"], self.SMALL_KEY)
        detail = self.run_long()
        self.assertEqual(detail["job"]["state"], "completed")
        self.assertEqual(len(detail["attempts"]), 1)
        self.assertIn(BIG, detail["attempts"][0]["model_json"])
        self.assertIn("does not fit its context window", detail["attempts"][0]["route_reason"])

    def test_a_pinned_model_is_not_swapped_for_a_larger_window(self):
        self.c.select_model("chat", self.SMALL_KEY)
        detail = self.run_long()
        self.assertEqual(detail["job"]["state"], "failed")
        self.assertNotIn(BIG, detail["attempts"][0]["model_json"] or "")

    def test_a_proposal_the_first_budget_cannot_hold_goes_to_the_next_model(self):
        for key in (f"llama.cpp|{GEMMA.id}", f"llama.cpp|{CODER.id}"):
            db.set_model_enabled(self.c.conn, key, True)
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        project = Path(outside.name) / "project"
        project.mkdir()
        (project / "a.py").write_text("x = 1\n")
        repo_id = self.c.code.connect(str(project))["repo_id"]
        self.c.conn.execute("UPDATE repositories SET mode='full' WHERE repo_id=?", (repo_id,))
        self.c.conn.commit()
        first = self.c.choose_model("code")["key"]
        real_limit = code_service.CodeService._proposal_output_limit

        def limit(messages, selection, profile):
            if runtime.model_key(profile.model.runtime, profile.model.model_id) == first:
                raise code_service.CodeError("selection_too_large", "does not fit")
            return real_limit(messages, selection, profile)

        reply = json.dumps({"summary": "s", "edits": [{
            "path": "a.py", "base_sha256": hashlib.sha256(b"x = 1\n").hexdigest(),
            "content": "x = 2\n"}]})
        with patch.object(code_service.CodeService, "_proposal_output_limit",
                          staticmethod(limit)), \
                patch.object(code_service.CodeService, "_ask_model",
                             return_value=(reply, False)):
            proposal = self.c.code.propose(repo_id, "set x to 2", ["a.py"],
                                           execution_target=code_service.TARGET_LOCAL)
        attempt = self.c.conn.execute(
            "SELECT route_reason, model_json FROM attempts WHERE attempt_id=?",
            (proposal["attempt_id"],)).fetchone()
        self.assertNotIn(runtime.split_key(first)[1], attempt["model_json"])
        self.assertIn("skipped", attempt["route_reason"])


class TestPictureRequestsWithoutVision(CoordinatorCase):
    """Only a text model is here: a request for a picture's text may use page
    reading, but nothing may be answered from a picture nobody could read, and
    a question about what it shows is never answered from OCR text."""

    STATE = runtime.merge({
        runtime.LLAMA_CPP: managed_state(),
        runtime.OLLAMA: ollama_state({ACME_HELPER: "1" * 64},
                                     capabilities={ACME_HELPER: ["completion"]},
                                     model_tags={ACME_HELPER: ["conversational"]})})

    def send(self, text):
        chat = db.create_chat(self.c.conn, self.c.workspace_id, "picture")
        db.add_attachment(self.c.conn, self.c.attachments_root,
                          workspace_id=self.c.workspace_id, chat_id=chat,
                          filename="note.png", data=ocr.selftest_image())
        self.c.observations()
        with patch("backend.coordinator.server.threading.Thread.start"):
            job = self.c.submit(chat, text)
        with patch.object(runtime, "stream_chat",
                          side_effect=AssertionError("no model may answer")):
            self.c._run(job, chat)
        detail = self.c.job_detail(job)
        return detail["job"]["state"], json.loads(detail["attempts"][-1]["error_json"])["message"]

    def test_a_transcription_with_nothing_readable_is_refused_not_answered(self):
        state, message = self.send("transcribe this")
        self.assertEqual(state, "failed")
        self.assertIn("No answer was written without the file", message)

    def test_a_visual_question_is_refused_without_a_model_that_sees(self):
        with self.assertRaises(RequestError) as caught:
            self.send("Is this signature genuine?")
        self.assertIn("does not accept images", str(caught.exception))


class TestAttachmentsNeedTheirSource(CoordinatorCase):
    """Review findings: a request whose files could not be read was answered
    anyway, and every document request waited for a page reader it might
    never need."""

    STATE = runtime.merge({
        runtime.LLAMA_CPP: managed_state(),
        runtime.OLLAMA: ollama_state({ACME_HELPER: "1" * 64},
                                     capabilities={ACME_HELPER: ["completion"]},
                                     model_tags={ACME_HELPER: ["conversational"]})})

    def send(self, text, files=(), *, skill_id=None, reply="Done.", **extra):
        chat = db.create_chat(self.c.conn, self.c.workspace_id, "sources")
        for filename, data in files:
            db.add_attachment(self.c.conn, self.c.attachments_root,
                              workspace_id=self.c.workspace_id, chat_id=chat,
                              filename=filename, data=data)
        self.c.observations()
        with patch("backend.coordinator.server.threading.Thread.start"):
            job = self.c.submit(chat, text, skill_id=skill_id, **extra)
        calls = []

        def stream(_messages, **_kwargs):
            calls.append(1)
            yield "delta", reply
            yield "done", {"done_reason": "stop"}

        readers = []

        def page_reader(*args, **kwargs):
            readers.append(1)
            return None, None

        with patch.object(runtime, "stream_chat", stream), \
                patch.object(self.c, "_page_reader", side_effect=page_reader):
            self.c._run(job, chat, skill_id)
        detail = self.c.job_detail(job)
        error = detail["attempts"][-1]["error_json"]
        return (detail["job"]["state"], json.loads(error)["message"] if error else "",
                len(calls), len(readers))

    def test_an_unreadable_pdf_never_reaches_generation(self):
        state, message, generated, _readers = self.send(
            "Summarise this PDF", [("report.pdf", b"%PDF-1.4 not really a document")])
        self.assertEqual((state, generated), ("failed", 0))
        self.assertIn("No answer was written without the file", message)
        self.assertEqual(message.count("report.pdf"), 1, "the file is named once")
        self.assertNotIn("..", message)

    def test_an_unreadable_word_file_never_reaches_generation(self):
        state, message, generated, readers = self.send(
            "What does this say about pumps?", [("notes.docx", b"PK\x03\x04 broken")])
        self.assertEqual((state, generated, readers), ("failed", 0, 0))
        self.assertIn("notes.docx", message)

    def test_text_and_word_files_never_ask_for_a_page_reader(self):
        import zipfile, io
        from backend.coordinator import docgen
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", docgen._CONTENT_TYPES)
            archive.writestr("_rels/.rels", docgen._ROOT_RELS)
            archive.writestr("word/document.xml", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:document xmlns:w="{docgen.W}"><w:body><w:p><w:r><w:t>Pump P-204 '
                "vibration is 7.9 mm/s.</w:t></w:r></w:p></w:body></w:document>"))
        for files in ([("notes.txt", b"Pump P-204 vibration is 7.9 mm/s.\n")],
                      [("notes.docx", buffer.getvalue())]):
            with self.subTest(files=files[0][0]):
                state, _message, generated, readers = self.send("Summarise this file", files)
                self.assertEqual((state, generated, readers), ("completed", 1, 0))

    def test_a_chat_with_files_reaches_the_runtime_with_one_leading_system_message(self):
        """Found in the walkthrough: the identity block and the untrusted-file
        note arrived as two system messages, which the Refinix engine's Qwen
        template refuses ("System message must be at the beginning")."""
        chat = db.create_chat(self.c.conn, self.c.workspace_id, "one system")
        db.add_attachment(self.c.conn, self.c.attachments_root,
                          workspace_id=self.c.workspace_id, chat_id=chat,
                          filename="notes.txt", data=b"Pump P-204 vibration is 7.9 mm/s.\n")
        self.c.observations()
        with patch("backend.coordinator.server.threading.Thread.start"):
            job = self.c.submit(chat, "Summarise this file")
        seen = []

        def stream(messages, **_kwargs):
            seen.append(messages)
            yield "delta", "Summary."
            yield "done", {"done_reason": "stop"}

        with patch.object(runtime, "stream_chat", stream):
            self.c._run(job, chat)
        (messages,) = seen
        roles = [m["role"] for m in messages]
        self.assertEqual(roles.count("system"), 1)
        self.assertEqual(roles[0], "system")
        self.assertIn("Refinix", messages[0]["content"])
        self.assertIn(docflow.UNTRUSTED_NOTE[:40], messages[0]["content"])
        self.assertIn("7.9 mm/s", messages[-1]["content"], "the file stays data in the user turn")

    def test_one_system_message_keeps_order_and_leaves_single_ones_alone(self):
        from backend.coordinator.server import one_system_message
        single = [{"role": "system", "content": "a"}, {"role": "user", "content": "q"}]
        self.assertIs(one_system_message(single), single)
        merged = one_system_message([{"role": "system", "content": "a"},
                                     {"role": "system", "content": "b"},
                                     {"role": "user", "content": "q"}])
        self.assertEqual(merged, [{"role": "system", "content": "a\n\nb"},
                                  {"role": "user", "content": "q"}])

    def test_writing_a_document_without_files_never_asks_for_a_page_reader(self):
        reply = json.dumps({"title": "Backups", "sections": [
            {"heading": "Steps", "paragraphs": ["Copy the folder every Friday."]}]})
        state, _message, generated, readers = self.send(
            "Write a short note about Friday backups", skill_id=docflow.WRITE_SKILL,
            doc_workflow=docflow.WORKFLOW_GENERAL, reply=reply)
        self.assertEqual(readers, 0)
        self.assertEqual((state, generated), ("completed", 1))

    def test_a_picture_asks_for_the_reader_once_and_only_then(self):
        state, message, generated, readers = self.send(
            "transcribe this", [("note.png", ocr.selftest_image())])
        self.assertEqual((readers, generated, state), (1, 0, "failed"))


READER = "acme/reader:1"


class TestPageReaderFallback(CoordinatorCase):
    """Review finding: the page reader was one model, with no second choice,
    and its record named Ollama whatever ran."""

    STATE = runtime.merge({
        runtime.LLAMA_CPP: managed_state(GEMMA, capabilities={GEMMA.id: ["completion", "vision"]}),
        runtime.OLLAMA: ollama_state({READER: "6" * 64},
                                     capabilities={READER: ["completion", "vision"]},
                                     model_tags={READER: ["ocr"]})})
    READER_KEY, GEMMA_KEY = f"ollama|{READER}", f"llama.cpp|{GEMMA.id}"

    def test_the_reader_is_admitted_before_the_first_page_or_the_next_one_reads(self):
        observed = self.c.observations()
        self.assertEqual(self.c.choose_model("documents.ocr")["key"], self.READER_KEY)
        real_admit = self.c._admit

        def admit(token, item, window, **kwargs):
            if item and item["key"] == self.READER_KEY:
                return capacity.Decision("refuse", "Not enough free memory (test).")
            return real_admit(token, item, window, **kwargs)

        with patch.object(self.c, "_admit", side_effect=admit):
            key, profile = self.c._page_reader("job-r", observed)
        self.assertEqual(key, self.GEMMA_KEY)
        self.assertEqual(profile.model.runtime, "llama.cpp")
        self.assertEqual(self.c.ledger.snapshot(), [], "the check holds nothing afterwards")

    def test_a_pinned_reader_is_not_swapped(self):
        self.c.select_model("documents.ocr", self.READER_KEY)
        with patch.object(self.c, "_admit",
                          return_value=capacity.Decision("refuse", "Not enough memory.")):
            key, _profile = self.c._page_reader("job-p", self.c.observations())
        self.assertEqual(key, self.READER_KEY)


class TestCategoriesAndSetup(CoordinatorCase):
    STATE = TestRoutingAcrossRuntimes.STATE

    def test_categories_come_from_evidence_and_installed_models_come_first(self):
        status = self.c.status()
        cats = {c["id"]: c for c in status["categories"]}
        self.assertEqual(set(cats), {"chat", "code", "documents", "page_reading",
                                     "vision", "reasoning", "other"})
        chat = [o["key"] for o in cats["chat"]["initial"]]
        self.assertIn(TestRoutingAcrossRuntimes.HELPER_KEY, chat)
        self.assertTrue(all(o["installed"] for o in cats["chat"]["initial"][:2]))
        self.assertIn(TestRoutingAcrossRuntimes.CODER_KEY,
                      [o["key"] for o in cats["code"]["initial"] + cats["code"]["more"]])
        # A model nobody described is in no strength category; its image input
        # still makes it a page-reading choice.
        self.assertNotIn(TestRoutingAcrossRuntimes.READER_KEY, chat)
        self.assertIn(TestRoutingAcrossRuntimes.READER_KEY,
                      [o["key"] for o in cats["page_reading"]["initial"]
                       + cats["page_reading"]["more"]])

    def test_one_model_serves_every_category_it_fits_without_a_second_download(self):
        ids = capacity.category_ids(("general", "vision"), accepts_images=True)
        self.assertEqual(ids, {"chat", "documents", "page_reading", "vision"})
        self.assertEqual(capacity.category_ids(("ocr",), accepts_images=True,
                                               limited_to=("ocr",)), {"page_reading"})
        self.assertEqual(capacity.category_ids((), accepts_images=False), set())

    def test_setup_choices_persist_and_change_no_model(self):
        before = self.c.choose_model("chat")["key"]
        self.assertFalse(self.c.setup_state()["intro_dismissed"])
        self.c.update_setup({"intro_dismissed": True, "choice": "existing_models"})
        self.c.conn.close()
        reopened = Coordinator(self.c.state_path)
        self.addCleanup(reopened.conn.close)
        self.assertEqual(reopened.setup_state()["choice"], "existing_models")
        self.assertTrue(reopened.setup_state()["intro_dismissed"])
        with patch.object(reopened, "preflight", return_value=None):
            self.assertEqual(reopened.choose_model("chat")["key"], before)
        with self.assertRaises(RequestError):
            reopened.update_setup({"choice": "something else"})


class TestAutoInTheCoordinator(CoordinatorCase):
    STATE = runtime.merge({
        runtime.LLAMA_CPP: managed_state(
            GEMMA, CODER, capabilities={GEMMA.id: ["completion", "vision"]}),
        runtime.OLLAMA: ollama_state()})

    def test_auto_assigns_by_task_with_a_truthful_reason(self):
        code = self.c.choose_model("code")
        self.assertEqual(code["key"], f"llama.cpp|{CODER.id}")
        self.assertIn("coding", code["reason"])
        picture = self.c.choose_model(
            "chat", task=router.classify("what is in this photo", workflow=profiles.CHAT,
                                         prefers_vision=True))
        self.assertEqual(picture["key"], f"llama.cpp|{GEMMA.id}")
        self.assertIn("accepts images", picture["reason"])

    def test_page_reading_goes_to_a_model_that_declares_vision(self):
        self.assertEqual(self.c.enabled_model_for_observed(
            "documents.ocr", self.c.observations()), f"llama.cpp|{GEMMA.id}")
        self.assertIsNotNone(self.c.ocr_profile())

    def test_a_pinned_model_that_cannot_do_the_task_is_refused_not_swapped(self):
        self.c.select_model("documents.ocr", f"llama.cpp|{GEMMA.id}")
        db.set_model_selection(self.c.conn, "documents.ocr", f"llama.cpp|{CODER.id}")
        choice = self.c.choose_model("documents.ocr",
                                     task=router.Task(profiles.OCR, needs_vision=True))
        self.assertTrue(choice["pinned"])
        self.assertEqual(choice["key"], f"llama.cpp|{CODER.id}")
        self.assertIsNotNone(choice["refusal"])

    def test_auto_and_manual_preference_round_trip(self):
        self.c.select_model("chat", f"ollama|{OLLAMA_QWEN}")
        self.assertEqual(self.c.choose_model("chat")["key"], f"ollama|{OLLAMA_QWEN}")
        self.c.select_model("chat", models.AUTO)
        self.assertFalse(self.c.choose_model("chat")["pinned"])

    def test_every_installed_model_is_its_own_row_with_its_runtime(self):
        rows = {row["key"]: row for row in self.c.model_inventory()}
        self.assertEqual(rows[f"ollama|{OLLAMA_QWEN}"]["runtime_label"], "Ollama")
        self.assertEqual(rows[f"llama.cpp|{GEMMA.id}"]["runtime_label"], "Refinix engine")
        self.assertEqual(rows[f"llama.cpp|{GEMMA.id}"]["evidence"]["chat"], "compatible")
        self.assertFalse(rows[f"ollama|{OLLAMA_QWEN}"]["removable"])


class TestLegacyChoices(CoordinatorCase):
    STATE = runtime.merge({
        runtime.LLAMA_CPP: {**managed_state(), "models": [models.MANAGED_MAIN],
                            "digests": {models.MANAGED_MAIN:
                                        models.entry_for(models.MANAGED_MAIN).manifest_sha256}},
        runtime.OLLAMA: ollama_state()})

    def test_the_catalogued_ollama_tag_resolves_to_ollama_not_the_engine(self):
        """The catalogue holds both runtimes; its engine field decides."""
        self.c.observations()
        self.assertEqual(self.c.resolve_key(OLLAMA_QWEN),
                         (f"ollama|{OLLAMA_QWEN}", "resolved"))
        self.assertEqual(self.c.resolve_key(models.MANAGED_MAIN),
                         (f"llama.cpp|{models.MANAGED_MAIN}", "resolved"))

    def test_a_stored_bare_name_keeps_its_old_preferences(self):
        db.set_model_enabled(self.c.conn, OLLAMA_QWEN, False)
        db.set_reasoning(self.c.conn, OLLAMA_QWEN, True)
        self.c.observations()
        self.assertFalse(self.c.model_enabled(f"ollama|{OLLAMA_QWEN}"))
        self.assertTrue(self.c.reasoning_for(f"ollama|{OLLAMA_QWEN}"))
        self.assertTrue(self.c.model_enabled(f"llama.cpp|{models.MANAGED_MAIN}"))

    def test_a_name_in_both_runtimes_needs_an_explicit_choice(self):
        both = runtime.merge({
            runtime.LLAMA_CPP: {**managed_state(), "models": ["shared"],
                                "digests": {"shared": "a" * 64}},
            runtime.OLLAMA: ollama_state({"shared": "b" * 64})})
        db.set_model_selection(self.c.conn, "chat", "shared")
        choice = self.c.choose_model("chat", observed=self.c.observations(both))
        self.assertIsNone(choice["key"])
        self.assertEqual(choice["code"], "ambiguous")


class TestFreezeOrder(CoordinatorCase):
    STATE = ollama_state()

    def test_an_identity_change_after_admission_fails_the_attempt_visibly(self):
        chat = db.create_chat(self.c.conn, self.c.workspace_id, "freeze")
        with patch("backend.coordinator.server.threading.Thread.start"):
            job = self.c.submit(chat, "hello")
        with patch.object(runtime, "confirm_ollama", side_effect=runtime.RuntimeUnavailable(
                "qwen changed in Ollama after this request was prepared")):
            self.c._run(job, chat)
        detail = self.c.job_detail(job)
        self.assertEqual(detail["job"]["state"], "failed")
        self.assertEqual(len(detail["attempts"]), 1, "no silent second attempt")
        attempt = detail["attempts"][0]
        self.assertIn("changed", json.loads(attempt["error_json"])["message"])
        self.assertIn("Auto:", attempt["route_reason"])
        self.assertEqual(attempt["actual_profile"]["model"]["manifest_sha256"],
                         OLLAMA_DIGEST)


class TestLoadedWindowReachesAdmission(CoordinatorCase):
    """A loaded model counts as already holding its working memory only for
    the window each runtime reports it was loaded with."""

    STATE = runtime.merge({
        runtime.LLAMA_CPP: {**managed_state(GEMMA),
                            "loaded": {"model": GEMMA.id, "context_length": 8192}},
        runtime.OLLAMA: {**ollama_state(), "loaded_all": [
            {"model": OLLAMA_QWEN, "digest": OLLAMA_DIGEST, "context_length": 8192}]}})

    def test_each_runtime_reports_its_loaded_window(self):
        observed = self.c.observations()
        for key in (f"llama.cpp|{GEMMA.id}", f"ollama|{OLLAMA_QWEN}"):
            self.assertTrue(observed[key]["resident"], key)
            self.assertEqual(observed[key]["loaded_window"], 8192, key)

    def test_only_the_loaded_window_reserves_no_working_memory(self):
        observed = self.c.observations()
        weights = observed[f"llama.cpp|{GEMMA.id}"]["weights_bytes"]
        roomy = {"memory_total_bytes": 64 * GIB, "memory_available_bytes": 32 * GIB}
        with patch.object(self.c, "hardware_facts", roomy), \
                patch.object(self.c.ledger, "_observe", return_value=32 * GIB):
            for token, key, window, state in (
                    ("same", f"llama.cpp|{GEMMA.id}", 8192, 0),
                    ("wider", f"llama.cpp|{GEMMA.id}", 32768,
                     capacity.state_estimate(weights, 32768)),
                    ("ollama-same", f"ollama|{OLLAMA_QWEN}", 8192, 0)):
                decision = self.c._admit(token, observed[key], window)
                self.assertEqual(decision.outcome, "admit", token)
                held = {r["job_id"]: r for r in self.c.ledger.snapshot()}[token]
                self.assertEqual((held["resident_bytes"], held["state_bytes"]),
                                 (0, state), token)
                self.c.ledger.release(token)


class TestCloudModels(CoordinatorCase):
    STATE = ollama_state({OLLAMA_QWEN: OLLAMA_DIGEST, "gpt-oss:120b-cloud": "d" * 64},
                         remote=["gpt-oss:120b-cloud"])

    def test_a_cloud_model_is_listed_but_never_routed(self):
        rows = {row["key"]: row for row in self.c.model_inventory()}
        cloud = rows["ollama|gpt-oss:120b-cloud"]
        self.assertEqual((cloud["state"], cloud["eligible_scopes"]), ("cloud", []))
        with self.assertRaises(RequestError):
            self.c.select_model("chat", "ollama|gpt-oss:120b-cloud")
        self.assertEqual(self.c.choose_model("chat")["key"], f"ollama|{OLLAMA_QWEN}")
        self.assertIn("gpt-oss:120b-cloud", self.c.status()["ollama"]["cloud_models"])


# --------------------------------------------------------------------------
# Capacity and the single-engine queue
# --------------------------------------------------------------------------

GIB = capacity.GIB
MEMORY = {"kind": capacity.UNIFIED, "host_total_bytes": 16 * GIB,
          "host_available_bytes": 10 * GIB, "device_bytes": None,
          "capacity_bytes": 16 * GIB}


class TestLedger(unittest.TestCase):
    def ledger(self, available):
        return capacity.Ledger(observe=lambda: available, sleep=lambda _s: None)

    def test_resident_weights_count_once_and_outlive_the_job(self):
        ledger = self.ledger(10 * GIB)
        first = ledger.decide(job_id="j1", key="m", origin="llama.cpp",
                              weights_bytes=3 * GIB, window=8192, resident=False,
                              memory=MEMORY)
        self.assertEqual(first.outcome, "admit")
        ledger.release("j1")
        ledger.mark_resident({"m"})
        self.assertEqual(ledger.snapshot(), [])
        again = ledger.decide(job_id="j2", key="m", origin="llama.cpp",
                              weights_bytes=3 * GIB, window=8192, resident=True,
                              memory=MEMORY)
        self.assertEqual(again.outcome, "admit")
        self.assertEqual(ledger.snapshot()[0]["resident_bytes"], 0,
                         "a resident model is not reserved twice")

    def test_two_big_loads_cannot_spend_the_same_total_memory(self):
        """Memory-mapped weights are bounded by the total for models, and two
        loads decided at the same moment share that total."""
        ledger = self.ledger(12 * GIB)
        one = ledger.decide(job_id="a", key="x", origin="llama.cpp", weights_bytes=7 * GIB,
                            window=8192, resident=False, memory=MEMORY)
        two = ledger.decide(job_id="b", key="y", origin="llama.cpp", weights_bytes=7 * GIB,
                            window=8192, resident=False, memory=MEMORY)
        self.assertEqual((one.outcome, two.outcome), ("admit", "wait"))
        self.assertIn("estimated", two.reason)

    def test_working_memory_must_be_free_now_and_is_not_double_spent(self):
        ledger = self.ledger(1 * GIB)
        one = ledger.decide(job_id="a", key="x", origin="llama.cpp", weights_bytes=GIB // 2,
                            window=8192, resident=False, memory=MEMORY)
        two = ledger.decide(job_id="b", key="y", origin="llama.cpp", weights_bytes=GIB // 2,
                            window=8192, resident=False, memory=MEMORY)
        self.assertEqual((one.outcome, two.outcome), ("admit", "wait"))
        self.assertIn("working memory", two.reason)

    def test_requests_to_resident_models_run_side_by_side(self):
        """The live finding: two loaded models (Ollama and the Refinix
        engine) must stream together, not queue on a per-request estimate."""
        ledger = self.ledger(GIB // 2)
        for job, key, origin in (("o", "ollama|q", "ollama"), ("m", "llama.cpp|q", "llama.cpp")):
            decision = ledger.decide(job_id=job, key=key, origin=origin,
                                     weights_bytes=3 * GIB, window=8192, resident=True,
                                     loaded_window=8192, memory=MEMORY)
            self.assertEqual(decision.outcome, "admit", key)

    def test_a_resident_model_asked_for_another_window_needs_that_state(self):
        """Both runtimes reload a model for a different window (Ollama on a
        num_ctx change, the Refinix engine on a settings change), so only a
        request for the loaded window adds no working memory. The weights
        are the same mapped bytes and are not counted again."""
        weights = 3 * GIB
        short = self.ledger(GIB)
        for loaded in (8192, None):
            decision = short.decide(job_id=f"w{loaded}", key="llama.cpp|q",
                                    origin="llama.cpp", weights_bytes=weights,
                                    window=32768, resident=True, loaded_window=loaded,
                                    memory=MEMORY)
            self.assertEqual(decision.outcome, "wait", loaded)
            self.assertIn("working memory", decision.reason)
        roomy = self.ledger(10 * GIB)
        decision = roomy.decide(job_id="r", key="llama.cpp|q", origin="llama.cpp",
                                weights_bytes=weights, window=32768, resident=True,
                                loaded_window=8192, memory=MEMORY)
        self.assertEqual(decision.outcome, "admit")
        (held,) = roomy.snapshot()
        self.assertEqual(held["resident_bytes"], 0)
        self.assertEqual(held["state_bytes"], capacity.state_estimate(weights, 32768))
        # Ollama is never held back, but its reload is still recorded so a
        # Refinix-engine load decided at the same moment cannot spend it.
        ollama = self.ledger(GIB)
        decision = ollama.decide(job_id="o", key="ollama|q", origin="ollama",
                                 weights_bytes=weights, window=16384, resident=True,
                                 loaded_window=8192, memory=MEMORY, enforce_wait=False)
        self.assertEqual(decision.outcome, "admit")
        self.assertEqual(ollama.snapshot()[0]["state_bytes"],
                         capacity.state_estimate(weights, 16384))

    def test_one_jobs_uses_of_one_model_do_not_add_up(self):
        """Page reading then writing with the same model is sequential: the
        second use reserves only what the first does not already hold."""
        ledger = self.ledger(10 * GIB)
        ledger.decide(job_id="j", key="m", origin="llama.cpp", weights_bytes=3 * GIB,
                      window=8192, resident=False, memory=MEMORY)
        ledger.decide(job_id="j:ocr", group="j", key="m", origin="llama.cpp",
                      weights_bytes=3 * GIB, window=16384, resident=False, memory=MEMORY)
        held = {r["job_id"]: r for r in ledger.snapshot()}
        self.assertEqual(held["j:ocr"]["resident_bytes"], 0)
        self.assertEqual(held["j:ocr"]["state_bytes"],
                         capacity.state_estimate(3 * GIB, 16384)
                         - capacity.state_estimate(3 * GIB, 8192))
        # Another model in the same job is reserved in full, and the job's
        # end releases everything it holds.
        ledger.decide(job_id="j:ocr2", group="j", key="other", origin="ollama",
                      weights_bytes=GIB, window=8192, resident=False, memory=MEMORY)
        self.assertGreater({r["job_id"]: r for r in ledger.snapshot()}["j:ocr2"]
                           ["resident_bytes"], 0)
        ledger.release_group("j")
        self.assertEqual(ledger.snapshot(), [])

    def test_a_later_page_needs_nothing_once_the_model_is_loaded(self):
        """Review finding: once the first page loaded the model, the reading
        already showed its memory in use, but the answer's reservation was
        still subtracted and a page needing nothing more was refused."""
        available = [3 * GIB]
        ledger = capacity.Ledger(observe=lambda: available[0], sleep=lambda _s: None,
                                 clock=iter(range(0, 10_000)).__next__)
        use = dict(key="m", origin="llama.cpp", weights_bytes=2 * GIB, window=8192,
                   memory=MEMORY)
        self.assertEqual(ledger.decide(job_id="j", resident=False, **use).outcome, "admit")
        self.assertEqual(ledger.acquire(job_id="j:ocr", group="j", resident=False,
                                        timeout=5, **use).outcome, "admit")
        ledger.release("j:ocr")
        available[0] = int(0.4 * GIB)        # the first page loaded the model
        ledger.mark_resident({"m": 8192})
        held = {r["job_id"]: r for r in ledger.snapshot()}["j"]
        self.assertEqual((held["resident_bytes"], held["state_bytes"]), (0, 0),
                         "the reading now shows the weights and the 8192 state")
        self.assertEqual(ledger.acquire(job_id="j:ocr", group="j", resident=True,
                                        loaded_window=8192, timeout=5, **use).outcome,
                         "admit")

    def test_nothing_new_to_allocate_is_never_refused(self):
        ledger = capacity.Ledger(observe=lambda: 0, sleep=lambda _s: None,
                                 clock=iter(range(0, 10_000)).__next__)
        ledger.decide(job_id="other", key="x", origin="llama.cpp", weights_bytes=GIB,
                      window=8192, resident=False, memory=MEMORY, enforce_wait=False)
        decision = ledger.acquire(job_id="j", key="m", origin="llama.cpp",
                                  weights_bytes=2 * GIB, window=8192, resident=True,
                                  loaded_window=8192, memory=MEMORY, timeout=5)
        self.assertEqual(decision.outcome, "admit")

    def test_only_state_for_the_loaded_window_stops_counting(self):
        ledger = self.ledger(10 * GIB)
        for job, window in (("a", 8192), ("b", 16384)):
            ledger.decide(job_id=job, key="m", origin="llama.cpp", weights_bytes=2 * GIB,
                          window=window, resident=False, memory=MEMORY)
        ledger.mark_resident({"m": 8192})
        held = {r["job_id"]: r for r in ledger.snapshot()}
        self.assertEqual(held["a"]["state_bytes"], 0)
        self.assertEqual(held["b"]["state_bytes"], capacity.state_estimate(2 * GIB, 16384),
                         "a different window reloads the model and needs its state")
        self.assertEqual({held["a"]["resident_bytes"], held["b"]["resident_bytes"]}, {0})

    def test_a_wait_sees_a_model_another_job_loaded(self):
        """Review finding: a queued request kept its first reading and timed
        out after another job had loaded its model."""
        ledger = capacity.Ledger(observe=lambda: int(2.5 * GIB), sleep=lambda _s: None,
                                 clock=iter(range(0, 10_000)).__next__)
        loading = ledger.decide(job_id="loader", key="m", origin="llama.cpp",
                                weights_bytes=7 * GIB, window=8192, resident=False,
                                memory=MEMORY)
        self.assertEqual(loading.outcome, "admit")
        readings = iter([None, {"resident": True, "loaded_window": 8192}])
        decision = ledger.acquire(job_id="waiter", key="m", origin="llama.cpp",
                                  weights_bytes=7 * GIB, window=8192, resident=False,
                                  memory=MEMORY, timeout=60,
                                  refresh=lambda: next(readings, None))
        self.assertEqual(decision.outcome, "admit")
        held = {r["job_id"]: r for r in ledger.snapshot()}
        self.assertEqual(held["loader"]["resident_bytes"], 0,
                         "the observation now counts the loaded weights")
        self.assertEqual((held["waiter"]["resident_bytes"], held["waiter"]["state_bytes"]),
                         (0, 0))
        # Without a fresh reading the same wait ends in a refusal.
        stale = capacity.Ledger(observe=lambda: int(2.5 * GIB), sleep=lambda _s: None,
                                clock=iter(range(0, 10_000)).__next__)
        stale.decide(job_id="loader", key="m", origin="llama.cpp",
                     weights_bytes=7 * GIB, window=8192, resident=False, memory=MEMORY)
        self.assertEqual(stale.acquire(job_id="waiter", key="m", origin="llama.cpp",
                                       weights_bytes=7 * GIB, window=8192,
                                       resident=False, memory=MEMORY,
                                       timeout=60).outcome, "refuse")

    def test_mapped_weights_do_not_need_to_be_free_this_instant(self):
        """The live finding: macOS reports little "available" memory, and a
        model the measured preset runs comfortably must not be held back."""
        ledger = self.ledger(3 * GIB)
        decision = ledger.decide(job_id="m", key="qwen", origin="llama.cpp",
                                 weights_bytes=int(2.74 * GIB), window=8192,
                                 resident=False, memory=MEMORY)
        self.assertEqual(decision.outcome, "admit")

    def test_ollama_work_is_recorded_without_being_held_back(self):
        ledger = self.ledger(2 * GIB)
        decision = ledger.decide(job_id="o", key="ollama|m", origin="ollama",
                                 weights_bytes=3 * GIB, window=8192, resident=False,
                                 memory=MEMORY, enforce_wait=False)
        self.assertEqual(decision.outcome, "admit")
        self.assertEqual(len(ledger.snapshot()), 1)

    def test_a_grossly_oversized_load_is_refused_as_an_estimate(self):
        decision = self.ledger(10 * GIB).decide(
            job_id="big", key="m", origin="llama.cpp", weights_bytes=63 * GIB,
            window=8192, resident=False, memory=MEMORY)
        self.assertEqual(decision.outcome, "refuse")
        self.assertIn("estimated", decision.reason)

    def test_a_wait_is_bounded_and_cancellable(self):
        ledger = capacity.Ledger(observe=lambda: GIB // 2, sleep=lambda _s: None,
                                 clock=iter(range(0, 10_000, 100)).__next__)
        refused = ledger.acquire(job_id="w", key="m", origin="llama.cpp",
                                 weights_bytes=3 * GIB, window=8192, resident=False,
                                 memory=MEMORY, timeout=300)
        self.assertEqual(refused.outcome, "refuse")
        cancelled = self.ledger(GIB // 2).acquire(
            job_id="c", key="m", origin="llama.cpp", weights_bytes=3 * GIB, window=8192,
            resident=False, memory=MEMORY, should_cancel=lambda: True)
        self.assertEqual(cancelled.outcome, "cancelled")


class TestSingleEngineQueue(unittest.TestCase):
    def engine(self):
        selection = SimpleNamespace(manifest=None, usable=False, problems=[],
                                    runtime_version="b1", describe=lambda: {})
        backend = local_engine.LocalEngine(selection, Path(tempfile.gettempdir()),
                                           registry=lambda: {}, settings_for=lambda *_: None)
        backend.switch_wait_seconds = 5
        return backend

    def test_another_model_waits_for_running_work_instead_of_cutting_it_off(self):
        backend = self.engine()
        first, second = ("m1", "files1", "s"), ("m2", "files2", "s")
        self.assertTrue(backend._enter(first, None, RuntimeError))
        entered = threading.Event()
        threading.Thread(target=lambda: (backend._enter(second, None, RuntimeError),
                                         entered.set()), daemon=True).start()
        time.sleep(0.4)
        self.assertFalse(entered.is_set(), "the switch waited")
        backend._leave(first)
        self.assertTrue(entered.wait(3), "and then went ahead")

    def test_the_same_model_shares_the_engine(self):
        backend = self.engine()
        lease = ("m1", "files1", "s")
        self.assertTrue(backend._enter(lease, None, RuntimeError))
        self.assertTrue(backend._enter(lease, None, RuntimeError))
        self.assertTrue(backend.in_use("m1"))

    def test_stop_works_while_queued_and_a_wait_is_bounded(self):
        backend = self.engine()
        backend._enter(("m1", "a", "s"), None, RuntimeError)
        self.assertFalse(backend._enter(("m2", "b", "s"), lambda: True, RuntimeError))
        backend.switch_wait_seconds = 0.3
        with self.assertRaisesRegex(RuntimeError, "still serving m1"):
            backend._enter(("m2", "b", "s"), None, RuntimeError)

    def test_a_model_answering_a_request_cannot_be_unloaded(self):
        backend = self.engine()
        backend._enter(("m1", "a", "s"), None, RuntimeError)
        with self.assertRaises(engine.EngineError):
            backend.unload("m1")


class TestOneEngineAcrossWorkflows(unittest.TestCase):
    """The live finding: page reading and document writing on the same model
    must not restart the engine between them when the window is the same."""

    def test_a_reviewed_preset_serves_every_workflow_at_its_window(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        c = Coordinator(Path(scratch.name) / "state.sqlite3")
        self.addCleanup(c.conn.close)
        c.tier_ids = [profiles.MAC_TIER]
        record = SimpleNamespace(manifest_sha256=profiles.MANAGED_MODEL_DIGEST)
        backend = SimpleNamespace(registry=lambda: {profiles.MANAGED_MODEL_ID: record},
                                  selection=SimpleNamespace(runtime_version="b11390-metal"))
        measured = next(p for p in profiles.PROFILES
                        if p.model.model_id == profiles.MANAGED_MODEL_ID
                        and p.workflow_mode == profiles.DOCUMENTS)
        candidate = admission.candidate(
            {"model_id": profiles.MANAGED_MODEL_ID, "digest": profiles.MANAGED_MODEL_DIGEST,
             "origin": "llama.cpp", "runtime_version": "b11390-metal", "locality": "local",
             "capabilities": ["completion", "vision"], "context_length": 262144},
            profiles.OCR)
        with patch.object(runtime, "managed_engine", return_value=backend):
            for_documents = c.engine_settings_for(profiles.MANAGED_MODEL_ID, measured)
            for_pages = c.engine_settings_for(profiles.MANAGED_MODEL_ID, candidate)
            wider = c.engine_settings_for(
                profiles.MANAGED_MODEL_ID,
                admission.candidate({**{"model_id": profiles.MANAGED_MODEL_ID,
                                        "digest": profiles.MANAGED_MODEL_DIGEST,
                                        "origin": "llama.cpp",
                                        "runtime_version": "b11390-metal",
                                        "locality": "local", "capabilities": None,
                                        "context_length": 262144}},
                                    profiles.CHAT, window=16384))
        self.assertEqual(for_documents, for_pages, "same window, same engine")
        self.assertEqual(for_documents.fit, "off")
        self.assertEqual((wider.fit, wider.context_tokens), ("on", 16384))


class TestEngineSettings(unittest.TestCase):
    def test_a_model_nobody_measured_uses_upstream_fitting_at_a_fixed_window(self):
        args = engine.fitted_settings(16384).arguments()
        self.assertEqual(args[args.index("-c") + 1], "16384")
        self.assertEqual(args[args.index("--fit") + 1], "on")
        self.assertEqual(args[args.index("-ngl") + 1], "auto")
        self.assertIn("--fit-target", args)

    def test_a_measured_preset_keeps_every_setting_pinned(self):
        args = engine.LaunchSettings(context_tokens=8192).arguments()
        self.assertEqual(args[args.index("--fit") + 1], "off")
        self.assertNotIn("--fit-target", args)


# --------------------------------------------------------------------------
# C. Library, resolved downloads, shards and identity on disk
# --------------------------------------------------------------------------

def _pinned(model_id, files, revision="1" * 40):
    return models.Entry(
        id=model_id, role="Library model", scopes=(models.CHAT,),
        source="huggingface.co/owner/repo", licence="mit",
        manifest_sha256=models.manifest_digest(model_id, revision, files),
        format="GGUF", parameters=None, storage_bytes=sum(f.size for f in files),
        minimum_runtime=None, evidence="test", evidence_state=models.LISTED,
        engine="llama.cpp", files=files, revision=revision, repo="owner/repo",
        context_length=4096, repo_tags=("conversational",))


class TestResolvedInstalls(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.home = Path(self.scratch.name)
        self.c = Coordinator(self.home / "state" / "state.sqlite3")
        self.addCleanup(self.c.conn.close)

    def parts(self, *payloads):
        files, paths = [], []
        count = len(payloads)
        for index, payload in enumerate(payloads, start=1):
            name = f"model-{index:05d}-of-{count:05d}.gguf"
            path = self.home / name
            path.write_bytes(payload)
            files.append(models.ModelFile("weights" if index == 1 else "weights-part", name,
                                          len(payload), hashlib.sha256(payload).hexdigest(),
                                          f"https://huggingface.co/owner/repo/resolve/x/{name}"))
            paths.append(path)
        return tuple(files), paths

    def test_a_split_model_keeps_every_part_in_order(self):
        files, paths = self.parts(b"A" * 64, b"B" * 32, b"C" * 16)
        entry = self.c.provisioner.add_plan(_pinned("hf-owner-model-1111111", files))
        self.c.provisioner.start_import(entry.id, list(reversed(paths)))
        self.c.provisioner.wait(10)
        self.assertEqual(self.c.provisioner.state()[entry.id]["state"], "done")
        installed = self.c.installed_models()[entry.id]
        self.assertEqual([c.path.name for c in installed.components],
                         [f.name for f in files])
        self.assertEqual(installed.weights.name, files[0].name)
        self.assertEqual(installed.context_length, 4096)

    def test_resolved_metadata_survives_reopening_and_old_rows_still_read(self):
        files, paths = self.parts(b"Z" * 40)
        entry = self.c.provisioner.add_plan(_pinned("hf-owner-solo-1111111", files))
        self.c.provisioner.start_import(entry.id, paths)
        self.c.provisioner.wait(10)
        self.c.conn.close()
        reopened = Coordinator(self.home / "state" / "state.sqlite3")
        self.addCleanup(reopened.conn.close)
        record = db.get_model_install(reopened.conn, entry.id)
        again = models.entry_from_record(record)
        self.assertEqual((again.repo, again.revision, again.repo_tags, again.hints),
                         ("owner/repo", "1" * 40, ("conversational",), ()))
        self.assertEqual(models.task_evidence(again)["strengths"], ("general",))
        self.assertEqual(models.task_evidence(again)["level"], models.EVIDENCE_REPOSITORY)
        legacy = {"model_id": "old-model", "source": "download from somewhere",
                  "manifest_sha256": "a" * 64}
        self.assertIsNone(models.entry_from_record(legacy))
        self.assertEqual(models.entry_from_record(
            {"model_id": models.MANAGED_MAIN, "source": "imported from files"}).id,
            models.MANAGED_MAIN)

    def test_a_plan_survives_a_restart_beside_its_partial_download(self):
        files, _paths = self.parts(b"P" * 10)
        entry = self.c.provisioner.add_plan(_pinned("hf-owner-later-1111111", files))
        fresh = provisioning.Provisioner(self.c.conn, self.c.state_path)
        self.assertEqual(fresh.plan(entry.id)["manifest_sha256"], entry.manifest_sha256)

    def test_an_import_checks_space_and_refuses_strangers_before_copying(self):
        files, paths = self.parts(b"Q" * 50)
        entry = self.c.provisioner.add_plan(_pinned("hf-owner-space-1111111", files))
        stranger = self.home / "stranger.gguf"
        stranger.write_bytes(b"x" * 7)
        with self.assertRaisesRegex(provisioning.ProvisioningError, "stranger.gguf"):
            self.c.provisioner.start_import(entry.id, [stranger])
        tight = provisioning.Provisioner(
            self.c.conn, self.c.state_path,
            disk_usage=lambda _p: SimpleNamespace(free=10))
        tight.add_plan(entry)
        with self.assertRaises(provisioning.ProvisioningError) as caught:
            tight.start_import(entry.id, paths)
        self.assertEqual(caught.exception.code, "insufficient_space")

    def test_removal_refuses_when_the_engine_cannot_be_stopped(self):
        files, paths = self.parts(b"R" * 20)
        entry = self.c.provisioner.add_plan(_pinned("hf-owner-busy-1111111", files))
        self.c.provisioner.start_import(entry.id, paths)
        self.c.provisioner.wait(10)

        def stuck(_model):
            raise engine.EngineError("engine_stop_blocked", "would not stop")
        self.c.provisioner.unload = stuck
        with self.assertRaises(provisioning.ProvisioningError) as caught:
            self.c.provisioner.remove(entry.id)
        self.assertEqual(caught.exception.code, "unload_failed")
        self.assertIsNotNone(db.get_model_install(self.c.conn, entry.id))

    def test_managed_ids_are_collision_safe(self):
        first = models.managed_id_for("Owner/Repo", "Model-Q4.gguf", "abcdef1234")
        self.assertRegex(first, r"^[a-z0-9._-]+$")
        self.assertNotIn(":", first)
        self.assertNotIn("|", first)
        self.assertNotEqual(models.managed_id_for("Owner/Repo", "Model-Q4.gguf",
                                                  "abcdef1234", {first}), first)


class TestPageReadingIsAdmitted(CoordinatorCase):
    """Review finding: a job's page reads called the page-reading model with
    no reservation of their own, beside the one held for the answer."""

    STATE = TestAutoInTheCoordinator.STATE

    def profile(self, observed, key):
        return admission.candidate(observed[key], profiles.OCR)

    def test_a_page_read_holds_its_own_reservation_while_it_runs(self):
        observed = self.c.observations()
        key = f"llama.cpp|{GEMMA.id}"
        seen = []

        def stream(_messages, **_kwargs):
            seen.append({r["job_id"]: r["key"] for r in self.c.ledger.snapshot()})
            yield "done", {"done_reason": "stop"}

        roomy = {"memory_total_bytes": 64 * GIB, "memory_available_bytes": 32 * GIB}
        with patch.object(self.c, "hardware_facts", roomy), \
                patch.object(self.c.ledger, "_observe", return_value=32 * GIB), \
                patch.object(runtime, "stream_chat", stream):
            call = self.c._page_reading_call("job-1", key)
            list(call([], profile=self.profile(observed, key), should_cancel=None))
        self.assertEqual(seen, [{"job-1:ocr": key}])
        self.assertEqual(self.c.ledger.snapshot(), [], "released after the page")

    def test_a_page_read_the_ledger_would_hold_is_refused_not_sent(self):
        observed = self.c.observations()
        key = f"llama.cpp|{GEMMA.id}"
        tight = {"memory_total_bytes": 16 * GIB, "memory_available_bytes": GIB // 4}
        self.c.ledger = capacity.Ledger(observe=lambda: GIB // 4, sleep=lambda _s: None,
                                        clock=iter(range(0, 100_000, 50)).__next__)

        def stream(*_a, **_k):
            raise AssertionError("the page must not be sent")
            yield  # pragma: no cover

        with patch.object(self.c, "hardware_facts", tight), \
                patch.object(self.c, "_residency", return_value=None), \
                patch.object(runtime, "stream_chat", stream):
            call = self.c._page_reading_call("job-2", key)
            with self.assertRaises(ocr.OcrError) as caught:
                list(call([], profile=self.profile(observed, key), should_cancel=None))
        self.assertEqual(caught.exception.code, "unavailable")
        self.assertIn("memory", str(caught.exception))
        self.assertEqual(self.c.ledger.snapshot(), [])

    def test_each_page_reads_residency_again(self):
        """After the first page loads the model, the next page is admitted on a
        fresh reading even when the memory figure is tight."""
        observed = self.c.observations()
        key = f"llama.cpp|{GEMMA.id}"
        tight = {"memory_total_bytes": 16 * GIB, "memory_available_bytes": GIB // 4}
        self.c.ledger = capacity.Ledger(observe=lambda: GIB // 4, sleep=lambda _s: None,
                                        clock=iter(range(0, 100_000, 50)).__next__)
        profile = self.profile(observed, key)
        window = profile.qualified_context_tokens
        # The job's answer already holds a reservation for this model.
        self.c.ledger.decide(job_id="job-3", key=key, origin="llama.cpp",
                             weights_bytes=observed[key]["weights_bytes"], window=window,
                             resident=False, memory=capacity.pool(tight),
                             enforce_wait=False)

        def stream(_messages, **_kwargs):
            yield "done", {"done_reason": "stop"}

        with patch.object(self.c, "hardware_facts", tight), \
                patch.object(self.c, "_residency",
                             return_value={"resident": True, "loaded_window": window}), \
                patch.object(runtime, "stream_chat", stream):
            call = self.c._page_reading_call("job-3", key)
            self.assertEqual(list(call([], profile=profile, should_cancel=None)),
                             [("done", {"done_reason": "stop"})])
        held = {r["job_id"]: r for r in self.c.ledger.snapshot()}["job-3"]
        self.assertEqual((held["resident_bytes"], held["state_bytes"]), (0, 0))

    def test_a_wait_reads_the_engine_it_is_waiting_for(self):
        observed = self.c.observations()
        item = observed[f"llama.cpp|{GEMMA.id}"]
        self.addCleanup(runtime.configure_managed, None)
        runtime.configure_managed(SimpleNamespace(loaded=lambda: {
            "model": GEMMA.id, "context_length": 16384}))
        self.assertEqual(self.c._residency(item),
                         {"resident": True, "loaded_window": 16384})
        runtime.configure_managed(SimpleNamespace(loaded=lambda: {
            "model": CODER.id, "context_length": 8192}))
        self.assertEqual(self.c._residency(item),
                         {"resident": False, "loaded_window": None})


class TestInstallReadsUnderConcurrency(unittest.TestCase):
    """The preview finding: Settings polls status and capabilities at once,
    and both read model installs through the one shared connection."""

    def test_parallel_install_reads_are_whole_and_consistent(self):
        with tempfile.TemporaryDirectory() as scratch:
            conn = db.connect(Path(scratch) / "state.sqlite3")
            try:
                for i in range(6):
                    db.record_model_install(
                        conn, model_id=f"m{i}", manifest_sha256=f"{i:064x}",
                        engine="llama.cpp", source="test", files=[{
                            "role": "weights", "name": "w", "path": f"m{i}/w",
                            "size": 1, "sha256": "0" * 64}])
                errors = []

                def read():
                    for _ in range(200):
                        try:
                            rows = db.model_installs(conn)
                            if [r["model_id"] for r in rows] != [f"m{i}" for i in range(6)]:
                                errors.append(len(rows))
                        except Exception as exc:          # noqa: BLE001
                            errors.append(repr(exc))

                threads = [threading.Thread(target=read) for _ in range(8)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
                self.assertEqual(errors, [])
            finally:
                conn.close()


class _FakeResponse:
    def __init__(self, status, body=b"", headers=None):
        self.status, self._body, self.headers = status, body, headers or {}

    def read(self, _amount=None, decode_content=True):
        return self._body

    def release_conn(self):
        pass


class _FakePool:
    def __init__(self, routes):
        self.routes, self.asked = routes, []

    def request(self, method, url, **_kwargs):
        self.asked.append(url)
        return self.routes[url.split("?", 1)[0]]


REVISION = "a" * 40
REPO_INFO = {
    "sha": REVISION, "gated": False, "private": False, "tags": ["code"],
    "cardData": {"license": "apache-2.0", "base_model": "Publisher/Base"},
    "gguf": {"architecture": "qwen3", "context_length": 32768, "total": 1_700_000_000},
    "siblings": [
        {"rfilename": "m-00001-of-00002.gguf", "size": 10, "lfs": {"sha256": "1" * 64}},
        {"rfilename": "m-00002-of-00002.gguf", "size": 5, "lfs": {"sha256": "2" * 64}},
        {"rfilename": "single.gguf", "size": 7, "lfs": {"sha256": "3" * 64}},
        {"rfilename": "mmproj-f16.gguf", "size": 3, "lfs": {"sha256": "4" * 64}},
        {"rfilename": "README.md", "size": 1}]}


class TestHub(unittest.TestCase):
    def pool(self, info=REPO_INFO):
        body = json.dumps(info).encode()
        base = "https://huggingface.co/api/models/Quant/Model-GGUF"
        return _FakePool({base: _FakeResponse(200, body),
                          f"{base}/revision/{REVISION}": _FakeResponse(200, body)})

    def test_a_choice_is_pinned_to_a_commit_with_every_file_hashed(self):
        # Two models and an unnamed projector here: pairing is the person's choice.
        entry = hub.resolve("Quant/Model-GGUF", "m-00001-of-00002.gguf", REVISION,
                            projector="mmproj-f16.gguf", projector_confirmed=True,
                            pool=self.pool())
        self.assertEqual([f.role for f in entry.files],
                         ["weights", "weights-part", "projector"])
        self.assertTrue(all(REVISION in f.url for f in entry.files))
        self.assertEqual((entry.quantizer, entry.base_model), ("Quant", "Publisher/Base"))
        # Only what the repository publishes: its "code" tag. Nothing assumes
        # "general", and a chosen projector is a capability, not a strength.
        self.assertEqual(entry.hints, ())
        self.assertEqual(entry.repo_tags, ("code",))
        self.assertEqual(models.task_evidence(entry)["strengths"], ("code",))

    def test_a_gated_repository_is_explained_not_fetched(self):
        with self.assertRaises(hub.HubError) as caught:
            hub.resolve("Quant/Model-GGUF", "single.gguf", REVISION,
                        pool=self.pool({**REPO_INFO, "gated": "manual"}))
        self.assertEqual(caught.exception.code, "gated")

    def test_an_incomplete_split_set_is_refused(self):
        info = {**REPO_INFO, "siblings": REPO_INFO["siblings"][:1]}
        with self.assertRaises(hub.HubError) as caught:
            hub.resolve("Quant/Model-GGUF", "m-00001-of-00002.gguf", REVISION,
                        pool=self.pool(info))
        self.assertEqual(caught.exception.code, "incomplete")

    def test_a_redirect_off_the_hub_is_refused(self):
        pool = _FakePool({"https://huggingface.co/api/models": _FakeResponse(
            302, headers={"Location": "https://elsewhere.example/api"})})
        with self.assertRaises(hub.HubError) as caught:
            hub.search("qwen", pool=pool)
        self.assertEqual(caught.exception.code, "unsafe_source")

    def test_the_repository_listing_groups_split_parts(self):
        listing = hub.repository("Quant/Model-GGUF", pool=self.pool())
        files = {choice["file"]: choice for choice in listing["choices"]}
        self.assertEqual(files["m-00001-of-00002.gguf"]["size"], 15)
        self.assertEqual(listing["projectors"][0]["file"], "mmproj-f16.gguf")

    def sibling_info(self, *names):
        return {**REPO_INFO, "siblings": [
            {"rfilename": name, "size": index + 1, "lfs": {"sha256": f"{index:064x}"}}
            for index, name in enumerate(names)]}

    def test_each_file_gets_the_projectors_of_its_own_model(self):
        """Review finding: every weight file was given the repository's first
        projector, whatever model it belonged to."""
        info = self.sibling_info(
            "gemma-3-4b-it-Q4_K_M.gguf", "gemma-3-12b-it-Q4_K_M.gguf",
            "mmproj-gemma-3-12b-it-f16.gguf", "mmproj-gemma-3-4b-it-f16.gguf")
        files = {c["file"]: c for c in
                 hub.repository("Quant/Model-GGUF", pool=self.pool(info))["choices"]}
        self.assertEqual([p["file"] for p in files["gemma-3-4b-it-Q4_K_M.gguf"]["projectors"]],
                         ["mmproj-gemma-3-4b-it-f16.gguf"])
        self.assertEqual([p["file"] for p in files["gemma-3-12b-it-Q4_K_M.gguf"]["projectors"]],
                         ["mmproj-gemma-3-12b-it-f16.gguf"])
        with self.assertRaises(hub.HubError) as caught:
            hub.resolve("Quant/Model-GGUF", "gemma-3-4b-it-Q4_K_M.gguf", REVISION,
                        projector="mmproj-gemma-3-12b-it-f16.gguf", pool=self.pool(info))
        self.assertEqual(caught.exception.code, "projector_mismatch")
        entry = hub.resolve("Quant/Model-GGUF", "gemma-3-4b-it-Q4_K_M.gguf", REVISION,
                            projector="mmproj-gemma-3-4b-it-f16.gguf", pool=self.pool(info))
        self.assertIn("projector", [f.role for f in entry.files])

    def test_a_related_name_is_a_choice_not_a_pairing(self):
        """Review finding: `Model-A-v2` was paired with `mmproj-Model-A` by a
        name prefix, and resolve accepted it."""
        info = self.sibling_info("Model-A-v2-Q4_K_M.gguf", "mmproj-Model-A-f16.gguf")
        (choice,) = hub.repository("Quant/Model-GGUF", pool=self.pool(info))["choices"]
        self.assertEqual((choice["pairing"], [p["file"] for p in choice["projectors"]]),
                         ("ambiguous", ["mmproj-Model-A-f16.gguf"]))
        with self.assertRaises(hub.HubError) as caught:
            hub.resolve("Quant/Model-GGUF", "Model-A-v2-Q4_K_M.gguf", REVISION,
                        projector="mmproj-Model-A-f16.gguf", pool=self.pool(info))
        self.assertEqual(caught.exception.code, "projector_unconfirmed")
        entry = hub.resolve("Quant/Model-GGUF", "Model-A-v2-Q4_K_M.gguf", REVISION,
                            projector="mmproj-Model-A-f16.gguf", projector_confirmed=True,
                            pool=self.pool(info))
        self.assertIn("projector", [f.role for f in entry.files])
        text_only = hub.resolve("Quant/Model-GGUF", "Model-A-v2-Q4_K_M.gguf", REVISION,
                                pool=self.pool(info))
        self.assertNotIn("projector", [f.role for f in text_only.files])
        # An exact name still pairs without being asked.
        exact = self.sibling_info("Model-A-Q4_K_M.gguf", "mmproj-Model-A-f16.gguf")
        (choice,) = hub.repository("Quant/Model-GGUF", pool=self.pool(exact))["choices"]
        self.assertEqual(choice["pairing"], "named")

    def test_an_unnamed_projector_beside_several_models_is_ambiguous(self):
        info = self.sibling_info("model-a-Q4_K_M.gguf", "model-b-Q4_K_M.gguf",
                                 "mmproj-f16.gguf")
        choices = hub.repository("Quant/Model-GGUF", pool=self.pool(info))["choices"]
        self.assertEqual({c["pairing"] for c in choices}, {"ambiguous"})
        single = self.sibling_info("Qwen3.5-4B-Q4_K_M.gguf", "Qwen3.5-4B-Q8_0.gguf",
                                   "mmproj-F16.gguf", "mmproj-BF16.gguf")
        choices = hub.repository("Quant/Model-GGUF", pool=self.pool(single))["choices"]
        self.assertEqual({c["pairing"] for c in choices}, {"repository"})
        self.assertEqual(len(choices[0]["projectors"]), 2, "two precisions: a choice")

    def test_a_projector_is_never_offered_as_weights(self):
        info = self.sibling_info("Qwen2.5-VL-7B-Instruct-q4_k_m.gguf",
                                 "Qwen2.5-VL-7B-Instruct-mmproj-f16.gguf",
                                 "gpt-oss-20b-mxfp4.gguf")
        listing = hub.repository("Quant/Model-GGUF", pool=self.pool(info))
        files = {c["file"]: c for c in listing["choices"]}
        self.assertNotIn("Qwen2.5-VL-7B-Instruct-mmproj-f16.gguf", files)
        self.assertEqual(files["Qwen2.5-VL-7B-Instruct-q4_k_m.gguf"]["pairing"], "named")
        self.assertEqual((files["gpt-oss-20b-mxfp4.gguf"]["pairing"],
                          files["gpt-oss-20b-mxfp4.gguf"]["projectors"]), ("none", []))
        with self.assertRaises(hub.HubError) as caught:
            hub.resolve("Quant/Model-GGUF", "Qwen2.5-VL-7B-Instruct-mmproj-f16.gguf",
                        REVISION, pool=self.pool(info))
        self.assertEqual(caught.exception.code, "not_weights")


# --------------------------------------------------------------------------
# Evidence settings and the schema upgrade
# --------------------------------------------------------------------------

class TestCheckFingerprints(unittest.TestCase):
    def test_a_settings_change_makes_old_evidence_history(self):
        profile = admission.candidate(observation(capabilities=["completion", "vision"]),
                                      profiles.OCR)
        before = admission.check_fingerprint(profile, "documents.ocr",
                                             {"render_long_edge": 1600})
        after = admission.check_fingerprint(profile, "documents.ocr",
                                            {"render_long_edge": 2200})
        self.assertNotEqual(before, after)
        record = {"model": "k", "scope": "documents.ocr", "state": "passed",
                  "detail": "ok", "digest": "c" * 64, "runtime_version": "x",
                  "ran_at": "2026-10-06T00:00:00Z", "check_fingerprint": before}
        view = models.selftest_view([record], model="k", digest="c" * 64,
                                    fingerprints={"documents.ocr": after})
        self.assertFalse(view["documents.ocr"]["current"])
        self.assertTrue(view["documents.ocr"]["settings_changed"])
        same = models.selftest_view([record], model="k", digest="c" * 64,
                                    fingerprints={"documents.ocr": before})
        self.assertTrue(same["documents.ocr"]["current"])

    def test_matches_now_is_computed_on_read_for_failures_too(self):
        """A stored failure is evidence only while it describes what is
        installed now; replacing the bytes or changing the check makes it
        history at once, with nothing written."""
        record = {"model": "k", "scope": "chat", "state": "failed", "detail": "no",
                  "digest": "c" * 64, "runtime_version": "x",
                  "ran_at": "2026-10-07T00:00:00Z", "check_fingerprint": "f" * 64,
                  "failure_kind": "missing_label", "reply_excerpt": "unsafe; 2.4"}
        now = models.selftest_view([record], model="k", digest="c" * 64,
                                   fingerprints={"chat": "f" * 64})["chat"]
        self.assertTrue(now["matches_now"])
        self.assertFalse(now["current"], "only a pass is current")
        self.assertEqual(now["reply_excerpt"], "unsafe; 2.4")
        replaced = models.selftest_view([record], model="k", digest="d" * 64,
                                        fingerprints={"chat": "f" * 64})["chat"]
        self.assertFalse(replaced["matches_now"])
        changed = models.selftest_view([record], model="k", digest="c" * 64,
                                       fingerprints={"chat": "e" * 64})["chat"]
        self.assertFalse(changed["matches_now"])
        self.assertNotIn("matches_now", db.selftests.__doc__ or "")

    def test_a_result_without_recorded_settings_is_never_current(self):
        record = {"model": "k", "scope": "chat", "state": "passed", "detail": "ok",
                  "digest": "c" * 64, "runtime_version": "x",
                  "ran_at": "2026-10-06T00:00:00Z", "check_fingerprint": None}
        view = models.selftest_view([record], model="k", digest="c" * 64,
                                    fingerprints={"chat": "f" * 64})
        self.assertFalse(view["chat"]["current"])


class TestSchemaFourteen(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.path = Path(self.scratch.name) / "state.sqlite3"

    def make_v13(self):
        conn = db.connect(self.path)
        db.record_selftest(conn, model="qwen", scope="chat", state="passed",
                           detail="ok", digest="c" * 64, runtime_version="0.34.2")
        conn.execute("ALTER TABLE model_selftests DROP COLUMN check_fingerprint")
        conn.execute("UPDATE meta SET value='13' WHERE key='schema_version'")
        conn.execute("PRAGMA user_version = 13")
        conn.commit()
        conn.close()

    def test_an_upgrade_adds_the_column_and_keeps_every_result(self):
        self.make_v13()
        conn = db.connect(self.path)
        self.addCleanup(conn.close)
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(model_selftests)")}
        self.assertIn("check_fingerprint", columns)
        self.assertTrue({"failure_kind", "reply_excerpt"} <= columns)
        rows = db.selftests(conn)
        self.assertEqual((rows[0]["state"], rows[0]["check_fingerprint"],
                          rows[0]["failure_kind"], rows[0]["reply_excerpt"]),
                         ("passed", None, None, None))
        self.assertEqual(conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'").fetchone()[0],
            str(db.SCHEMA_VERSION))

    def test_a_schema_14_store_gains_the_diagnostic_columns(self):
        conn = db.connect(self.path)
        db.record_selftest(conn, model="qwen", scope="chat", state="failed",
                           detail="old", digest="c" * 64, runtime_version="0.35.1",
                           check_fingerprint="f" * 64)
        conn.execute("ALTER TABLE model_selftests DROP COLUMN failure_kind")
        conn.execute("ALTER TABLE model_selftests DROP COLUMN reply_excerpt")
        conn.execute("UPDATE meta SET value='14' WHERE key='schema_version'")
        conn.execute("PRAGMA user_version = 14")
        conn.commit()
        conn.close()
        conn = db.connect(self.path)
        self.addCleanup(conn.close)
        (row,) = db.selftests(conn)
        self.assertEqual((row["state"], row["check_fingerprint"], row["failure_kind"]),
                         ("failed", "f" * 64, None))
        view = models.selftest_view([row], model="qwen", digest="c" * 64,
                                    fingerprints={"chat": "f" * 64})["chat"]
        self.assertTrue(view["matches_now"])
        self.assertIsNone(view["failure_kind"])

    def test_an_interrupted_upgrade_completes_on_the_next_open(self):
        self.make_v13()
        raw = sqlite3.connect(self.path)
        raw.execute("ALTER TABLE model_selftests ADD COLUMN check_fingerprint TEXT")
        raw.commit()
        raw.close()
        conn = db.connect(self.path)
        self.addCleanup(conn.close)
        self.assertEqual(len(db.selftests(conn)), 1)

    def test_an_older_binary_refuses_the_upgraded_store(self):
        db.connect(self.path).close()
        with patch.object(db, "SCHEMA_VERSION", 13):
            with self.assertRaises(db.AdmissionRefused) as caught:
                db.admit(self.path)
        self.assertEqual(caught.exception.code, "schema_newer")


# --------------------------------------------------------------------------
# Recommendations
# --------------------------------------------------------------------------

class TestRecommendations(unittest.TestCase):
    FACTS = {"os_family": "macos", "architecture": "arm64",
             "memory_total_bytes": 16 * GIB, "memory_available_bytes": 9 * GIB}

    def test_categories_start_small_and_never_become_an_allowlist(self):
        offered = [e for e in models.CATALOGUE if e.engine == "llama.cpp" and e.files]
        result = capacity.categories(offered, [], capacity.pool(self.FACTS),
                                     free_disk=500 * GIB)
        rows = {}
        for category in result:
            self.assertLessEqual(len(category["initial"]), capacity.PER_CATEGORY)
            for row in category["initial"] + category["more"]:
                rows[row["id"]] = row
        self.assertEqual(set(rows), {e.id for e in offered}, "every model can be chosen")
        self.assertEqual(rows["gpt-oss-120b-mxfp4"]["fit"], capacity.TOO_LARGE)
        self.assertEqual(rows["qwen3-1.7b-q8_0"]["fit"], capacity.GOOD)
        self.assertTrue(all("estimated" in row["fit_label"] or row["fit"] == "unknown"
                            for row in rows.values()))
        reasoning = next(c for c in result if c["id"] == "reasoning")
        self.assertNotIn("gpt-oss-120b-mxfp4", [r["id"] for r in reasoning["initial"]],
                         "a model too large here is offered under Show more, with a warning")

    def test_the_disk_check_counts_downloads_already_chosen(self):
        offered = [models.entry_for("qwen3-1.7b-q8_0")]
        free = offered[0].storage_bytes + 2 * GIB
        alone = capacity.categories(offered, [], capacity.pool(self.FACTS), free_disk=free)
        busy = capacity.categories(offered, [], capacity.pool(self.FACTS), free_disk=free,
                                   pending_bytes=2 * GIB)
        first = lambda result: next(r for c in result for r in c["initial"] + c["more"])
        self.assertFalse(first(alone)["disk_short"])
        self.assertTrue(first(busy)["disk_short"])

    def test_unified_discrete_and_cpu_memory_are_told_apart(self):
        self.assertEqual(capacity.pool(self.FACTS)["kind"], capacity.UNIFIED)
        gpu = {"os_family": "windows", "architecture": "x86_64",
               "memory_total_bytes": 16 * GIB,
               "engine_devices": [{"id": "Vulkan0", "memory_mib": 4096}]}
        self.assertEqual(capacity.pool(gpu)["kind"], capacity.DISCRETE)
        self.assertEqual(capacity.pool(gpu)["capacity_bytes"], 20 * GIB)
        cpu = {"os_family": "linux", "architecture": "x86_64",
               "memory_total_bytes": 8 * GIB}
        self.assertEqual(capacity.pool(cpu)["kind"], capacity.CPU)


if __name__ == "__main__":
    unittest.main(verbosity=2)
