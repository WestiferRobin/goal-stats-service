"""Explicit offline research execution; no database connection, fitting routes or migrations."""

import hashlib
import json

from research.model_validation import PACKAGE, evaluate, reconstruct
from research.special_ratings import digest
from research.three_input import SPEC


def main() -> None:
    if json.loads((PACKAGE / "protocol.json").read_text()) != SPEC:
        raise ValueError("Freeze and independently review the protocol before evaluation")
    data = reconstruct()
    report = evaluate(data)
    for name, value in [("predictions.json", data), ("results.json", report)]:
        (PACKAGE / name).write_text(
            json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    manifest = {
        "package_id": "three-input-validation-v1",
        "protocol_hash": digest(SPEC),
        "files": {
            name: hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest()
            for name in ["protocol.json", "rankings.json", "predictions.json", "results.json"]
        },
        "status": "retrospective_research_not_production_approved",
    }
    (PACKAGE / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
