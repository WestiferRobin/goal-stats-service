"""Explicit production-only bootstrap. Never called by application construction."""

import argparse
import os
from copy import copy
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from alembic import command
from alembic.config import Config
from psycopg import Error as PostgresError
from psycopg import OperationalError
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError
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


class FailureCategory(Enum):
    CONFIGURATION = "production configuration or target/TLS policy failure"
    SOURCE = "historical source validation failure"
    CONNECTION = "database connection or DNS failure"
    AUTHENTICATION = "PostgreSQL authentication failure"
    TLS = "TLS certificate verification failure"
    TRANSPORT = "database TLS transport verification failure"
    IDENTITY = "database identity mismatch"
    CONFIGURED_HOST = "database identity mismatch: configured hostname"
    CONFIGURED_DATABASE = "database identity mismatch: configured database name"
    CONNECTED_HOST = "database identity mismatch: connected driver hostname"
    CONNECTED_DATABASE = "database identity mismatch: connected database name"
    CONNECTED_USER = "database identity mismatch: connected user"
    GUARD = "database safety guard failure"
    MIGRATION = "Alembic migration failure"
    IMPORT = "historical import failure"
    CATALOG = "catalog verification failure"
    COMMIT = "database transaction completion failure"


IDENTITY_FAILURES = {
    "Database hostname does not match --expect-host.": FailureCategory.CONFIGURED_HOST,
    "Database name does not match --expect-database.": FailureCategory.CONFIGURED_DATABASE,
    "Connected hostname does not match --expect-host.": FailureCategory.CONNECTED_HOST,
    "Connected database does not match --expect-database.": FailureCategory.CONNECTED_DATABASE,
    "Connected database user differs from configured user.": FailureCategory.CONNECTED_USER,
}


@dataclass
class BootstrapDiagnostic:
    stage: FailureCategory = FailureCategory.CONFIGURATION

    def category(self, error: BaseException) -> FailureCategory:
        """Inspect driver failures privately; return only fixed, credential-free labels."""
        seen: set[int] = set()
        while id(error) not in seen:
            seen.add(id(error))
            if isinstance(error, PostgresError):
                if (error.sqlstate or "").startswith("28"):
                    return FailureCategory.AUTHENTICATION
                if isinstance(error, OperationalError) and error.sqlstate is None:
                    # libpq connection failures commonly have no SQLSTATE. Never emit this text.
                    message = str(error).lower()
                    if any(
                        term in message
                        for term in (
                            "certificate verify failed",
                            "certificate verification failed",
                            "root certificate",
                            "server certificate",
                            "ssl certificate",
                        )
                    ):
                        return FailureCategory.TLS
                    if any(
                        term in message
                        for term in (
                            "password authentication failed",
                            "no password supplied",
                            "no pg_hba.conf entry",
                            "authentication failed",
                        )
                    ):
                        return FailureCategory.AUTHENTICATION
                    return FailureCategory.CONNECTION
                if (error.sqlstate or "").startswith("08"):
                    return FailureCategory.CONNECTION
            if isinstance(error, ConfigurationError) and str(error) in IDENTITY_FAILURES:
                return IDENTITY_FAILURES[str(error)]
            if isinstance(error, ConfigurationError) and str(error) == (
                "Cloud import connection must use verified TLS."
            ):
                return FailureCategory.TRANSPORT
            nested = (
                error.orig
                if isinstance(error, DBAPIError)
                else (error.__cause__ or error.__context__)
            )
            if nested is None:
                break
            error = nested
        return self.stage


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


def bootstrap(
    database: Database,
    target: ImportTarget,
    directory: Path,
    diagnostic: BootstrapDiagnostic | None = None,
) -> str:
    """One outer transaction; existing importer commits release only savepoints."""
    diagnostic = diagnostic or BootstrapDiagnostic()
    target.validate(database.engine.url)
    diagnostic.stage = FailureCategory.SOURCE
    batches = [read_historical_dataset(directory, load_manifest(d)) for d in APPROVED_DATASETS]
    diagnostic.stage = FailureCategory.CONNECTION
    with database.engine.begin() as connection:
        bound = copy(database)
        bound.sessions = sessionmaker(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
            close_resets_only=False,
        )
        with bound.transaction() as session:
            diagnostic.stage = FailureCategory.IDENTITY
            verify_database_identity(session, target)
            diagnostic.stage = FailureCategory.GUARD
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
        diagnostic.stage = FailureCategory.MIGRATION
        config = Config(str(ROOT / "alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        diagnostic.stage = FailureCategory.CATALOG
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
            diagnostic.stage = FailureCategory.IMPORT
            for dataset in APPROVED_DATASETS:
                import_historical_dataset(bound, directory, target, dataset_id=dataset)
        diagnostic.stage = FailureCategory.CATALOG
        with bound.transaction() as session:
            verify_catalog(session, batches)
        diagnostic.stage = FailureCategory.COMMIT
    return "imported" if empty else "verified existing"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-production", action="store_true", required=True)
    args = parser.parse_args()
    database = None
    diagnostic = BootstrapDiagnostic()
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
        result = bootstrap(database, target, SOURCE.parent, diagnostic)
    except Exception as error:
        # Never print driver errors, URLs, credentials, or partially committed success reports.
        parser.exit(
            1,
            "Production bootstrap failed; no startup authorized. "
            f"Category: {diagnostic.category(error).value}.\n",
        )
    finally:
        if database is not None:
            database.dispose()
    print(f"Historical bootstrap {result}: 44 teams, 9 competitions, 348 matches verified.")


if __name__ == "__main__":
    main()
