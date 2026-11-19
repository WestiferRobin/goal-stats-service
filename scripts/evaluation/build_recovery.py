"""Offline full-population rebuild. Never reads/writes the database or original evidence.

PYTHONPATH=src .venv/bin/python -B scripts/evaluation/build_recovery.py
Review generated hashes before updating the runtime manifest pin.
"""

import hashlib
import json
from datetime import date, timedelta

from football import team_ratings
from football.results_recovery import OVERLAY_SHA256, RECOVERY_ID, ROOT, load_overlay, merge_results
from services.evaluation import approved_source, digest
from services.evaluation_full import MANIFEST_SHA256, assets


def write(name, value):
    raw = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    (ROOT / name).write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def complete(rating):
    return rating is not None and all(rating[k] is not None for k in ("offense", "defense", "form"))


def diagnostics(rows, cutoff, team, rating, baseline):
    recent = [
        r
        for r in rows
        if cutoff - timedelta(days=365) < r.day <= cutoff and team in (r.home, r.away)
    ]
    return dict(
        rating=rating,
        matches=rating["evidence"]["matches"] if rating else 0,
        qualifying_form_matches=rating["evidence"]["form_matches"] if rating else 0,
        frozen_baseline_day=(cutoff - timedelta(days=365)).isoformat(),
        team_in_frozen_baseline=team in baseline,
        missing_reference_teams=sorted(
            {n for r in recent for n in (r.home, r.away) if n not in baseline}
        ),
        disqualified_form_fixtures=[
            dict(date=r.day.isoformat(), home=r.home, away=r.away)
            for r in recent
            if r.home not in baseline or r.away not in baseline
        ],
        failures=[]
        if complete(rating)
        else [
            k
            for k, bad in (
                ("fewer_than_eight_matches", rating is None or rating["evidence"]["matches"] < 8),
                (
                    "fewer_than_three_qualifying_form_matches",
                    rating is None or rating["evidence"]["form_matches"] < 3,
                ),
                (
                    "last_match_older_than_730_days",
                    rating is not None
                    and (cutoff - date.fromisoformat(rating["evidence"]["last_match"])).days > 730,
                ),
            )
            if bad
        ],
    )


def main():
    _, registry, old = assets()
    overlay = load_overlay()
    base = approved_source()
    rows = merge_results(base, overlay)
    populations = {}
    baselines = {}
    old_baselines = {}
    for key in old["populations"]:
        cutoff = date.fromisoformat(key)
        earlier = [r for r in rows if r.day <= cutoff]
        values = team_ratings.calculate(earlier, cutoff)
        populations[key] = dict(
            cutoff=key,
            source_rows=len(earlier),
            source_population_hash=digest([r.__dict__ for r in earlier]),
            latest_source_day=max(r.day for r in earlier).isoformat(),
            population_hash=digest(values),
            ratings=values,
            recovery_package_id=RECOVERY_ID,
            overlay_sha256=OVERLAY_SHA256,
            recovered_fixture_ids=[
                r["fixture_id"]
                for r in overlay["fixtures"]
                if (cutoff - timedelta(days=1826)).isoformat() < r["date"] <= key
            ],
        )
        # Fit reference membership precedes individual rating eligibility.
        start = cutoff - timedelta(days=365)
        baselines[key] = {
            n
            for r in rows
            if start - timedelta(days=1461) < r.day <= start
            for n in (r.home, r.away)
        }
        old_baselines[key] = {
            n
            for r in base
            if start - timedelta(days=1461) < r.day <= start
            for n in (r.home, r.away)
        }
        print("Rebuilt", key, len(values), "teams", flush=True)
    cases = []
    editions = {}
    for record in registry["records"]:
        cutoff = date.fromisoformat(record["date"]) - timedelta(days=1)
        key = cutoff.isoformat()
        before = old["populations"][key]["ratings"]
        after = populations[key]["ratings"]
        names = (record["home"], record["away"])
        was = all(complete(before.get(n)) for n in names)
        now = all(complete(after.get(n)) for n in names)
        case = dict(
            match_id=record["match_id"],
            match_key=record["match_key"],
            edition=record["edition"],
            cutoff=key,
            home=names[0],
            away=names[1],
            complete_before=was,
            complete_after=now,
            participants={
                n: dict(
                    before=diagnostics(base, cutoff, n, before.get(n), old_baselines[key]),
                    after=diagnostics(rows, cutoff, n, after.get(n), baselines[key]),
                )
                for n in names
            },
            changed_previously_complete_teams=[
                n for n in names if complete(before.get(n)) and before[n] != after.get(n)
            ],
        )
        cases.append(case)
        e = editions.setdefault(
            record["edition"], dict(total=0, before=0, after=0, newly_complete=[], remaining=[])
        )
        e["total"] += 1
        e["before"] += was
        e["after"] += now
        if not was and now:
            e["newly_complete"].append(record["match_id"])
        if not now:
            e["remaining"].append(record["match_id"])
    report = dict(
        package_id=RECOVERY_ID,
        total_cases=len(cases),
        source_rows_before=len(base),
        source_rows_after=len(rows),
        approved_fixtures=len(overlay["fixtures"]),
        editions=editions,
        remaining_match_ids=[c["match_id"] for c in cases if not c["complete_after"]],
        recovered_match_ids=[
            c["match_id"] for c in cases if not c["complete_before"] and c["complete_after"]
        ],
        affected_rating_cutoffs=[
            k
            for k, p in populations.items()
            if p["population_hash"] != old["populations"][k]["population_hash"]
        ],
        changed_previously_complete_case_ids=[
            c["match_id"]
            for c in cases
            if c["complete_before"] and c["changed_previously_complete_teams"]
        ],
        cases=cases,
    )
    rating_sha = write(
        "ratings.json",
        dict(
            model=team_ratings.MODEL,
            original_source_sha256=team_ratings.SOURCE_SHA,
            overlay_sha256=OVERLAY_SHA256,
            populations=populations,
        ),
    )
    report_sha = write("coverage.json", report)
    manifest = dict(
        package_id=RECOVERY_ID,
        original_manifest_sha256=MANIFEST_SHA256,
        overlay_sha256=OVERLAY_SHA256,
        ratings_sha256=rating_sha,
        coverage_sha256=report_sha,
        historical_availability_verified=False,
        model=team_ratings.MODEL,
        merged_source_hash=digest([r.__dict__ for r in rows]),
        original_source_sha256=team_ratings.SOURCE_SHA,
        expected_cases=348,
        expected_cutoffs=137,
    )
    print("MANIFEST_SHA256", write("manifest.json", manifest), flush=True)
    print(json.dumps(editions, indent=2), flush=True)


if __name__ == "__main__":
    main()
