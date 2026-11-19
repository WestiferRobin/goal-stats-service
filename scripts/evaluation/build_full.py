"""Offline evidence build: no database writes or network; requires reviewed source snapshots.

PYTHONPATH=src .venv/bin/python -B scripts/evaluation/build_full.py /path/to/catalog.json
The catalog is a read-only export of existing Match records, never imported by this script.
"""

import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from football import team_ratings
from football.backtesting_evidence import EDITION_COUNTS, reconcile, validate_inventory
from services.evaluation import REVISION, approved_source, digest

ROOT = Path(__file__).resolve().parents[2] / "data/evaluation/womens-world-cup-full-v1"
# Reviewed regulation scores for ALL 19 archive-annotated extra-time matches.
# Checked against the archive's scorer timelines; stoppage time belongs to its half.
ET = {
    "1991-11-24|Denmark|Germany": [1, 1],
    "1991-11-24|Norway|Italy": [2, 2],
    "1995-06-13|Sweden|China": [1, 1],
    "1999-07-01|Brazil|Nigeria": [3, 3],
    "1999-07-10|United States|China": [0, 0],
    "2003-10-12|Germany|Sweden": [1, 1],
    "2011-07-09|England|France": [1, 1],
    "2011-07-09|Germany|Japan": [0, 0],
    "2011-07-10|Brazil|United States": [1, 1],
    "2011-07-17|Japan|United States": [1, 1],
    "2015-06-26|Germany|France": [1, 1],
    "2015-07-04|Germany|England": [0, 0],
    "2019-06-22|Norway|Australia": [1, 1],
    "2019-06-23|France|Brazil": [1, 1],
    "2019-07-03|Netherlands|Sweden": [0, 0],
    "2023-08-06|Sweden|United States": [0, 0],
    "2023-08-07|England|Nigeria": [0, 0],
    "2023-08-11|Spain|Netherlands": [1, 1],
    "2023-08-12|Australia|France": [0, 0],
}
AUTHORS = {
    1991: "David Shannon",
    1995: "David Shannon",
    1999: "David Shannon",
    2003: "Lars Aarhus and Sturmius Burkert",
    2007: "Roberto Di Maggio",
    2011: "Roberto Di Maggio",
    2015: "Karel Stokkermans",
    2019: "Roberto Di Maggio",
    2023: "Roberto Di Maggio",
}


def write(name, value):
    raw = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    (ROOT / name).write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def main(catalog_path):
    catalog = json.loads(Path(catalog_path).read_text())
    assert len(catalog) == 348
    sources = []
    records = []
    used_et = set()
    for year in EDITION_COUNTS:
        filename = f"wwc{str(year)[2:] if year < 2010 else year}f.html"
        raw = (ROOT / "sources" / filename).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        source = dict(
            id=f"rsssf-{year}",
            url="https://www.rsssf.org/tablesw/" + filename,
            publisher="RSSSF",
            authors=AUTHORS[year],
            filename="sources/" + filename,
            sha256=sha,
            revision="content-addressed snapshot " + sha,
            retrieved_on="2026-11-15",
            rights_basis=(
                "Page footer expressly permits copying in whole or part "
                "with author acknowledgement; attribution retained."
            ),
            verification=(
                "archive final scores, stage and extra-time/shootout annotations "
                "reconciled to pinned catalog"
            ),
            independence=(
                "martj42 lists RSSSF among upstream sources; "
                "not claimed as two independent observations"
            ),
        )
        sources.append(source)
        parsed = reconcile(raw, year, catalog)
        for c in catalog:
            key = c["source_record_key"]
            if key not in parsed:
                continue
            archive = parsed[key]
            identity = "|".join([c["match_date"], c["source_home_team"], c["source_away_team"]])
            if archive["extra_time_played"]:
                reg = ET[identity]
                used_et.add(identity)
            else:
                reg = archive["final_score"]
            discrepancies = []
            if identity == "2003-10-12|Germany|Sweden":
                discrepancies.append(
                    "Golden goal minute: RSSSF 97, FIFA 98; both after regulation. "
                    "Regulation score agrees at 1–1; minute discrepancy retained, not resolved."
                )
            if identity == "1999-07-01|Brazil|Nigeria":
                discrepancies.append(
                    "Golden goal minute: RSSSF 104, FIFA 105; both after regulation. "
                    "Regulation score agrees at 3–3; minute discrepancy retained, not resolved."
                )
            records.append(
                dict(
                    match_id=c["match_id"],
                    match_key=key,
                    edition=year,
                    date=c["match_date"],
                    home=c["source_home_team"],
                    away=c["source_away_team"],
                    home_team_id=c["home_team_id"],
                    away_team_id=c["away_team_id"],
                    regulation_minutes=80 if year == 1991 else 90,
                    regulation_score=reg,
                    extra_time_score=archive["final_score"]
                    if archive["extra_time_played"]
                    else None,
                    completion_status="completed",
                    verification_status="verified_attributed_archive",
                    source_id=source["id"],
                    source_url=source["url"],
                    source_sha256=sha,
                    source_revision=source["revision"],
                    catalog_source_sha256=team_ratings.SOURCE_SHA,
                    catalog_revision=REVISION,
                    definition="observed_score_at_end_of_regulation",
                    discrepancies=discrepancies,
                    **archive,
                )
            )
    assert used_et == set(ET)
    records.sort(key=lambda c: (c["date"], c["match_key"]))
    validate_inventory(records)
    registry_hash = write("registry.json", dict(records=records, sources=sources))
    rows = approved_source()
    populations = {}
    for day in sorted({r["date"] for r in records}):
        cutoff = date.fromisoformat(day) - timedelta(days=1)
        earlier = [r for r in rows if r.day <= cutoff]
        values = team_ratings.calculate(earlier, cutoff)
        populations[cutoff.isoformat()] = dict(
            cutoff=cutoff.isoformat(),
            source_rows=len(earlier),
            source_population_hash=digest([r.__dict__ for r in earlier]),
            latest_source_day=max(r.day for r in earlier).isoformat(),
            population_hash=digest(values),
            ratings=values,
        )
        print("Reconstructed", cutoff, len(values), "teams", flush=True)
    rating_hash = write(
        "ratings.json",
        dict(
            model=team_ratings.MODEL,
            source_sha256=team_ratings.SOURCE_SHA,
            source_revision=REVISION,
            populations=populations,
        ),
    )
    rules = json.loads((ROOT / "rules.json").read_text())
    manifest = dict(
        dataset_id="womens-world-cup-full-v1",
        package_id="womens-world-cup-1991-2023-evidence-v1",
        expected_catalog_matches=348,
        expected_dataset_hash="96449615bc6d7ab91252d5d6a988ee47772b22c22d5a6850c981fb132e1d3e88",
        source_revision=REVISION,
        source_sha256=team_ratings.SOURCE_SHA,
        registry_sha256=registry_hash,
        ratings_sha256=rating_hash,
        rules_sha256=hashlib.sha256((ROOT / "rules.json").read_bytes()).hexdigest(),
        historical_availability_verified=False,
        rating_model_version=team_ratings.MODEL,
        prediction_model_version="road-to-the-final-heuristic-v2",
        protocol_version="edition-regulation-v1",
        assumption_policy=(
            "Explicit caller-named, versioned package; no defaults; no observed special ratings"
        ),
        rules=rules,
    )
    manifest["expected_dataset_hash"] = (
        "96449615bc6d7ab91252d5d6a988ee47772b22c22d5a6850c981fb132e1d3e88"
    )
    print("MANIFEST_SHA256", write("manifest.json", manifest), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
