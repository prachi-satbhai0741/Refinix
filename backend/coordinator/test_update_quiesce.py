"""Before an update is installed: refuse changes, drain writers, close the database.

A real coordinator and listener on loopback. The event stream stays open
during the drain, as the window's does.

    python3 -m unittest backend.coordinator.test_update_quiesce -v
"""

from __future__ import annotations

import http.client
import json
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from backend.coordinator import server


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Running(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.port = free_port()
        self.httpd, self.c = server.build_server(Path(self.dir.name) / "c.sqlite3", self.port)
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        if not self.c.stopping.is_set():
            server.shutdown_server(self.httpd, self.c)
        if not self.c.closed:
            self.c.conn.close()

    def post(self, route, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        data = json.dumps(body or {}).encode()
        conn.request("POST", route, data, {"Content-Type": "application/json",
                                           "Host": f"127.0.0.1:{self.port}",
                                           "Content-Length": str(len(data))})
        response = conn.getresponse()
        payload = json.loads(response.read() or b"{}")
        conn.close()
        return response.status, payload

    def open_stream(self):
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        sock.sendall(f"GET /v1/events HTTP/1.1\r\nHost: 127.0.0.1:{self.port}\r\n\r\n"
                     .encode())
        sock.recv(64)                                    # the stream's headers began
        self.addCleanup(sock.close)
        return sock


class TestQuiesce(Running):
    def test_changes_are_refused_while_installing_and_accepted_again_after(self):
        self.c.begin_install()
        status, body = self.post("/v1/chats", {"title": "during"})
        self.assertEqual((status, body.get("code")), (409, "installing"))
        status, _ = self.post("/v1/updates/cancel")
        self.assertEqual(status, 200)
        self.c.end_install()
        status, _ = self.post("/v1/chats", {"title": "after"})
        self.assertEqual(status, 201)

    def test_a_writer_that_does_not_finish_is_named_and_nothing_closes(self):
        release = threading.Event()

        def busy():
            with self.c.writers.hold("a running reply"):
                release.wait(5)

        worker = threading.Thread(target=busy)
        worker.start()
        time.sleep(0.05)
        self.c.begin_install()
        self.assertEqual(self.c.writers.wait_idle(0.2), ["a running reply"])
        self.c.end_install()
        self.assertFalse(self.c.closed)
        self.c.conn.execute("SELECT 1").fetchone()       # still open
        release.set()
        worker.join()
        self.assertEqual(self.c.writers.wait_idle(1), [])

    def test_an_open_event_stream_does_not_stall_the_drain_and_ends_before_closing(self):
        self.open_stream()
        deadline = time.monotonic() + 2
        while not self.c.requests.active() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(self.c.requests.active(), ["a request"])
        self.c.begin_install()
        self.assertEqual(self.c.writers.wait_idle(0.5), [], "the stream counted as a writer")
        server.shutdown_server(self.httpd, self.c)          # sets stopping
        self.assertEqual(self.c.close_for_install(5), [])
        self.assertTrue(self.c.closed)
        with self.assertRaises(sqlite3.ProgrammingError):
            self.c.conn.execute("SELECT 1")
        self.assertFalse(Path(f"{self.c.state_path}-wal").exists()
                         and Path(f"{self.c.state_path}-wal").stat().st_size,
                         "the write-ahead log was not checkpointed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
