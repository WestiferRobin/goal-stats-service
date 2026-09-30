"""Apply host LOCAL migrations and import football data before development startup."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from football.datasets import import_datasets
from infra.resources.db import Database
from settings.environment import load_local


def main():
    database = Database(load_local().database)
    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        with database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with database.transaction() as session:
            print(f"CSV import complete: {import_datasets(session)}")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
