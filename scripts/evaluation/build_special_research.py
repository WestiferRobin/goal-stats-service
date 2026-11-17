"""Rebuild the offline research audit; run with PYTHONPATH=src. Never fits a model."""

import hashlib
import json

from research.feasibility import PACKAGE, build
from research.special_ratings import SPEC, digest


def main() -> None:
    for name, value in [("specification.json", SPEC), ("coverage.json", build())]:
        (PACKAGE / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
    names = ["specification.json", "coverage.json", "sources.json"]
    manifest = {
        "package_id": "historical-special-ratings-v1",
        "method_hash": digest(SPEC),
        "status": "unvalidated_research_not_production_eligible",
        "files": {
            name: hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest() for name in names
        },
    }
    (PACKAGE / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
