"""One explicit transaction for the manifest-selected historical catalog import."""

from pathlib import Path
from typing import Any

from sqlalchemy import select, text, tuple_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from football.datasets import (
    HistoricalBatch,
    HistoricalImportError,
    ImportSummary,
    read_historical_dataset,
)
from football.historical_dataset import HistoricalMatchRecord, load_manifest
from infra.resources.db import Database, verify_import_database
from models.catalog import Competition, Match, Team
from settings.base import ConfigurationError
from settings.database import ImportTarget


def _match_values(
    record: HistoricalMatchRecord, home: int, away: int, competition: int
) -> dict[str, Any]:
    values = record.model_dump(exclude={"home_team", "away_team", "competition"})
    return {**values, "home_team_id": home, "away_team_id": away, "competition_id": competition}


def _same_facts(
    existing: Match,
    record: HistoricalMatchRecord,
    home: int | None,
    away: int | None,
    competition: int | None,
) -> bool:
    # Provenance can vary across identical source versions/orderings; preserve first import.
    values = _match_values(record, home or -1, away or -1, competition or -1)
    fields = (
        "home_team_id",
        "away_team_id",
        "competition_id",
        "match_date",
        "home_score",
        "away_score",
        "score_basis",
        "neutral",
        "city",
        "country",
    )
    return all(getattr(existing, field) == values[field] for field in fields)


def _compare_and_insert(session: Session, batch: HistoricalBatch, *, dry_run: bool) -> None:
    manifest, records, summary = batch.manifest, batch.records, batch.summary
    team_records = {
        team.name_key: team for record in records for team in (record.home_team, record.away_team)
    }
    existing_teams = {
        team.name_key: team
        for team in session.scalars(
            select(Team).where(
                Team.category == manifest.team_category, Team.name_key.in_(team_records)
            )
        )
    }
    c = manifest.competition
    competition = session.scalar(
        select(Competition).where(
            Competition.name_key == c.name_key,
            Competition.edition_label == c.edition_label,
            Competition.category == c.category,
        )
    )
    existing_matches = {
        match.source_record_key: match
        for match in session.scalars(
            select(Match).where(
                tuple_(Match.source, Match.source_record_key).in_(
                    [(record.source, record.source_record_key) for record in records]
                )
            )
        )
    }
    new_records = []
    for record in records:
        existing = existing_matches.get(record.source_record_key)
        if existing is None:
            new_records.append(record)
            continue
        home = existing_teams.get(record.home_team.name_key)
        away = existing_teams.get(record.away_team.name_key)
        if _same_facts(
            existing,
            record,
            home.team_id if home else None,
            away.team_id if away else None,
            competition.competition_id if competition else None,
        ):
            summary.unchanged += 1
        else:
            summary.conflicts += 1
            summary.issues.append(
                {
                    "source_row": record.source_row,
                    "source_record_key": record.source_record_key,
                    "reason": "stored facts conflict",
                }
            )
    if summary.conflicts:
        raise HistoricalImportError(
            "Stored match facts conflict with the source; review conflicts "
            "explicitly. Nothing was overwritten.",
            summary,
        )
    new_teams = [record for key, record in team_records.items() if key not in existing_teams]
    summary.teams_inserted = len(new_teams)
    summary.competitions_inserted = int(competition is None)
    summary.matches_inserted = len(new_records)
    if dry_run:
        return
    for team_record in new_teams:
        team = Team(**team_record.model_dump())
        session.add(team)
        existing_teams[team_record.name_key] = team
    session.flush()
    if competition is None:
        competition = Competition(**c.model_dump(exclude={"source_tournament"}))
        session.add(competition)
        session.flush()
    for record in new_records:
        session.add(
            Match(
                **_match_values(
                    record,
                    existing_teams[record.home_team.name_key].team_id,
                    existing_teams[record.away_team.name_key].team_id,
                    competition.competition_id,
                )
            )
        )
    session.flush()


def import_historical_dataset(
    database: Database,
    directory: Path,
    target: ImportTarget,
    *,
    dry_run: bool = False,
) -> ImportSummary:
    """No schema changes, updates, deletes or partial commits. Report only after commit."""
    # The only runtime manifest comes from the checked-in contract, not a CLI override.
    try:
        manifest = load_manifest()
    except (OSError, ValueError):
        raise HistoricalImportError(
            "Pinned dataset manifest is missing or invalid.", ImportSummary("unavailable")
        ) from None
    batch = read_historical_dataset(directory, manifest)
    summary = batch.summary
    try:
        target.validate(database.engine.url)
        with database.transaction() as session:
            if dry_run:
                # Must be the first statement: enforce no writes even if comparison regresses.
                session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            verify_import_database(session, target)
            if not dry_run:
                # Serialize cooperating importers before comparison, without upserting conflicts.
                session.execute(text("SELECT pg_advisory_xact_lock(718235940215)"))
            _compare_and_insert(session, batch, dry_run=dry_run)
        summary.committed = not dry_run
        summary.insert_counts = "proposed" if dry_run else "committed"
        return summary
    except (ConfigurationError, HistoricalImportError) as exc:
        summary.discard_insert_counts()
        raise HistoricalImportError(str(exc), summary) from None
    except SQLAlchemyError:
        summary.discard_insert_counts()
        raise HistoricalImportError(
            "Database import failed; the transaction was not confirmed committed. "
            "Verify connectivity/schema and retry a dry-run; existing rows are preserved.",
            summary,
        ) from None
