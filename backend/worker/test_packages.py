"""AF-010 checks: what may be written into a worker's job workspace.

Standard library only, so these run on the coordinator, in CI and inside the
image build — unlike the route checks in `test_worker_app.py`, which need
FastAPI and therefore only run where the image is built.

Every case here is an escape someone would actually try: a traversal, an
absolute path, a case collision, a lying digest, a lying size, a binary blob,
a duplicate id, an oversized package, a conflicting retry. The format has no
representation for a symlink, a device node or an archive member, so those are
covered by construction rather than by a filter.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path

from backend.contracts import v1
from backend.worker import packages


def entry(path: str, text: str = "print('x')\n", *, resource_id: str | None = None,
          media_type: str = "text/x-python", **overrides) -> dict:
    content = text.encode("utf-8")
    built = {
        "resource_id": resource_id or str(uuid.uuid4()),
        "path": path, "media_type": media_type,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "content_base64": base64.b64encode(content).decode("ascii"),
    }
    built.update(overrides)
    return built


def body(entries: list[dict], **overrides) -> dict:
    decoded = [{"resource_id": item["resource_id"], "path": item["path"],
                "media_type": item["media_type"], "size_bytes": item["size_bytes"],
                "sha256": item["sha256"]} for item in entries]
    payload = {
        "contract_version": v1.CONTRACT_VERSION,
        "workspace_id": str(uuid.uuid4()),
        "relationship_id": str(uuid.uuid4()),
        "attempt_id": str(uuid.uuid4()),
        "package_sha256": packages.package_digest(decoded),
        "files": entries,
    }
    payload.update(overrides)
    return payload


class TestPaths(unittest.TestCase):
    def refuses(self, path):
        with self.assertRaises(packages.PackageError) as caught:
            packages.normalise_relative(path)
        self.assertEqual(caught.exception.code, "invalid_request")

    def test_ordinary_relative_paths_are_accepted(self):
        for path in ("a.py", "pkg/mod.py", "a/b/c/d.txt"):
            with self.subTest(path=path):
                self.assertEqual(packages.normalise_relative(path), path)

    def test_traversal_is_refused(self):
        for path in ("../secret", "a/../../etc/passwd", "..", "a/..", "./a"):
            with self.subTest(path=path):
                self.refuses(path)

    def test_absolute_and_drive_paths_are_refused(self):
        for path in ("/etc/passwd", "/", "C:/Windows/system32", "C:\\a"):
            with self.subTest(path=path):
                self.refuses(path)

    def test_backslashes_are_refused_rather_than_translated(self):
        self.refuses("a\\b.py")

    def test_control_characters_and_nul_are_refused(self):
        for path in ("a\x00b", "a\nb", "a\tb"):
            with self.subTest(path=path):
                self.refuses(path)

    def test_names_that_collapse_on_a_filesystem_are_refused(self):
        for path in ("a.", "a ", "dir./x", " a"):
            with self.subTest(path=path):
                self.refuses(path)

    def test_excessive_length_and_depth_are_refused(self):
        self.refuses("a" * (packages.MAX_PATH_LENGTH + 1))
        self.refuses("x" * (packages.MAX_COMPONENT_LENGTH + 1) + "/a.py")
        self.refuses("/".join(["d"] * (packages.MAX_DEPTH + 1)) + "/a.py")


class TestValidation(unittest.TestCase):
    def refuses(self, payload, *, code="invalid_request"):
        with self.assertRaises(packages.PackageError) as caught:
            packages.validate(payload)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_a_well_formed_package_validates(self):
        result = packages.validate(body([entry("a.py"), entry("pkg/b.py")]))
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(len(result["package_sha256"]), 64)

    def test_a_duplicate_resource_id_is_refused(self):
        shared = str(uuid.uuid4())
        self.refuses(body([entry("a.py", resource_id=shared),
                           entry("b.py", resource_id=shared)]))

    def test_two_entries_naming_the_same_file_are_refused(self):
        self.refuses(body([entry("a.py"), entry("a.py")]))

    def test_a_case_only_collision_is_refused(self):
        """On a case-insensitive mount these become one file, and the package
        digest would then describe bytes that are not on disk."""
        self.refuses(body([entry("Mod.py"), entry("mod.py")]))

    def test_invalid_base64_is_refused(self):
        self.refuses(body([entry("a.py", content_base64="not base64!!")]))

    def test_base64_with_stray_characters_is_refused_not_stripped(self):
        clean = base64.b64encode(b"hello").decode()
        self.refuses(body([entry("a.py", content_base64=clean[:2] + "\n" + clean[2:],
                                 size_bytes=5,
                                 sha256=hashlib.sha256(b"hello").hexdigest())]))

    def test_non_utf8_content_is_refused(self):
        blob = bytes([0xff, 0xfe, 0x00, 0x01])
        self.refuses(body([entry(
            "a.bin", content_base64=base64.b64encode(blob).decode(),
            size_bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest())]))

    def test_a_digest_that_does_not_match_its_content_is_refused(self):
        self.refuses(body([entry("a.py", sha256="0" * 64)]))

    def test_a_size_that_does_not_match_its_content_is_refused(self):
        self.refuses(body([entry("a.py", size_bytes=99999)]))

    def test_a_package_digest_that_does_not_match_the_manifest_is_refused(self):
        payload = body([entry("a.py")])
        payload["package_sha256"] = "f" * 64
        self.refuses(payload)

    def test_changing_one_file_changes_the_package_digest(self):
        first = packages.validate(body([entry("a.py", "one\n")]))
        second = packages.validate(body([entry("a.py", "two\n")]))
        self.assertNotEqual(first["package_sha256"], second["package_sha256"])

    def test_too_many_files_is_refused(self):
        entries = [entry(f"f{index}.py") for index in range(packages.MAX_FILES + 1)]
        self.refuses(body(entries))

    def test_one_oversized_file_is_refused(self):
        text = "x" * (packages.MAX_FILE_BYTES + 1)
        self.refuses(body([entry("a.py", text)]))

    def test_an_oversized_total_is_refused(self):
        chunk = "x" * (packages.MAX_FILE_BYTES - 1)
        count = (packages.MAX_TOTAL_BYTES // len(chunk)) + 2
        self.refuses(body([entry(f"f{index}.py", chunk) for index in range(count)]))

    def test_an_empty_package_is_refused(self):
        self.refuses(body([]))

    def test_unexpected_fields_are_refused(self):
        payload = body([entry("a.py")])
        payload["mode"] = "0777"
        self.refuses(payload)
        payload = body([entry("a.py", symlink_to="/etc/passwd")])
        self.refuses(payload)

    def test_a_non_uuid_resource_id_is_refused(self):
        self.refuses(body([entry("a.py", resource_id="../../etc/passwd")]))


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = packages.PackageStore(Path(self.tmp.name))
        self.relationship = str(uuid.uuid4())
        self.workspace = str(uuid.uuid4())
        self.attempt = str(uuid.uuid4())

    def put(self, entries, *, attempt=None):
        validated = packages.validate(body(entries))
        return self.store.store(relationship_id=self.relationship,
                                workspace_id=self.workspace,
                                attempt_id=attempt or self.attempt,
                                validated=validated), validated

    def test_files_land_inside_the_attempt_directory_only(self):
        stored, _ = self.put([entry("pkg/mod.py", "value = 1\n")])
        base = self.store.files_dir(relationship_id=self.relationship,
                                    workspace_id=self.workspace,
                                    attempt_id=self.attempt)
        written = sorted(str(path.relative_to(base))
                         for path in base.rglob("*") if path.is_file())
        self.assertEqual(written, ["pkg/mod.py"])
        self.assertEqual((base / "pkg/mod.py").read_text(), "value = 1\n")
        self.assertFalse(stored["replayed"])

    def test_written_files_are_owner_only(self):
        self.put([entry("a.py")])
        base = self.store.files_dir(relationship_id=self.relationship,
                                    workspace_id=self.workspace,
                                    attempt_id=self.attempt)
        mode = os.stat(base / "a.py").st_mode & 0o777
        self.assertEqual(mode & 0o077, 0, oct(mode))

    def test_an_identical_retry_is_idempotent(self):
        entries = [entry("a.py", "same\n", resource_id=str(uuid.uuid4()))]
        first, validated = self.put(entries)
        again = self.store.store(relationship_id=self.relationship,
                                 workspace_id=self.workspace,
                                 attempt_id=self.attempt, validated=validated)
        self.assertTrue(again["replayed"])
        self.assertEqual(first["package_sha256"], again["package_sha256"])

    def test_a_different_package_for_the_same_attempt_conflicts(self):
        self.put([entry("a.py", "one\n")])
        with self.assertRaises(packages.PackageError) as caught:
            self.put([entry("a.py", "two\n")])
        self.assertEqual(caught.exception.code, "idempotency_conflict")
        self.assertEqual(caught.exception.status, 409)

    def test_the_original_package_survives_a_conflicting_retry(self):
        self.put([entry("a.py", "original\n")])
        with self.assertRaises(packages.PackageError):
            self.put([entry("a.py", "replacement\n")])
        base = self.store.files_dir(relationship_id=self.relationship,
                                    workspace_id=self.workspace,
                                    attempt_id=self.attempt)
        self.assertEqual((base / "a.py").read_text(), "original\n")

    def test_a_resource_resolves_only_inside_its_own_attempt(self):
        entries = [entry("a.py", "mine\n")]
        self.put(entries)
        resource_id = entries[0]["resource_id"]
        found = self.store.resolve(relationship_id=self.relationship,
                                   workspace_id=self.workspace,
                                   attempt_id=self.attempt,
                                   resource_id=resource_id)
        self.assertEqual(found["content"], b"mine\n")
        # The same id, addressed through a different attempt, resolves nothing.
        self.assertIsNone(self.store.resolve(
            relationship_id=self.relationship, workspace_id=self.workspace,
            attempt_id=str(uuid.uuid4()), resource_id=resource_id))
        # ... and through a different relationship.
        self.assertIsNone(self.store.resolve(
            relationship_id=str(uuid.uuid4()), workspace_id=self.workspace,
            attempt_id=self.attempt, resource_id=resource_id))

    def test_an_unknown_resource_id_resolves_to_nothing(self):
        self.put([entry("a.py")])
        self.assertIsNone(self.store.resolve(
            relationship_id=self.relationship, workspace_id=self.workspace,
            attempt_id=self.attempt, resource_id=str(uuid.uuid4())))

    def test_content_altered_on_disk_stops_resolving(self):
        """The bytes the sandbox receives are re-checked, not assumed."""
        entries = [entry("a.py", "trusted\n")]
        self.put(entries)
        base = self.store.files_dir(relationship_id=self.relationship,
                                    workspace_id=self.workspace,
                                    attempt_id=self.attempt)
        (base / "a.py").write_text("tampered\n")
        self.assertIsNone(self.store.resolve(
            relationship_id=self.relationship, workspace_id=self.workspace,
            attempt_id=self.attempt, resource_id=entries[0]["resource_id"]))

    def test_a_package_that_was_never_uploaded_has_no_manifest(self):
        self.assertIsNone(self.store.manifest(
            relationship_id=self.relationship, workspace_id=self.workspace,
            attempt_id=str(uuid.uuid4())))

    def test_purge_removes_only_the_named_attempt(self):
        other = str(uuid.uuid4())
        self.put([entry("a.py", "first\n")])
        self.put([entry("b.py", "second\n")], attempt=other)
        self.assertTrue(self.store.purge(relationship_id=self.relationship,
                                         workspace_id=self.workspace,
                                         attempt_id=self.attempt))
        self.assertIsNone(self.store.manifest(
            relationship_id=self.relationship, workspace_id=self.workspace,
            attempt_id=self.attempt))
        self.assertIsNotNone(self.store.manifest(
            relationship_id=self.relationship, workspace_id=self.workspace,
            attempt_id=other))

    def test_purging_something_that_is_not_there_is_not_an_error(self):
        self.assertFalse(self.store.purge(relationship_id=self.relationship,
                                          workspace_id=self.workspace,
                                          attempt_id=str(uuid.uuid4())))

    def test_expired_packages_are_reclaimed_and_fresh_ones_are_not(self):
        stale = str(uuid.uuid4())
        self.put([entry("a.py", "old\n")], attempt=stale)
        self.put([entry("b.py", "new\n")])
        directory = Path(self.tmp.name) / self.relationship / self.workspace / stale
        old = 1_000_000.0
        os.utime(directory, (old, old))
        removed = self.store.purge_expired(older_than=60)
        self.assertIn(stale, removed)
        self.assertIsNotNone(self.store.manifest(
            relationship_id=self.relationship, workspace_id=self.workspace,
            attempt_id=self.attempt))

    def test_identifiers_must_be_uuid4_before_they_become_a_directory(self):
        validated = packages.validate(body([entry("a.py")]))
        for bad in ("../..", "..", "a/b", ""):
            with self.subTest(value=bad):
                with self.assertRaises(packages.PackageError):
                    self.store.store(relationship_id=self.relationship,
                                     workspace_id=self.workspace,
                                     attempt_id=bad, validated=validated)

    def test_a_stored_manifest_never_records_a_coordinator_path(self):
        self.put([entry("pkg/mod.py")])
        stored = json.dumps(self.store.manifest(
            relationship_id=self.relationship, workspace_id=self.workspace,
            attempt_id=self.attempt))
        for leak in ("/Users", "/home", "Documents", "GitHub"):
            self.assertNotIn(leak, stored)


if __name__ == "__main__":                                    # pragma: no cover
    unittest.main()
