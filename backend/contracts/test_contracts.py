"""Synthetic AF-001 checks. No network, database, model, or service is used."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from .v1 import (
    CONTRACT_VERSION, MAX_EVENT_BYTES, MAX_REQUEST_BYTES, RECORDS,
    TERMINAL_ATTEMPT_STATES, TERMINAL_JOB_STATES,
    Event, JobEnvelope, export_contract, parse_message, payload_sha256,
    redis_key, require_grounded_citations, require_transition, sse_frame,
)

EXAMPLES = json.loads(Path(__file__).with_name("examples.json").read_text())
TYPES = {record.__name__: record for record in RECORDS}


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

    def test_citations_resolve_only_against_supplied_inputs(self):
        envelope = deepcopy(EXAMPLES["JobEnvelope"])
        envelope["task_type"] = "documents"
        envelope["required_capabilities"] = ["document.extract"]
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
        elsewhere = deepcopy(EXAMPLES["Proof"])
        elsewhere["job_id"] = "00000000-0000-4000-8000-000000000022"
        no_inputs = deepcopy(envelope)
        no_inputs["context"] = []
        for description, package, proof in (
            ("cites a document the job never received", no_inputs, cited),
            ("claims grounding with no citation", envelope, parse("Proof", uncited)),
            ("pairs a proof with another job", envelope, parse("Proof", elsewhere)),
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
        self.assertEqual(redis_key("dispatch", relationship), f"af:1.0:{relationship}:dispatch")
        self.assertEqual(redis_key("lease", relationship, original.attempt_id),
                         f"af:1.0:{relationship}:lease:{original.attempt_id}")
        for args in (("dispatch", "../escape"), ("lease", relationship),
                     ("arbitrary", relationship), ("dispatch", relationship, original.attempt_id)):
            with self.assertRaises(ValueError):
                redis_key(*args)


if __name__ == "__main__":
    unittest.main()
