"""Explicit production-only bootstrap. Never called by application construction."""

import argparse
import os
from copy import copy
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from football.datasets import HistoricalBatch, read_historical_dataset
from football.historical_dataset import APPROVED_DATASETS, load_manifest
from football.historical_import import import_historical_dataset
from infra.resources.db import Database, verify_database_identity, verify_import_database
from models.base import Base
from models.competition import Competition
from models.match import Match
from models.prediction import Prediction
from models.scenario import Scenario
from models.team import Team
from settings.base import ConfigurationError, Environment
from settings.database import ImportTarget
from settings.environment import load_application

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/bootstrap/results.csv"
CATALOG = (Team, Competition, Match)


def verify_catalog(session: Session, batches: list[HistoricalBatch]) -> None:
    """Compare every source fact/provenance field, not only aggregate counts."""
    teams = {t.name_key: t for t in session.scalars(select(Team))}
    competitions = {c.edition_label: c for c in session.scalars(select(Competition))}
    matches = {m.source_record_key: m for m in session.scalars(select(Match))}
    # Check row counts separately: dictionary keys must not conceal extra rows.
    counts = [session.scalar(select(text("count(*)")).select_from(m)) for m in CATALOG]
    if counts != [44, 9, 348] or [len(teams), len(competitions), len(matches)] != [44, 9, 348]:
        raise ConfigurationError("Bootstrap requires the exact complete historical catalog.")
    for batch in batches:
        manifest = batch.manifest
        competition = competitions.get(manifest.competition.edition_label)
        if competition is None or any(
            getattr(competition, key) != value
            for key, value in manifest.competition.model_dump(exclude={"source_tournament"}).items()
        ):
            raise ConfigurationError("Historical competition differs from the approved source.")
        for record in batch.records:
            for participant in (record.home_team, record.away_team):
                team = teams.get(participant.name_key)
                if team is None or (team.name, team.category) != (
                    participant.name,
                    participant.category,
                ):
                    raise ConfigurationError("Historical team differs from the approved source.")
            expected = record.model_dump(exclude={"home_team", "away_team", "competition"})
            expected.update(
                home_team_id=teams[record.home_team.name_key].team_id,
                away_team_id=teams[record.away_team.name_key].team_id,
                competition_id=competition.competition_id,
            )
            match = matches.get(record.source_record_key)
            if (
                match is None
                or match.imported_at is None
                or any(getattr(match, key) != value for key, value in expected.items())
            ):
                raise ConfigurationError("Historical match differs from the approved source.")


def bootstrap(database: Database, target: ImportTarget, directory: Path) -> str:
    """One outer transaction; existing importer commits release only savepoints."""
    target.validate(database.engine.url)
    batches = [read_historical_dataset(directory, load_manifest(d)) for d in APPROVED_DATASETS]
    with database.engine.begin() as connection:
        bound = copy(database)
        bound.sessions = sessionmaker(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
            close_resets_only=False,
        )
        with bound.transaction() as session:
            verify_database_identity(session, target)
            # Same lock as the importer; serialize cooperating import/bootstrap processes.
            if not session.scalar(text("SELECT pg_try_advisory_xact_lock(718235940215)")):
                raise ConfigurationError("Another historical import/bootstrap is running.")
        allowed = set(Base.metadata.tables) | {
            "alembic_version",
            "items",
            "actions",
            "football_teams",
            "football_history",
            "football_snapshots",
        }
        if set(inspect(connection).get_table_names()) - allowed:
            raise ConfigurationError("Bootstrap refuses a schema containing unrelated tables.")
        config = Config(str(ROOT / "alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        # Hold catalog writes and scenario creation until classification/import/verification end.
        connection.execute(
            text(
                "LOCK TABLE teams, competitions, matches, scenarios, predictions "
                "IN SHARE ROW EXCLUSIVE MODE"
            )
        )
        with bound.transaction() as session:
            verify_import_database(session, target)
            empty = all(
                session.scalar(select(model).limit(1)) is None
                for model in (*CATALOG, Scenario, Prediction)
            )
        if empty:
            for dataset in APPROVED_DATASETS:
                import_historical_dataset(bound, directory, target, dataset_id=dataset)
        with bound.transaction() as session:
            verify_catalog(session, batches)
    return "imported" if empty else "verified existing"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-production", action="store_true", required=True)
    args = parser.parse_args()
    database = None
    try:
        settings = load_application()
        if settings.core.app_env != Environment.PRODUCTION:
            raise ConfigurationError("Bootstrap requires APP_ENV=production.")
        target = ImportTarget(
            "cloud",
            os.environ.get("BOOTSTRAP_EXPECT_HOST", ""),
            os.environ.get("BOOTSTRAP_EXPECT_DATABASE", ""),
            args.confirm_production,
        )
        database = Database(settings.database)
        result = bootstrap(database, target, SOURCE.parent)
    except Exception:
        # Never print driver errors, URLs, credentials, or partially committed success reports.
        parser.exit(
            1,
            "Production bootstrap failed; no startup authorized. "
            "Check source, target/TLS, migration guards and catalog consistency.\n",
        )
    finally:
        if database is not None:
            database.dispose()
    print(f"Historical bootstrap {result}: 44 teams, 9 competitions, 348 matches verified.")


if __name__ == "__main__":
    main()
