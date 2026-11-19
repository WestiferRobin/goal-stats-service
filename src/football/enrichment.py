"""Explicit acquisition and atomic, idempotent Teams enrichment. Never seeds matches.

Run with --help. Downloads are private local artifacts, not redistribution permission.
"""

import argparse
import hashlib
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from football import team_ratings
from infra.resources.db import Database, verify_import_database
from models.enrichment import (
    FifaTeamMapping,
    RankingObservation,
    RankingRelease,
    RatingRun,
    TeamRating,
)
from models.team import Team
from settings.database import ImportTarget
from settings.environment import load_application, local_runtime

INDEX_URL = "https://inside.fifa.com/fifa-rankings/world-ranking/women"
API_URL = "https://api.fifa.com/api/v3/fifarankings/rankings/rankingsbyschedule"
ALIASES = {
    "United States": "USA",
    "China": "China PR",
    "Taiwan": "Chinese Taipei",
    "North Korea": "Korea DPR",
    "South Korea": "Korea Republic",
    "Ivory Coast": "Côte d'Ivoire",
}
ROOT = Path(__file__).resolve().parents[2]
RESULTS = (
    ROOT / "data/raw/martj42-womens-results/1855e313ae8bcd0330426e62c8e4cf15ce45077c/results.csv"
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def release_index(raw: bytes) -> list[dict[str, Any]]:
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', raw.decode(), re.S)
    if not match:
        raise ValueError("FIFA release-index page contract changed")
    rows = json.loads(match[1])["props"]["pageProps"]["pageData"]["ranking"]["allAvailableDates"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Empty FIFA release index")
    seen = set()
    dates = set()
    for row in rows:
        if not isinstance(row, dict) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,100}", row.get("id", "")
        ):
            raise ValueError("Invalid release identity")
        day = date.fromisoformat(row["date"])
        if day < date(2003, 1, 1) or day > date.today() or row["id"] in seen or day in dates:
            raise ValueError("Invalid/duplicate FIFA publication date or release")
        seen.add(row["id"])
        dates.add(day)
    return sorted(rows, key=lambda r: r["date"])


def observations(raw: bytes) -> list[dict[str, Any]]:
    body = json.loads(raw)
    if body.get("ContinuationToken") or body.get("ContinuationHash"):
        raise ValueError("FIFA now requires pagination; refusing a partial release")
    rows = body.get("Results")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Empty FIFA observation response")
    seen = set()
    for row in rows:
        identity = row.get("IdTeam")
        if (
            not isinstance(identity, str)
            or not identity.isdigit()
            or identity in seen
            or row.get("Gender") != 2
        ):
            raise ValueError("Invalid/duplicate women's FIFA identity")
        seen.add(identity)
        if not isinstance(row.get("TeamName"), list) or not row["TeamName"]:
            raise ValueError("Missing FIFA team name")
        if type(row.get("RankingStatus")) is not int:
            raise ValueError("Missing ranking status")
        rank, points = row.get("Rank"), row.get("TotalPoints")
        if rank is not None and (type(rank) is not int or rank < 0):
            raise ValueError("Invalid FIFA rank")
        if points is not None and (
            type(points) not in (int, float) or not math.isfinite(points) or points < 0
        ):
            raise ValueError("Invalid FIFA points")
        if row["RankingStatus"] == 0 and rank and points is None:
            raise ValueError("Ranked observation lacks points")
    return rows


def fetch(url: str) -> bytes:
    with urlopen(url, timeout=45) as response:
        if response.status != 200:
            raise ValueError("Source acquisition failed")
        raw: bytes = response.read(20_000_001)
        if len(raw) > 20_000_000:
            raise ValueError("Source exceeds response size limit")
        return raw


def acquire(directory: Path) -> dict[str, Any]:
    if directory.exists():
        raise ValueError("Use a new artifact directory; acquisitions are immutable")
    index = fetch(INDEX_URL)
    releases = release_index(index)

    def download(row: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
        url = API_URL + "?" + urlencode({"rankingScheduleId": row["id"], "language": "en"})
        raw = fetch(url)
        parsed = observations(raw)
        return {**row, "url": url, "sha256": digest(raw), "rows": len(parsed)}, raw

    with ThreadPoolExecutor(max_workers=4) as pool:
        downloaded = list(pool.map(download, releases))
    # No package is written until every release validates successfully.
    directory.mkdir(parents=True)
    (directory / "index.html").write_bytes(index)
    for row, raw in downloaded:
        (directory / (row["id"] + ".json")).write_bytes(raw)
    manifest = {
        "source": INDEX_URL,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "index_sha256": digest(index),
        "releases": [row for row, _ in downloaded],
    }
    (directory / "manifest.json").write_bytes(encoded(manifest))
    return manifest


def load_package(
    directory: Path,
) -> tuple[dict[str, Any], list[tuple[dict[str, Any], list[dict[str, Any]]]]]:
    manifest = json.loads((directory / "manifest.json").read_bytes())
    index = (directory / "index.html").read_bytes()
    if digest(index) != manifest["index_sha256"] or manifest["source"] != INDEX_URL:
        raise ValueError("FIFA index provenance mismatch")
    releases = release_index(index)
    if [(r["id"], r["date"]) for r in releases] != [
        (r["id"], r["date"]) for r in manifest["releases"]
    ]:
        raise ValueError("Release manifest does not match official index")
    package = []
    for row in manifest["releases"]:
        raw = (directory / (row["id"] + ".json")).read_bytes()
        expected_url = API_URL + "?" + urlencode({"rankingScheduleId": row["id"], "language": "en"})
        if digest(raw) != row["sha256"] or row["url"] != expected_url:
            raise ValueError("FIFA observation provenance mismatch")
        values = observations(raw)
        if len(values) != row["rows"]:
            raise ValueError("FIFA observation count mismatch")
        package.append((row, values))
    return manifest, package


def mapped_teams(
    teams: list[Team],
    latest: list[dict[str, Any]],
    known: dict[int, FifaTeamMapping] | None = None,
) -> dict[int, tuple[str, str]]:
    names: dict[str, list[str]] = {}
    for row in latest:
        for label in row["TeamName"]:
            if label["Locale"].startswith("en"):
                names.setdefault(label["Description"], []).append(row["IdTeam"])
    mapped = {}
    for team in teams:
        name = ALIASES.get(team.name, team.name)
        ids = set(names.get(name, []))
        if not ids and known and team.team_id in known:
            previous = known[team.team_id]
            mapped[team.team_id] = (previous.fifa_team_id, previous.source_name)
            continue
        if len(ids) != 1:
            raise ValueError(f"Unresolved FIFA identity for catalog team {team.team_id}")
        mapped[team.team_id] = (ids.pop(), name)
    if len({v[0] for v in mapped.values()}) != len(mapped):
        raise ValueError("Multiple catalog teams map to one FIFA identity")
    return mapped


def import_package(
    session: Session,
    manifest: dict[str, Any],
    package: list[tuple[dict[str, Any], list[dict[str, Any]]]],
    ratings: dict[str, dict[str, Any]],
    report: dict[str, Any],
    cutoff: date,
    *,
    apply: bool,
) -> dict[str, Any]:
    teams = list(
        session.scalars(
            select(Team).where(Team.category == "women_senior_national").order_by(Team.team_id)
        )
    )
    if not teams:
        raise ValueError("No historical catalog teams; enrichment never creates catalog teams")
    inserted = unchanged = 0
    existing_mappings = {r.team_id: r for r in session.scalars(select(FifaTeamMapping))}
    mapping = mapped_teams(teams, package[-1][1], existing_mappings)
    for team_id, (identity, name) in mapping.items():
        existing = existing_mappings.get(team_id)
        if existing and existing.fifa_team_id != identity:
            raise ValueError("Stored FIFA identity conflicts; no automatic remapping")
        if not existing and apply:
            session.add(FifaTeamMapping(team_id=team_id, fifa_team_id=identity, source_name=name))
    for metadata, values in package:
        release = session.get(RankingRelease, metadata["id"])
        if release:
            if (
                release.sha256 != metadata["sha256"]
                or release.published_on.isoformat() != metadata["date"]
            ):
                raise ValueError("Stored ranking release conflicts; no observations overwritten")
            stored = list(
                session.scalars(
                    select(RankingObservation).where(
                        RankingObservation.release_id == release.release_id
                    )
                )
            )
            if {r.fifa_team_id: r.raw for r in stored} != {r["IdTeam"]: r for r in values}:
                raise ValueError("Stored ranking observations are incomplete or changed")
            unchanged += len(values)
            continue
        inserted += len(values)
        if apply:
            session.add(
                RankingRelease(
                    release_id=metadata["id"],
                    published_on=date.fromisoformat(metadata["date"]),
                    retrieved_at=datetime.fromisoformat(manifest["retrieved_at"]),
                    source_url=metadata["url"],
                    sha256=metadata["sha256"],
                    index_sha256=manifest["index_sha256"],
                    release_metadata=metadata,
                )
            )
            session.flush()
            session.add_all(
                [
                    RankingObservation(
                        release_id=metadata["id"],
                        fifa_team_id=r["IdTeam"],
                        rank=r["Rank"] if r["RankingStatus"] == 0 and r.get("Rank") else None,
                        points=Decimal(str(r["TotalPoints"]))
                        if r["RankingStatus"] == 0
                        and r.get("Rank")
                        and r.get("TotalPoints") is not None
                        else None,
                        status=r["RankingStatus"],
                        raw=r,
                    )
                    for r in values
                ]
            )
            session.flush()
    payload = {
        "model": team_ratings.MODEL,
        "cutoff": cutoff.isoformat(),
        "source": team_ratings.SOURCE_SHA,
        "ratings": ratings,
        "report": report,
    }
    run_id = digest(encoded(payload))
    run = session.get(RatingRun, run_id)
    snapshots = {}
    for team in teams:
        snapshots[team.team_id] = ratings.get(
            team.name,
            {
                "offense": None,
                "defense": None,
                "form": None,
                "evidence": {"reason": "no_eligible_matches", "status": "unavailable"},
            },
        )
    if run:
        stored_ratings = {
            r.team_id: {
                "offense": r.offense,
                "defense": r.defense,
                "form": r.form,
                "evidence": r.evidence,
            }
            for r in session.scalars(select(TeamRating).where(TeamRating.run_id == run_id))
        }
        if stored_ratings != snapshots or run.report != report:
            raise ValueError("Stored rating cohort conflicts with reproducible calculation")
    elif apply:
        session.add(
            RatingRun(
                run_id=run_id,
                cutoff=cutoff,
                model_version=team_ratings.MODEL,
                source_sha256=team_ratings.SOURCE_SHA,
                source_url=team_ratings.SOURCE_URL,
                report=report,
            )
        )
        session.flush()
        session.add_all(
            [
                TeamRating(run_id=run_id, team_id=identity, **value)
                for identity, value in snapshots.items()
            ]
        )
        session.flush()
    return {
        "committed": apply,
        "releases": len(package),
        "observations_inserted": inserted,
        "observations_unchanged": unchanged,
        "mapped_teams": len(mapping),
        "run_id": run_id,
        "ratings_inserted": 0 if run else len(snapshots),
        "cutoff": cutoff.isoformat(),
        "coverage": {t.name: snapshots[t.team_id] for t in teams},
        "validation": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("acquire", "import"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--cutoff", type=date.fromisoformat)
    parser.add_argument("--apply", action="store_true", help="Default is a SELECT-only dry-run")
    parser.add_argument("--target", choices=("local", "test", "cloud"))
    parser.add_argument("--expect-host")
    parser.add_argument("--expect-database")
    parser.add_argument("--confirm-production", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command == "acquire":
        result = acquire(args.directory)
        print(
            json.dumps(
                {
                    "releases": len(result["releases"]),
                    "rows": sum(r["rows"] for r in result["releases"]),
                }
            )
        )
        return
    if not all((args.target, args.expect_host, args.expect_database)):
        parser.error("import requires --target, --expect-host and --expect-database")
    manifest, package = load_package(args.directory)
    rows = team_ratings.read_results(RESULTS.read_bytes())
    cutoff = args.cutoff or max(r.day for r in rows)
    if cutoff > min(date.today(), max(r.day for r in rows)):
        parser.error("cutoff must not exceed the source's latest observation or today")
    ratings = team_ratings.calculate(rows, cutoff)
    report = team_ratings.validate_model(rows, cutoff)
    settings = load_application(local_runtime() if args.target == "local" else None)
    target = ImportTarget(
        args.target, args.expect_host, args.expect_database, args.confirm_production
    )
    target.validate(settings.database.url)
    database = Database(settings.database)
    try:
        with database.transaction() as session:
            if not args.apply:
                session.execute(text("SET TRANSACTION READ ONLY"))
            else:
                session.execute(text("SELECT pg_advisory_xact_lock(71839461)"))
            verify_import_database(session, target)
            result = import_package(
                session, manifest, package, ratings, report, cutoff, apply=args.apply
            )
        if args.report:
            args.report.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(json.dumps(result, indent=2, allow_nan=False))
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
