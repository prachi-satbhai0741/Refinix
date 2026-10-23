"""Offline checks for the evidence-only qualification artifact."""

from copy import deepcopy
import tempfile
import unittest
from pathlib import Path

from . import profiles, qualification, v1


CURRENT = {
    item.workflow_mode: item for item in profiles.PROFILES
    if item.target_profile_id == profiles.MAC_M5_16GB
    and item.model.runtime_version == "0.33.3"
}


def candidate(profile):
    return v1.ExecutionProfile.model_validate({
        **profile.model_dump(),
        "qualification_state": "candidate",
        "eligible": False,
        "evidence_kind": "unverified",
        "evidence_ref": "qualification-run:pending-review",
    })


def run(profile, reasoning):
    workflow_checks = {
        profiles.CHAT: ["answer.nonempty"],
        profiles.CODE: ["structured.decoder", "proposal.schema",
                        "canonical.unchanged"],
        profiles.DOCUMENTS: ["structured.decoder", "document.schema",
                             "document.readable", "document.required_facts",
                             "source.fenced"],
    }
    return qualification.RunEvidence(
        reasoning=reasoning, decoder=profile.decoder_modes[0],
        requested_profile_id=profile.profile_id,
        actual_profile_id=profile.profile_id,
        context_window_tokens=profile.qualified_context_tokens,
        output_allowance_tokens=profile.max_output_tokens,
        done_reason="stop", prompt_tokens=10, output_tokens=3, total_ms=20,
        output_sha256="a" * 64,
        thinking_observed=reasoning == "enabled",
        verifications=[
            "runtime.identity", "profile.identity", "workflow.completed",
            "reasoning.separated" if reasoning == "enabled" else "reasoning.disabled",
            *workflow_checks[profile.workflow_mode],
        ])


def artifact():
    workflows = []
    for registered in CURRENT.values():
        profile = candidate(registered)
        workflows.append(qualification.WorkflowQualification(
            profile=profile, result="passed",
            evidence=[run(profile, mode) for mode in profile.reasoning_modes]))
    return qualification.QualificationArtifact(
        artifact_version=qualification.ARTIFACT_VERSION,
        generated_at="2026-09-21T12:00:00Z",
        device=qualification.DeviceObservation(
            os_family="macos", os_release="25.6.0", architecture="arm64",
            target_profile_id=profiles.MAC_M5_16GB),
        observed_model=next(iter(CURRENT.values())).model,
        result="passed", release_accepted=False, workflows=workflows)


class QualificationArtifactChecks(unittest.TestCase):
    def test_current_mac_profiles_round_trip_without_granting_authority(self):
        record = artifact()
        parsed = qualification.loads(record.model_dump_json())
        self.assertEqual(
            {item.profile.profile_id for item in parsed.workflows},
            {item.profile_id for item in CURRENT.values()})
        self.assertEqual(
            {item.profile.workflow_mode: (
                item.profile.qualified_context_tokens,
                item.profile.max_output_tokens) for item in parsed.workflows},
            {profiles.CHAT: (8192, 2048), profiles.CODE: (8192, 2048),
             profiles.DOCUMENTS: (8192, 3072)})
        self.assertTrue(all(not item.profile.eligible for item in parsed.workflows))
        self.assertTrue(all(not profiles.compatible(
            item.profile, model_id=item.profile.model.model_id,
            workflow=item.profile.workflow_mode, reasoning="disabled",
            decoder=item.profile.decoder_modes[0]) for item in parsed.workflows))

    def test_runtime_version_drift_is_refused(self):
        payload = artifact().model_dump()
        payload["observed_model"]["runtime_version"] = "0.33.4"
        with self.assertRaisesRegex(ValueError, "differs from the observation"):
            qualification.QualificationArtifact.model_validate(payload)

    def test_missing_workflow_evidence_is_refused(self):
        payload = artifact().model_dump()
        code = next(item for item in payload["workflows"]
                    if item["profile"]["workflow_mode"] == profiles.CODE)
        code["evidence"][0]["verifications"].remove("canonical.unchanged")
        with self.assertRaisesRegex(ValueError, "workflow-specific"):
            qualification.QualificationArtifact.model_validate(payload)

    def test_a_larger_code_maximum_requires_representative_proof(self):
        values = candidate(CURRENT[profiles.CODE]).model_dump(exclude={"profile_id"})
        values["max_output_tokens"] = 4096
        profile = v1.ExecutionProfile(
            profile_id=v1.execution_profile_id(values), **values)
        evidence = [run(profile, mode) for mode in profile.reasoning_modes]
        with self.assertRaisesRegex(ValueError, "workflow-specific"):
            qualification.WorkflowQualification(
                profile=profile, result="passed", evidence=evidence)
        for item in evidence:
            item.verifications.extend(
                ["representative.compile", "representative.behavior"])
        self.assertEqual(
            qualification.WorkflowQualification(
                profile=profile, result="passed", evidence=evidence).result,
            "passed")

    def test_incomplete_reasoning_coverage_is_refused(self):
        payload = artifact().model_dump()
        payload["workflows"][0]["evidence"].pop()
        with self.assertRaisesRegex(ValueError, "combination"):
            qualification.QualificationArtifact.model_validate(payload)

    def test_malformed_or_extra_data_is_refused(self):
        for change in ("missing", "extra"):
            with self.subTest(change=change):
                payload = artifact().model_dump()
                if change == "missing":
                    del payload["device"]["os_release"]
                else:
                    payload["trusted"] = True
                with self.assertRaises(ValueError):
                    qualification.QualificationArtifact.model_validate(payload)

    def test_writer_round_trips_and_never_overwrites_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qualification.json"
            qualification.write(path, artifact())
            self.assertEqual(qualification.read(path), artifact())
            with self.assertRaises(FileExistsError):
                qualification.write(path, artifact())


if __name__ == "__main__":
    unittest.main()
