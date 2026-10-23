"""The process observer and what a Proof Card may say about the network.

No traffic leaves the computer: coordinator connections are real loopback
sockets or audit events fed straight to the hook, and the engine's sockets
come from a stand-in listing.

    python3 -m unittest backend.coordinator.test_observer -v
"""

from __future__ import annotations

import json
import socket
import unittest
from unittest.mock import patch

from backend.contracts import v1
from backend.coordinator import db, observer, proof, runtime
from backend.coordinator.test_documents import fake_stream
from backend.coordinator.test_execution4a import Harness

NODE = "11111111-2222-4333-8444-555555555555"


class TestClassify(unittest.TestCase):
    def test_addresses_are_sorted_into_loopback_lan_and_public(self):
        cases = {"127.0.0.1": "loopback", "::1": "loopback", "0.0.0.0": "loopback",
                 "192.168.1.20": "lan", "10.0.0.5": "lan", "172.16.4.1": "lan",
                 "fe80::1%en0": "lan", "169.254.1.1": "lan", "fd00::1": "lan",
                 "8.8.8.8": "public", "2606:4700::1111": "public",
                 "::ffff:8.8.8.8": "public", "huggingface.co": None, "": None}
        for host, kind in cases.items():
            with self.subTest(host=host):
                self.assertEqual(observer.classify(host), kind)


class TestWindow(unittest.TestCase):
    def test_a_coordinator_connection_inside_the_window_is_counted(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        self.addCleanup(listener.close)
        window = observer.Window(node_id=NODE).start()
        with socket.create_connection(listener.getsockname(), timeout=2):
            pass
        observer._hook("socket.connect", (None, ("8.8.8.8", 443)))
        observer._hook("socket.getaddrinfo", ("api.example.com", 443, 0, 0, 0, 0))
        result = window.stop()
        self.assertGreaterEqual(result["loopback_connections"], 1)
        self.assertEqual(result["public_outbound_flows"], 1)
        self.assertEqual(result["public_name_lookups"], ["api.example.com"])
        self.assertEqual(result["observer_errors"], 0)
        self.assertLess(result["started_at"], result["ended_at"])

    def test_events_outside_the_window_are_not_counted(self):
        observer.install()
        observer._hook("socket.connect", (None, ("8.8.4.4", 443)))
        result = observer.Window(node_id=NODE).start().stop()
        self.assertEqual(result["public_outbound_flows"], 0)

    def test_unix_sockets_are_local_ipc_not_flows(self):
        window = observer.Window(node_id=NODE).start()
        observer._hook("socket.connect", (None, "/var/run/something.sock"))
        self.assertEqual(window.stop()["public_outbound_flows"], 0)

    def test_the_engines_sockets_are_sampled_and_named_as_sampled(self):
        listing = [("127.0.0.1", 50000), ("192.168.1.9", 443), ("1.2.3.4", 443)]
        window = observer.Window(node_id=NODE, engine_pid=lambda: 4242, interval=0.01,
                                 connections=lambda pid: listing).start()
        result = window.stop()
        self.assertGreater(result["engine_samples"], 0)
        self.assertIn("engine process sockets (sampled)", result["interfaces"])
        self.assertEqual((result["public_outbound_flows"], result["trusted_lan_connections"]),
                         (1, 1))

    def test_an_engine_that_cannot_be_listed_is_an_observer_error(self):
        def denied(pid):
            raise PermissionError("denied")
        result = observer.Window(node_id=NODE, engine_pid=lambda: 4242, interval=0.01,
                                 connections=denied).start().stop()
        self.assertGreater(result["observer_errors"], 0)

    def test_no_engine_means_only_the_coordinator_was_observed(self):
        result = observer.Window(node_id=NODE).start().stop()
        self.assertEqual(result["interfaces"], ["coordinator process sockets"])
        self.assertEqual(result["engine_samples"], 0)


class TestProofNetwork(unittest.TestCase):
    def raw(self, **changes):
        base = observer.Window(node_id=NODE).start().stop()
        base.update(changes)
        return base

    def test_an_observed_local_attempt_carries_counts_but_no_policy_claim(self):
        record, source = proof._network(self.raw(), local=True)
        self.assertIsInstance(record, v1.NetworkEvidence)
        self.assertEqual(record.public_egress_policy, "unavailable")
        self.assertIsNone(record.enforcer)
        self.assertEqual(record.observer, observer.OBSERVER)
        self.assertEqual(record.public_outbound_flows, 0)
        self.assertIsNone(record.blocked_attempts)
        self.assertIn("not enforcement", source)

    def test_an_observation_with_errors_is_not_shown_as_complete(self):
        record, source = proof._network(self.raw(observer_errors=2), local=True)
        self.assertIsNone(record.observer)
        self.assertIn("reported errors", source)

    def test_a_remote_attempt_never_borrows_this_computers_observation(self):
        record, source = proof._network(self.raw(), local=False)
        self.assertIsNone(record.observer)
        self.assertEqual(source, proof.NETWORK_UNAVAILABLE_NOTE)

    def test_no_observation_stays_unavailable(self):
        record, source = proof._network(None, local=True)
        self.assertIsNone(record.public_outbound_flows)
        self.assertEqual(source, proof.NETWORK_UNAVAILABLE_NOTE)


class TestJobObservation(Harness):
    def test_a_finished_chat_job_records_its_window_and_the_card_shows_it(self):
        job = self.send("explain the reading")
        with patch.object(runtime, "stream_chat", fake_stream("An answer.")):
            self.c._run(job, self.chat, None)
        row = self.c.conn.execute(
            "SELECT network_json FROM attempts WHERE job_id=?", (job,)).fetchone()
        recorded = json.loads(row["network_json"])
        self.assertEqual(recorded["node_id"], self.c.node_id)
        card = proof.job_card(self.c, job)
        attempt = card["attempts"][0]
        self.assertEqual(attempt["proof"]["network"]["observer"], observer.OBSERVER)
        self.assertIn("public connection", attempt["sources"]["network"])
        self.assertNotEqual(card["network"], proof.NETWORK_UNAVAILABLE_NOTE)

    def test_older_attempts_without_an_observation_stay_unavailable(self):
        job = self.send("explain the reading")
        with patch.object(runtime, "stream_chat", fake_stream("An answer.")):
            self.c._run(job, self.chat, None)
        self.c.conn.execute("UPDATE attempts SET network_json=NULL WHERE job_id=?", (job,))
        self.c.conn.commit()
        card = proof.job_card(self.c, job)
        self.assertEqual(card["network"], proof.NETWORK_UNAVAILABLE_NOTE)
        self.assertIsNone(card["attempts"][0]["proof"]["network"]["observer"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
