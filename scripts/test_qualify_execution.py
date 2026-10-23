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

    def test_candidate_can_omit_code_when_no_sandbox_validator_exists(self):
        model = v1.ModelRef(**profiles.model_ref("0.34.2"))
        selected, transient = qualify_execution._profiles(
            model, profiles.MAC_M5_16GB, 8192, self.outputs, True,
            self.maxima,
            ((profiles.CHAT, "text"),
             (profiles.DOCUMENTS, "json_schema")))
        self.assertTrue(transient)
        self.assertEqual(
            [item.workflow_mode for item in selected],
            [profiles.CHAT, profiles.DOCUMENTS])

    def test_a_workflow_can_claim_only_the_reasoning_mode_it_passed(self):
        selected, _transient = qualify_execution._profiles(
            self.model, profiles.MAC_M5_16GB, 8192, self.outputs, True,
            self.maxima, qualify_execution.WORKFLOWS,
            {profiles.DOCUMENTS: ("disabled",)})
        by_workflow = {item.workflow_mode: item for item in selected}
        self.assertEqual(by_workflow[profiles.DOCUMENTS].reasoning_modes, ["disabled"])
        self.assertEqual(by_workflow[profiles.DOCUMENTS].default_reasoning, "disabled")
        self.assertEqual(by_workflow[profiles.CHAT].reasoning_modes,
                         ["disabled", "enabled"])

    def test_a_registered_profile_with_both_modes_does_not_cover_a_narrower_claim(self):
        registered = next(item for item in profiles.PROFILES
                          if item.workflow_mode == profiles.DOCUMENTS)
        model = registered.model
        outputs = dict(self.outputs, **{profiles.DOCUMENTS: registered.default_output_tokens})
        maxima = dict(self.maxima, **{profiles.DOCUMENTS: registered.max_output_tokens})
        with self.assertRaisesRegex(RuntimeError, "no exact registered"):
            qualify_execution._profiles(
                model, registered.target_profile_id,
                registered.qualified_context_tokens, outputs, False, maxima,
                ((profiles.DOCUMENTS, "json_schema"),),
                {profiles.DOCUMENTS: ("disabled",)})

    def test_representative_workload_refuses_host_execution(self):
        with self.assertRaisesRegex(RuntimeError, "host execution.*refused"):
            qualify_execution._representative_checks("int main(void) { return 0; }")

    def test_a_larger_code_maximum_requires_the_representative_workload(self):
        with self.assertRaisesRegex(RuntimeError, "new Code profile"):
            qualify_execution._require_representative_code(
                2048, 4096, False, False, None)
        with self.assertRaisesRegex(RuntimeError, "new Code profile"):
            qualify_execution._require_representative_code(
                4096, 4096, True, False, None)
        with self.assertRaisesRegex(RuntimeError, "sandbox validator"):
            qualify_execution._require_representative_code(
                2048, 4096, False, True, None)
        qualify_execution._require_representative_code(
            2048, 4096, False, True, lambda _source: {})

    def test_proposal_only_admits_a_candidate_without_widening_it(self):
        qualify_execution._require_representative_code(
            2048, 2048, True, False, None, proposal_only=True)
        with self.assertRaisesRegex(RuntimeError, "cannot claim a larger maximum"):
            qualify_execution._require_representative_code(
                2048, 4096, True, False, None, proposal_only=True)

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
