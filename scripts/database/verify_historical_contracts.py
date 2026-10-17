"""Read-only prepared-contract verification; deliberately separate from the importer."""

import argparse
import csv
import hashlib
import io
import json
import re
from datetime import date
from pathlib import Path

from football.historical_dataset import name_key

ROOT = Path(__file__).resolve().parents[2]
REVISION = "1855e313ae8bcd0330426e62c8e4cf15ce45077c"
CHECKSUM = "de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0"
COLUMNS = "date home_team away_team home_score away_score tournament city country neutral".split()
SPECS = {
    "1991": ("1991-11-16", "1991-11-30", 26, 12, 99),
    "1995": ("1995-06-05", "1995-06-18", 26, 12, 99),
    "1999": ("1999-06-19", "1999-07-10", 32, 16, 123),
    "2003": ("2003-09-20", "2003-10-12", 32, 16, 107),
    "2007": ("2007-09-10", "2007-09-30", 32, 16, 111),
    "2011": ("2011-06-26", "2011-07-17", 32, 16, 86),
    "2015": ("2015-06-06", "2015-07-05", 52, 24, 146),
    "2019": ("2019-06-07", "2019-07-07", 52, 24, 146),
    "2023": ("2023-07-20", "2023-08-20", 64, 32, 164),
}
SCORE_BASIS = "including_extra_time_no_shootout"
SOURCE_URL = f"https://github.com/martj42/womens-international-results/blob/{REVISION}"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def expected_manifest(year):
    require(year in SPECS, f"Unknown edition: {year}")
    start, end, matches, teams, _ = SPECS[year]
    return {
        "dataset_id": f"womens-world-cup-{year}",
        "source": "martj42_womens_results",
        "source_name": "Women's International Football Results",
        "author": "Mart Jürisoo",
        "source_url": f"{SOURCE_URL}/results.csv",
        "upstream_revision": REVISION,
        "sha256": CHECKSUM,
        "attribution_reference": f"{SOURCE_URL}/README.md",
        "license_reference": "https://www.kaggle.com/datasets/martj42/"
        "womens-international-football-results",
        "source_filename": "results.csv",
        "required_columns": COLUMNS,
        "selection": {"tournament": "FIFA World Cup", "date_from": start, "date_to": end},
        "competition": {
            "source_tournament": "FIFA World Cup",
            "name": "FIFA Women's World Cup",
            "name_key": "fifa women's world cup",
            "edition_label": year,
            "category": "women_senior_national",
        },
        "team_category": "women_senior_national",
        "score_basis": SCORE_BASIS,
        "expected_counts": {"matches": matches, "teams": teams, "competitions": 1},
        "reviewed_team_aliases": {},
    }


def validate_contract(manifest, evidence):
    year = manifest.get("competition", {}).get("edition_label")
    require(manifest == expected_manifest(year), f"Manifest differs from pinned contract: {year}")
    start, end, matches, teams, goals = SPECS[year]
    expected = {
        "dataset_id": manifest["dataset_id"],
        "date_from": start,
        "date_to": end,
        "matches": matches,
        "participant_count": teams,
        "total_goals": goals,
        "approval_status": "approved_pinned_basic_results",
        "runtime_supported": year == "2023",
        "identity_policy": "source-record-key-v1",
        "home_away_policy": "preserve_source_order",
        "score_basis": SCORE_BASIS,
    }
    require(set(evidence) == set(expected) | {"participants", "fixture_sha256"}, "Evidence schema")
    require(all(evidence[k] == v for k, v in expected.items()), f"Evidence contract: {year}")
    participants = evidence["participants"]
    require(participants == sorted(set(participants)), f"Participant ordering/duplicates: {year}")
    require(len(participants) == teams, f"Participant count: {year}")
    require(len({name_key(p) for p in participants if p.strip()}) == teams, "Team identities")
    require(re.fullmatch(r"[0-9a-f]{64}", evidence["fixture_sha256"]), "Fixture digest")


def load_contracts():
    coverage = json.loads((ROOT / "data/verification/womens-world-cup-coverage.json").read_text())
    for key, value in {
        "schema_version": 1,
        "source_revision": REVISION,
        "source_sha256": CHECKSUM,
        "source_rows": 11650,
        "total_matches": 348,
        "distinct_participants": 44,
        "total_goals": 1081,
    }.items():
        require(coverage[key] == value, f"Coverage {key}")
    editions = coverage["editions"]
    require(
        [e["dataset_id"] for e in editions] == [f"womens-world-cup-{y}" for y in SPECS],
        "Coverage editions/order",
    )
    contracts = []
    for evidence in editions:
        path = ROOT / "data/womens-world-cup" / f"{evidence['dataset_id']}.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        validate_contract(manifest, evidence)
        contracts.append((manifest, evidence))
    require(len({p for e in editions for p in e["participants"]}) == 44, "Global participants")
    return contracts


def fixture_digest(rows):
    ordered = sorted(rows, key=lambda r: (r["date"], r["home_team"], r["away_team"]))
    return hashlib.sha256(
        json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def validate_row(row):
    require(
        set(row) == set(COLUMNS) and all(isinstance(v, str) for v in row.values()),
        "Malformed CSV row",
    )
    for key in ("date", "home_team", "away_team", "home_score", "away_score", "tournament"):
        require(bool(row[key].strip()), f"Missing required field: {key}")
    require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["date"]), "Invalid date format")
    date.fromisoformat(row["date"])
    for key in ("home_score", "away_score"):
        require(
            re.fullmatch(r"[0-9]+", row[key]) and int(row[key]) <= 32767, f"Invalid score: {key}"
        )
    require(name_key(row["home_team"]) != name_key(row["away_team"]), "Self-match")
    require(row["neutral"].strip().upper() in {"", "TRUE", "FALSE"}, "Invalid neutral")


def verify_selection(rows, selection, evidence):
    """Pure fixture checks, usable with small synthetic fixtures in ordinary tests."""
    selected = []
    identities = {}
    for ordinal, row in enumerate(rows, 2):
        try:
            validate_row(row)
            if row["tournament"] != selection["tournament"]:
                continue
            if not selection["date_from"] <= row["date"] <= selection["date_to"]:
                continue
            # Also reject reversed duplicate associations without changing source ordering.
            key = (row["date"], *sorted([name_key(row["home_team"]), name_key(row["away_team"])]))
            if key in identities:
                kind = "Duplicate" if identities[key] == row else "Contradictory"
                raise ValueError(f"{kind} fixture identity: {key}")
            identities[key] = row
            selected.append(row)
        except ValueError as exc:
            raise ValueError(f"Source row {ordinal}: {exc}") from exc
    require(len(selected) == evidence["matches"], "Match count differs")
    participants = sorted({r[k] for r in selected for k in ("home_team", "away_team")})
    require(participants == evidence["participants"], "Exact participant set differs")
    require(len(participants) == evidence["participant_count"], "Participant count differs")
    goals = sum(int(r[k]) for r in selected for k in ("home_score", "away_score"))
    require(goals == evidence["total_goals"], "Goal total differs")
    require(
        fixture_digest(selected) == evidence["fixture_sha256"], "Complete fixture digest differs"
    )
    return selected


def verify_source(path):
    payload = path.read_bytes()
    require(hashlib.sha256(payload).hexdigest() == CHECKSUM, "STOP: source checksum differs")
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), strict=True)
    require(reader.fieldnames == COLUMNS, "Source headers differ")
    rows = list(reader)
    require(len(rows) == 11650, "Source row count differs")
    contracts = load_contracts()
    selected = []
    summaries = []
    for manifest, evidence in contracts:
        fixtures = verify_selection(rows, manifest["selection"], evidence)
        selected.extend(fixtures)
        summaries.append(
            {
                "dataset_id": manifest["dataset_id"],
                "matches": len(fixtures),
                "participants": evidence["participant_count"],
                "goals": evidence["total_goals"],
            }
        )
    require(
        sum(r["tournament"] == "FIFA World Cup" for r in rows) == len(selected),
        "World Cup rows outside approved selections",
    )
    require(
        len({r[k] for r in selected for k in ("home_team", "away_team")}) == 44,
        "Global source participant set differs",
    )
    return {
        "source_revision": REVISION,
        "source_sha256": CHECKSUM,
        "source_rows": len(rows),
        "editions": summaries,
        "matches": len(selected),
        "participants": 44,
        "goals": sum(e["goals"] for e in summaries),
        "status": "PASS",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=ROOT / "data/raw/martj42-womens-results" / REVISION / "results.csv",
    )
    args = parser.parse_args()
    try:
        result = verify_source(args.source)
    except (ValueError, OSError, csv.Error, KeyError, TypeError) as exc:
        parser.exit(1, f"Verification failed: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
