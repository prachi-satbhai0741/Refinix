"""Model download, import and removal, offline.

The network is a scripted pool standing in for urllib3, and the catalogue
entry is synthetic: three small files with pinned sizes and SHA-256. Nothing
is fetched and no model is loaded.

    python3 -m unittest backend.coordinator.test_provisioning -v
"""

from __future__ import annotations

import hashlib
import os
import ssl
import tempfile
import threading
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import db, models, provisioning

WEIGHTS = b"GGUF-weights-" + bytes(range(256)) * 40
PROJECTOR = b"GGUF-projector-" + b"\x07" * 3000


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


FILES = (
    models.ModelFile("weights", "weights.gguf", len(WEIGHTS), _sha(WEIGHTS),
                     "https://models.example/weights.gguf"),
    models.ModelFile("projector", "mmproj.gguf", len(PROJECTOR), _sha(PROJECTOR),
                     "https://models.example/mmproj.gguf"),
)
ENTRY = models.Entry(
    id="test-model", role="Main engine", scopes=(models.CHAT,), source="test source",
    licence="test licence", manifest_sha256=models.manifest_digest("test-model", "r1", FILES),
    format="GGUF", parameters=None, storage_bytes=len(WEIGHTS) + len(PROJECTOR),
    minimum_runtime=None, evidence="synthetic", engine="llama.cpp", files=FILES,
    revision="r1")
BODIES = {FILES[0].url: WEIGHTS, FILES[1].url: PROJECTOR}


class Response:
    def __init__(self, status, body=b"", headers=None, chunk=1000, on_chunk=None):
        self.status, self.body, self.headers = status, body, headers or {}
        self.chunk, self.on_chunk = chunk, on_chunk

    def stream(self, _size):
        for start in range(0, len(self.body), self.chunk):
            if self.on_chunk:
                self.on_chunk(start)
            yield self.body[start:start + self.chunk]

    def drain_conn(self):
        pass

    def release_conn(self):
        pass


class Pool:
    """Serves BODIES, honouring Range unless told not to, and scripted redirects."""

    def __init__(self, *, honour_range=True, corrupt=(), redirects=None, on_chunk=None):
        self.honour_range, self.corrupt = honour_range, set(corrupt)
        self.redirects = dict(redirects or {})
        self.on_chunk = on_chunk
        self.requests = []

    def request(self, method, url, headers=None, redirect=True, preload_content=True):
        self.requests.append((url, dict(headers or {})))
        if url in self.redirects:
            return Response(302, headers={"Location": self.redirects[url]})
        body = BODIES[url]
        if url in self.corrupt:
            body = body[:-1] + bytes([body[-1] ^ 1])
        start = 0
        if headers and "Range" in headers and self.honour_range:
            start = int(headers["Range"].split("=")[1].rstrip("-"))
            return Response(206, body[start:], on_chunk=self.on_chunk)
        return Response(200, body, on_chunk=self.on_chunk)


Disk = namedtuple("Disk", "total used free")


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.state = Path(self.dir.name) / "coordinator.sqlite3"
        self.conn = db.connect(self.state)
        self.addCleanup(self.conn.close)
        patcher = patch.object(models, "entry_for",
                               side_effect=lambda m: ENTRY if m == ENTRY.id else None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.unloaded = []
        self.busy = False

    def provisioner(self, pool=None, free=10 ** 12):
        return provisioning.Provisioner(
            self.conn, self.state, unload=self.unloaded.append,
            busy=lambda: self.busy, pool=pool or Pool(),
            disk_usage=lambda _p: Disk(0, 0, free))

    def finish(self, p, start):
        operation = start()
        p.wait(10)
        return p.state()[operation["model_id"]]

    def installed(self, name):
        return (db.models_root(self.state) / ENTRY.id / name)


class TestDownload(Base):
    def test_a_download_installs_verified_files_and_one_record(self):
        p = self.provisioner()
        result = self.finish(p, lambda: p.start_download(ENTRY.id))
        self.assertEqual(result["state"], "done", result)
        self.assertEqual(self.installed("weights.gguf").read_bytes(), WEIGHTS)
        record = db.get_model_install(self.conn, ENTRY.id)
        self.assertEqual(record["manifest_sha256"], ENTRY.manifest_sha256)
        self.assertEqual(sorted(f["path"] for f in record["files"]),
                         ["test-model/mmproj.gguf", "test-model/weights.gguf"])
        self.assertEqual(result["bytes_done"], ENTRY.storage_bytes)
        self.assertFalse(any((db.models_root(self.state) / ".partial").rglob("*.part")))

    def test_staged_bytes_are_rehashed_then_resumed_with_a_range(self):
        staged = db.models_root(self.state) / ".partial" / ENTRY.id / "weights.gguf.part"
        staged.parent.mkdir(parents=True)
        staged.write_bytes(WEIGHTS[:4000])
        pool = Pool()
        p = self.provisioner(pool)
        self.assertEqual(self.finish(p, lambda: p.start_download(ENTRY.id))["state"], "done")
        self.assertEqual(pool.requests[0][1], {"Range": "bytes=4000-"})
        self.assertEqual(self.installed("weights.gguf").read_bytes(), WEIGHTS)

    def test_a_server_that_ignores_the_range_starts_the_file_again(self):
        staged = db.models_root(self.state) / ".partial" / ENTRY.id / "weights.gguf.part"
        staged.parent.mkdir(parents=True)
        staged.write_bytes(WEIGHTS[:4000])
        p = self.provisioner(Pool(honour_range=False))
        self.assertEqual(self.finish(p, lambda: p.start_download(ENTRY.id))["state"], "done")
        self.assertEqual(self.installed("weights.gguf").read_bytes(), WEIGHTS)

    def test_corrupted_staged_bytes_are_never_installed(self):
        staged = db.models_root(self.state) / ".partial" / ENTRY.id / "weights.gguf.part"
        staged.parent.mkdir(parents=True)
        staged.write_bytes(b"X" * 4000)                    # not the start of the file
        p = self.provisioner()
        result = self.finish(p, lambda: p.start_download(ENTRY.id))
        self.assertEqual((result["state"], result["error_code"]),
                         ("failed", "integrity_mismatch"))
        self.assertFalse(self.installed("weights.gguf").exists())
        self.assertFalse(staged.exists(), "bad staged bytes were kept")
        self.assertIsNone(db.get_model_install(self.conn, ENTRY.id))

    def test_wrong_bytes_from_the_server_are_discarded(self):
        p = self.provisioner(Pool(corrupt={FILES[1].url}))
        result = self.finish(p, lambda: p.start_download(ENTRY.id))
        self.assertEqual(result["error_code"], "integrity_mismatch")
        self.assertFalse(self.installed("mmproj.gguf").exists())
        self.assertIsNone(db.get_model_install(self.conn, ENTRY.id))

    def test_redirects_are_followed_only_over_https(self):
        p = self.provisioner(Pool(redirects={FILES[0].url: "http://plain.example/w"}))
        result = self.finish(p, lambda: p.start_download(ENTRY.id))
        self.assertEqual(result["error_code"], "unsafe_source")
        BODIES["https://cdn.example/w"] = WEIGHTS
        self.addCleanup(BODIES.pop, "https://cdn.example/w")
        pool = Pool(redirects={FILES[0].url: "https://cdn.example/w"})
        p = self.provisioner(pool)
        self.assertEqual(self.finish(p, lambda: p.start_download(ENTRY.id))["state"], "done")
        self.assertIn("https://cdn.example/w", [url for url, _ in pool.requests])

    def test_cancel_keeps_staged_bytes_and_installs_nothing(self):
        started, release = threading.Event(), threading.Event()

        def slow(start):
            if start >= 3000:
                started.set()
                release.wait(5)

        p = self.provisioner(Pool(on_chunk=slow))
        p.start_download(ENTRY.id)
        self.assertTrue(started.wait(5))
        self.assertTrue(p.cancel(ENTRY.id)["cancelled"])
        release.set()
        p.wait(10)
        self.assertEqual(p.state()[ENTRY.id]["state"], "cancelled")
        self.assertIsNone(db.get_model_install(self.conn, ENTRY.id))
        staged = db.models_root(self.state) / ".partial" / ENTRY.id / "weights.gguf.part"
        self.assertGreater(staged.stat().st_size, 0)
        self.assertFalse(self.installed("weights.gguf").exists())

    def test_too_little_disk_space_is_refused_before_any_request(self):
        pool = Pool()
        p = self.provisioner(pool, free=1000)
        with self.assertRaises(provisioning.ProvisioningError) as caught:
            p.start_download(ENTRY.id)
        self.assertEqual(caught.exception.code, "insufficient_space")
        self.assertEqual(pool.requests, [])

    def test_an_installed_file_is_reread_and_reused_not_fetched_again(self):
        self.installed("weights.gguf").parent.mkdir(parents=True)
        self.installed("weights.gguf").write_bytes(WEIGHTS)
        pool = Pool()
        p = self.provisioner(pool)
        self.assertEqual(self.finish(p, lambda: p.start_download(ENTRY.id))["state"], "done")
        self.assertEqual([url for url, _ in pool.requests], [FILES[1].url])

    def test_a_changed_installed_file_is_replaced(self):
        self.installed("weights.gguf").parent.mkdir(parents=True)
        self.installed("weights.gguf").write_bytes(WEIGHTS[:-1] + b"!")
        p = self.provisioner()
        self.assertEqual(self.finish(p, lambda: p.start_download(ENTRY.id))["state"], "done")
        self.assertEqual(self.installed("weights.gguf").read_bytes(), WEIGHTS)

    def test_only_catalogued_managed_models_can_be_downloaded(self):
        p = self.provisioner()
        with self.assertRaises(provisioning.ProvisioningError) as caught:
            p.start_download("somebody/else")
        self.assertEqual(caught.exception.code, "unknown_model")

    def test_one_operation_at_a_time(self):
        release = threading.Event()
        p = self.provisioner(Pool(on_chunk=lambda _s: release.wait(5)))
        p.start_download(ENTRY.id)
        try:
            with self.assertRaises(provisioning.ProvisioningError) as caught:
                p.start_download(ENTRY.id)
            self.assertEqual(caught.exception.code, "busy")
        finally:
            p.cancel(ENTRY.id)
            release.set()
            p.wait(10)

    def test_the_plan_shows_source_size_and_hashes_before_anything_starts(self):
        pool = Pool()
        plan = self.provisioner(pool).plan(ENTRY.id)
        self.assertEqual(plan["download_bytes"], ENTRY.storage_bytes)
        self.assertEqual((plan["source"], plan["licence"], plan["revision"]),
                         ("test source", "test licence", "r1"))
        self.assertEqual([f["sha256"] for f in plan["files"]], [f.sha256 for f in FILES])
        self.assertTrue(plan["enough_space"])
        self.assertEqual(pool.requests, [])


class TestImport(Base):
    def chosen(self, *pairs):
        folder = Path(self.dir.name) / "usb"
        folder.mkdir(exist_ok=True)
        paths = []
        for name, data in pairs:
            (folder / name).write_bytes(data)
            paths.append(folder / name)
        return paths

    def test_files_are_kept_by_their_bytes_whatever_they_are_called(self):
        paths = self.chosen(("a.gguf", PROJECTOR), ("b.gguf", WEIGHTS))
        p = self.provisioner()
        result = self.finish(p, lambda: p.start_import(ENTRY.id, paths))
        self.assertEqual(result["state"], "done", result)
        self.assertEqual(self.installed("weights.gguf").read_bytes(), WEIGHTS)
        self.assertEqual(self.installed("mmproj.gguf").read_bytes(), PROJECTOR)
        self.assertIn("imported", db.get_model_install(self.conn, ENTRY.id)["source"])
        self.assertTrue(paths[0].exists(), "the person's own file was moved")

    def test_a_file_that_matches_nothing_is_not_kept(self):
        paths = self.chosen(("w.gguf", WEIGHTS), ("other.gguf", b"something else"))
        p = self.provisioner()
        result = self.finish(p, lambda: p.start_import(ENTRY.id, paths))
        self.assertEqual(result["error_code"], "incomplete")
        self.assertIn("other.gguf", result["error"])
        self.assertIn("mmproj.gguf", result["error"])
        self.assertIsNone(db.get_model_install(self.conn, ENTRY.id))
        self.assertTrue(self.installed("weights.gguf").exists(),
                        "a verified file should stay for the next attempt")

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symbolic links")
    def test_a_link_is_refused(self):
        target = self.chosen(("w.gguf", WEIGHTS))[0]
        link = target.with_name("link.gguf")
        link.symlink_to(target)
        with self.assertRaises(provisioning.ProvisioningError) as caught:
            self.provisioner().start_import(ENTRY.id, [link])
        self.assertEqual(caught.exception.code, "not_a_file")


class TestRemove(Base):
    def install(self):
        p = self.provisioner()
        self.finish(p, lambda: p.start_download(ENTRY.id))
        return p

    def test_removal_unloads_forgets_and_deletes(self):
        p = self.install()
        result = p.remove(ENTRY.id)
        self.assertTrue(result["removed"])
        self.assertFalse(result["files_left"])
        self.assertEqual(self.unloaded, [ENTRY.id])
        self.assertIsNone(db.get_model_install(self.conn, ENTRY.id))
        self.assertFalse((db.models_root(self.state) / ENTRY.id).exists())

    def test_removal_waits_for_running_work(self):
        p = self.install()
        self.busy = True
        with self.assertRaises(provisioning.ProvisioningError) as caught:
            p.remove(ENTRY.id)
        self.assertEqual(caught.exception.code, "in_use")
        self.assertIsNotNone(db.get_model_install(self.conn, ENTRY.id))

    def test_a_folder_left_by_an_interrupted_removal_can_be_removed(self):
        p = self.install()
        db.delete_model_install(self.conn, ENTRY.id)       # crash after the record
        self.assertTrue(p.remove(ENTRY.id)["removed"])
        self.assertFalse((db.models_root(self.state) / ENTRY.id).exists())


class TestTransport(unittest.TestCase):
    def test_tls_always_verifies_certificates_and_names(self):
        context = provisioning.tls_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_a_python_without_root_certificates_uses_the_systems_file(self):
        loaded = []

        class Empty(ssl.SSLContext):
            def cert_store_stats(self):
                return {"x509_ca": 0}

            def load_verify_locations(self, cafile=None, *a, **k):
                loaded.append(cafile)

        with patch.object(provisioning.ssl, "create_default_context",
                          return_value=Empty(ssl.PROTOCOL_TLS_CLIENT)), \
                patch.object(provisioning.os.path, "isfile",
                             side_effect=lambda p: p == "/etc/ssl/certs/ca-certificates.crt"):
            provisioning.tls_context()
        self.assertEqual(loaded, ["/etc/ssl/certs/ca-certificates.crt"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
