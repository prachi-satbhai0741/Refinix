"""The Windows containment backend, exercised on whatever computer runs this.

`repo.py` refused the whole Code surface on Windows because there is no
`openat` there. `winfs` supplies the same guarantee from pinned handles, and
this file is the evidence for the parts that can be checked without a Windows
machine: the call sequence, every refusal, the handle lifetime and the
identical bounds.

The stand-in below is not a mock that returns canned answers. It is a small
`CreateFileW` emulator over a **real directory tree**, which means the bytes
read, the atomic replacement, the stale-hash refusal and the traversal
decisions are all executed for real through `repo.py`'s Windows branch. What
it emulates is Windows' *semantics*, and it asserts the two invariants the
design rests on at every single call:

* no name is ever opened without `FILE_FLAG_OPEN_REPARSE_POINT`, so a link can
  never be followed;
* no handle is ever opened with `FILE_SHARE_DELETE`, so every ancestor stays
  pinned against rename and delete for the whole operation.

A POSIX symlink stands in for a reparse point: `os.lstat` reports it, the fake
returns a handle carrying `FILE_ATTRIBUTE_REPARSE_POINT` exactly as Windows
would, and the refusal that follows is `repo.py`'s own.

**This is not device evidence.** The real `kernel32` binding in `winfs.Api` is
never executed here, and no support claim follows from these tests.

    python3 -m unittest backend.coordinator.test_repo_windows -v
"""

import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.coordinator import repo, winfs

FILE_SHARE_DELETE = 0x00000004


class FakeWindows:
    """`CreateFileW` and friends, over a real POSIX tree."""

    def __init__(self, base: Path):
        self.base = Path(base)
        self._records: dict[int, tuple[Path, int | None]] = {}
        self._next = 1000
        self.opens: list[tuple] = []
        self.live: set[int] = set()
        self.max_live = 0

    # -- translation ----------------------------------------------------
    def _translate(self, path: str) -> Path:
        assert path.startswith("\\\\?\\"), f"every path must be extended: {path}"
        return Path(path[4:].replace("\\", "/"))

    def _entry(self, info: os.stat_result, attributes: int) -> winfs.Entry:
        return winfs.Entry(attributes=attributes, device=info.st_dev,
                           inode=info.st_ino, size=info.st_size,
                           links=info.st_nlink)

    def _register(self, real: Path, descriptor: int | None,
                  entry: winfs.Entry) -> int:
        self._next += 1
        handle = self._next
        self._records[handle] = (real, descriptor, entry)
        self.live.add(handle)
        self.max_live = max(self.max_live, len(self.live))
        return handle

    # -- the emulated API -----------------------------------------------
    def open(self, path, *, access, share, disposition, flags):
        self.opens.append((path, access, share, disposition, flags))
        assert flags & winfs.FILE_FLAG_OPEN_REPARSE_POINT, \
            f"{path} was opened in a way that could follow a link"
        assert not share & FILE_SHARE_DELETE, \
            f"{path} was opened in a way that lets another process replace it"
        real = self._translate(path)

        if disposition == winfs.CREATE_NEW:
            try:
                descriptor = os.open(real, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError as exc:
                raise winfs.WindowsError_(winfs.ERROR_FILE_EXISTS, "exists",
                                          "the name already exists") from exc
            except OSError as exc:
                raise winfs.WindowsError_(winfs.ERROR_ACCESS_DENIED, "unreadable",
                                          str(exc)) from exc
            return self._register(real, descriptor, self._entry(os.fstat(descriptor), 0))

        try:
            info = os.lstat(real)
        except FileNotFoundError as exc:
            raise winfs.WindowsError_(winfs.ERROR_FILE_NOT_FOUND, "missing",
                                      "the name was not found") from exc
        except NotADirectoryError as exc:
            raise winfs.WindowsError_(winfs.ERROR_DIRECTORY, "bad_path",
                                      "a component is not a folder") from exc
        except OSError as exc:
            raise winfs.WindowsError_(winfs.ERROR_ACCESS_DENIED, "unreadable",
                                      str(exc)) from exc

        if stat.S_ISLNK(info.st_mode):
            # Windows opens the reparse point itself and reports its attribute;
            # refusing it is the caller's job, and that is what is under test.
            return self._register(real, None,
                                  self._entry(info, winfs.FILE_ATTRIBUTE_REPARSE_POINT))
        if stat.S_ISDIR(info.st_mode):
            if not flags & winfs.FILE_FLAG_BACKUP_SEMANTICS:
                # CreateFileW refuses a directory without backup semantics.
                raise winfs.WindowsError_(winfs.ERROR_ACCESS_DENIED, "unreadable",
                                          "a folder cannot be opened as a file")
            return self._register(real, None,
                                  self._entry(info, winfs.FILE_ATTRIBUTE_DIRECTORY))
        if not stat.S_ISREG(info.st_mode):
            raise winfs.WindowsError_(winfs.ERROR_ACCESS_DENIED, "unreadable",
                                      "not an ordinary file")
        descriptor = os.open(real, os.O_RDONLY | os.O_NOFOLLOW)
        return self._register(real, descriptor, self._entry(os.fstat(descriptor), 0))

    def information(self, handle):
        return self._records[handle][2]

    def close(self, handle):
        real, descriptor, _entry = self._records.pop(handle)
        self.live.discard(handle)
        if descriptor is not None:
            os.close(descriptor)

    def descriptor(self, handle, flags):
        real, descriptor, _entry = self._records.pop(handle)
        self.live.discard(handle)
        assert descriptor is not None, "no descriptor was opened for this handle"
        return descriptor

    def replace(self, source, target):
        os.replace(self._translate(source), self._translate(target))

    def unlink(self, path):
        os.unlink(self._translate(path))

    def entries(self, path):
        found = []
        with os.scandir(self._translate(path)) as scan:
            for item in scan:
                try:
                    info = item.stat(follow_symlinks=False)
                except OSError:
                    continue
                attributes = (winfs.FILE_ATTRIBUTE_REPARSE_POINT
                              if stat.S_ISLNK(info.st_mode)
                              else winfs.FILE_ATTRIBUTE_DIRECTORY
                              if stat.S_ISDIR(info.st_mode) else 0)
                found.append((item.name, attributes, info.st_size, info.st_nlink))
        return found


class WindowsBase(unittest.TestCase):
    """Every test here runs `repo.py` as though this computer were Windows."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.project = Path(self.scratch.name) / "project"
        (self.project / "src").mkdir(parents=True)
        self.write("notes.md", "first line\n")
        self.write("src/app.py", "print('hi')\n")

        self.api = FakeWindows(self.project)
        patches = [
            patch.object(repo, "descriptor_traversal_supported", return_value=False),
            patch.object(winfs, "supported", return_value=True),
            patch.object(winfs, "Api", lambda: self.api),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def write(self, relative, text):
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def sha(self, relative):
        return hashlib.sha256((self.project / relative).read_bytes()).hexdigest()


class TestTheBackendIsSelected(WindowsBase):
    def test_the_windows_backend_answers_when_dir_fd_is_absent(self):
        self.assertEqual(repo.containment_backend(), repo.WINDOWS_BACKEND)
        self.assertTrue(repo.containment_supported())

    def test_neither_backend_means_the_surface_stays_closed(self):
        with patch.object(winfs, "supported", return_value=False):
            self.assertIsNone(repo.containment_backend())
            with self.assertRaises(repo.RepositoryError) as caught:
                repo.read_text_file(self.project, "notes.md")
            self.assertEqual(caught.exception.code, "platform")

    def test_a_runtime_without_the_api_fails_closed_rather_than_falling_back(self):
        def refuse():
            raise winfs.Unavailable("no kernel32 here")
        with patch.object(winfs, "Api", refuse):
            with self.assertRaises(repo.RepositoryError) as caught:
                repo.read_text_file(self.project, "notes.md")
        self.assertEqual(caught.exception.code, "platform")


class TestReading(WindowsBase):
    def test_a_file_reads_with_the_same_identity_the_posix_backend_returns(self):
        text, identity = repo.read_text_file(self.project, "src/app.py")
        self.assertEqual(text, "print('hi')\n")
        self.assertEqual(identity.sha256, self.sha("src/app.py"))
        self.assertEqual(identity.size, len("print('hi')\n"))

    def test_every_open_uses_the_extended_path_form(self):
        repo.read_text_file(self.project, "src/app.py")
        self.assertTrue(self.api.opens)
        for path, *_rest in self.api.opens:
            self.assertTrue(path.startswith("\\\\?\\"), path)

    def test_every_ancestor_stays_open_for_the_whole_read(self):
        """Pinning only the last folder would leave the ones above it free to
        be swapped while the read runs."""
        repo.read_text_file(self.project, "src/app.py")
        # root + src held together, plus the file itself before it is adopted.
        self.assertGreaterEqual(self.api.max_live, 3)

    def test_no_handle_is_left_open_afterwards(self):
        repo.read_text_file(self.project, "src/app.py")
        self.assertEqual(self.api.live, set())

    def test_a_linked_file_is_refused_rather_than_followed(self):
        outside = Path(self.scratch.name) / "secret.txt"
        outside.write_text("not yours\n")
        os.symlink(outside, self.project / "link.md")
        with self.assertRaises(repo.RepositoryError) as caught:
            repo.read_text_file(self.project, "link.md")
        self.assertEqual(caught.exception.code, "symlink")

    def test_a_linked_folder_ends_the_traversal(self):
        outside = Path(self.scratch.name) / "elsewhere"
        outside.mkdir()
        (outside / "app.py").write_text("stolen\n")
        os.symlink(outside, self.project / "linked")
        with self.assertRaises(repo.RepositoryError) as caught:
            repo.read_text_file(self.project, "linked/app.py")
        self.assertEqual(caught.exception.code, "symlink")

    def test_a_missing_file_says_so(self):
        with self.assertRaises(repo.RepositoryError) as caught:
            repo.read_text_file(self.project, "src/absent.py")
        self.assertEqual(caught.exception.code, "missing")

    def test_a_folder_opened_as_a_file_is_refused(self):
        with self.assertRaises(repo.RepositoryError) as caught:
            repo.read_text_file(self.project, "src")
        # Windows refuses the open itself; the POSIX backend refuses after it.
        # Either way nothing is read.
        self.assertIn(caught.exception.code, ("unreadable", "not_regular"))

    def test_a_hard_linked_file_is_refused_on_this_backend_too(self):
        os.link(self.project / "notes.md", self.project / "twin.md")
        with self.assertRaises(repo.RepositoryError) as caught:
            repo.read_text_file(self.project, "twin.md")
        self.assertEqual(caught.exception.code, "hard_link")

    def test_an_oversized_file_is_refused_before_it_is_decoded(self):
        self.write("big.txt", "x" * (repo.MAX_FILE_BYTES + 1))
        with self.assertRaises(repo.RepositoryError) as caught:
            repo.read_text_file(self.project, "big.txt")
        self.assertEqual(caught.exception.code, "too_large")

    def test_binary_and_non_utf8_content_are_refused(self):
        (self.project / "blob.txt").write_bytes(b"ab\x00cd")
        (self.project / "latin.txt").write_bytes(b"caf\xe9\n")
        for name, code in (("blob.txt", "binary"), ("latin.txt", "encoding")):
            with self.subTest(name=name), self.assertRaises(repo.RepositoryError) as caught:
                repo.read_text_file(self.project, name)
            self.assertEqual(caught.exception.code, code)

    def test_traversal_is_refused_before_any_handle_is_opened(self):
        with self.assertRaises(repo.RepositoryError) as caught:
            repo.read_text_file(self.project, "../outside.txt")
        self.assertEqual(caught.exception.code, "traversal")
        self.assertEqual(self.api.opens, [])


class TestListing(WindowsBase):
    def test_the_listing_finds_files_and_keeps_relative_posix_paths(self):
        found = {row["path"] for row in repo.list_text_files(self.project)}
        self.assertEqual(found, {"notes.md", "src/app.py"})

    def test_excluded_folders_are_never_entered(self):
        self.write(".git/config", "[core]\n")
        self.write("node_modules/x/index.js", "1\n")
        found = {row["path"] for row in repo.list_text_files(self.project)}
        self.assertEqual(found, {"notes.md", "src/app.py"})

    def test_links_are_skipped_rather_than_followed(self):
        outside = Path(self.scratch.name) / "elsewhere"
        outside.mkdir()
        (outside / "secret.py").write_text("no\n")
        os.symlink(outside, self.project / "linked")
        os.symlink(outside / "secret.py", self.project / "shortcut.py")
        found = {row["path"] for row in repo.list_text_files(self.project)}
        self.assertEqual(found, {"notes.md", "src/app.py"})

    def test_credential_shaped_names_are_left_out(self):
        self.write(".env", "TOKEN=1\n")
        self.write("server.pem", "----\n")
        found = {row["path"] for row in repo.list_text_files(self.project)}
        self.assertEqual(found, {"notes.md", "src/app.py"})

    def test_the_listing_is_bounded(self):
        for index in range(8):
            self.write(f"many/f{index}.txt", "x\n")
        self.assertEqual(len(repo.list_text_files(self.project, limit=4)), 4)


    def test_the_walk_descends_without_reopening_the_chain_each_time(self):
        """Reopening from the root per folder is O(depth) opens per folder on a
        deep tree; the walk holds each ancestor instead."""
        self.write("a/b/c/d/deep.txt", "x\n")
        repo.list_text_files(self.project)
        opened = [path for path, *_rest in self.api.opens]
        # One open per directory entered (root, a, b, c, d) plus the files.
        self.assertEqual(sum(1 for path in opened if path.endswith("\\a")), 1)
        self.assertEqual(sum(1 for path in opened if path.endswith("\\b")), 1)

    def test_nothing_stays_pinned_after_the_walk(self):
        self.write("a/b/c.txt", "x\n")
        repo.list_text_files(self.project)
        self.assertEqual(self.api.live, set())


class TestReplacing(WindowsBase):
    def test_an_unchanged_file_is_replaced_atomically(self):
        identity = repo.replace_text_file(
            self.project, "notes.md", expected_sha256=self.sha("notes.md"),
            text="second line\n")
        self.assertEqual((self.project / "notes.md").read_text(), "second line\n")
        self.assertEqual(identity.sha256,
                         hashlib.sha256(b"second line\n").hexdigest())

    def test_a_file_that_changed_underneath_is_stale_and_nothing_is_written(self):
        stale = self.sha("notes.md")
        self.write("notes.md", "somebody else wrote this\n")
        with self.assertRaises(repo.RepositoryError) as caught:
            repo.replace_text_file(self.project, "notes.md",
                                   expected_sha256=stale, text="mine\n")
        self.assertEqual(caught.exception.code, "stale")
        self.assertEqual((self.project / "notes.md").read_text(),
                         "somebody else wrote this\n")

    def test_a_linked_target_is_refused_and_its_destination_is_untouched(self):
        outside = Path(self.scratch.name) / "victim.txt"
        outside.write_text("original\n")
        os.symlink(outside, self.project / "link.md")
        with self.assertRaises(repo.RepositoryError) as caught:
            repo.replace_text_file(
                self.project, "link.md",
                expected_sha256=hashlib.sha256(b"original\n").hexdigest(),
                text="overwritten\n")
        self.assertEqual(caught.exception.code, "stale")
        self.assertEqual(outside.read_text(), "original\n")

    def test_no_temporary_file_survives_a_refused_write(self):
        stale = self.sha("notes.md")
        self.write("notes.md", "changed\n")
        with self.assertRaises(repo.RepositoryError):
            repo.replace_text_file(self.project, "notes.md",
                                   expected_sha256=stale, text="mine\n")
        leftovers = [p.name for p in self.project.iterdir()
                     if p.name.startswith(".refinix-")]
        self.assertEqual(leftovers, [])

    def test_a_write_that_fails_midway_leaves_the_original_and_no_temporary(self):
        original = (self.project / "notes.md").read_text()
        broken = FakeWindows(self.project)

        def fail_after_create(*args, **kwargs):
            handle = FakeWindows.open(broken, *args, **kwargs)
            if kwargs.get("disposition") == winfs.CREATE_NEW:
                raise OSError(5, "the disk went away")
            return handle

        with patch.object(winfs, "Api", lambda: broken), \
                patch.object(broken, "open", fail_after_create):
            with self.assertRaises(repo.RepositoryError):
                repo.replace_text_file(self.project, "notes.md",
                                       expected_sha256=self.sha("notes.md"),
                                       text="mine\n")
        self.assertEqual((self.project / "notes.md").read_text(), original)
        self.assertEqual([p.name for p in self.project.iterdir()
                          if p.name.startswith(".refinix-")], [])

    def test_an_unexpected_failure_still_removes_the_temporary_file(self):
        """Not only an OSError. One `finally` covers every way the block can
        end, so a failure this code did not anticipate leaves the folder as it
        was found."""
        original = (self.project / "notes.md").read_text()

        def explode(*args, **kwargs):
            handle = FakeWindows.open(self.api, *args, **kwargs)
            if kwargs.get("disposition") == winfs.CREATE_NEW:
                raise MemoryError("something nobody planned for")
            return handle

        with patch.object(self.api, "open", explode):
            with self.assertRaises(MemoryError):
                repo.replace_text_file(self.project, "notes.md",
                                       expected_sha256=self.sha("notes.md"),
                                       text="mine\n")
        self.assertEqual((self.project / "notes.md").read_text(), original)
        self.assertEqual([p.name for p in self.project.iterdir()
                          if p.name.startswith(".refinix-")], [])

    def test_a_temporary_name_that_already_exists_is_never_deleted(self):
        """The name is random, so a collision is somebody else's file. Removing
        it to clean up after ourselves would delete what we did not create."""
        victim = {}

        def collide(*args, **kwargs):
            if kwargs.get("disposition") == winfs.CREATE_NEW:
                victim["path"] = args[0] if args else kwargs.get("path")
                raise winfs.WindowsError_(winfs.ERROR_FILE_EXISTS, "exists",
                                          "the name already exists")
            return FakeWindows.open(self.api, *args, **kwargs)

        removed = []
        with patch.object(self.api, "open", collide), \
                patch.object(self.api, "unlink", lambda path: removed.append(path)):
            with self.assertRaises(repo.RepositoryError) as caught:
                repo.replace_text_file(self.project, "notes.md",
                                       expected_sha256=self.sha("notes.md"),
                                       text="mine\n")
        self.assertEqual(caught.exception.code, "exists")
        self.assertEqual(removed, [], "a name we did not create must survive")

    def test_an_oversized_replacement_is_refused_before_any_handle_opens(self):
        with self.assertRaises(repo.RepositoryError) as caught:
            repo.replace_text_file(self.project, "notes.md",
                                   expected_sha256=self.sha("notes.md"),
                                   text="x" * (repo.MAX_FILE_BYTES + 1))
        self.assertEqual(caught.exception.code, "too_large")
        self.assertEqual(self.api.opens, [])

    def test_no_handle_is_left_open_after_a_successful_replacement(self):
        repo.replace_text_file(self.project, "notes.md",
                               expected_sha256=self.sha("notes.md"),
                               text="second\n")
        self.assertEqual(self.api.live, set())


class TestRootRules(unittest.TestCase):
    """Root selection, which is shared by both backends."""

    def test_a_windows_system_folder_is_refused(self):
        with patch.object(repo.sys, "platform", "win32"):
            self.assertTrue(repo._is_windows_system_folder(Path("C:/Windows")))
            self.assertTrue(repo._is_windows_system_folder(Path("D:/Program Files")))
            self.assertFalse(repo._is_windows_system_folder(Path("C:/Projects")))
            self.assertFalse(repo._is_windows_system_folder(Path("C:/Users/me/app")))

    def test_the_windows_names_are_not_applied_on_other_platforms(self):
        with patch.object(repo.sys, "platform", "darwin"):
            self.assertFalse(repo._is_windows_system_folder(Path("/Windows")))

    def test_a_reparse_point_is_detected_by_attribute_not_by_is_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            plain = Path(folder) / "plain"
            plain.mkdir()
            self.assertFalse(repo._is_reparse_point(plain))
            # A junction has no POSIX equivalent, so the attribute is supplied
            # the way Windows reports it and the helper must act on it.
            fake = os.stat_result(
                (stat.S_IFDIR | 0o755, 0, 0, 1, 0, 0, 0, 0, 0, 0))
            class WithAttributes:
                st_file_attributes = winfs.FILE_ATTRIBUTE_REPARSE_POINT
                st_mode = fake.st_mode
            with patch.object(repo.os, "lstat", return_value=WithAttributes()):
                self.assertTrue(repo._is_reparse_point(plain))

    def test_a_root_that_became_a_junction_is_not_intact(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "project"
            root.mkdir()
            identity = repo.root_identity(root)
            self.assertTrue(repo.root_is_intact(root, identity))

            class Junction:
                st_mode = stat.S_IFDIR | 0o755
                st_file_attributes = winfs.FILE_ATTRIBUTE_REPARSE_POINT
                st_dev = identity["device"]
                st_ino = identity["inode"]
            with patch.object(repo.os, "stat", return_value=Junction()):
                self.assertFalse(repo.root_is_intact(root, identity))


class TestTheSharedInvariants(unittest.TestCase):
    """Constants the guarantee depends on, asserted rather than assumed."""

    def test_the_share_mask_never_allows_delete(self):
        self.assertFalse(winfs.SHARE_READ_WRITE & FILE_SHARE_DELETE)

    def test_directory_handles_ask_for_no_access_at_all(self):
        self.assertEqual(winfs.METADATA_ONLY, 0)

    def test_the_extended_form_handles_drive_and_unc_paths(self):
        self.assertEqual(winfs.extended(r"C:\work\app"), "\\\\?\\C:\\work\\app")
        self.assertEqual(winfs.extended(r"\\server\share\app"),
                         "\\\\?\\UNC\\server\\share\\app")
        self.assertEqual(winfs.extended("\\\\?\\C:\\already"), "\\\\?\\C:\\already")

    def test_the_backend_is_unavailable_off_windows(self):
        with patch.object(winfs.sys, "platform", "darwin"):
            self.assertFalse(winfs.supported())


if __name__ == "__main__":
    unittest.main(verbosity=2)
