"""Host-side pairing command: show the fingerprint, mint one code.

Run by the operator on the Ubuntu worker, not by the coordinator and not over
the network. It exists because OD-06 requires both values to travel **out of
band, read by a human** — so they must be obtainable without the application
printing them anywhere an application log can reach.

Three deliberate properties:

* **Nothing is logged.** Both values go to stdout and only to stdout. There is
  no logging call in this module, and it never writes to the pairing file except
  through `PairingStore`, which stores a hash.
* **The code is shown once.** `PairingStore.issue_code` returns it once and
  keeps a salted hash; re-running mints a *new* code rather than reprinting the
  old one, because reprinting would mean it had been stored in the clear.
* **`--json` still refuses to emit a secret unless asked.** `fingerprint` and
  `status` are safe to capture in a transcript; `code` is not, and says so on
  stderr so a copied transcript carries the warning.

    python -m backend.worker.pairing_cli fingerprint --cert /path/tls.crt
    python -m backend.worker.pairing_cli code
    python -m backend.worker.pairing_cli status
    python -m backend.worker.pairing_cli revoke <relationship_id>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from backend.worker import pairing as pairing_module

DEFAULT_STATE = "/var/lib/aegisforge/pairing.json"
DEFAULT_CERT = "/etc/aegisforge/tls/tls.crt"


def _der_from_file(path: Path) -> bytes:
    """Accept the PEM the operator actually has, or raw DER.

    `ssl.PEM_cert_to_DER_cert` is the standard library's own converter, so the
    fingerprint here is the same bytes OpenSSL hashes — that equality is the
    entire point of the value.
    """
    raw = path.read_bytes()
    if b"-----BEGIN CERTIFICATE-----" not in raw:
        return raw
    import ssl
    return ssl.PEM_cert_to_DER_cert(raw.decode("ascii", "strict"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aegisforge-pair",
        description="OD-06 pairing values for this worker host.")
    parser.add_argument("--state", default=os.environ.get("AEGIS_PAIRING_STATE",
                                                          DEFAULT_STATE))
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("fingerprint",
                          help="print the certificate SHA-256 to compare by hand")
    show.add_argument("--cert", default=os.environ.get("AEGIS_TLS_CERT", DEFAULT_CERT))

    sub.add_parser("code", help="mint one short-lived single-use pairing code")
    sub.add_parser("status", help="paired relationships and open codes (no secrets)")
    revoke = sub.add_parser("revoke", help="delete a relationship and fence its work")
    revoke.add_argument("relationship_id")

    args = parser.parse_args(argv)
    store = pairing_module.PairingStore(Path(args.state))

    if args.command == "fingerprint":
        path = Path(args.cert)
        if not path.exists():
            sys.stderr.write(
                f"no certificate at {path}. Generate the worker's self-signed "
                "certificate first; see docs/worker-operations.md.\n")
            return 2
        print(pairing_module.fingerprint(_der_from_file(path)))
        return 0

    if args.command == "code":
        try:
            code = store.issue_code()
        except pairing_module.PairingError as exc:
            sys.stderr.write(f"{exc.message}\n")
            return 1
        sys.stderr.write(
            "This code is shown once, is single-use, and expires in "
            f"{pairing_module.CODE_TTL_SECONDS // 60} minutes. "
            "Do not paste it into a ticket, a chat or a saved transcript.\n")
        print(code)
        return 0

    if args.command == "status":
        # Metadata only: no salt, no hash, no code, no credential.
        print(json.dumps({"relationships": store.relationships(),
                          "open_codes": store.open_code_count(),
                          "epoch": store.epoch()}, indent=2, sort_keys=True))
        return 0

    if args.command == "revoke":
        removed = store.revoke(args.relationship_id)
        sys.stderr.write("revoked\n" if removed else "no such relationship\n")
        # Restart the worker and the executor so nothing in flight survives the
        # revocation; the fence is recorded either way.
        return 0 if removed else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
