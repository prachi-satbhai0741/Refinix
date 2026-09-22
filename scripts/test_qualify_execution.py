"""Offline checks for the qualification runner's fail-closed boundaries."""

import unittest

from backend.contracts import profiles, v1
from scripts import qualify_execution


class QualificationRunnerChecks(unittest.TestCase):
    def setUp(self):
        self.model = v1.ModelRef(**profiles.model_ref("0.33.3"))
        self.outputs = {
            profiles.CHAT: 2048,
            profiles.CODE: 2048,
            profiles.DOCUMENTS: 3072,
        }
        self.maxima = dict(self.outputs)

    def test_registered_profile_must_match_default_and_maximum(self):
        self.outputs[profiles.CODE] = 1024
        with self.assertRaisesRegex(RuntimeError, "no exact registered code"):
            qualify_execution._profiles(
                self.model, profiles.MAC_M5_16GB, 8192, self.outputs, False,
                self.maxima)

    def test_candidate_keeps_default_separate_from_maximum(self):
        self.outputs[profiles.CODE] = 1024
        selected, transient = qualify_execution._profiles(
            self.model, profiles.MAC_M5_16GB, 8192, self.outputs, True,
            self.maxima)
        code = next(item for item in selected
                    if item.workflow_mode == profiles.CODE)
        self.assertTrue(transient)
        self.assertEqual(code.default_output_tokens, 1024)
        self.assertEqual(code.max_output_tokens, 2048)

    def test_representative_workload_refuses_host_execution(self):
        with self.assertRaisesRegex(RuntimeError, "host execution.*refused"):
            qualify_execution._representative_checks("int main(void) { return 0; }")

    def test_a_larger_code_maximum_requires_the_representative_workload(self):
        with self.assertRaisesRegex(RuntimeError, "new or larger Code profile"):
            qualify_execution._require_representative_code(
                2048, 4096, False, False, None)
        with self.assertRaisesRegex(RuntimeError, "new or larger Code profile"):
            qualify_execution._require_representative_code(
                4096, 4096, True, False, None)
        with self.assertRaisesRegex(RuntimeError, "sandbox validator"):
            qualify_execution._require_representative_code(
                2048, 4096, False, True, None)
        qualify_execution._require_representative_code(
            2048, 4096, False, True, lambda _source: {})

    def test_representative_proof_is_bound_to_source_and_sandbox(self):
        source = "int main(void) { return 0; }"

        def passed(value):
            return {
                "workload_id": qualify_execution.REPRESENTATIVE_CODE_WORKLOAD_ID,
                "source_sha256": qualify_execution._sha(value),
                "compiler": ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror"],
                "sandboxed": True,
                "network": "disabled",
                "compiled": True,
                "behavior_passed": True,
            }

        self.assertEqual(
            qualify_execution._representative_checks(source, passed),
            ["representative.compile", "representative.behavior"])
        with self.assertRaisesRegex(RuntimeError, "did not pass"):
            qualify_execution._representative_checks(
                source, lambda _value: {**passed(source), "network": "enabled"})
        with self.assertRaisesRegex(RuntimeError, "did not pass"):
            qualify_execution._representative_checks(
                source, lambda _value: {**passed(source), "compiler": ["cc"]})


if __name__ == "__main__":
    unittest.main()
