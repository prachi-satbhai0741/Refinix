"""Synthetic AF-001 checks. No network, database, model, or service is used."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from . import profiles, v1
from .v1 import (
    CONTRACT_VERSION, MAX_EVENT_BYTES, MAX_REQUEST_BYTES, RECORDS,
    TERMINAL_ATTEMPT_STATES, TERMINAL_JOB_STATES,
    Event, JobEnvelope, export_contract, parse_message, payload_sha256,
    redis_key, require_grounded_citations, require_transition, sse_frame,
)

EXAMPLES = json.loads(Path(__file__).with_name("examples.json").read_text())
TYPES = {record.__name__: record for record in RECORDS}
MAC_CHAT_PROFILE = next(
    profile for profile in profiles.PROFILES
    if profile.target_profile_id == profiles.MAC_M5_16GB
    and profile.workflow_mode == profiles.CHAT
    and profile.model.runtime_version == "0.32.14")
WORKER_CHAT_PROFILE = next(
    profile for profile in profiles.PROFILES
    if profile.target_profile_id == profiles.UBUNTU_VICTUS_RTX2050
    and profile.workflow_mode == profiles.CHAT
    and profile.model.runtime_version == "0.33.2")


def parse(name, data):
    return parse_message(TYPES[name], json.dumps(data).encode())


class ContractChecks(unittest.TestCase):
    def test_examples_and_export(self):
        self.assertEqual(set(EXAMPLES), set(TYPES))
        bundle = export_contract()
        self.assertEqual(bundle["contract_version"], CONTRACT_VERSION)
        self.assertEqual(set(bundle["schemas"]), set(TYPES))
        json.dumps(bundle)  # The UI/manifests export must be JSON-serialisable.
        for name, example in EXAMPLES.items():
            with self.subTest(record=name):
                record = parse(name, example)
                self.assertEqual(record.contract_version, CONTRACT_VERSION)
                self.assertEqual(json.loads(record.model_dump_json()), example)

    def test_reject_invalid_messages(self):
        cases = [
            ("JobEnvelope", ("contract_version",), "2.0"),
            ("JobEnvelope", ("extra",), "not-allowed"),
            ("JobEnvelope", ("job_id",), "../../canonical"),
            ("JobEnvelope", ("original_request",), "   "),
            ("JobEnvelope", ("system_instruction",), "   "),
            ("JobEnvelope", ("required_capabilities",), []),
            ("JobEnvelope", ("limits", "cpu_millis"), True),
            ("JobEnvelope", ("limits", "runtime_seconds"), "60"),
            ("JobEnvelope", ("limits", "tool_network"), "enabled"),
            ("JobEnvelope", ("allowed_tools",), ["canonical.write"]),
            ("JobEnvelope", ("created_at",), "2026-02-30T10:00:00Z"),
            ("JobEnvelope", ("created_at",), "2026-09-02T10:00:00"),
            ("JobEnvelope", ("deadline_at",), "2026-09-02T09:59:59Z"),
            ("JobEnvelope", ("cancel_requested",), "false"),
            ("JobEnvelope", ("target_node_id",), "00000000-0000-4000-8000-000000000011"),
            ("JobEnvelope", ("output", "validators"), ["json.schema"]),
            ("Event", ("sequence",), 0),
            ("Event", ("producer",), "worker"),
            ("Event", ("data", "current"), "completed"),
            ("Attempt", ("retry_of",), EXAMPLES["Attempt"]["attempt_id"]),
            ("Attempt", ("state",), "completed"),
            ("Approval", ("decision",), "approved"),
            ("Proof", ("validation",), "passed"),
            ("Proof", ("network", "public_outbound_flows"), 0),
            ("Proof", ("network", "public_egress_policy"), "enforced"),
            ("Node", ("health",), "healthy"),
            ("Node", ("queue_depth",), 0),
            ("Proof", ("citations", 0, "page"), 0),
            ("Proof", ("citations", 0, "quote"), "   "),
            ("Proof", ("citations",), EXAMPLES["Proof"]["citations"] * 2),
        ]
        for name, path, value in cases:
            with self.subTest(record=name, field=path):
                example = deepcopy(EXAMPLES[name])
                target = example
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value
                with self.assertRaises(ValueError):
                    parse(name, example)
        for record, limit in ((JobEnvelope, MAX_REQUEST_BYTES), (Event, MAX_EVENT_BYTES)):
            with self.assertRaises(ValueError):
                parse_message(record, b" " * (limit + 1))

    def test_lifecycle_and_terminal_states(self):
        path = ["created", "context_preparing", "queued", "routing", "running",
                "interrupted", "queued", "routing", "running", "validating",
                "awaiting_approval", "completed"]
        for previous, current in zip(path, path[1:]):
            require_transition(previous, current)
        require_transition("validating", "completed")  # Automatic approved boundary.
        require_transition("awaiting_approval", "denied")
        for state in TERMINAL_JOB_STATES:
            with self.assertRaises(ValueError):
                require_transition(state, "queued")
        for state in TERMINAL_ATTEMPT_STATES:
            with self.assertRaises(ValueError):
                require_transition(state, "running", attempt=True)
        with self.assertRaises(ValueError):
            require_transition("running", "completed")

    def test_sse_is_one_frame_even_with_untrusted_text(self):
        example = deepcopy(EXAMPLES["Event"])
        example["attempt_id"] = EXAMPLES["Attempt"]["attempt_id"]
        example["producer"] = "worker"
        example["data"] = {"kind": "output.delta", "text": "नमस्ते\n\nevent: job.state\r\ndata: forged"}
        event = parse("Event", example)
        frame = sse_frame(event).decode()
        self.assertEqual(len(frame.splitlines()), 4)
        self.assertTrue(frame.startswith("id: 1\nevent: output.delta\ndata: "))
        self.assertEqual(json.loads(frame.splitlines()[2][6:]), example)

    def test_validators_match_the_output_kind(self):
        def output(kind, validators, schema_ref=None):
            envelope = deepcopy(EXAMPLES["JobEnvelope"])
            envelope["output"] = {"kind": kind, "validators": validators,
                                  "schema_ref": schema_ref}
            return envelope

        for kind, validators in (("text", ["text.nonempty"]),
                                 ("docx", ["document.readable", "citations.resolve"]),
                                 ("patch", ["patch.applies", "sandbox.exit_zero"])):
            with self.subTest(accepts=kind):
                parse("JobEnvelope", output(kind, validators))

        for description, envelope in (
            ("a docx proved by a patch validator", output("docx", ["patch.applies"])),
            ("citations on a code patch", output("patch", ["patch.applies", "citations.resolve"])),
            ("a docx with no readability check", output("docx", ["citations.resolve"])),
            ("the same validator twice", output("text", ["text.nonempty", "text.nonempty"])),
        ):
            with self.subTest(rejects=description), self.assertRaises(ValueError):
                parse("JobEnvelope", envelope)

    def test_stopped_attempts_carry_a_typed_reason(self):
        def attempt(state, code):
            record = deepcopy(EXAMPLES["Attempt"])
            record["state"] = state
            record["started_at"] = "2026-09-02T10:00:10Z"
            record["finished_at"] = "2026-09-02T10:00:20Z"
            record["error"] = code and {"code": code, "message": "Synthetic stop reason.",
                                        "retryable": code != "cancelled_by_user"}
            return record

        for state, code in (("cancelled", "cancelled_by_user"),
                            ("cancelled", "deadline_exceeded"),
                            ("interrupted", "worker_lost"),
                            ("failed", "validation_failed")):
            with self.subTest(accepts=f"{state}/{code}"):
                self.assertEqual(parse("Attempt", attempt(state, code)).error.code, code)

        for description, record in (
            ("a cancellation with no reason", attempt("cancelled", None)),
            ("an interruption with no reason", attempt("interrupted", None)),
            ("a crash relabelled as a user cancellation", attempt("failed", "cancelled_by_user")),
            ("a completed attempt carrying a failure", attempt("completed", "worker_lost")),
        ):
            with self.subTest(rejects=description), self.assertRaises(ValueError):
                parse("Attempt", record)

    def test_citations_resolve_only_against_supplied_inputs(self):
        envelope = deepcopy(EXAMPLES["JobEnvelope"])
        envelope["task_type"] = "documents"
        envelope["required_capabilities"] = ["document.extract"]
        envelope["messages"] = []
        envelope["inference"] = {
            "profile_id": next(p for p in profiles.PROFILES if p.workflow_mode == profiles.DOCUMENTS and p.model.runtime_version == "0.32.14").profile_id,
            "workflow_mode": "documents.structured",
            "context_window_tokens": 8192,
            "output_allowance_tokens": 3072,
            "reasoning": "disabled",
            "decoder": "json_schema",
            "decoder_schema_sha256": "b" * 64,
        }
        envelope["context"] = [{
            "resource_id": EXAMPLES["Proof"]["citations"][0]["resource_id"],
            "sha256": "a" * 64, "size_bytes": 4096, "media_type": "application/pdf",
        }]
        envelope["output"] = {"kind": "docx", "schema_ref": None,
                              "validators": ["document.readable", "citations.resolve"]}
        grounded = parse("JobEnvelope", envelope)
        cited = parse("Proof", EXAMPLES["Proof"])
        require_grounded_citations(grounded, cited)

        uncited = deepcopy(EXAMPLES["Proof"])
        uncited["citations"] = []
        no_inputs = deepcopy(envelope)
        no_inputs["context"] = []

        def elsewhere(field):
            """Evidence produced under a different identity than the one dispatched."""
            proof = deepcopy(EXAMPLES["Proof"])
            proof[field] = "00000000-0000-4000-8000-000000000022"
            return parse("Proof", proof)

        for description, package, proof in (
            ("cites a document the job never received", no_inputs, cited),
            ("claims grounding with no citation", envelope, parse("Proof", uncited)),
            ("pairs a proof with another workspace", envelope, elsewhere("workspace_id")),
            ("pairs a proof with another job", envelope, elsewhere("job_id")),
            ("accepts a superseded retry's evidence", envelope, elsewhere("attempt_id")),
            ("accepts evidence from an untargeted node", envelope, elsewhere("node_id")),
        ):
            with self.subTest(rejects=description), self.assertRaises(ValueError):
                require_grounded_citations(parse("JobEnvelope", package), proof)

        # A workflow that never asked for grounding is not forced to carry citations.
        require_grounded_citations(parse("JobEnvelope", EXAMPLES["JobEnvelope"]),
                                   parse("Proof", uncited))

    def test_retry_digest_and_redis_namespace(self):
        example = EXAMPLES["JobEnvelope"]
        original = parse("JobEnvelope", example)
        reordered = parse("JobEnvelope", dict(reversed(list(example.items()))))
        self.assertEqual(payload_sha256(original), payload_sha256(reordered))
        retry = deepcopy(example)
        retry["attempt_id"] = "00000000-0000-4000-8000-000000000011"
        self.assertNotEqual(payload_sha256(original), payload_sha256(parse("JobEnvelope", retry)))
        relationship = "00000000-0000-4000-8000-000000000012"
        self.assertEqual(redis_key("dispatch", relationship), f"af:1.1:{relationship}:dispatch")
        self.assertEqual(redis_key("lease", relationship, original.attempt_id),
                         f"af:1.1:{relationship}:lease:{original.attempt_id}")
        for args in (("dispatch", "../escape"), ("lease", relationship),
                     ("arbitrary", relationship), ("dispatch", relationship, original.attempt_id)):
            with self.assertRaises(ValueError):
                redis_key(*args)

    def test_profile_identity_binds_every_material_semantic(self):
        original = MAC_CHAT_PROFILE.model_dump()
        for path, value in (
            (("qualified_context_tokens",), 4096),
            (("default_output_tokens",), 1024),
            (("reasoning_modes",), ["disabled"]),
            (("decoder_modes",), ["json_schema"]),
            (("model", "runtime_version"), "0.32.15"),
            (("target_profile_id",), "another-device"),
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                changed = deepcopy(original)
                target = changed
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value
                v1.ExecutionProfile.model_validate(changed)

    def test_node_profiles_are_qualified_and_bound_to_advertised_models(self):
        profile = WORKER_CHAT_PROFILE
        node = deepcopy(EXAMPLES["Node"])
        node["models"] = [profile.model.model_dump()]
        node["inference_profiles"] = [profile.model_dump()]
        parsed = parse("Node", node)
        self.assertEqual(parsed.inference_profiles[0].profile_id, profile.profile_id)

        stale = deepcopy(node)
        stale["models"][0]["runtime_version"] = "0.33.3"
        with self.assertRaises(ValueError):
            parse("Node", stale)

        candidate = deepcopy(node)
        candidate["inference_profiles"][0]["qualification_state"] = "candidate"
        candidate["inference_profiles"][0]["eligible"] = False
        with self.assertRaises(ValueError):
            parse("Node", candidate)

    def test_current_mac_runtime_admits_only_its_three_measured_workflows(self):
        model = v1.ModelRef(
            model_id=profiles.MODEL_ID,
            manifest_sha256=profiles.MODEL_DIGEST,
            runtime=profiles.RUNTIME,
            runtime_version="0.33.3")
        admitted = profiles.for_observation(
            target_profile_id=profiles.MAC_M5_16GB, models=[model])
        self.assertEqual(
            {profile.workflow_mode for profile in admitted},
            {profiles.CHAT, profiles.CODE, profiles.DOCUMENTS})
        self.assertEqual(
            {profile.workflow_mode: profile.max_output_tokens for profile in admitted},
            {profiles.CHAT: 2048, profiles.CODE: 2048,
             profiles.DOCUMENTS: 3072})
        changed = model.model_copy(update={"runtime_version": "0.33.4"})
        self.assertEqual(profiles.for_observation(
            target_profile_id=profiles.MAC_M5_16GB, models=[changed]), [])

    def test_ollama_0342_admits_its_measured_mac_workflows(self):
        model = v1.ModelRef(
            model_id=profiles.MODEL_ID,
            manifest_sha256=profiles.MODEL_DIGEST,
            runtime=profiles.RUNTIME,
            runtime_version="0.34.2")
        admitted = profiles.for_observation(
            target_profile_id=profiles.MAC_M5_16GB, models=[model])
        self.assertEqual(
            {profile.workflow_mode: profile.max_output_tokens
             for profile in admitted},
            {profiles.CHAT: 2048, profiles.CODE: 2048})
        changed = model.model_copy(update={"runtime_version": "0.34.3"})
        self.assertEqual(profiles.for_observation(
            target_profile_id=profiles.MAC_M5_16GB, models=[changed]), [])

    def test_legacy_contract_cannot_claim_qualified_semantics(self):
        legacy = deepcopy(EXAMPLES["JobEnvelope"])
        legacy["contract_version"] = "1.0"
        legacy["messages"] = []
        legacy["inference"] = None
        self.assertEqual(parse("JobEnvelope", legacy).contract_version, "1.0")

        event = deepcopy(EXAMPLES["Event"])
        event["contract_version"] = "1.0"
        event["data"] = {
            "kind": "inference.metrics",
            "requested_profile_id": MAC_CHAT_PROFILE.profile_id,
            "actual_profile_id": MAC_CHAT_PROFILE.profile_id,
            "context_window": 8192,
            "output_token_limit": 2048,
            "reasoning": "disabled",
            "decoder": "text",
            "prompt_tokens": 1,
            "output_tokens": 1,
            "runtime_ms": 1,
        }
        with self.assertRaises(ValueError):
            parse("Event", event)

        legacy["inference"] = deepcopy(EXAMPLES["JobEnvelope"]["inference"])
        with self.assertRaises(ValueError):
            parse("JobEnvelope", legacy)


if __name__ == "__main__":
    unittest.main()
