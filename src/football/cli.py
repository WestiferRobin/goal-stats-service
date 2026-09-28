"""Explicit imports; application startup never modifies persistent data."""

from pathlib import Path

import click
from flask import Flask

from football.datasets import DATA_DIRECTORY, import_datasets
from infra.resources.db import Database


def register_commands(app: Flask, database: Database) -> None:
    @app.cli.command("import-football")
    @click.option(
        "--directory",
        type=click.Path(exists=True, file_okay=False, path_type=Path),
        default=DATA_DIRECTORY,
    )
    def import_football(directory: Path) -> None:
        """Import teams and history atomically; existing rows are preserved."""
        with database.transaction() as session:
            result = import_datasets(session, directory)
        click.echo(f"Import complete: {result}")
