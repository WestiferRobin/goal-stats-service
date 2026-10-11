"""Application-owned engine; sessions belong to explicit service operations."""

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, cast

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from psycopg import Connection as PsycopgConnection
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from models.action import Action
from models.catalog import Competition, Match, Team
from models.football import FootballHistory, FootballSnapshot, FootballTeam
from models.item import Item
from models.prediction import Prediction
from models.scenario import Scenario
from settings.base import ConfigurationError
from settings.database import DatabaseSettings, ImportTarget


class Database:
    def __init__(self, settings: DatabaseSettings) -> None:
        # Engine construction is lazy: no connection or DDL occurs here.
        connect_args: dict[str, object] = {
            "connect_timeout": 3,
            "options": "-c statement_timeout=3000",
        }
        if settings.url.query.get("sslmode"):
            # libpq can otherwise prefer GSS encryption over requested TLS.
            connect_args["gssencmode"] = "disable"
        self.engine = create_engine(
            settings.url,
            pool_pre_ping=True,
            pool_timeout=3,
            connect_args=connect_args,
            hide_parameters=True,
        )
        self.sessions = sessionmaker(
            bind=self.engine, expire_on_commit=False, close_resets_only=False
        )

    def transaction(self) -> AbstractContextManager[Session]:
        """An explicit application operation: commit on success, rollback on failure."""
        return self.sessions.begin()

    def dispose(self) -> None:
        """Release the pool when the owning app/test/CLI operation is retired."""
        self.engine.dispose()


def is_ready(database: Database) -> bool:
    try:
        expected = set(
            ScriptDirectory(str(Path(__file__).resolve().parents[3] / "alembic")).get_heads()
        )
        with database.engine.connect() as connection:
            if connection.scalar(text("SELECT current_database()")) != database.engine.url.database:
                return False
            if (
                not expected
                or set(MigrationContext.configure(connection).get_current_heads()) != expected
            ):
                return False
            connection.execute(select(Item).limit(1)).all()
            connection.execute(select(Action).limit(1)).all()
            for model in (
                FootballTeam,
                FootballHistory,
                FootballSnapshot,
                Team,
                Competition,
                Match,
                Scenario,
                Prediction,
            ):
                connection.execute(select(model).limit(1)).all()
            return True
    except (SQLAlchemyError, OSError, CommandError):
        return False


def verify_import_database(session: Session, target: ImportTarget) -> None:
    """Bounded reads on the same connection that will perform the import."""
    connection = session.connection()
    target.validate(connection.engine.url)
    driver = cast(PsycopgConnection[Any], connection.connection.driver_connection)
    if driver.info.host != target.expect_host:
        raise ConfigurationError("Connected hostname does not match --expect-host.")
    if session.scalar(text("SELECT current_database()")) != target.expect_database:
        raise ConfigurationError("Connected database does not match --expect-database.")
    if session.scalar(text("SELECT current_user")) != connection.engine.url.username:
        raise ConfigurationError("Connected database user differs from configured user.")
    if target.target == "cloud" and not session.scalar(
        text("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
    ):
        raise ConfigurationError("Cloud import connection must use verified TLS.")
    expected = set(
        ScriptDirectory(str(Path(__file__).resolve().parents[3] / "alembic")).get_heads()
    )
    if set(MigrationContext.configure(connection).get_current_heads()) != expected:
        raise ConfigurationError(
            "Historical schema is not current. Verify the target, then run "
            "alembic upgrade head separately before importing."
        )
    try:
        for model in (Team, Competition, Match):
            session.execute(select(model).limit(0)).all()
    except SQLAlchemyError:
        raise ConfigurationError(
            "Historical tables/columns are missing or incompatible. "
            "Verify the target and apply/review migrations separately."
        ) from None
