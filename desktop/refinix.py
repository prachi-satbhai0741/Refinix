"""Entry point of the packaged app (py2app on macOS, PyInstaller on Windows and Linux).

Both launch a script, not a module, so this is the package's main script. It
does exactly what `python3 -m desktop` does with default arguments, and two
more things for in-app updates:

* `Refinix --apply-update|--resume <database>` runs the update helper
  (desktop/update_apply.py) — no window, no interface — from a clone of the
  app that started it;
* `Refinix --deb-admit|--deb-install|--deb-recover|--deb-rollback <folder>`,
  started only by pkexec on Ubuntu, runs the root package step
  (desktop/deb_root.py) and nothing else;
* before anything opens the workspace, a launch asks the update journal what
  it may do (`update_apply.on_launch`): continue, hand an unfinished update
  back to a helper, or explain why an update stopped safely.

Anything else on the command line is refused before the workspace opens. The
development entry's `--no-window`, `--port` and `--state` do not exist here, and
silently ignoring them once opened a person's real data folder during a smoke
check. To run a packaged build against other data, set the absolute folder in
`REFINIX_DATA_ROOT` (backend/coordinator/paths.py) instead.
"""

import sys

# Loose application modules live inside the bundle so the package verifier can
# compare them with source. Keep a launch from modifying that immutable package
# with __pycache__ files.
sys.dont_write_bytecode = True


def _helper(argv) -> int:
    from desktop import update_apply
    return update_apply.helper_main(argv)


def _update_gate(instance, state_db):
    from backend.coordinator import build_info, updates
    from desktop import update_apply
    try:
        return update_apply.on_launch(instance, state_db, build_info.describe()["version"],
                                      bundle=updates.running_install())
    except Exception as exc:                               # noqa: BLE001
        # Opening the workspace beside an update journal that cannot be read
        # could undo the update's protection; stop and say so instead.
        return update_apply.Gate(proceed=False, message=(
            "Refinix could not check an update that may be unfinished, so it did "
            f"not open your workspace: {exc}"))


# Ubuntu `.deb` updates: the only steps that run as root. Dispatched before
# anything else is imported, so as root nothing opens a window, the workspace,
# the coordinator or a model runtime (desktop/deb_root.py).
DEB_ROOT_MODES = ("--deb-admit", "--deb-install", "--deb-recover", "--deb-rollback")


HELPER_MODES = ("--apply-update", "--resume")


def unsupported_arguments(argv) -> list[str]:
    """Arguments an ordinary launch does not understand.

    Older macOS versions add `-psn_<n>_<n>` when Finder opens an app; that one
    is the system's, not a request, and is ignored.
    """
    return [arg for arg in argv if not arg.startswith("-psn_")]


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in DEB_ROOT_MODES:
        from desktop import deb_root
        return deb_root.main(sys.argv[1:])
    if len(sys.argv) > 1 and sys.argv[1] in HELPER_MODES:
        return _helper(sys.argv[1:])
    unknown = unsupported_arguments(sys.argv[1:])
    if unknown:
        # Refused before any import that resolves or opens the workspace.
        sys.stderr.write(f"Refinix: unsupported option(s) {' '.join(unknown)}. The "
                         "packaged app takes no options; to use another data folder, "
                         "set REFINIX_DATA_ROOT to its absolute path.\n")
        return 2
    # An interrupted setup may not have copied native application dependencies yet.
    from backend.coordinator import ownership, paths
    state_db = paths.select_root().database
    instance = ownership.WorkspaceLock.for_database(state_db)
    existing = instance.acquire()
    if existing is not None:
        # LSMultipleInstancesProhibited normally prevents this; the lock covers
        # a copy started another way, for example from the command line.
        port = existing.get("port")
        if not isinstance(port, int):
            return 0
        from desktop import lifecycle
        if lifecycle.identify_occupant(port):
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
        gate = _update_gate(instance, state_db)
        if not gate.proceed:
            if gate.message:
                if sys.platform == "win32":
                    from desktop import update_apply
                    update_apply.System().tell("Refinix update", gate.message)
                else:
                    from desktop import shell
                    shell._native_message("Refinix update", gate.message)
            return 0
        from desktop import lifecycle, shell
        return shell.run(owner=instance, update_gate=gate,
                         on_started=lambda startup: instance.record(
                             port=startup.port, mode="bundle"))
    finally:
        instance.release()


if __name__ == "__main__":
    sys.exit(main())
