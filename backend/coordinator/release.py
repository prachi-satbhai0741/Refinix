"""What a Refinix version label means, and the one order every tool uses.

A label is `X.Y.Z-<tag>.<n>` or a plain `X.Y.Z`:

    internal   `0.1.0-internal.6`   the internal test channel (its own trust root)
    preview    `0.1.0-preview.2`    the public `beta` channel, maturity "preview"
    beta       `0.1.0-beta.1`       the public `beta` channel, maturity "accepted"
    (none)     `0.1.0`              the public `beta` channel, maturity "final"

There are two channels, `internal` and `beta`. A public build's maturity is
recorded in its build identity, its signed offer pointer and its package
target, and the label's tag must agree with it.

The ordering key is `K = (major, minor, patch, rank, number)`: the numeric
version always decides first, then the rank (preview 1, accepted 2, final 3;
internal labels rank 0 and are only ever compared with each other), then the
label's number. Every platform encodes the same order:

    Debian    `X.Y.Z~R.S` (final: `X.Y.Z`); `~` sorts before anything, and R is
              the numeric rank, so preview < accepted < final for one X.Y.Z.
    macOS     CFBundleShortVersionString `X.Y.Z`, CFBundleVersion the public
              build number N, which only ever goes up across public builds.
    Windows   version information `X.Y.Z.N`, with the same N.

Internal builds keep their existing scheme (`X.Y.Z~internal.n` for Debian,
the label's number as the build number), so internal.6 keeps working.

Standard library only; imported by the application, the build driver and the
release tooling alike.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CHANNELS = ("internal", "beta")
MATURITIES = ("preview", "accepted", "final")
RANK = {"internal": 0, "preview": 1, "accepted": 2, "final": 3}
TAG_MATURITY = {"preview": "preview", "beta": "accepted", None: "final"}
MATURITY_TAG = {maturity: tag for tag, maturity in TAG_MATURITY.items()}
# The signed pointer each maturity is offered through, per lane.
POINTERS = {"accepted": "latest.json", "final": "latest.json",
            "preview": "latest-preview.json"}
LABEL = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-(internal|preview|beta)\.([1-9]\d*))?")


class LabelError(ValueError):
    pass


@dataclass(frozen=True)
class Label:
    major: int
    minor: int
    patch: int
    tag: str | None
    number: int | None

    @property
    def core(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def channel(self) -> str:
        return "internal" if self.tag == "internal" else "beta"

    @property
    def maturity(self) -> str | None:
        """None for internal builds; preview, accepted or final otherwise."""
        return None if self.tag == "internal" else TAG_MATURITY[self.tag]

    @property
    def rank(self) -> int:
        return RANK["internal"] if self.tag == "internal" else RANK[self.maturity]

    @property
    def key(self) -> tuple[int, int, int, int, int]:
        return (self.major, self.minor, self.patch, self.rank, self.number or 0)

    def debian(self) -> str:
        if self.tag == "internal":
            return f"{self.core}~internal.{self.number}"
        if self.tag is None:
            return self.core
        return f"{self.core}~{self.rank}.{self.number}"

    def windows(self, build: int) -> str:
        return f"{self.core}.{int(build)}"

    def __str__(self) -> str:
        return self.core if self.tag is None else f"{self.core}-{self.tag}.{self.number}"


def parse(text) -> Label:
    match = LABEL.fullmatch(str(text or ""))
    if not match:
        raise LabelError(f"not a Refinix version: {text!r}")
    major, minor, patch, tag, number = match.groups()
    return Label(int(major), int(minor), int(patch), tag, int(number) if number else None)


def key(text) -> tuple[int, int, int, int, int]:
    return parse(text).key


def check_identity(version, channel, maturity) -> Label:
    """The label agrees with the channel and maturity it is published under."""
    label = parse(version)
    if channel not in CHANNELS:
        raise LabelError(f"unknown channel {channel!r}")
    if label.channel != channel:
        raise LabelError(f"{version} is a {label.channel} label, not {channel}")
    if channel == "internal":
        if maturity not in (None, ""):
            raise LabelError("internal builds carry no maturity")
    elif maturity != label.maturity:
        raise LabelError(f"{version} is labelled {label.maturity}, not {maturity}")
    return label


def offered_to(own_maturity: str | None, offered_maturity: str | None) -> bool:
    """Whether an install of one maturity may take a build of another.

    Preview installs take previews and, later, accepted or final builds.
    Accepted and final installs never take a preview, from any source.
    """
    if own_maturity is None or offered_maturity is None:
        return own_maturity == offered_maturity
    if own_maturity == "preview":
        return offered_maturity in MATURITIES
    return offered_maturity in ("accepted", "final")


def pointers_for(own_maturity: str | None) -> tuple[str, ...]:
    """The signed pointer names an installation of this maturity reads."""
    if own_maturity is None:
        return ("latest.json",)
    if own_maturity == "preview":
        return ("latest.json", "latest-preview.json")
    return ("latest.json",)


def pointer_allows(pointer: str, maturity: str | None, channel: str) -> bool:
    """A pointer only ever names builds of its own maturity class."""
    if channel == "internal":
        return pointer == "latest.json" and maturity in (None, "")
    return POINTERS.get(maturity) == pointer


# --------------------------------------------------------------------------
# Install formats and the files that carry them
# --------------------------------------------------------------------------

# How each lane's installations are made and updated. A DMG is only ever a
# first-install download; the macOS update payload is the ZIP of the same app.
LANE_FORMATS = {"macos-arm64": ("zip",), "windows-x64": ("exe",),
                "linux-x64": ("deb", "appimage")}
FORMAT_SUFFIX = {"zip": ".zip", "exe": ".exe", "deb": ".deb", "appimage": ".AppImage"}


def asset_name(version, lane: str, fmt: str) -> str:
    """The one file name a lane's package of one format has, everywhere."""
    label = parse(version)
    if fmt not in LANE_FORMATS.get(lane, ()):
        raise LabelError(f"{lane} has no {fmt} package")
    if fmt == "deb":
        return f"refinix_{label.debian()}_amd64.deb"
    if fmt == "exe":
        return f"Refinix-{label}-windows-x64-setup.exe"
    if fmt == "appimage":
        return f"Refinix-{label}-linux-x86_64.AppImage"
    return f"Refinix-{label}-{lane}.zip"


def dmg_name(version) -> str:
    return f"Refinix-{parse(version)}-macos-arm64.dmg"


def format_of(name: str) -> str | None:
    """The install format a package file carries, from its name; None for a DMG."""
    for fmt, suffix in FORMAT_SUFFIX.items():
        if name.endswith(suffix):
            return fmt
    return None


def package_target(version, lane: str, fmt: str) -> str:
    """A public package's signed target name: `v<version>/<asset>`."""
    return f"v{parse(version)}/{asset_name(version, lane, fmt)}"
