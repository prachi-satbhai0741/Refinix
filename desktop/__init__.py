"""Refinix desktop shell.

A thin native window around the coordinator that already exists in
`backend.coordinator`. Nothing here replaces the coordinator, the SQLite state,
the frontend or the event stream; the command-line coordinator
(`python3 -m backend.coordinator`) keeps working unchanged.
"""

__all__ = ["lifecycle"]
