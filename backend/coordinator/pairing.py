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
the operating system's own credential store — no dependency, no bespoke crypto,
and the OS owns the at-rest protection. What SQLite holds is the non-secret half:
node address, fingerprint, relationship ID, paired timestamp. That split is what
lets the database be copied, backed up or inspected without carrying the bearer
token with it.

`credentials.py` owns which store that is per platform: the macOS Keychain,
Windows Credential Manager or the Secret Service keyring on Linux. This module
keeps the pairing-facing names, so the rule reads the same at every call site as
it did when only macOS had an implementation.

Where the platform has no such store (a headless Linux box, a container, CI),
`KeychainUnavailable` is raised rather than silently falling back to a file. A
quieter fallback would put the credential exactly where the decision says it must
never be.
"""

from __future__ import annotations

import hashlib
import json
import ssl

from backend.coordinator import credentials

# Kept as re-exports: callers and existing checks refer to them through this
# module, and the values themselves are compatibility-sensitive.
SERVICE = credentials.SERVICE
KEYCHAIN_TIMEOUT = credentials.TIMEOUT_SECONDS


class PairingError(Exception):
    """A refusal that is safe to show. Never contains the credential."""


class KeychainUnavailable(PairingError):
    """No OS credential store on this host, so there is nowhere legitimate to
    put the credential. Callers must stop, not improvise.

    Still a `PairingError`, so every existing caller that handles pairing
    failures keeps handling this one. The name predates Windows and Linux
    support and is kept because the callers and the interface use it.
    """


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


# ---------------------------------------------------- credential storage ---
# `credentials.py` owns the per-platform store. These names stay because the
# callers, the status payload and the interface copy all use them, and because a
# rename here would be a change to the pairing contract rather than to storage.

def keychain_available() -> bool:
    """Whether this computer has an OS credential store Refinix will use.

    The name is historical; the answer is now per platform. `credential_store()`
    is the one to report to a person, because it names which store and why not.
    """
    return credentials.available()


def credential_store() -> dict:
    """Which protected store this computer has, and why not if it has none.

    An observation the interface can show instead of naming a framework from
    another operating system.
    """
    return credentials.probe()


def store_credential(relationship_id: str, credential: str) -> None:
    """Hand the credential to the OS store, replacing any prior value."""
    try:
        credentials.store_credential(relationship_id, credential)
    except credentials.CredentialUnavailable as exc:
        raise KeychainUnavailable(str(exc)) from exc
    except credentials.CredentialError as exc:
        raise PairingError(str(exc)) from exc


def load_credential(relationship_id: str) -> str:
    try:
        return credentials.load_credential(relationship_id)
    except credentials.CredentialUnavailable as exc:
        raise KeychainUnavailable(str(exc)) from exc
    except credentials.CredentialError as exc:
        raise PairingError(str(exc)) from exc


def delete_credential(relationship_id: str) -> bool:
    """True when a credential was removed. A store that is absent returns False
    rather than raising: revocation must not be blocked by the store being gone."""
    return credentials.delete_credential(relationship_id)


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
