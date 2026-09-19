"""Protected credential storage, on each operating system Refinix supports.

Phase 1 item G. `docs/PROJECT.md` 21.2 and `docs/security.md` 4.1 say the worker
credential must never reach SQLite, a dotfile or the repository: the operating
system owns its protection at rest, and the database holds only the non-secret
half — address, fingerprint, relationship id, paired timestamp. That split is
what lets the workspace database be copied, backed up or inspected without
carrying a bearer token with it.

Until now that rule was implemented once, for macOS, which meant pairing simply
could not happen on Windows or Linux. This module keeps the rule and gives each
platform its own OS-owned store:

* **macOS** — the login Keychain, through the `security` binary that ships with
  the OS. Unchanged, including the service name and the hex encoding, so
  credentials stored by earlier builds are still found.
* **Windows** — Credential Manager, through `CredWriteW`/`CredReadW` in
  `advapi32`. The blob is DPAPI-protected by the OS and scoped to the signed-in
  user profile. `ctypes` reaches it, so no dependency is added.
* **Linux** — the Secret Service (GNOME Keyring, KWallet) through `secret-tool`.
  The secret is passed on stdin, never in `argv`, where any local process could
  read it. This is the one backend with a **host prerequisite**: `secret-tool`
  (Debian/Ubuntu `libsecret-tools`) plus a desktop session running an unlocked
  keyring. No Python dependency is added, but FR-002 requires the graphical
  setup to provision and verify this for the selected Linux Beta profile rather
  than leaving a user to install it from a terminal. Until that exists, Phase 1
  item H owns it and `probe()` reports the gap by name.

**No fallback, on any platform.** Where the OS store is absent — a headless
Linux box without a Secret Service, a container, CI — `CredentialUnavailable`
says so and names the missing prerequisite. A quieter fallback to a file would
put the credential exactly where the decision says it must never be, and a
feature that appears to work by weakening its own boundary is worse than one
that is honestly switched off.

**Every refusal names one prerequisite**, because each needs a different fix.
`probe()` reports which backend this computer has and why not, so the interface
can explain the real reason rather than naming a framework from another OS.

Standard library only.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass

# The macOS Keychain service string, and the Windows/Linux equivalent of it.
# Compatibility-sensitive: renaming it would orphan every credential an earlier
# build stored, so the prototype's name stays even though the product renamed.
SERVICE = "AegisForge worker credential"

# Credential Manager keys on one string, so the account is folded into it.
WINDOWS_TARGET_PREFIX = "Refinix worker credential"

TIMEOUT_SECONDS = 10

# Enough to hold a bearer token and small enough that nothing else fits. A
# bound on a secret is a bound on what a compromised caller can stash in the
# OS store under Refinix's name.
MAX_CREDENTIAL_BYTES = 4096


class CredentialError(Exception):
    """A refusal that is safe to show. Never contains the credential."""


class CredentialUnavailable(CredentialError):
    """No OS credential store on this computer, so there is nowhere legitimate
    to put the credential. Callers must stop, not improvise."""


@dataclass(frozen=True)
class Backend:
    """One platform's store: what it is called, and whether it is here."""

    name: str                   # keychain | credential-manager | secret-service
    label: str                  # the words a person reads
    available: bool
    detail: str


# --------------------------------------------------------------------------
# Shared checks
# --------------------------------------------------------------------------

def _check_account(account: str) -> str:
    if not isinstance(account, str) or not account.strip():
        raise CredentialError("a credential needs a relationship to belong to")
    account = account.strip()
    # The account reaches a command line and a Windows target string. Refusing
    # anything but the id shapes this application mints keeps it from becoming
    # an argument or a separator.
    if len(account) > 128 or any(c in account for c in "\\/:\"'`$ \t\r\n\x00"):
        raise CredentialError("that relationship id cannot name a credential")
    return account


def _check_secret(secret: str) -> str:
    if not isinstance(secret, str) or not secret:
        raise CredentialError("there is no credential to store")
    if len(secret.encode("utf-8")) > MAX_CREDENTIAL_BYTES:
        raise CredentialError("that credential is larger than Refinix stores")
    if "\x00" in secret:
        raise CredentialError("a credential cannot contain a null byte")
    return secret


def _run(argv: list[str], *, stdin: str | None = None,
         runner=None) -> subprocess.CompletedProcess:
    """Run a store's own CLI. Injectable, so no test writes to a real keyring."""
    if runner is not None:
        return runner(argv, stdin)
    return subprocess.run(argv, capture_output=True, text=True,
                          timeout=TIMEOUT_SECONDS, input=stdin, check=False)


# --------------------------------------------------------------------------
# macOS — the login Keychain
# --------------------------------------------------------------------------

class Keychain:
    """The existing macOS path, moved here unchanged in behaviour.

    `security add-generic-password -w` would take the secret as an argument,
    putting it in this process's `argv` where any local process could read it.
    There is no stdin mode, so the value goes as hex through `-X`, which is the
    documented alternative and keeps the plaintext off the command line.
    """

    name = "keychain"
    label = "macOS Keychain"

    def __init__(self, runner=None):
        self._runner = runner

    def probe(self) -> Backend:
        if shutil.which("security") is None:
            return Backend(self.name, self.label, False,
                           "The macOS `security` tool is not on this computer, "
                           "so the Keychain cannot be reached.")
        return Backend(self.name, self.label, True,
                       "Credentials are held in the macOS login Keychain; the "
                       "operating system protects them at rest.")

    def _security(self, *args: str, stdin: str | None = None):
        return _run(["security", *args], stdin=stdin, runner=self._runner)

    def store(self, account: str, secret: str) -> None:
        encoded = secret.encode("utf-8").hex()
        result = self._security("add-generic-password", "-U", "-a", account,
                                "-s", SERVICE, "-X", encoded)
        if result.returncode != 0:
            raise CredentialError(
                "the Keychain refused to store the worker credential")

    def load(self, account: str) -> str:
        result = self._security("find-generic-password", "-a", account,
                                "-s", SERVICE, "-w")
        if result.returncode != 0:
            raise CredentialError("no stored credential for this relationship")
        value = (result.stdout or "").strip()
        try:
            # `-X` stored hex, so `-w` returns hex. A pre-existing plain value
            # is accepted rather than corrupted into nonsense.
            return bytes.fromhex(value).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return value

    def delete(self, account: str) -> bool:
        return self._security("delete-generic-password", "-a", account,
                              "-s", SERVICE).returncode == 0


# --------------------------------------------------------------------------
# Windows — Credential Manager
# --------------------------------------------------------------------------

CRED_TYPE_GENERIC = 1
# Persisted for this user on this computer, and never roamed to another machine
# by a profile service. A credential pinned to one LAN worker has no business
# following the account somewhere else.
CRED_PERSIST_LOCAL_MACHINE = 2


def _windows_api():
    """Bind Credential Manager on demand, never at import.

    A lazy bind keeps this module importable on macOS and on the Linux worker,
    and means a capability probe costs nothing until something actually asks.
    """
    # Every failure mode of binding a Windows-only API from a module that must
    # stay importable on macOS and Linux. `ctypes.wintypes` imports on some
    # non-Windows builds and `ctypes.WinDLL` then does not exist at all, so the
    # import succeeding is not evidence that the rest will work.
    try:
        import ctypes                                          # noqa: PLC0415
        from ctypes import wintypes                            # noqa: PLC0415
        return _bind_credential_manager(ctypes, wintypes)
    except (ImportError, ValueError, AttributeError, OSError) as exc:
        raise CredentialUnavailable(
            "Windows Credential Manager is not reachable on this computer."
        ) from exc


def _bind_credential_manager(ctypes, wintypes):
    class CREDENTIAL(ctypes.Structure):
        _fields_ = [("Flags", wintypes.DWORD),
                    ("Type", wintypes.DWORD),
                    ("TargetName", wintypes.LPWSTR),
                    ("Comment", wintypes.LPWSTR),
                    ("LastWritten", wintypes.FILETIME),
                    ("CredentialBlobSize", wintypes.DWORD),
                    ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
                    ("Persist", wintypes.DWORD),
                    ("AttributeCount", wintypes.DWORD),
                    ("Attributes", ctypes.c_void_p),
                    ("TargetAlias", wintypes.LPWSTR),
                    ("UserName", wintypes.LPWSTR)]

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
    advapi.CredWriteW.restype = wintypes.BOOL
    advapi.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                 wintypes.DWORD,
                                 ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
    advapi.CredReadW.restype = wintypes.BOOL
    advapi.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                   wintypes.DWORD]
    advapi.CredDeleteW.restype = wintypes.BOOL
    advapi.CredFree.argtypes = [ctypes.c_void_p]
    advapi.CredFree.restype = None
    return ctypes, advapi, CREDENTIAL


class CredentialManager:
    """Windows Credential Manager. Source-present; not device-observed.

    Written against the documented `advapi32` surface and exercised here through
    an injected fake, which proves the call sequence and every refusal path but
    not the real API. It stays a Phase 1 foundation claim until a Windows
    profile observes it.
    """

    name = "credential-manager"
    label = "Windows Credential Manager"

    def __init__(self, api=None):
        self._api = api

    def _bind(self):
        return self._api if self._api is not None else _windows_api()

    def _target(self, account: str) -> str:
        return f"{WINDOWS_TARGET_PREFIX}:{account}"

    def probe(self) -> Backend:
        try:
            self._bind()
        except CredentialUnavailable as exc:
            return Backend(self.name, self.label, False, str(exc))
        return Backend(self.name, self.label, True,
                       "Credentials are held in Windows Credential Manager; the "
                       "operating system protects them at rest for this account.")

    def store(self, account: str, secret: str) -> None:
        ctypes, advapi, CREDENTIAL = self._bind()
        blob = secret.encode("utf-8")
        record = CREDENTIAL()
        record.Flags = 0
        record.Type = CRED_TYPE_GENERIC
        record.TargetName = self._target(account)
        record.Comment = None
        record.CredentialBlobSize = len(blob)
        record.CredentialBlob = ctypes.cast(
            ctypes.create_string_buffer(blob, len(blob)),
            ctypes.POINTER(ctypes.c_char))
        record.Persist = CRED_PERSIST_LOCAL_MACHINE
        record.AttributeCount = 0
        record.Attributes = None
        record.TargetAlias = None
        record.UserName = account
        if not advapi.CredWriteW(ctypes.byref(record), 0):
            raise CredentialError(
                "Windows Credential Manager refused to store the worker "
                "credential")

    def load(self, account: str) -> str:
        ctypes, advapi, CREDENTIAL = self._bind()
        pointer = ctypes.POINTER(CREDENTIAL)()
        if not advapi.CredReadW(self._target(account), CRED_TYPE_GENERIC, 0,
                                ctypes.byref(pointer)):
            raise CredentialError("no stored credential for this relationship")
        try:
            record = pointer.contents
            size = int(record.CredentialBlobSize)
            if size <= 0:
                raise CredentialError(
                    "the stored credential for this relationship is empty")
            blob = ctypes.string_at(record.CredentialBlob, size)
        finally:
            # Freed on every path, including the empty-blob refusal above.
            advapi.CredFree(pointer)
        try:
            return blob.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CredentialError(
                "the stored credential for this relationship is unreadable"
            ) from exc

    def delete(self, account: str) -> bool:
        try:
            _ctypes, advapi, _CREDENTIAL = self._bind()
        except CredentialUnavailable:
            return False
        return bool(advapi.CredDeleteW(self._target(account),
                                       CRED_TYPE_GENERIC, 0))


# --------------------------------------------------------------------------
# Linux — the Secret Service
# --------------------------------------------------------------------------

SECRET_TOOL_PACKAGE = "libsecret-tools"


class SecretService:
    """GNOME Keyring / KWallet through `secret-tool`.

    The secret is written to the tool's stdin, never passed as an argument. A
    locked or absent Secret Service is reported, not worked around: there is no
    user session to unlock a keyring on a headless machine, and that is a real
    limitation of the profile rather than something to paper over with a file.
    """

    name = "secret-service"
    label = "Secret Service keyring"
    ATTRIBUTES = ("service", SERVICE)

    def __init__(self, runner=None):
        self._runner = runner

    def probe(self) -> Backend:
        if shutil.which("secret-tool") is None:
            return Backend(
                self.name, self.label, False,
                "This computer has no `secret-tool`, so the desktop keyring "
                f"cannot be reached. Install {SECRET_TOOL_PACKAGE} and sign in "
                "to a desktop session with a keyring.")
        return Backend(self.name, self.label, True,
                       "Credentials are held in the desktop keyring through the "
                       "Secret Service; the keyring protects them at rest.")

    def _tool(self, *args: str, stdin: str | None = None):
        return _run(["secret-tool", *args], stdin=stdin, runner=self._runner)

    def _attributes(self, account: str) -> list[str]:
        return [*self.ATTRIBUTES, "account", account]

    def store(self, account: str, secret: str) -> None:
        result = self._tool("store", "--label", f"{SERVICE} ({account})",
                            *self._attributes(account), stdin=secret)
        if result.returncode != 0:
            raise CredentialError(
                "the desktop keyring refused to store the worker credential; "
                "it may be locked")

    def load(self, account: str) -> str:
        result = self._tool("lookup", *self._attributes(account))
        if result.returncode != 0:
            raise CredentialError("no stored credential for this relationship")
        # `secret-tool lookup` writes the secret with no trailing newline, but a
        # keyring that stored one must not have it silently removed from the
        # value, so only the newline the tool itself adds is stripped.
        value = result.stdout or ""
        if value.endswith("\n"):
            value = value[:-1]
        if not value:
            raise CredentialError("no stored credential for this relationship")
        return value

    def delete(self, account: str) -> bool:
        return self._tool("clear", *self._attributes(account)).returncode == 0


# --------------------------------------------------------------------------
# Picking the platform's store
# --------------------------------------------------------------------------

class NoStore:
    """A platform with no OS credential store Refinix knows how to use."""

    name = "none"
    label = "no OS credential store"

    def __init__(self, platform: str):
        self._platform = platform

    def probe(self) -> Backend:
        return Backend(self.name, self.label, False,
                       f"Refinix has no protected credential store for "
                       f"{self._platform!r}, and it will not keep a worker "
                       "credential in the database or a file instead.")

    def _refuse(self):
        raise CredentialUnavailable(self.probe().detail)

    def store(self, account: str, secret: str) -> None:
        self._refuse()

    def load(self, account: str) -> str:
        self._refuse()

    def delete(self, account: str) -> bool:
        return False


def backend_for(platform: str | None = None, *, runner=None, api=None):
    """The store this platform uses. An object, so a caller can inject a fake."""
    platform = sys.platform if platform is None else platform
    if platform == "darwin":
        return Keychain(runner=runner)
    if platform == "win32":
        return CredentialManager(api=api)
    if platform.startswith("linux"):
        return SecretService(runner=runner)
    # Deliberately not "anything else POSIX". The three required desktop
    # families each have a store above; guessing that an unlisted platform
    # speaks the Secret Service would be a support claim made by a fallback.
    return NoStore(platform)


def probe(platform: str | None = None, *, runner=None, api=None) -> dict:
    """What this computer can actually protect a credential with, and why not.

    An observation rather than a default: reaching a store starts no service and
    opens no socket, and a name here is not a claim that the profile is
    qualified.
    """
    state = backend_for(platform, runner=runner, api=api).probe()
    return {"available": state.available, "backend": state.name,
            "label": state.label, "detail": state.detail}


def available(platform: str | None = None, *, runner=None, api=None) -> bool:
    return probe(platform, runner=runner, api=api)["available"]


def _ready(platform, runner, api):
    store = backend_for(platform, runner=runner, api=api)
    state = store.probe()
    if not state.available:
        raise CredentialUnavailable(state.detail)
    return store


def store_credential(account: str, secret: str, *, platform: str | None = None,
                     runner=None, api=None) -> None:
    """Hand the credential to the OS. Raises rather than storing it anywhere
    Refinix controls."""
    store = _ready(platform, runner, api)
    store.store(_check_account(account), _check_secret(secret))


def load_credential(account: str, *, platform: str | None = None,
                    runner=None, api=None) -> str:
    store = _ready(platform, runner, api)
    return store.load(_check_account(account))


def delete_credential(account: str, *, platform: str | None = None,
                      runner=None, api=None) -> bool:
    """True when a credential was removed. A missing store is False, not an
    error: revocation must never be blocked by the store being gone."""
    try:
        store = _ready(platform, runner, api)
    except CredentialUnavailable:
        return False
    try:
        return store.delete(_check_account(account))
    except CredentialError:
        return False
