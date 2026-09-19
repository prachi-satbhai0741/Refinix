"""Where durable data lives, checked for all three OS families on one computer.

The point of these checks is that a Windows or Linux root can be wrong in a way
nobody notices until that device arrives. `platform_root` and `select_root` take
the platform, environment and home explicitly for exactly this reason, so the
layout each OS gets is asserted here rather than assumed.

The other half is what resolution must **not** do: it creates no directory,
moves nothing, and never silently picks between two canonical stores.

    python -m unittest backend.coordinator.test_paths
"""

from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from backend.coordinator import paths


class PlatformRoots(unittest.TestCase):
    """`docs/PROJECT.md` 12.4, one row at a time."""

    HOME = Path("/home/example")
    MAC_HOME = Path("/Users/example")

    def test_macos_uses_application_support(self):
        self.assertEqual(
            paths.platform_root(platform="darwin", environ={}, home=self.MAC_HOME),
            self.MAC_HOME / "Library/Application Support/Refinix")

    def test_windows_uses_local_appdata(self):
        self.assertEqual(
            paths.platform_root(platform="win32", home=self.HOME,
                                environ={"LOCALAPPDATA": r"C:\Users\ex\AppData\Local"}),
            Path(r"C:\Users\ex\AppData\Local") / "Refinix")

    def test_windows_without_local_appdata_stays_in_the_user_profile(self):
        """A broken environment is not a reason to leave the profile."""
        self.assertEqual(
            paths.platform_root(platform="win32", environ={}, home=self.HOME),
            self.HOME / "AppData/Local/Refinix")

    def test_linux_uses_the_xdg_default(self):
        self.assertEqual(
            paths.platform_root(platform="linux", environ={}, home=self.HOME),
            self.HOME / ".local/share/refinix")

    def test_linux_honours_an_absolute_xdg_data_home(self):
        self.assertEqual(
            paths.platform_root(platform="linux", home=self.HOME,
                                environ={"XDG_DATA_HOME": "/data/example"}),
            Path("/data/example/refinix"))

    def test_a_relative_environment_path_is_ignored_not_resolved(self):
        """A root resolved against the working directory would follow whichever
        folder the application happened to be launched from."""
        for value in ("relative/share", "", "   ", "~/share"):
            with self.subTest(value=value):
                self.assertEqual(
                    paths.platform_root(platform="linux", home=self.HOME,
                                        environ={"XDG_DATA_HOME": value}),
                    self.HOME / ".local/share/refinix")

    def test_an_unknown_platform_still_gets_the_posix_layout(self):
        self.assertEqual(
            paths.platform_root(platform="freebsd14", environ={}, home=self.HOME),
            self.HOME / ".local/share/refinix")

    def test_the_legacy_root_keeps_its_prototype_name(self):
        """12.5: the directory name does not follow the product rename."""
        self.assertEqual(paths.legacy_root(home=self.HOME),
                         self.HOME / ".aegisforge")


class PortableProfile(unittest.TestCase):
    def test_a_chosen_folder_gains_the_refinix_component(self):
        self.assertEqual(paths.portable_root("/Volumes/Stick"),
                         Path("/Volumes/Stick/.refinix"))

    def test_choosing_the_refinix_folder_itself_is_not_nested_twice(self):
        self.assertEqual(paths.portable_root("/Volumes/Stick/.refinix"),
                         Path("/Volumes/Stick/.refinix"))

    def test_a_relative_portable_folder_is_refused(self):
        with self.assertRaises(paths.DataRootError) as caught:
            paths.portable_root("stick")
        self.assertEqual(caught.exception.code, "relative_root")


class Subdirectories(unittest.TestCase):
    def test_every_defined_name_resolves_under_the_root(self):
        for name in paths.SUBDIRECTORIES:
            with self.subTest(name=name):
                self.assertEqual(paths.subdirectory("/root", name),
                                 Path("/root") / name)

    def test_an_undefined_name_is_refused_rather_than_joined(self):
        with self.assertRaises(paths.DataRootError) as caught:
            paths.subdirectory("/root", "../escape")
        self.assertEqual(caught.exception.code, "unknown_subdirectory")

    def test_the_defined_names_cover_what_the_application_already_writes(self):
        """db.py derives these three from the database's parent today."""
        self.assertLessEqual({"artifacts", "attachments", "backups"},
                             set(paths.SUBDIRECTORIES))


class OccupiedRoots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_a_root_with_no_database_holds_no_state(self):
        self.assertIsNone(paths.database_in(self.root))
        self.assertFalse(paths.holds_state(self.root))

    def test_a_zero_byte_database_alone_is_not_a_store(self):
        """`sqlite3` against a missing path leaves one behind, and this
        computer has exactly such a leftover from an archived handoff."""
        (self.root / paths.DATABASE_NAME).touch()
        self.assertIsNone(paths.database_in(self.root))
        self.assertFalse(paths.holds_state(self.root))

    def test_a_zero_byte_database_is_reported_as_residue_not_dropped(self):
        (self.root / paths.DATABASE_NAME).touch()
        held = paths.inspect_root(self.root)
        self.assertIn(f"{paths.DATABASE_NAME} (empty)", held.residue)

    def test_content_beside_an_empty_database_still_makes_it_a_workspace(self):
        """12.5 protects content and credentials, not one file. A root holding
        someone's artifacts is theirs even when the database is residue."""
        (self.root / paths.DATABASE_NAME).touch()
        artifacts = self.root / paths.ARTIFACTS
        artifacts.mkdir()
        (artifacts / "approval-note.docx").write_bytes(b"PK\x03\x04")
        self.assertTrue(paths.holds_state(self.root))
        self.assertIn(paths.ARTIFACTS, paths.inspect_root(self.root).populated)

    def test_each_durable_subdirectory_makes_a_root_occupied_on_its_own(self):
        for name in (paths.ARTIFACTS, paths.ATTACHMENTS, paths.BACKUPS,
                     paths.CORPUS, paths.MODEL_MANIFESTS):
            with self.subTest(name=name):
                root = Path(self.tmp.name) / name
                (root / name).mkdir(parents=True)
                (root / name / "content").write_bytes(b"x")
                self.assertTrue(paths.holds_state(root))

    def test_written_instructions_and_memory_make_a_root_occupied(self):
        """A user wrote these; losing them by selecting the other store is the
        same harm as losing chats."""
        for name in paths.STATE_FILES:
            with self.subTest(name=name):
                root = Path(self.tmp.name) / f"state-{name}"
                root.mkdir()
                (root / name).write_text("do not lose me")
                self.assertTrue(paths.holds_state(root))

    def test_an_empty_subdirectory_is_residue_not_content(self):
        (self.root / paths.ARTIFACTS).mkdir()
        held = paths.inspect_root(self.root)
        self.assertFalse(held.occupied)
        self.assertIn(f"{paths.ARTIFACTS}/ (empty)", held.residue)

    def test_a_stray_file_is_listed_but_does_not_block_startup(self):
        """A pinned worker certificate someone placed by hand is exactly this
        case on the macOS target root. Refusing to start over it would be a
        worse failure than reporting it."""
        (self.root / "ubuntu-worker.crt").write_bytes(b"-----BEGIN CERT-----")
        held = paths.inspect_root(self.root)
        self.assertFalse(held.occupied)
        self.assertIn("ubuntu-worker.crt", held.residue)

    def test_desktop_metadata_is_not_even_residue(self):
        (self.root / ".DS_Store").write_bytes(b"\x00\x01")
        self.assertEqual(paths.inspect_root(self.root).residue, ())

    def test_the_summary_names_what_was_found(self):
        (self.root / paths.DATABASE_NAME).write_bytes(b"SQLite format 3\x00")
        (self.root / paths.BACKUPS).mkdir()
        (self.root / paths.BACKUPS / "original.py").write_text("x")
        summary = paths.inspect_root(self.root).summary()
        self.assertIn(paths.DATABASE_NAME, summary)
        self.assertIn("backups/", summary)

    def test_an_empty_root_summarises_as_nothing_durable(self):
        self.assertEqual(paths.inspect_root(self.root).summary(),
                         "nothing durable")

    def test_a_populated_database_is_a_store(self):
        database = self.root / paths.DATABASE_NAME
        database.write_bytes(b"SQLite format 3\x00")
        self.assertEqual(paths.database_in(self.root), database)
        self.assertTrue(paths.holds_state(self.root))

    def test_every_plausible_rename_of_the_database_also_counts(self):
        """So a rename cannot quietly become a store this reads as empty."""
        for name in paths.ALTERNATE_DATABASE_NAMES:
            with self.subTest(name=name):
                root = Path(self.tmp.name) / f"alt-{name}"
                root.mkdir()
                (root / name).write_bytes(b"SQLite format 3\x00")
                self.assertEqual(paths.database_in(root), root / name)
                self.assertTrue(paths.holds_state(root))

    def test_a_missing_root_is_empty_rather_than_an_error(self):
        self.assertIsNone(paths.database_in(self.root / "absent"))

    @unittest.skipIf(os.name != "posix", "POSIX permission bits")
    def test_owner_only_is_observed_not_enforced(self):
        os.chmod(self.root, 0o700)
        self.assertTrue(paths.owner_only(self.root))
        os.chmod(self.root, 0o755)
        self.assertFalse(paths.owner_only(self.root))
        # Observing did not change it back.
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o755)


class Selection(unittest.TestCase):
    """Which of the possible roots an installation actually uses."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.legacy = paths.legacy_root(home=self.home)
        self.native = paths.platform_root(platform="darwin", environ={},
                                          home=self.home)

    def occupy(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / paths.DATABASE_NAME).write_bytes(b"SQLite format 3\x00")

    def select(self, **environ):
        return paths.select_root(platform="darwin", environ=environ,
                                 home=self.home)

    def test_a_new_installation_uses_the_platform_root(self):
        chosen = self.select()
        self.assertEqual(chosen.path, self.native)
        self.assertEqual(chosen.source, "platform")
        self.assertTrue(chosen.ok)

    def test_an_existing_legacy_store_keeps_being_used(self):
        """12.5: moving it is a separate versioned migration, so it stays."""
        self.occupy(self.legacy)
        chosen = self.select()
        self.assertEqual(chosen.path, self.legacy)
        self.assertEqual(chosen.source, "legacy")
        self.assertIn("separate versioned migration", chosen.detail)

    def test_an_explicit_override_wins_over_both(self):
        self.occupy(self.legacy)
        override = self.home / "portable" / ".refinix"
        chosen = self.select(**{paths.ROOT_ENVIRONMENT_VARIABLE: str(override)})
        self.assertEqual(chosen.path, override)
        self.assertEqual(chosen.source, "override")

    def test_a_relative_override_is_ignored(self):
        chosen = self.select(**{paths.ROOT_ENVIRONMENT_VARIABLE: "somewhere"})
        self.assertEqual(chosen.source, "platform")

    def test_two_occupied_roots_are_a_conflict_not_a_choice(self):
        self.occupy(self.legacy)
        self.occupy(self.native)
        chosen = self.select()
        self.assertFalse(chosen.ok)
        self.assertIsInstance(chosen.conflict, paths.DataRootConflict)
        self.assertEqual(chosen.conflict.code, "two_stores")

    def test_the_conflict_names_both_paths_and_the_way_out(self):
        self.occupy(self.legacy)
        self.occupy(self.native)
        message = str(self.select().conflict)
        self.assertIn(str(self.legacy), message)
        self.assertIn(str(self.native), message)
        self.assertIn(paths.ROOT_ENVIRONMENT_VARIABLE, message)

    def test_an_override_resolves_a_conflict_because_it_is_the_answer(self):
        self.occupy(self.legacy)
        self.occupy(self.native)
        chosen = self.select(**{paths.ROOT_ENVIRONMENT_VARIABLE: str(self.legacy)})
        self.assertTrue(chosen.ok)
        self.assertEqual(chosen.path, self.legacy)

    def test_require_root_raises_where_select_root_reports(self):
        self.occupy(self.legacy)
        self.occupy(self.native)
        with self.assertRaises(paths.DataRootConflict) as caught:
            paths.require_root(platform="darwin", environ={}, home=self.home)
        self.assertEqual(caught.exception.legacy, self.legacy)
        self.assertEqual(caught.exception.platform, self.native)

    def test_a_conflict_can_be_caused_by_content_rather_than_a_database(self):
        """The case the first implementation missed: a root holding a user's
        artifacts but no usable database is still their workspace."""
        self.occupy(self.legacy)
        self.native.mkdir(parents=True)
        (self.native / paths.DATABASE_NAME).touch()          # residue
        (self.native / paths.ARTIFACTS).mkdir()
        (self.native / paths.ARTIFACTS / "note.docx").write_bytes(b"PK\x03\x04")
        chosen = self.select()
        self.assertFalse(chosen.ok)
        self.assertIn("artifacts/", str(chosen.conflict))

    def test_stray_content_in_the_target_root_does_not_block_startup(self):
        """This computer's real state: a zero-byte database and a hand-placed
        certificate in the macOS root, with the workspace in the legacy one."""
        self.occupy(self.legacy)
        self.native.mkdir(parents=True)
        (self.native / "refinix.db").touch()
        (self.native / "ubuntu-worker.crt").write_bytes(b"-----BEGIN CERT-----")
        chosen = self.select()
        self.assertTrue(chosen.ok)
        self.assertEqual(chosen.path, self.legacy)

    def test_what_was_in_the_root_not_chosen_is_reported_not_dropped(self):
        """So "the other root looked empty" is checkable rather than a silent
        classification."""
        self.occupy(self.legacy)
        self.native.mkdir(parents=True)
        (self.native / "ubuntu-worker.crt").write_bytes(b"-----BEGIN CERT-----")
        chosen = self.select()
        self.assertIn("ubuntu-worker.crt", chosen.unselected_residue)
        self.assertIn("ubuntu-worker.crt", chosen.as_dict()["unselected_residue"])

    def test_resolution_creates_nothing(self):
        """db.py makes the directory with mode 0o700 when it opens the
        database. Creating it here would leave empty roots proving nothing."""
        self.select()
        self.assertFalse(self.native.exists())
        self.assertFalse(self.legacy.exists())

    def test_the_database_is_inside_the_selected_root(self):
        chosen = self.select()
        self.assertEqual(chosen.database, chosen.path / paths.DATABASE_NAME)
        self.assertEqual(
            paths.state_path(platform="darwin", environ={}, home=self.home),
            chosen.database)

    def test_the_report_carries_the_reason_and_never_a_path_it_did_not_pick(self):
        chosen = self.select()
        payload = chosen.as_dict()
        self.assertEqual(payload["source"], "platform")
        self.assertEqual(payload["path"], str(self.native))
        self.assertIsNone(payload["conflict"])
        self.assertIn("macOS", payload["detail"])

    def test_each_platform_reports_its_own_name(self):
        for platform, label in (("darwin", "macOS"), ("win32", "Windows"),
                                ("linux", "Linux")):
            with self.subTest(platform=platform):
                chosen = paths.select_root(platform=platform, environ={},
                                           home=self.home)
                self.assertIn(label, chosen.detail)


if __name__ == "__main__":
    unittest.main()
