# ruff: noqa: E402
"""Generate reviewable PostgreSQL setup/upgrade SQL and bundled dataset inserts."""

import argparse
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from alembic import command
from alembic.config import Config


def export_schema(directory: Path) -> None:
    """Generate schema exports offline without reading prototype datasets."""
    directory.mkdir(parents=True, exist_ok=True)
    stream = io.StringIO()
    config = Config(str(ROOT / "alembic.ini"), output_buffer=stream)
    command.upgrade(config, "head", sql=True)
    sql = "\n".join(line.rstrip() for line in stream.getvalue().splitlines()) + "\n"
    (directory / "001_fresh_database.sql").write_text(sql)


def export(directory: Path = ROOT / "sql", *, mode: str = "schema") -> None:
    """Export migrations offline; application data is imported only through approved manifests."""
    if mode != "schema":
        raise ValueError("Only schema exports are supported")
    export_schema(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("schema",), default="schema")
    parser.add_argument("--output-directory", type=Path, default=ROOT / "sql")
    args = parser.parse_args()
    export(args.output_directory, mode=args.mode)
