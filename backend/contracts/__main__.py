"""Export JSON Schema and protocol constants to stdout without writing files."""

import json

from .v1 import export_contract

print(json.dumps(export_contract(), indent=2, sort_keys=True))
