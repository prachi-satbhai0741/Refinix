"""Which computer this is, in the words the product is allowed to use.

Refinix had two device labels written into its source as constants: models
found on the local runtime were reported as living on the "macOS coordinator",
and models on a paired execution agent on the "Ubuntu worker". Both were true
of the two machines the prototype was built on and of nothing else.
`docs/PROJECT.md` 6 is explicit that coordinator and worker are *runtime
responsibilities, not fixed OS assignments*, and 25 requires Windows, macOS and
Linux to be equally ordinary. A Windows installation that told its user a model
was installed on the "macOS coordinator" would be stating something false about
the machine in front of them.

This module is where a device label comes from instead. Two rules shape it:

* **The local machine is named by its role, not by its operating system.**
  `HERE` is "this computer" everywhere a location is shown, because that is
  the fact the sentence actually needs and it is true on all three OS
  families. The operating system is reported separately, as an observation,
  for the places that genuinely want it.
* **Everything observed is observed, never assumed.** `describe()` reads
  `platform` and reports what it got. A value the standard library cannot
  supply is reported as unknown rather than filled in with a plausible one.

`platform.machine()` and friends read the running interpreter's view of the
host; nothing here touches the network, the runtime or the database.

Standard library only.
"""

from __future__ import annotations

import platform as _platform
import subprocess
import sys

from backend.contracts import profiles as inference_profiles

# The label for work that ran on the computer the user is sitting at. A role,
# not an operating system: the same words are correct on all three families.
HERE = "this computer"

# The label for a paired execution agent. It names the relationship, because
# that is all this installation knows — a peer's OS is whatever it reports of
# itself, and it is never a Refinix requirement that it be any particular one.
PEER = "paired worker"

_LABELS = {"darwin": "macOS", "win32": "Windows"}


def os_family(platform: str | None = None) -> str:
    """A stable identifier for the OS family: macos, windows, linux, other.

    Taken from `sys.platform` rather than `platform.system()` because that is
    the value every other decision in Refinix already keys on, and two spellings
    of the same question drift apart.
    """
    platform = sys.platform if platform is None else platform
    if platform == "darwin":
        return "macos"
    if platform == "win32":
        return "windows"
    if platform.startswith("linux"):
        return "linux"
    return "other"


def os_label(platform: str | None = None) -> str:
    """The OS family as a person writes it, for display only.

    An unrecognised platform is shown by its own name rather than being folded
    into "Linux": claiming a family Refinix has not identified would be the
    same fabrication this module exists to remove.
    """
    platform = sys.platform if platform is None else platform
    if platform in _LABELS:
        return _LABELS[platform]
    return "Linux" if platform.startswith("linux") else platform


def describe(platform: str | None = None) -> dict:
    """What this computer is, as far as the standard library can observe it.

    For the status surface and for diagnostics. Every field is either an
    observation or `None`; nothing is defaulted, and nothing here decides
    whether a profile is *supported* — that is evidence held elsewhere.
    """
    platform = sys.platform if platform is None else platform
    return {
        "platform": platform,
        "os_family": os_family(platform),
        "os": os_label(platform),
        # Only meaningful for the interpreter actually running, so it is left
        # out when a caller is asking about another platform on this machine.
        "release": _platform.release() or None if platform == sys.platform else None,
        "machine": _platform.machine() or None if platform == sys.platform else None,
        "python": _platform.python_version() if platform == sys.platform else None,
    }


def location_label(*, local: bool) -> str:
    """Where a model or an attempt lives, in one word the UI can show.

    One function rather than two constants at each call site, so a future
    change — naming a specific paired device, say — lands in one place.
    """
    return HERE if local else PEER


def _sysctl(name: str) -> str | None:
    """Read one stable macOS hardware fact without invoking a shell."""
    try:
        result = subprocess.run(
            ["/usr/sbin/sysctl", "-n", name], check=True, capture_output=True,
            text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def qualified_target_profile(*, platform: str | None = None,
                             machine: str | None = None,
                             hardware_model: str | None = None,
                             memory_bytes: int | None = None) -> str | None:
    """Stable measured device profile, or ``None`` when it is not proven.

    The only current local qualification belongs to the recorded Mac17,3 M5
    with 16 GiB.  OS family or architecture alone would include other Macs and
    fabricate evidence, so all stable hardware fields must match.  Free memory,
    load and queue state are deliberately irrelevant.
    """
    platform = sys.platform if platform is None else platform
    machine = (_platform.machine() if machine is None else machine).lower()
    if platform != "darwin" or machine not in {"arm64", "aarch64"}:
        return None
    hardware_model = _sysctl("hw.model") if hardware_model is None else hardware_model
    if memory_bytes is None:
        raw = _sysctl("hw.memsize")
        try:
            memory_bytes = int(raw) if raw is not None else None
        except ValueError:
            memory_bytes = None
    if hardware_model == "Mac17,3" and memory_bytes == 16 * 1024 ** 3:
        return inference_profiles.MAC_M5_16GB
    return None
