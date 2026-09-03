import argparse
from pathlib import Path

from backend.coordinator.server import DEFAULT_PORT, serve

parser = argparse.ArgumentParser(prog="python3 -m backend.coordinator")
parser.add_argument("--port", type=int, default=DEFAULT_PORT)
parser.add_argument("--state", type=Path,
                    default=Path.home() / ".aegisforge" / "coordinator.sqlite3",
                    help="SQLite database path (outside the repository)")
args = parser.parse_args()
serve(args.state, args.port)
