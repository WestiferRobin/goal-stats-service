# ruff: noqa: E402
"""Generate reviewable PostgreSQL setup/upgrade SQL and bundled dataset inserts."""

import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from alembic import command
from alembic.config import Config
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert

from football.datasets import read_datasets
from models.football import FootballHistory, FootballTeam


def export_schema(directory: Path) -> None:
    """Generate schema exports offline without reading prototype datasets."""
    directory.mkdir(parents=True, exist_ok=True)
    stream = io.StringIO()
    config = Config(str(ROOT / "alembic.ini"), output_buffer=stream)
    command.upgrade(config, "head", sql=True)
    sql = "\n".join(line.rstrip() for line in stream.getvalue().splitlines()) + "\n"
    (directory / "001_fresh_database.sql").write_text(sql)


def export_prototype(directory: Path) -> None:
    """Compatibility inserts only; never connect to or modify PostgreSQL."""
    directory = directory / "prototype"
    directory.mkdir(parents=True, exist_ok=True)
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


def export(directory: Path = ROOT / "sql", *, mode: str = "all") -> None:
    """Keep the legacy no-option export-all behavior explicit and documented."""
    if mode not in {"schema", "prototype", "all"}:
        raise ValueError("Unknown SQL export mode")
    if mode in {"schema", "all"}:
        export_schema(directory)
    if mode in {"prototype", "all"}:
        export_prototype(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("schema", "prototype", "all"), default="all")
    parser.add_argument("--output-directory", type=Path, default=ROOT / "sql")
    args = parser.parse_args()
    export(args.output_directory, mode=args.mode)
