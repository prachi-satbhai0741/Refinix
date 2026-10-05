"""Typed readiness: each problem gets its own code, words and fix.

The bad state these tests start from is the reported one: after an external
Ollama upgrade the engine answers, the model is installed and enabled, and no
qualified profile matches the new version. The old ready line said "The selected
model is unavailable for new work" for that and for several other causes.
"""

from __future__ import annotations

import unittest

from backend.coordinator import readiness

ROW = {"digests": {"local": "a" * 64}, "integrity": {"local": {"state": "verified"}},
       "enabled": True}


def assess(**overrides):
    values = dict(runtime_state={"reachable": True, "models": ["m"],
                                 "server_version": "0.34.4"},
                  engine={"mode": "developer"}, chat_row=dict(ROW), model_id="m",
                  chat_profile_found=True, device_tier="tier", managed=False)
    values.update(overrides)
    return readiness.assess(**values)


class TestCodes(unittest.TestCase):
    def test_an_external_runtime_upgrade_is_named_not_called_unavailable(self):
        result = assess(chat_profile_found=False)
        self.assertEqual(result["code"], "no_qualified_profile")
        self.assertIn("Ollama 0.34.4", result["message"])
        self.assertNotIn("unavailable for new work", result["message"])
        self.assertEqual(result["action"]["kind"], "open_settings")

    def test_ready_is_ready(self):
        self.assertEqual(assess()["code"], readiness.READY)

    def test_a_silent_developer_engine_says_so(self):
        result = assess(runtime_state={"reachable": False})
        self.assertEqual(result["code"], "engine_not_running")

    def test_a_missing_managed_engine_needs_a_reinstall_not_a_download(self):
        result = assess(managed=True, engine={"problems": ["not part of this installation"]})
        self.assertEqual(result["code"], "engine_missing")
        self.assertEqual(result["action"]["kind"], "reinstall")

    def test_a_modified_managed_engine_is_a_failure(self):
        result = assess(managed=True, engine={"release": "b11390",
                                              "problems": ["llama-server does not match"]})
        self.assertEqual((result["code"], result["state"]), ("engine_unverified", "failed"))

    def test_an_engine_that_could_not_start_offers_a_retry(self):
        result = assess(managed=True, engine={"release": "b11390", "problems": [],
                                              "error_code": "engine_failed",
                                              "error": "stopped while loading"})
        self.assertEqual(result["code"], "engine_failed")
        self.assertEqual(result["action"]["kind"], "retry")

    def test_no_installed_model_is_setup_not_an_error(self):
        result = assess(managed=True, engine={"release": "b11390", "problems": []},
                        runtime_state={"reachable": True, "models": []})
        self.assertEqual((result["code"], result["state"]),
                         ("setup_incomplete", "attention"))

    def test_a_missing_selected_model(self):
        result = assess(chat_row=None)
        self.assertEqual(result["code"], "model_not_installed")

    def test_wrong_bytes_are_a_failure(self):
        row = dict(ROW, integrity={"local": {"state": "mismatch"}})
        self.assertEqual(assess(chat_row=row)["code"], "model_integrity_mismatch")

    def test_changed_files_are_named_although_no_digest_is_published(self):
        row = dict(ROW, digests={"local": None},
                   integrity={"local": {"state": "mismatch",
                                        "detail": "main.gguf is 5 bytes; the installed "
                                                  "file was 4"}})
        result = assess(managed=True, engine={"release": "b11390", "problems": []},
                        chat_row=row)
        self.assertEqual(result["code"], "model_integrity_mismatch")
        self.assertIn("main.gguf is 5 bytes", result["detail"])

    def test_an_engine_that_would_not_stop_blocks_with_its_own_code(self):
        result = assess(managed=True, engine={
            "release": "b11390", "problems": [], "error_code": "engine_stop_blocked",
            "error": "The Refinix engine (process 42) did not stop when asked."})
        self.assertEqual((result["code"], result["state"]),
                         ("engine_stop_blocked", "failed"))
        self.assertIn("process 42", result["detail"])

    def test_a_switched_off_model(self):
        self.assertEqual(assess(chat_row=dict(ROW, enabled=False))["code"],
                         "model_disabled")

    def test_an_unmatched_computer_under_the_managed_engine(self):
        result = assess(managed=True, engine={"release": "b11390", "problems": []},
                        device_tier=None)
        self.assertEqual(result["code"], "device_unsupported")

    def test_no_managed_action_is_a_terminal_command(self):
        for result in (assess(managed=True, engine={"problems": ["x"]}),
                       assess(managed=True, engine={"release": "b", "problems": []},
                              runtime_state={"reachable": True, "models": []}),
                       assess(chat_profile_found=False)):
            self.assertNotIn("command", result["action"] or {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
