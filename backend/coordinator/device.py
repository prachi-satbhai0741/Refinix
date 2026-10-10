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


def _version_tuple(text: str | None) -> tuple[int, ...] | None:
    parts = []
    for piece in str(text or "").replace("-", ".").split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) or None


def os_version(platform: str | None = None) -> tuple[str | None, tuple[int, ...] | None]:
    """The OS release as a person reads it, and as a comparable tuple."""
    platform = sys.platform if platform is None else platform
    if platform != sys.platform:
        return None, None
    if platform == "darwin":
        release = _platform.mac_ver()[0] or None
        return release, _version_tuple(release)
    if platform == "win32":
        build = _platform.version() or None       # e.g. 10.0.26200
        return build, _version_tuple(build)
    if platform.startswith("linux"):
        try:
            release = _platform.freedesktop_os_release()
        except OSError:
            return None, None
        version = release.get("VERSION_ID")
        name = release.get("ID")
        return (f"{name} {version}" if name and version else version), _version_tuple(version)
    return None, None


def os_distribution(platform: str | None = None) -> str | None:
    """The Linux distribution's own ID (`ubuntu`, `fedora`, …), lower case.

    Kept as a structured fact because a version number alone does not say
    which distribution it belongs to: Fedora 41 is not "Ubuntu 41". `ID_LIKE`
    is deliberately not used: a derivative is a different system, with its own
    packages, until it has its own evidence. None outside Linux or unknown.
    """
    platform = sys.platform if platform is None else platform
    if platform != sys.platform or not platform.startswith("linux"):
        return None
    try:
        identity = _platform.freedesktop_os_release().get("ID")
    except OSError:
        return None
    return identity.strip().lower() if identity and identity.strip() else None


def _cpu_brand(platform: str) -> str | None:
    if platform == "darwin":
        return _sysctl("machdep.cpu.brand_string")
    if platform.startswith("linux"):
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.lower().startswith("model name"):
                        return line.split(":", 1)[1].strip() or None
        except OSError:
            return None
        return None
    return _platform.processor() or None


def _architecture(machine: str | None) -> str | None:
    machine = (machine or "").lower()
    return {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64",
            "amd64": "x86_64"}.get(machine)


def hardware(*, data_root=None, engine_devices=None) -> dict:
    """What this computer offers, for matching a reviewed hardware tier.

    Every value is an observation or None. Missing sensors and unknown GPUs
    stay unknown; they are never reported as zero, and a product or brand name
    is never used to decide anything.
    """
    platform = sys.platform
    release, version = os_version(platform)
    facts = {
        "os_family": os_family(platform),
        "os_version": release,
        "os_version_tuple": list(version) if version else None,
        "os_distribution": os_distribution(platform),
        "architecture": _architecture(_platform.machine()),
        "cpu_brand": _cpu_brand(platform),
        "cpu_count": None,
        "memory_total_bytes": None,
        "memory_available_bytes": None,
        "disk_free_bytes": None,
        "engine_devices": engine_devices,
    }
    try:
        import psutil
        memory = psutil.virtual_memory()
        facts["memory_total_bytes"] = int(memory.total)
        facts["memory_available_bytes"] = int(memory.available)
        facts["cpu_count"] = psutil.cpu_count(logical=False) or psutil.cpu_count()
    except Exception:                                      # noqa: BLE001
        pass
    if data_root is not None:
        import shutil
        try:
            facts["disk_free_bytes"] = int(shutil.disk_usage(data_root).free)
        except OSError:
            pass
    return facts


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
        from backend.contracts import profiles as inference_profiles
        return inference_profiles.MAC_M5_16GB
    return None
