"""Access-mode policy: one pure decision function, one place to audit.

Every repository operation asks this module what to do. It is deliberately
free of HTTP, SQLite, filesystem and model code so the whole matrix can be read
in one screen and tested exhaustively.

Three visible modes:

    partial   read and propose automatically; every canonical write is approved
    full      read, propose and apply eligible existing-file replacements
              automatically, inside the connected folder only
    ask       approve the reads as one immutable batch, then approve the write

What "Full" does *not* mean is as important as what it does. Running project
commands, Git or GitHub writes, installing anything, enabling network access,
creating, deleting or renaming files, and reaching outside the connected folder
are denied in every mode. The word is not a permission escalation.

The model can propose paths and content. It cannot choose a mode, mark an
action approved, add an action to this table, or turn a denial into a retry:
those words simply do not appear in the data it produces.
"""

from __future__ import annotations

from dataclasses import dataclass

MODES = ("partial", "full", "ask")
DEFAULT_MODE = "partial"

MODE_LABELS = {
    "partial": "Partial access",
    "full": "Full access",
    "ask": "Ask before actions",
}

MODE_SUMMARIES = {
    "partial": "Reads the files you select and prepares edits on its own. "
               "Every change to a real file asks you first.",
    "full": "Reads, prepares and applies edits to the files you select inside "
            "this folder without asking each time. Still cannot run commands, "
            "use Git, install anything, or work outside this folder.",
    "ask": "Asks before reading the folder and again before any change.",
}

# Actions this execution implements.
#
# Reading the selection and sending it to the local model are ONE action, not
# two. They always happen together, an approval for them is one immutable
# batch over one exact set of paths, and splitting them in this table while
# gating them once would make the matrix and the audit disagree about how the
# work was authorised.
ACTION_LIST = "repo.list"                  # enumerate candidate files
ACTION_VIEW = "repo.view"                  # show one file to the person, not the model
ACTION_READ = "repo.read_and_propose"      # read the selection and send it to the model
ACTION_WRITE = "canonical.write"           # replace an existing selected file

SUPPORTED_ACTIONS = (ACTION_LIST, ACTION_VIEW, ACTION_READ, ACTION_WRITE)

# `repo.view` is deliberately its own action rather than a use of `repo.read`.
# The two send the file to different places: viewing puts it on the person's
# own screen, reading puts it in a model prompt. Gating them together would
# make the audit say a file was sent to the model when it was only opened,
# and would make "ask before the model sees my code" impossible to honour
# while still letting someone look at their own file.
ACTION_LABELS = {
    ACTION_LIST: "list the text files in this project",
    ACTION_VIEW: "show one file from this project on this screen",
    ACTION_READ: "read the selected files and send them to the model on this computer",
    ACTION_WRITE: "write the reviewed change to this project",
}

# Named so a refusal can say what was asked for rather than "not allowed".
# None of these is implemented, and no mode enables any of them.
# Retired action names. Nothing may authorise one: a caller still using it is
# a bug, not a request. They are not shown to the user as missing features.
RETIRED_ACTIONS = {
    "model.propose": "Reading files and sending them to the model is one action; "
                     "ask for repo.read_and_propose instead.",
    "repo.read": "Reading files and sending them to the model is one action; "
                 "ask for repo.read_and_propose instead.",
}

DENIED_ACTIONS = {
    **RETIRED_ACTIONS,
    "file.create": "Creating files is not available yet.",
    "file.delete": "Deleting files is not available yet.",
    "file.rename": "Renaming or moving files is not available yet.",
    "file.chmod": "Changing file permissions is not available.",
    "command.run": "Running project commands is not available.",
    "git.write": "Git and GitHub actions are not available.",
    "package.install": "Installing packages is not available.",
    "network.enable": "Enabling network access is not available.",
    "path.outside_root": "That path is outside the connected folder.",
    "sandbox.execute": "Sandboxed execution is not available yet.",
}

AUTOMATIC = "automatic"
APPROVAL_REQUIRED = "approval_required"
DENIED = "denied"

_MATRIX = {
    "partial": {ACTION_LIST: AUTOMATIC, ACTION_VIEW: AUTOMATIC,
                ACTION_READ: AUTOMATIC, ACTION_WRITE: APPROVAL_REQUIRED},
    "full": {ACTION_LIST: AUTOMATIC, ACTION_VIEW: AUTOMATIC,
             ACTION_READ: AUTOMATIC, ACTION_WRITE: AUTOMATIC},
    "ask": {ACTION_LIST: APPROVAL_REQUIRED, ACTION_VIEW: APPROVAL_REQUIRED,
            ACTION_READ: APPROVAL_REQUIRED, ACTION_WRITE: APPROVAL_REQUIRED},
}

# Audit outcomes. Denials never collapse into a generic failure.
OUTCOMES = ("allowed_automatically", "awaiting_approval", "approved", "denied",
            "expired", "rejected_stale", "failed", "applied")


@dataclass(frozen=True)
class Decision:
    outcome: str          # automatic | approval_required | denied
    action: str
    mode: str
    reason: str

    @property
    def automatic(self) -> bool:
        return self.outcome == AUTOMATIC

    @property
    def denied(self) -> bool:
        return self.outcome == DENIED

    def as_dict(self) -> dict:
        return {"outcome": self.outcome, "action": self.action,
                "mode": self.mode, "reason": self.reason}


def normalise_mode(raw) -> str:
    if raw in MODES:
        return raw
    raise ValueError(f"unknown access mode: {raw!r}")


def decide(mode: str, action: str) -> Decision:
    """The only place an access mode is interpreted.

    An unknown mode or action is denied rather than guessed at, so a new action
    added elsewhere fails closed until it is added to the table on purpose.
    """
    if action in DENIED_ACTIONS:
        return Decision(DENIED, action, mode if mode in MODES else "unknown",
                        DENIED_ACTIONS[action])
    if mode not in MODES:
        return Decision(DENIED, action, "unknown",
                        "No access mode is set for this folder.")
    if action not in SUPPORTED_ACTIONS:
        return Decision(DENIED, action, mode,
                        f"{action} is not something Refinix can do.")
    outcome = _MATRIX[mode][action]
    if outcome == AUTOMATIC:
        reason = (f"{MODE_LABELS[mode]} allows this without asking."
                  if action != ACTION_WRITE else
                  "Full access applies edits inside this folder without asking each time.")
    elif action == ACTION_WRITE:
        reason = "This change needs your approval before any file is written."
    elif action == ACTION_VIEW:
        # Said precisely: opening a file shows it to the person, and nothing
        # about opening it sends it to the model.
        reason = ("Ask before actions needs your approval before this file is "
                  "opened on screen. Opening it does not send it to the model.")
    else:
        reason = "Ask before actions needs your approval before reading this folder."
    return Decision(outcome, action, mode, reason)


# What Full access must say before it is switched on for a project. Automatic
# local writing is the one place where nobody looks at the change before it
# lands, so the sentence has to be the one a person would want to have read.
FULL_LOCAL_WARNING = (
    "Full access applies changes to this project without asking each time. "
    "On this device the Ubuntu sandbox tests do not run, so a change is "
    "written after Refinix's own checks and nothing else. Refinix keeps a copy "
    "of every file it replaces so you can undo it.")


def mode_options() -> list[dict]:
    """What the Code surface offers, straight from this module."""
    return [{"id": mode, "label": MODE_LABELS[mode], "summary": MODE_SUMMARIES[mode],
             "confirm": mode == "full",
             "confirm_note": FULL_LOCAL_WARNING if mode == "full" else None}
            for mode in MODES]


def unavailable_actions() -> list[dict]:
    """Named refusals, so the interface can say what is not built rather than
    leaving a control that looks as though it might work."""
    return [{"action": action, "detail": detail}
            for action, detail in sorted(DENIED_ACTIONS.items())
            if action not in RETIRED_ACTIONS]
