"""Where Refinix keeps durable data, on each operating system it supports.

Phase 1's platform boundary. `docs/PROJECT.md` 12.4 names one logical durable
root per platform, outside the replaceable application files, and 12.5 makes the
existing `.aegisforge` store compatibility-sensitive. Both rules live here and
nowhere else: every other module already derives its storage from the
coordinator database path it is handed — `db.attachments_root`,
`db.artifacts_root` and `db.backups_root` all hang off `state_path.parent` — so
choosing that one path *is* the whole abstraction.

**Resolution, never migration.** This module decides which root an installation
is already using. It copies, merges, renames and deletes nothing, and it creates
nothing either: `db.py` makes the directory with owner-only permissions when it
opens the database. A versioned migration is separately authorised work (12.5).
Until it exists, an installation holding state in `~/.aegisforge` keeps using it
on every platform — including macOS, where the native root is also defined.

**Two writable canonical stores are refused, not reconciled.** Where both the
legacy and the platform-native root hold durable content, 12.5 says the user
chooses which one wins. `select_root` reports that as a conflict rather than
picking one, and `require_root` raises. Silently preferring either would strand a
workspace's chats, approvals and artifacts in a store nothing opens again — and
running both would be two canonical stores at once, which 12.5 forbids outright.

**"Holds content" is wider than "has a database."** 12.5 protects credentials and
content, not one file, so `inspect_root` also counts artifacts, attachments,
backups, instructions and curated memory. A root carrying a user's artifacts but
no usable database is still their workspace. The converse matters too: a lone
zero-byte database is residue — `sqlite3` against a missing path leaves one, and
this computer has exactly such a leftover from a manual command in an archived
handoff — and an unrecognised loose file, such as a pinned worker certificate
someone placed by hand, is residue as well. Refusing to start over a stray file
would be a worse failure than reporting it, so residue is *listed* on the result
rather than either counted or silently dropped.

**A path is not a capability.** Naming a Windows or Linux root proves a
directory layout, not that the profile is qualified. Nothing here reaches the
network, starts a service or claims an OS is supported.

Standard library only.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from backend.coordinator import device

# The product directory name on platforms that capitalise application data, and
# the lower-case form used where the convention is a dotted/XDG directory.
PRODUCT_DIRECTORY = "Refinix"
XDG_DIRECTORY = "refinix"

# Compatibility-sensitive (12.5). The name does not follow the product rename,
# and nothing in this module ever writes to, moves or removes it.
LEGACY_DIRECTORY = ".aegisforge"

# The directory name an explicit portable profile uses inside a folder the user
# picked — a removable volume, say. `PORTABLE_ROOT` overrides with a full path.
PORTABLE_DIRECTORY = ".refinix"

# The canonical database filename. Unchanged from the existing store so no
# installation needs a migration to be readable by this resolution.
DATABASE_NAME = "coordinator.sqlite3"

# Names a store could plausibly carry instead. `state.db` is the one
# `docs/PROJECT.md` 12.4 sketches; `refinix.db` is the obvious product-rename
# spelling, and a file of that name already exists on the macOS target root here.
# No build writes either today. Recognising them is what keeps a rename from
# quietly becoming a second store that resolution reads as an empty directory.
ALTERNATE_DATABASE_NAMES = ("state.db", "refinix.db")

# An absolute path selecting the root outright, for an explicit portable profile
# and for tests. A relative or empty value is ignored rather than resolved
# against the working directory, where a root must never land.
ROOT_ENVIRONMENT_VARIABLE = "REFINIX_DATA_ROOT"

# Logical subdirectories, defined here so callers stop inventing their own
# names, and deliberately *not* created here. `db.py` makes each one with mode
# 0o700 at the moment it first has something to put in it; creating them eagerly
# would leave a new installation full of empty directories that prove nothing.
ARTIFACTS = "artifacts"
ATTACHMENTS = "attachments"
BACKUPS = "backups"
JOBS = "jobs"
TEMPORARY = "tmp"
MODEL_MANIFESTS = "model-manifests"
CORPUS = "corpus"
AUDIT = "audit"

SUBDIRECTORIES = (ARTIFACTS, ATTACHMENTS, BACKUPS, JOBS, TEMPORARY,
                  MODEL_MANIFESTS, CORPUS, AUDIT)

# Top-level files from 12.4's representative layout that make a root somebody's
# workspace even before a database exists. Instructions and curated memory are
# content a user wrote; losing them by selecting the other store would be the
# same harm as losing chats.
STATE_FILES = ("config.toml", "AGENTS.md", "memory.md")

# Desktop metadata every file manager leaves in any folder it displays. Never
# evidence of anything, and not worth listing as residue either.
IGNORED_NAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini",
                           "ehthumbs.db", ".localized"})


class DataRootError(ValueError):
    """A refusal the interface can show, with a code a check can assert."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class DataRootConflict(DataRootError):
    """Two roots hold a canonical store, so there is no safe automatic choice.

    Separate from every other failure on purpose: this must stop startup and ask
    the user, and must never be folded into a "use the other one" fallback.
    """

    def __init__(self, message: str, *, legacy: Path, platform: Path):
        super().__init__("two_stores", message)
        self.legacy = legacy
        self.platform = platform


# --------------------------------------------------------------------------
# The roots each platform defines
# --------------------------------------------------------------------------

def _home(home: Path | None = None) -> Path:
    return Path(home) if home is not None else Path.home()


def _absolute(value: str | None, *, platform: str | None = None) -> Path | None:
    """An environment path only when it is usable as a root.

    Blank, relative and `~`-prefixed values are rejected rather than repaired: a
    root resolved against the working directory would follow whichever folder
    the application happened to be launched from.

    Absoluteness is judged with the *target* platform's rules, not the host's.
    `C:\\Users\\…` is absolute on Windows and meaningless to a POSIX `Path`, so
    deciding with the host's flavour would quietly reject every real Windows
    value whenever these roots are checked from another computer — which is the
    only way they can be checked before the device arrives.
    """
    if not value or not value.strip():
        return None
    text = value.strip()
    platform = sys.platform if platform is None else platform
    flavour = PureWindowsPath if platform == "win32" else PurePosixPath
    return Path(text) if flavour(text).is_absolute() else None


def platform_root(*, platform: str | None = None, environ=None,
                  home: Path | None = None) -> Path:
    """The OS-native durable root from `docs/PROJECT.md` 12.4.

    Returned for every platform, including ones Refinix has not qualified: the
    layout is defined by the contract, while support is decided by evidence
    elsewhere. The arguments exist so the three platforms can be checked on one
    computer, which is the only way this stays honest before the devices arrive.
    """
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    base = _home(home)
    if platform == "darwin":
        return base / "Library" / "Application Support" / PRODUCT_DIRECTORY
    if platform == "win32":
        local = _absolute(environ.get("LOCALAPPDATA"), platform=platform)
        # An unset LOCALAPPDATA is a broken environment rather than a reason to
        # fall out of the user profile, so the documented default stands in.
        return (local or base / "AppData" / "Local") / PRODUCT_DIRECTORY
    # Linux and anything else POSIX. The XDG default is spelled out rather than
    # assumed, and a relative XDG_DATA_HOME is ignored as the specification says.
    data_home = _absolute(environ.get("XDG_DATA_HOME"), platform=platform)
    return (data_home or base / ".local" / "share") / XDG_DIRECTORY


def legacy_root(*, home: Path | None = None) -> Path:
    """The prototype store. Compatibility-sensitive; never written to by this
    module, and never renamed because the product name changed (12.5)."""
    return _home(home) / LEGACY_DIRECTORY


def portable_root(directory: str | os.PathLike) -> Path:
    """The root for an explicit portable profile inside a folder the user chose.

    A folder, not a file, and the `.refinix` component is added here so the
    caller cannot accidentally adopt the whole of a removable volume as a root.
    """
    chosen = Path(directory).expanduser()
    if not chosen.is_absolute():
        raise DataRootError(
            "relative_root",
            "A portable Refinix folder must be an absolute path.")
    if chosen.name == PORTABLE_DIRECTORY:
        return chosen
    return chosen / PORTABLE_DIRECTORY


def database_path(root: str | os.PathLike) -> Path:
    """The coordinator database inside a root. Every other storage location in
    the application is derived from this path's parent."""
    return Path(root) / DATABASE_NAME


def subdirectory(root: str | os.PathLike, name: str) -> Path:
    """One defined subdirectory of a root, by name rather than by string
    concatenation at the call site. Creates nothing."""
    if name not in SUBDIRECTORIES:
        raise DataRootError("unknown_subdirectory",
                            f"{name!r} is not a defined Refinix subdirectory.")
    return Path(root) / name


# --------------------------------------------------------------------------
# What a root actually contains
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Occupancy:
    """What durable Refinix content a root actually holds.

    Deliberately more than "is there a database". 12.5 says the two stores are
    compatibility-sensitive and that the user chooses when *both contain data* —
    it does not say data means a database. A root carrying artifacts, backups or
    instructions but no usable database is still somebody's workspace, and
    selecting the other store would strand it.

    `residue` is the other half of the same honesty: entries that are present
    but are *not* evidence of a store. They are listed rather than ignored, so
    "this root looked empty" can always be checked against what was really in it.
    """

    databases: tuple[Path, ...] = ()
    state_files: tuple[str, ...] = ()
    populated: tuple[str, ...] = ()          # defined subdirectories with content
    residue: tuple[str, ...] = ()
    unreadable: tuple[str, ...] = ()

    @property
    def occupied(self) -> bool:
        # Unreadable is deliberately occupied. Treating "could not inspect" as
        # "empty" can create a second writable store while the first still
        # holds a workspace — the exact ambiguity this resolver prevents.
        return bool(self.databases or self.state_files or self.populated
                    or self.unreadable)

    @property
    def database(self) -> Path | None:
        return self.databases[0] if self.databases else None

    def summary(self) -> str:
        """What was found, in the words a refusal can quote."""
        found = [*(p.name for p in self.databases), *self.state_files,
                 *(f"{name}/" for name in self.populated), *self.unreadable]
        return ", ".join(found) if found else "nothing durable"


def inspect_root(root: str | os.PathLike) -> Occupancy:
    """Everything `root` holds that bears on whether it is a canonical store.

    Cheap by construction: the top level is listed once and each defined
    subdirectory is tested for a single entry. Nothing is opened, recursed or
    counted, because this runs before the application has decided anything.
    """
    directory = Path(root)
    try:
        entries = sorted(directory.iterdir())
    except FileNotFoundError:
        return Occupancy()
    except OSError as exc:
        reason = exc.strerror or str(exc) or type(exc).__name__
        return Occupancy(unreadable=(f"{directory} ({reason})",))

    database_names = (DATABASE_NAME, *ALTERNATE_DATABASE_NAMES)
    databases: list[Path] = []
    state_files: list[str] = []
    populated: list[str] = []
    residue: list[str] = []
    unreadable: list[str] = []

    for entry in entries:
        name = entry.name
        try:
            if entry.is_dir():
                if name in SUBDIRECTORIES:
                    # Anything inside is evidence: `db.py` creates each one only
                    # when it first has something to put there.
                    if next(entry.iterdir(), None) is not None:
                        populated.append(name)
                    else:
                        residue.append(f"{name}/ (empty)")
                else:
                    residue.append(f"{name}/")
                continue
            if name in database_names:
                if entry.stat().st_size > 0:
                    databases.append(entry)
                else:
                    # `sqlite3` against a missing path and an interrupted copy
                    # both leave a zero-byte file. On its own it is residue — but
                    # only on its own: anything real beside it still counts above.
                    residue.append(f"{name} (empty)")
                continue
            if name in STATE_FILES:
                if entry.stat().st_size > 0:
                    state_files.append(name)
                else:
                    residue.append(f"{name} (empty)")
                continue
            if name in IGNORED_NAMES:
                continue
            # A loose file nothing here recognises: user-placed material such as
            # a pinned worker certificate, or an editor's leftover. Recorded so
            # it is visible, and deliberately NOT occupancy: refusing to start
            # over a stray file would be a worse failure than reporting it.
            residue.append(name)
        except OSError:
            unreadable.append(f"{name} (unreadable)")

    return Occupancy(databases=tuple(databases), state_files=tuple(state_files),
                     populated=tuple(populated), residue=tuple(residue),
                     unreadable=tuple(unreadable))


def database_in(root: str | os.PathLike) -> Path | None:
    """The usable canonical database in `root`, or None when there is none."""
    return inspect_root(root).database


def holds_state(root: str | os.PathLike) -> bool:
    """Whether `root` is somebody's workspace — by any durable content, not only
    by a database."""
    return inspect_root(root).occupied


def owner_only(root: str | os.PathLike) -> bool | None:
    """Whether the root is readable by its owner alone.

    An observation, not an enforcement: None where the platform does not express
    permissions this way. `db.py` creates directories with mode 0o700; this
    module does not tighten a directory a user or another tool already made,
    because silently changing permissions on an existing folder is not
    resolution work.
    """
    if sys.platform == "win32":
        return None
    try:
        mode = Path(root).stat().st_mode
    except OSError:
        return None
    return not mode & 0o077


# --------------------------------------------------------------------------
# Choosing the root
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DataRoot:
    """Which root an installation uses, and why — an answer with its reason.

    `conflict` carries the refusal when there is no safe automatic choice, so a
    caller that must not raise can still report the truth.
    """

    path: Path
    database: Path
    source: str                      # override | portable | legacy | platform
    detail: str
    legacy: Path
    platform: Path
    conflict: DataRootConflict | None = None
    # What was in the root this resolution did *not* select. Reported so that
    # "the other root looked empty" is a statement someone can check, rather
    # than a silent classification.
    unselected_residue: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.conflict is None

    def as_dict(self) -> dict:
        return {"path": str(self.path), "database": str(self.database),
                "source": self.source, "detail": self.detail,
                "owner_only": owner_only(self.path),
                "unselected_residue": list(self.unselected_residue),
                "conflict": None if self.ok else str(self.conflict)}


def select_root(*, platform: str | None = None, environ=None,
                home: Path | None = None) -> DataRoot:
    """Which root this installation uses. Never raises, never creates, never
    migrates.

    The order is deliberate:

    1. an explicit absolute override, which is the portable profile and the only
       way a test or a removable volume gets a say;
    2. the legacy `.aegisforge` store when it holds durable content, because
       12.5 forbids moving it without a separately authorised migration;
    3. the platform-native root from 12.4, for every new installation.

    Occupancy is decided by `inspect_root`, which counts artifacts, backups,
    instructions and curated memory as well as a database. A root holding a
    user's content but no usable database is still their workspace, and 12.5
    asks the user when *both* stores contain data.

    A conflict — both stores occupied — is reported rather than resolved.
    """
    environ = os.environ if environ is None else environ
    legacy = legacy_root(home=home)
    native = platform_root(platform=platform, environ=environ, home=home)

    override = _absolute(environ.get(ROOT_ENVIRONMENT_VARIABLE),
                         platform=platform)
    if override is not None:
        return DataRoot(
            path=override, database=database_path(override),
            source="override", legacy=legacy, platform=native,
            detail=(f"Using the root named by {ROOT_ENVIRONMENT_VARIABLE}. "
                    "An explicit choice overrides both the existing store and "
                    "the platform default."))

    held_legacy = inspect_root(legacy)
    held_native = inspect_root(native)

    if held_legacy.occupied and held_native.occupied:
        conflict = DataRootConflict(
            "Refinix found workspace data in two places: "
            f"{legacy} ({held_legacy.summary()}) and "
            f"{native} ({held_native.summary()}). Only one can be the canonical "
            "store, and Refinix does not merge them or choose for you. Move or "
            "rename the one you do not want to keep, or set "
            f"{ROOT_ENVIRONMENT_VARIABLE} to the one that wins.",
            legacy=legacy, platform=native)
        # Reported against the legacy root so the message names a real path,
        # never so a caller can ignore the conflict and open it anyway.
        return DataRoot(path=legacy,
                        database=held_legacy.database or database_path(legacy),
                        source="legacy", legacy=legacy, platform=native,
                        detail=str(conflict), conflict=conflict)

    if held_legacy.occupied:
        return DataRoot(
            path=legacy, database=held_legacy.database or database_path(legacy),
            source="legacy", legacy=legacy, platform=native,
            detail=(f"Using the existing workspace at {legacy}. Moving it to "
                    f"{native} is a separate versioned migration, so it stays "
                    "where it is."),
            unselected_residue=held_native.residue)

    return DataRoot(
        path=native, database=held_native.database or database_path(native),
        source="platform", legacy=legacy, platform=native,
        detail=(f"Using the {device.os_label(platform)} location for "
                f"application data: {native}."),
        unselected_residue=held_legacy.residue)


def require_root(**kwargs) -> DataRoot:
    """`select_root`, raising `DataRootConflict` instead of reporting it.

    For a caller that must not proceed on an ambiguous store — which is every
    caller about to open the database for writing.
    """
    root = select_root(**kwargs)
    if root.conflict is not None:
        raise root.conflict
    return root


def state_path(**kwargs) -> Path:
    """The coordinator database this installation should open.

    The one call the rest of the application needs. Non-raising on purpose: a
    conflict must be reported by the startup sequence with somewhere for the
    user to go, not raised out of a module-level default.
    """
    return select_root(**kwargs).database
