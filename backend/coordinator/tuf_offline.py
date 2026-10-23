"""Signed update metadata checked again without the network and without the clock.

Shared by the update client's kept-evidence check (`updates.verify_evidence`)
and the Ubuntu package step that runs as root (`desktop/deb_root.py`), so both
authenticate a kept download the same way:

* root versions are walked one at a time from a trusted anchor: each must be
  exactly the next version and meet both the old and the new root's
  thresholds, and the walk must reach the newest root this computer already
  trusts (`continue_to`) — a missing link refuses;
* timestamp, snapshot and targets must be signed by the newest root's keys;
* the version links timestamp → snapshot → targets, and any recorded lengths
  and hashes, must hold.

Expiry is deliberately not judged here: it was judged, with the full TUF
client, when the metadata was downloaded or admitted.

Imports only the TUF metadata API.
"""

from __future__ import annotations

import hashlib


class OfflineError(RuntimeError):
    pass


def metadata(data: bytes, role: str):
    from tuf.api.metadata import Metadata
    try:
        item = Metadata.from_bytes(data)
    except Exception as exc:                               # noqa: BLE001
        raise OfflineError(f"Kept {role} metadata cannot be read: {exc}") from exc
    if item.signed.type != role:
        raise OfflineError(f"Kept {role} metadata is of another kind.")
    return item


def next_root(current, data: bytes):
    """One step of root rotation: exactly the next version, both thresholds met."""
    item = metadata(data, "root")
    if item.signed.version != current.signed.version + 1:
        raise OfflineError("The kept root versions are not consecutive.")
    try:
        current.signed.verify_delegate("root", item.signed_bytes, item.signatures)
        item.signed.verify_delegate("root", item.signed_bytes, item.signatures)
    except Exception as exc:                               # noqa: BLE001
        raise OfflineError(f"A kept root is not properly signed: {exc}") from exc
    return item


def walk_roots(anchor: bytes, newer) -> tuple[object, list[str]]:
    """The newest root reached from `anchor` through `newer` (bytes, in order),
    and the SHA-256 of every root on the way, anchor first."""
    root = metadata(anchor, "root")
    seen = [hashlib.sha256(anchor).hexdigest()]
    for data in newer:
        root = next_root(root, data)
        seen.append(hashlib.sha256(data).hexdigest())
    return root, seen


def continue_to(root, trusted_bytes: bytes, next_bytes, *,
                allow_newer: bool = False) -> tuple[object, list[str]]:
    """Carry `root` on to the newest root this computer already trusts.

    `next_bytes(version)` returns that root version's bytes, or None when it
    is not kept. Every version between must be present and properly signed,
    and the walk must end on exactly the trusted root's signed bytes: a
    missing or damaged link refuses rather than leaving older keys (perhaps
    since revoked) in charge. With `allow_newer`, a chain that is already past
    the trusted root (a download newer than the local state) is accepted as is.
    Returns the root reached and the SHA-256 of each root added on the way.
    """
    trusted = metadata(trusted_bytes, "root")
    seen = []
    if root.signed.version > trusted.signed.version and not allow_newer:
        raise OfflineError("The kept update keys are newer than this computer's trusted "
                           "keys; the trust state looks damaged.")
    while root.signed.version < trusted.signed.version:
        version = root.signed.version + 1
        data = next_bytes(version)
        if data is None:
            raise OfflineError(f"Trusted root {version} is missing or unreadable, so the "
                               "update keys cannot be followed to the newest ones.")
        root = next_root(root, data)
        seen.append(hashlib.sha256(data).hexdigest())
    if root.signed.version == trusted.signed.version \
            and root.signed_bytes != trusted.signed_bytes:
        raise OfflineError("The kept roots end on different keys than this computer "
                           "trusts.")
    return root, seen


def verify_roles(root, timestamp_bytes: bytes, snapshot_bytes: bytes,
                 targets_bytes: bytes) -> tuple:
    """Timestamp, snapshot and targets signed under `root` and linked together."""
    signed = {}
    for role, data in (("timestamp", timestamp_bytes), ("snapshot", snapshot_bytes),
                       ("targets", targets_bytes)):
        item = metadata(data, role)
        try:
            root.signed.verify_delegate(role, item.signed_bytes, item.signatures)
        except Exception as exc:                           # noqa: BLE001
            raise OfflineError(f"The kept {role} metadata is not signed by the trusted "
                               f"keys: {exc}") from exc
        signed[role] = item
    timestamp, snapshot, targets = signed["timestamp"], signed["snapshot"], signed["targets"]
    try:
        link = timestamp.signed.snapshot_meta
        if link.version != snapshot.signed.version:
            raise OfflineError("The kept snapshot is not the one its timestamp names.")
        if link.length is not None or link.hashes:
            link.verify_length_and_hashes(snapshot_bytes)
        link = snapshot.signed.meta.get("targets.json")
        if link is None or link.version != targets.signed.version:
            raise OfflineError("The kept targets metadata is not the one its snapshot "
                               "names.")
        if link.length is not None or link.hashes:
            link.verify_length_and_hashes(targets_bytes)
    except OfflineError:
        raise
    except Exception as exc:                               # noqa: BLE001
        raise OfflineError(f"The kept metadata does not link up: {exc}") from exc
    return timestamp, snapshot, targets
