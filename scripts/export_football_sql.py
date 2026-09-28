# ruff: noqa: E402
"""Generate reviewable PostgreSQL setup/upgrade SQL and bundled dataset inserts."""

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from alembic import command
from alembic.config import Config
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert

from football.datasets import read_datasets
from models.football import FootballHistory, FootballTeam


def export() -> None:
    directory = ROOT / "sql"
    directory.mkdir(exist_ok=True)
    for filename, revision in [
        ("001_fresh_database.sql", "head"),
        ("002_upgrade_template.sql", "b7f42e9c1a60:head"),
    ]:
        stream = io.StringIO()
        config = Config(str(ROOT / "alembic.ini"), output_buffer=stream)
        command.upgrade(config, revision, sql=True)
        sql = stream.getvalue()
        if filename == "002_upgrade_template.sql":
            guard = """DO $$ BEGIN
IF (SELECT count(*) FROM alembic_version) <> 1 OR NOT EXISTS (
    SELECT 1 FROM alembic_version WHERE version_num = 'b7f42e9c1a60'
) THEN RAISE EXCEPTION 'Expected template revision b7f42e9c1a60'; END IF;
END $$;
"""
            sql = sql.replace("BEGIN;", "BEGIN;\n\n" + guard, 1)
        (directory / filename).write_text(sql)
    teams, history = read_datasets()
    # JSON literals use the PostgreSQL string literal compiler; never concatenate raw CSV.
    from sqlalchemy import String, literal

    def json_literal(value):
        return literal(json.dumps(value), type_=String()).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )

    statements = [
        "-- Bundled RoadToTheFinal data. Repeatable; existing rows are preserved.",
        "BEGIN;",
    ]
    for team in teams:
        statement = (
            insert(FootballTeam)
            .values(name=team["name"], ratings=team)
            .on_conflict_do_nothing(index_elements=["name"])
        )
        # JSON's dialect has no literal renderer; substitute a typed SQL string expression.
        from sqlalchemy import literal_column

        statement = statement.values(ratings=literal_column(str(json_literal(team)) + "::json"))
        statements.append(
            str(
                statement.compile(
                    dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
                )
            )
            + ";"
        )
    for row in history:
        values = {**row, "data": literal_column(str(json_literal(row["data"])) + "::json")}
        statement = (
            insert(FootballHistory).values(**values).on_conflict_do_nothing(index_elements=["id"])
        )
        statements.append(
            str(
                statement.compile(
                    dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
                )
            )
            + ";"
        )
    statements.append("COMMIT;")
    (directory / "003_seed_football.sql").write_text("\n".join(statements) + "\n")


if __name__ == "__main__":
    export()
