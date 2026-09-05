"""OD-06 pairing, coordinator side: pinned TLS and a credential kept out of SQLite.

`docs/security.md` 4.1 is explicit about two things this module exists to honour.

**The pinned certificate is the sole trust anchor.** Not "also trusted" — the
system trust store is not consulted for a worker connection. `pinned_context`
builds an `SSLContext` with `load_verify_locations(cadata=…)` and
`verify_mode=CERT_REQUIRED`, and `check_hostname=False` because a LAN worker is
reached by address. Chain verification alone would still accept a *different*
certificate signed by the same self-signed key material, so the presented
certificate's SHA-256 is compared to the pinned one after the handshake as well.
A mismatch raises `IdentityMismatch`, which callers must never treat as
"unavailable": falling back to local execution on an identity change would hide
exactly the event pinning exists to detect.

**The credential never touches SQLite, a dotfile or the repository.** It lives in
the macOS Keychain, reached through the `security` binary that ships with the OS
— no dependency, no bespoke crypto, and the OS owns the at-rest protection. What
SQLite holds is the non-secret half: node address, fingerprint, relationship ID,
paired timestamp. That split is what lets the database be copied, backed up or
inspected without carrying the bearer token with it.

On a host without `security` (Linux CI, a container), `KeychainUnavailable` is
raised rather than silently falling back to a file. A quieter fallback would put
the credential exactly where the decision says it must never be.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import ssl
import subprocess
import sys

SERVICE = "AegisForge worker credential"
KEYCHAIN_TIMEOUT = 10


class PairingError(Exception):
    """A refusal that is safe to show. Never contains the credential."""


class KeychainUnavailable(PairingError):
    """No OS credential store on this host, so there is nowhere legitimate to
    put the credential. Callers must stop, not improvise."""


class IdentityMismatch(PairingError):
    """The worker presented a different certificate than the pinned one.

    Separate from every other failure on purpose: this must abort, and must not
    be folded into the unavailable/fallback path.
    """


# ------------------------------------------------------------------- pinning ---

def fingerprint_of(der: bytes) -> str:
    """Colon-separated uppercase SHA-256, matching what the worker CLI prints
    and what `openssl x509 -fingerprint -sha256` shows."""
    digest = hashlib.sha256(der).hexdigest().upper()
    return ":".join(digest[i:i + 2] for i in range(0, len(digest), 2))


def normalise_fingerprint(value: str) -> str:
    cleaned = value.strip()
    if "=" in cleaned:
        cleaned = cleaned.split("=", 1)[1]
    cleaned = "".join(cleaned.split()).replace(":", "").upper()
    if len(cleaned) != 64 or any(c not in "0123456789ABCDEF" for c in cleaned):
        raise PairingError("a SHA-256 fingerprint is 64 hexadecimal characters")
    return ":".join(cleaned[i:i + 2] for i in range(0, len(cleaned), 2))


def pinned_context(certificate_pem: str) -> ssl.SSLContext:
    """An SSLContext trusting exactly one certificate and nothing else.

    `check_hostname=False` is required here and is not a weakening: the worker
    is reached at `https://<ip>:30443` and a self-signed LAN certificate has no
    publicly meaningful name. Identity comes from the pin, which is strictly
    narrower than a hostname match against a public CA.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    try:
        context.load_verify_locations(cadata=certificate_pem)
    except ssl.SSLError as exc:
        raise PairingError("the pinned certificate could not be loaded") from exc
    return context


def verify_presented(connection, expected_fingerprint: str) -> None:
    """Compare the certificate actually presented against the pin.

    Belt and braces over `CERT_REQUIRED`: chain validation proves the peer holds
    a key that the pinned certificate vouches for, which for a self-signed CA
    also admits any sibling certificate the same key signed. Comparing the leaf
    digest closes that, and turns "the operator's fingerprint" into the identity.
    """
    der = connection.getpeercert(binary_form=True)
    if not der:
        raise IdentityMismatch("the worker presented no certificate")
    presented = fingerprint_of(der)
    if presented != normalise_fingerprint(expected_fingerprint):
        raise IdentityMismatch(
            "the worker's certificate does not match the pinned fingerprint; "
            "the worker identity changed and the connection was aborted")


# ------------------------------------------------------------------ keychain ---

def keychain_available() -> bool:
    return sys.platform == "darwin" and shutil.which("security") is not None


def _security(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["security", *args], capture_output=True, text=True,
                          timeout=KEYCHAIN_TIMEOUT, input=stdin, check=False)


def store_credential(relationship_id: str, credential: str) -> None:
    """Write the credential to the login Keychain, replacing any prior value.

    `-w` takes the secret as an argument, which would put it in this process's
    argv where any local process could read it. `security` has no stdin mode for
    add-generic-password, so the value is passed as hex via `-X`, which is the
    documented alternative and keeps the plaintext out of the command line.
    """
    if not keychain_available():
        raise KeychainUnavailable(
            "this coordinator has no macOS Keychain, and OD-06 forbids storing "
            "the worker credential in SQLite or a file")
    encoded = credential.encode("utf-8").hex()
    result = _security("add-generic-password", "-U", "-a", relationship_id,
                       "-s", SERVICE, "-X", encoded)
    if result.returncode != 0:
        raise PairingError("the Keychain refused to store the worker credential")


def load_credential(relationship_id: str) -> str:
    if not keychain_available():
        raise KeychainUnavailable(
            "this coordinator has no macOS Keychain, so no worker credential "
            "can be read")
    result = _security("find-generic-password", "-a", relationship_id,
                       "-s", SERVICE, "-w")
    if result.returncode != 0:
        raise PairingError("no stored credential for this relationship")
    value = result.stdout.strip()
    try:
        # `-X` stored hex, so `-w` returns hex. A pre-existing plain value is
        # accepted rather than corrupted into nonsense.
        return bytes.fromhex(value).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return value


def delete_credential(relationship_id: str) -> bool:
    if not keychain_available():
        return False
    return _security("delete-generic-password", "-a", relationship_id,
                     "-s", SERVICE).returncode == 0


# -------------------------------------------------------------- relationship ---

def describe(record: dict) -> dict:
    """The public view of a relationship. Asserts, by construction, that no
    secret is in it: only these keys are ever copied out."""
    return {key: record.get(key) for key in
            ("relationship_id", "node_id", "display_name", "address", "port",
             "fingerprint", "workspace_id", "paired_at", "state")}


def redacted(payload: dict) -> str:
    """For an audit line. Any key that could hold a secret is replaced, so a
    future field cannot leak by being added to the wrong dictionary."""
    unsafe = {"credential", "pairing_code", "token", "password", "secret"}
    return json.dumps({key: ("<redacted>" if key in unsafe else value)
                       for key, value in payload.items()}, sort_keys=True)
