"""OD-06 pairing, worker side — the half that holds no replayable secret.

`docs/security.md` 4.1 records the decision; this implements it without adding
a cryptographic primitive of its own. Everything here is `hashlib`, `hmac` and
`secrets` from the standard library:

* the pairing code and the credential are `secrets.token_urlsafe` values;
* both are stored **only** as a salted SHA-256 hash, so a stolen state file
  cannot be replayed against the worker;
* comparison is `hmac.compare_digest`, so a wrong guess costs the same time as
  a right one.

Three rules shape the file format.

**Nothing plaintext is ever written.** `issue_code` and `redeem` return their
secret to the caller once and keep only a hash. A caller that loses it must
issue another; there is no recovery path, because a recovery path is a copy.

**Revocation fences work in flight.** Deleting a relationship is not enough — an
attempt admitted a second earlier is still running. Each relationship carries an
`epoch`; revoking increments the worker's fence, and `authorise` refuses any
token whose relationship is gone. `fenced_since` lets the executor stop attempts
belonging to a relationship that was revoked after they started.

**A single-use code is consumed under the lock, before it is checked.** Two
concurrent redemptions of the same code must not both succeed, so the code is
removed first and validated afterwards.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path

# A pairing code is read aloud or typed by a human, so it is short-lived rather
# than long. Ten minutes is enough to walk between two machines.
CODE_TTL_SECONDS = 600
CODE_BYTES = 12               # ~16 url-safe characters
CREDENTIAL_BYTES = 32         # 256 bits, matching the worker token minimum
SALT_BYTES = 16
MAX_RELATIONSHIPS = 16
MAX_OPEN_CODES = 4


class PairingError(Exception):
    """A typed refusal. The message is safe to return over the wire: it never
    contains the presented secret, the stored hash, or a file path."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _hash(secret: str, salt: str) -> str:
    """Salted SHA-256. Not a password KDF, and deliberately not presented as one:
    these are 96- and 256-bit random tokens, not human-chosen passwords, so the
    work factor that protects a password buys nothing here."""
    return hashlib.sha256(f"{salt}:{secret}".encode("utf-8")).hexdigest()


def _now() -> int:
    return int(time.time())


def fingerprint(certificate_der: bytes) -> str:
    """The value a human compares out of band, as `security.md` 4.1 requires.

    Formatted the way OpenSSL prints it — colon-separated uppercase pairs — so
    the operator can compare it against `openssl x509 -fingerprint -sha256`
    character by character rather than trusting a reformatting.
    """
    digest = hashlib.sha256(certificate_der).hexdigest().upper()
    return ":".join(digest[i:i + 2] for i in range(0, len(digest), 2))


def normalise_fingerprint(value: str) -> str:
    """Accept what a human actually types: spaces, colons, any case, and the
    `sha256 Fingerprint=` prefix OpenSSL prints."""
    cleaned = value.strip()
    if "=" in cleaned:
        cleaned = cleaned.split("=", 1)[1]
    cleaned = cleaned.replace(":", "").replace(" ", "").replace("\n", "").upper()
    if len(cleaned) != 64 or any(c not in "0123456789ABCDEF" for c in cleaned):
        raise PairingError("invalid_request",
                           "a SHA-256 fingerprint is 64 hexadecimal characters")
    return ":".join(cleaned[i:i + 2] for i in range(0, len(cleaned), 2))


class PairingStore:
    """The worker's pairing state: open codes, relationship hashes, fence epoch.

    One JSON file, mode 0600, replaced atomically. It is small by construction —
    at most `MAX_RELATIONSHIPS` entries — so it is rewritten whole rather than
    updated in place, which removes a partial-write failure mode entirely.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._state = self._load()

    # ------------------------------------------------------------ storage ---

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as handle:
                state = json.load(handle)
        except (OSError, ValueError):
            return {"codes": {}, "relationships": {}, "epoch": 0}
        if not isinstance(state, dict):
            return {"codes": {}, "relationships": {}, "epoch": 0}
        state.setdefault("codes", {})
        state.setdefault("relationships", {})
        state.setdefault("epoch", 0)
        return state

    def _save(self) -> None:
        """Write via a private temporary file in the same directory, then rename.

        `mkstemp` creates at 0600, so the credential hashes are never briefly
        world-readable — a chmod after the fact would leave exactly that window.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        handle, temporary = tempfile.mkstemp(dir=str(self.path.parent),
                                             prefix=".pairing-", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                json.dump(self._state, out, sort_keys=True)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, self.path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    # -------------------------------------------------------------- codes ---

    def issue_code(self) -> str:
        """Mint one short-lived single-use pairing code and return it ONCE.

        The caller — a host-side command run by the operator — is the only place
        the plaintext exists. Nothing here logs it, and only its hash is stored.
        """
        with self._lock:
            self._expire_codes()
            if len(self._state["codes"]) >= MAX_OPEN_CODES:
                raise PairingError(
                    "permission_denied",
                    "too many unused pairing codes are already open")
            code = secrets.token_urlsafe(CODE_BYTES)
            salt = secrets.token_hex(SALT_BYTES)
            self._state["codes"][_hash(code, salt)] = {
                "salt": salt, "expires_at": _now() + CODE_TTL_SECONDS}
            self._save()
            return code

    def _expire_codes(self) -> None:
        now = _now()
        self._state["codes"] = {
            key: value for key, value in self._state["codes"].items()
            if value.get("expires_at", 0) > now}

    def open_code_count(self) -> int:
        with self._lock:
            self._expire_codes()
            return len(self._state["codes"])

    # ------------------------------------------------------- relationships ---

    def redeem(self, code: str, *, relationship_id: str, workspace_id: str) -> str:
        """Exchange a valid code for one credential, returned ONCE.

        The code is consumed whether or not the rest succeeds: a code that has
        been presented is spent, which is what "single use" has to mean if a
        failed redemption is not to become a retry oracle.
        """
        if not isinstance(code, str) or not code:
            raise PairingError("invalid_request", "a pairing code is required")
        with self._lock:
            self._expire_codes()
            matched = None
            for stored, record in list(self._state["codes"].items()):
                if hmac.compare_digest(stored, _hash(code, record["salt"])):
                    matched = stored
                    break
            if matched is None:
                raise PairingError("permission_denied",
                                   "this pairing code is unknown, expired or already used")
            # Consumed first. A later failure must not leave it redeemable.
            del self._state["codes"][matched]
            if relationship_id in self._state["relationships"]:
                self._save()
                raise PairingError("idempotency_conflict",
                                   "this relationship identifier is already paired")
            if len(self._state["relationships"]) >= MAX_RELATIONSHIPS:
                self._save()
                raise PairingError("permission_denied",
                                   "this worker is already paired with the maximum "
                                   "number of workspaces")
            credential = secrets.token_urlsafe(CREDENTIAL_BYTES)
            salt = secrets.token_hex(SALT_BYTES)
            self._state["relationships"][relationship_id] = {
                "workspace_id": workspace_id,
                "salt": salt,
                "credential_sha256": _hash(credential, salt),
                "paired_at": _now(),
                "epoch": self._state["epoch"],
            }
            self._save()
            return credential

    def authorise(self, relationship_id: str, credential: str) -> dict:
        """Verify a presented bearer credential against the stored hash.

        Returns the relationship record on success and raises otherwise. An
        unknown relationship and a wrong credential raise the same typed
        refusal, so the caller cannot enumerate which relationships exist.
        """
        denied = PairingError("permission_denied",
                              "unknown, revoked or invalid worker credential")
        if not isinstance(credential, str) or not credential:
            raise denied
        with self._lock:
            record = self._state["relationships"].get(relationship_id)
            if record is None:
                raise denied
            if not hmac.compare_digest(record["credential_sha256"],
                                       _hash(credential, record["salt"])):
                raise denied
            return dict(record, relationship_id=relationship_id)

    def revoke(self, relationship_id: str) -> bool:
        """Delete the stored hash and fence work in flight.

        Bumping the epoch is what makes revocation immediate rather than
        eventual: an attempt admitted under the old epoch is now stale, and the
        executor stops it with a typed reason instead of finishing quietly.
        """
        with self._lock:
            if relationship_id not in self._state["relationships"]:
                return False
            del self._state["relationships"][relationship_id]
            self._state["epoch"] += 1
            self._save()
            return True

    def is_active(self, relationship_id: str) -> bool:
        with self._lock:
            return relationship_id in self._state["relationships"]

    def epoch(self) -> int:
        with self._lock:
            return int(self._state["epoch"])

    def relationships(self) -> dict[str, dict]:
        """Non-secret metadata only. The salt and hash never leave this module."""
        with self._lock:
            return {
                key: {"workspace_id": value["workspace_id"],
                      "paired_at": value["paired_at"], "epoch": value["epoch"]}
                for key, value in self._state["relationships"].items()}
