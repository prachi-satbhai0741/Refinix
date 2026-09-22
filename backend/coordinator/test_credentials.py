"""Protected credential storage, checked for all three OS families here.

Two things these checks are for.

**The boundary holds on every platform.** A store that is absent must refuse,
and the refusal must name *that* computer's missing prerequisite. Nothing may
fall back to a file, and nothing may put the secret on a command line where any
local process could read it — so the arguments each backend builds are asserted,
not just its return value.

**The Windows path is exercised, not merely written.** `FakeAdvapi` stands in
for `advapi32` while the real `ctypes` does the marshalling, so the call
sequence, the blob round trip and every refusal are checked on this computer.
That proves the logic; it does not prove the real API. Windows Credential
Manager stays source-present until a Windows profile observes it.

    python -m unittest backend.coordinator.test_credentials
"""

from __future__ import annotations

import ctypes
import subprocess
import unittest
from unittest import mock

from backend.coordinator import credentials

ACCOUNT = "rel-0123456789abcdef"
SECRET = "a-bearer-token-value"


class Recorder:
    """A stand-in for `subprocess.run` that remembers what it was asked."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.calls: list[tuple[list[str], str | None]] = []
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr

    def __call__(self, argv, stdin):
        self.calls.append((list(argv), stdin))
        return subprocess.CompletedProcess(argv, self.returncode,
                                           self.stdout, self.stderr)

    @property
    def argv(self) -> list[str]:
        return self.calls[-1][0]

    @property
    def stdin(self):
        return self.calls[-1][1]


# --------------------------------------------------------------------------
# Choosing a backend
# --------------------------------------------------------------------------

class BackendSelection(unittest.TestCase):
    def test_each_required_os_family_has_its_own_store(self):
        for platform, expected in (("darwin", credentials.Keychain),
                                   ("win32", credentials.CredentialManager),
                                   ("linux", credentials.SecretService)):
            with self.subTest(platform=platform):
                self.assertIsInstance(credentials.backend_for(platform), expected)

    def test_an_unlisted_platform_gets_no_store_rather_than_a_guess(self):
        """Assuming an unknown OS speaks the Secret Service would be a support
        claim made by a fallback."""
        store = credentials.backend_for("freebsd14")
        self.assertIsInstance(store, credentials.NoStore)
        self.assertFalse(store.probe().available)

    def test_no_store_refuses_instead_of_writing_somewhere_else(self):
        with self.assertRaises(credentials.CredentialUnavailable):
            credentials.store_credential(ACCOUNT, SECRET, platform="freebsd14")
        with self.assertRaises(credentials.CredentialUnavailable):
            credentials.load_credential(ACCOUNT, platform="freebsd14")

    def test_deleting_without_a_store_is_false_not_an_error(self):
        """Revocation must never be blocked by the store being gone."""
        self.assertFalse(
            credentials.delete_credential(ACCOUNT, platform="freebsd14"))


# --------------------------------------------------------------------------
# macOS
# --------------------------------------------------------------------------

class KeychainBackend(unittest.TestCase):
    def store(self, runner):
        return credentials.Keychain(runner=runner)

    def test_the_secret_never_appears_on_the_command_line(self):
        """`security` has no stdin mode, so the value goes as hex through -X.
        Anything else would put it in argv, which any local process can read."""
        runner = Recorder()
        self.store(runner).store(ACCOUNT, SECRET)
        self.assertNotIn(SECRET, runner.argv)
        self.assertNotIn(SECRET, " ".join(runner.argv))
        self.assertIn(SECRET.encode("utf-8").hex(), runner.argv)

    def test_storing_replaces_a_prior_value_rather_than_adding_one(self):
        runner = Recorder()
        self.store(runner).store(ACCOUNT, SECRET)
        self.assertIn("-U", runner.argv)
        self.assertIn(credentials.SERVICE, runner.argv)
        self.assertIn(ACCOUNT, runner.argv)

    def test_a_refused_write_is_reported_not_swallowed(self):
        with self.assertRaises(credentials.CredentialError):
            self.store(Recorder(returncode=1)).store(ACCOUNT, SECRET)

    def test_a_stored_value_round_trips(self):
        runner = Recorder(stdout=SECRET.encode("utf-8").hex() + "\n")
        self.assertEqual(self.store(runner).load(ACCOUNT), SECRET)

    def test_a_pre_existing_plain_value_is_read_not_corrupted(self):
        """Entries written before the hex encoding must still work."""
        runner = Recorder(stdout="plain-legacy-value\n")
        self.assertEqual(self.store(runner).load(ACCOUNT), "plain-legacy-value")

    def test_a_missing_entry_is_a_refusal(self):
        with self.assertRaises(credentials.CredentialError):
            self.store(Recorder(returncode=1)).load(ACCOUNT)

    def test_the_service_name_is_the_prototype_one(self):
        """Renaming it would orphan every credential an earlier build stored."""
        self.assertEqual(credentials.SERVICE, "AegisForge worker credential")

    def test_availability_follows_the_security_tool(self):
        with mock.patch.object(credentials.shutil, "which", return_value=None):
            state = credentials.Keychain().probe()
        self.assertFalse(state.available)
        self.assertIn("security", state.detail)

    def test_this_computer_reports_its_real_store(self):
        """An observation of the machine the checks are running on."""
        state = credentials.probe("darwin")
        self.assertEqual(state["backend"], "keychain")
        self.assertIn("macOS", state["label"])


# --------------------------------------------------------------------------
# Linux
# --------------------------------------------------------------------------

class SecretServiceBackend(unittest.TestCase):
    def store(self, runner):
        return credentials.SecretService(runner=runner)

    def present(self):
        return mock.patch.object(credentials.shutil, "which",
                                 return_value="/usr/bin/secret-tool")

    def test_the_secret_goes_on_stdin_and_never_into_argv(self):
        runner = Recorder()
        self.store(runner).store(ACCOUNT, SECRET)
        self.assertEqual(runner.stdin, SECRET)
        self.assertNotIn(SECRET, " ".join(runner.argv))

    def test_the_entry_is_keyed_by_service_and_account(self):
        runner = Recorder()
        self.store(runner).store(ACCOUNT, SECRET)
        self.assertIn("service", runner.argv)
        self.assertIn(credentials.SERVICE, runner.argv)
        self.assertIn("account", runner.argv)
        self.assertIn(ACCOUNT, runner.argv)

    def test_a_locked_keyring_is_reported_not_worked_around(self):
        with self.assertRaises(credentials.CredentialError) as caught:
            self.store(Recorder(returncode=1)).store(ACCOUNT, SECRET)
        self.assertIn("locked", str(caught.exception))

    def test_a_stored_value_round_trips_without_its_trailing_newline(self):
        runner = Recorder(stdout=SECRET + "\n")
        self.assertEqual(self.store(runner).load(ACCOUNT), SECRET)

    def test_an_empty_lookup_is_a_refusal_not_an_empty_credential(self):
        with self.assertRaises(credentials.CredentialError):
            self.store(Recorder(stdout="\n")).load(ACCOUNT)

    def test_clearing_reports_whether_anything_was_removed(self):
        self.assertTrue(self.store(Recorder()).delete(ACCOUNT))
        self.assertFalse(self.store(Recorder(returncode=1)).delete(ACCOUNT))

    def test_a_missing_secret_tool_names_the_package_to_install(self):
        with mock.patch.object(credentials.shutil, "which", return_value=None):
            state = credentials.SecretService().probe()
        self.assertFalse(state.available)
        self.assertIn(credentials.SECRET_TOOL_PACKAGE, state.detail)

    def test_an_available_keyring_says_the_os_protects_it(self):
        with self.present():
            state = credentials.probe("linux")
        self.assertTrue(state["available"])
        self.assertEqual(state["backend"], "secret-service")


# --------------------------------------------------------------------------
# Windows
# --------------------------------------------------------------------------

class CREDENTIAL(ctypes.Structure):
    """The same field names the real binding uses, in host-portable types.

    `wintypes` is not dependable off Windows, and the code only assigns and
    reads these attributes, so an equivalent layout exercises the real
    marshalling without needing the Windows type aliases.
    """

    _fields_ = [("Flags", ctypes.c_uint32),
                ("Type", ctypes.c_uint32),
                ("TargetName", ctypes.c_wchar_p),
                ("Comment", ctypes.c_wchar_p),
                ("LastWritten", ctypes.c_uint64),
                ("CredentialBlobSize", ctypes.c_uint32),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
                ("Persist", ctypes.c_uint32),
                ("AttributeCount", ctypes.c_uint32),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", ctypes.c_wchar_p),
                ("UserName", ctypes.c_wchar_p)]


class FakeAdvapi:
    """Credential Manager's documented surface, in memory.

    Real `ctypes` does the pointer work on both sides, so the blob really is
    marshalled out of a buffer and read back out of one.
    """

    def __init__(self, *, writable=True, blob_override=None,
                 max_persist=credentials.CRED_PERSIST_LOCAL_MACHINE):
        self.entries: dict[str, bytes] = {}
        self.writable = writable
        self.blob_override = blob_override
        self.max_persist = max_persist
        self.freed = 0
        self._alive: list = []

    def CredWriteW(self, reference, flags):
        if not self.writable:
            return 0
        record = reference._obj
        size = int(record.CredentialBlobSize)
        self.entries[record.TargetName] = ctypes.string_at(
            record.CredentialBlob, size)
        self.persist = int(record.Persist)
        self.type = int(record.Type)
        return 1

    def CredReadW(self, target, type_, flags, out):
        if target not in self.entries:
            if hasattr(ctypes, "set_last_error"):
                ctypes.set_last_error(credentials.ERROR_NOT_FOUND)
            return 0
        blob = (self.entries[target] if self.blob_override is None
                else self.blob_override)
        buffer = ctypes.create_string_buffer(blob, len(blob))
        record = CREDENTIAL()
        record.TargetName = target
        record.CredentialBlobSize = len(blob)
        record.CredentialBlob = ctypes.cast(buffer,
                                            ctypes.POINTER(ctypes.c_char))
        pointer = ctypes.pointer(record)
        # Held so the caller's read happens against live memory.
        self._alive.append((buffer, record, pointer))
        holder = ctypes.cast(out, ctypes.POINTER(ctypes.POINTER(CREDENTIAL)))
        holder[0] = pointer
        return 1

    def CredDeleteW(self, target, type_, flags):
        return 1 if self.entries.pop(target, None) is not None else 0

    def CredGetSessionTypes(self, count, out):
        values = ctypes.cast(out, ctypes.POINTER(ctypes.c_uint32))
        for index in range(count):
            values[index] = self.max_persist
        return 1

    def CredFree(self, pointer):
        self.freed += 1


class CredentialManagerBackend(unittest.TestCase):
    def store(self, advapi):
        return credentials.CredentialManager(api=(ctypes, advapi, CREDENTIAL))

    def test_a_stored_credential_round_trips_through_the_blob(self):
        advapi = FakeAdvapi()
        store = self.store(advapi)
        store.store(ACCOUNT, SECRET)
        self.assertEqual(store.load(ACCOUNT), SECRET)

    def test_probe_checks_the_logon_session_not_only_the_binding(self):
        state = self.store(FakeAdvapi()).probe()
        self.assertTrue(state.available)

        state = self.store(FakeAdvapi(max_persist=1)).probe()
        self.assertFalse(state.available)
        self.assertIn("session-only", state.detail)

    def test_the_entry_is_generic_and_stays_on_this_computer(self):
        """A credential pinned to one LAN worker must not roam to another
        machine with the profile."""
        advapi = FakeAdvapi()
        self.store(advapi).store(ACCOUNT, SECRET)
        self.assertEqual(advapi.type, credentials.CRED_TYPE_GENERIC)
        self.assertEqual(advapi.persist, credentials.CRED_PERSIST_LOCAL_MACHINE)

    def test_the_target_names_refinix_and_the_relationship(self):
        advapi = FakeAdvapi()
        self.store(advapi).store(ACCOUNT, SECRET)
        target, = advapi.entries
        self.assertIn(credentials.WINDOWS_TARGET_PREFIX, target)
        self.assertIn(ACCOUNT, target)

    def test_a_refused_write_is_reported_not_swallowed(self):
        with self.assertRaises(credentials.CredentialError):
            self.store(FakeAdvapi(writable=False)).store(ACCOUNT, SECRET)

    def test_a_missing_entry_is_a_refusal(self):
        with self.assertRaises(credentials.CredentialError):
            self.store(FakeAdvapi()).load(ACCOUNT)

    def test_an_empty_blob_is_refused_and_still_freed(self):
        advapi = FakeAdvapi(blob_override=b"")
        store = self.store(advapi)
        store.store(ACCOUNT, SECRET)
        with self.assertRaises(credentials.CredentialError):
            store.load(ACCOUNT)
        self.assertEqual(advapi.freed, 1, "the credential was not freed")

    def test_an_unreadable_blob_is_refused_and_still_freed(self):
        advapi = FakeAdvapi(blob_override=b"\xff\xfe\x00 not utf-8")
        store = self.store(advapi)
        store.store(ACCOUNT, SECRET)
        with self.assertRaises(credentials.CredentialError):
            store.load(ACCOUNT)
        self.assertEqual(advapi.freed, 1)

    def test_a_successful_read_frees_the_credential_too(self):
        advapi = FakeAdvapi()
        store = self.store(advapi)
        store.store(ACCOUNT, SECRET)
        store.load(ACCOUNT)
        self.assertEqual(advapi.freed, 1)

    def test_deleting_reports_whether_anything_was_removed(self):
        advapi = FakeAdvapi()
        store = self.store(advapi)
        store.store(ACCOUNT, SECRET)
        self.assertTrue(store.delete(ACCOUNT))
        self.assertFalse(store.delete(ACCOUNT))

    def test_binding_off_windows_is_unavailable_rather_than_an_exception(self):
        with mock.patch.object(
                credentials, "_windows_api",
                side_effect=credentials.CredentialUnavailable(
                    "Windows Credential Manager is unavailable")):
            state = credentials.CredentialManager().probe()
        self.assertFalse(state.available)
        self.assertIn("Credential Manager", state.detail)

    def test_deleting_without_a_binding_is_false_not_an_error(self):
        with mock.patch.object(
                credentials, "_windows_api",
                side_effect=credentials.CredentialUnavailable("unavailable")):
            self.assertFalse(credentials.delete_credential(
                ACCOUNT, platform="win32"))


# --------------------------------------------------------------------------
# What every backend refuses before it reaches the store
# --------------------------------------------------------------------------

class InputBounds(unittest.TestCase):
    def store(self, account, secret=SECRET):
        with mock.patch.object(credentials.shutil, "which",
                               return_value="/usr/bin/security"):
            credentials.store_credential(account, secret, platform="darwin",
                                         runner=Recorder())

    def test_an_empty_relationship_cannot_own_a_credential(self):
        for account in ("", "   ", None):
            with self.subTest(account=account):
                with self.assertRaises(credentials.CredentialError):
                    self.store(account)

    def test_an_account_cannot_carry_separators_into_a_command_or_a_target(self):
        for account in ("rel id", "rel/../other", "rel\\other", "rel:other",
                        "rel\nother", "rel\x00other", 'rel"other'):
            with self.subTest(account=account):
                with self.assertRaises(credentials.CredentialError):
                    self.store(account)

    def test_an_over_long_account_is_refused(self):
        with self.assertRaises(credentials.CredentialError):
            self.store("r" * 129)

    def test_an_empty_credential_is_refused(self):
        with self.assertRaises(credentials.CredentialError):
            self.store(ACCOUNT, "")

    def test_a_credential_larger_than_the_bound_is_refused(self):
        oversized = "x" * (credentials.MAX_CREDENTIAL_BYTES + 1)
        with self.assertRaises(credentials.CredentialError):
            self.store(ACCOUNT, oversized)

    def test_a_credential_cannot_contain_a_null_byte(self):
        with self.assertRaises(credentials.CredentialError):
            self.store(ACCOUNT, "before\x00after")

    def test_a_valid_account_and_secret_reach_the_store(self):
        runner = Recorder()
        with mock.patch.object(credentials.shutil, "which",
                               return_value="/usr/bin/security"):
            credentials.store_credential(ACCOUNT, SECRET, platform="darwin",
                                         runner=runner)
        self.assertEqual(len(runner.calls), 1)


class Reporting(unittest.TestCase):
    def test_every_platform_reports_a_backend_name_and_a_reason(self):
        for platform in ("darwin", "win32", "linux", "freebsd14"):
            with self.subTest(platform=platform):
                state = credentials.probe(platform)
                self.assertIn("available", state)
                self.assertTrue(state["backend"])
                self.assertTrue(state["detail"].strip())

    def test_an_unavailable_store_names_its_own_prerequisite(self):
        """A Windows computer must not be told to fix a macOS framework."""
        windows = credentials.probe("win32")["detail"]
        self.assertNotIn("Keychain", windows)
        with mock.patch.object(credentials.shutil, "which", return_value=None):
            linux = credentials.probe("linux")["detail"]
        self.assertNotIn("Keychain", linux)
        self.assertNotIn("Credential Manager", linux)


if __name__ == "__main__":
    unittest.main()
