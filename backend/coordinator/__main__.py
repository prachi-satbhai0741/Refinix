import argparse
import sys
from pathlib import Path

from backend.coordinator import paths
from backend.coordinator.server import DEFAULT_PORT, serve

parser = argparse.ArgumentParser(prog="python3 -m backend.coordinator")
parser.add_argument("--port", type=int, default=DEFAULT_PORT)
# `paths` decides where durable data lives on this platform: the OS-native root,
# the existing `.aegisforge` store when one is already there, or an explicit
# portable profile. An explicit --state still wins, which is how a test or a
# second workspace runs without touching the canonical store.
parser.add_argument("--state", type=Path, default=None,
                    help="SQLite database path (outside the repository)")
args = parser.parse_args()

state = args.state
if state is None:
    root = paths.select_root()
    if root.conflict is not None:
        # Two canonical stores must not both be opened (PROJECT.md 12.5), and a
        # command line has somewhere to say so. Naming --state is the answer.
        sys.exit(f"{root.conflict}\n"
                 f"Pass --state to name the database this run should open.")
    state = root.database

serve(state, args.port)
