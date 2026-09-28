"""Application-owned engine; sessions belong to explicit service operations."""

from contextlib import AbstractContextManager
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from models.action import Action
from models.football import FootballHistory, FootballSnapshot, FootballTeam
from models.item import Item
from settings.database import DatabaseSettings


class Database:
    def __init__(self, settings: DatabaseSettings) -> None:
        # Engine construction is lazy: no connection or DDL occurs here.
        self.engine = create_engine(
            settings.url,
            pool_pre_ping=True,
            pool_timeout=3,
            connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
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
            for model in (FootballTeam, FootballHistory, FootballSnapshot):
                connection.execute(select(model).limit(1)).all()
            return True
    except (SQLAlchemyError, OSError, CommandError):
        return False
