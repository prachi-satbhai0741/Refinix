"""py2app entry point for Refinix.app.

py2app launches a script, not a module, so this is the bundle's main script. It
does exactly what `python3 -m desktop` does with default arguments.
"""

import sys

from desktop import lifecycle, shell


def main() -> int:
    instance = lifecycle.SingleInstance()
    existing = instance.acquire()
    if existing is not None:
        # LSMultipleInstancesProhibited normally prevents this; the lock covers
        # a copy started another way, for example from the command line.
        port = existing.get("port")
        if isinstance(port, int) and lifecycle.identify_occupant(port):
            import urllib.request
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/v1/desktop/focus", data=b"{}",
                method="POST", headers={"Content-Type": "application/json",
                                        "Host": f"127.0.0.1:{port}"})
            try:
                urllib.request.build_opener(
                    urllib.request.ProxyHandler({})).open(request, timeout=5)
            except OSError:
                pass
        return 0
    try:
        instance.record(port=None, mode="starting")
        return shell.run(on_started=lambda startup: instance.record(
            port=startup.port, mode="bundle"))
    finally:
        instance.release()


if __name__ == "__main__":
    sys.exit(main())
