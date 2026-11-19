"""Build the 1991 evidence inventory without database access or predictions."""

import json
from pathlib import Path

from research.duration_audit import build

if __name__ == "__main__":
    target = Path(__file__).resolve().parents[2] / "data/research/duration-80-v1"
    target.mkdir(parents=True, exist_ok=True)
    (target / "coverage.json").write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n")
