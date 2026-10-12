"""Explicit imports; application startup never modifies persistent data."""

import json
from pathlib import Path

import click
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from football.datasets import DATA_DIRECTORY, HistoricalImportError, import_datasets
from football.historical_dataset import APPROVED_DATASETS
from football.historical_import import import_historical_dataset
from infra.resources.db import Database
from settings.base import ConfigurationError
from settings.database import ImportTarget, validate_prototype_target


def register_commands(app: Flask, database: Database) -> None:
    @app.cli.command("import-football")
    @click.option(
        "--dataset", help="Explicit manifest dataset identifier; omitted = prototype CSVs."
    )
    @click.option(
        "--directory",
        type=click.Path(exists=True, file_okay=False, path_type=Path),
        default=DATA_DIRECTORY,
    )
    @click.option("--target", type=click.Choice(["local", "cloud", "test"]))
    @click.option("--expect-host")
    @click.option("--expect-database")
    @click.option("--confirm-production", is_flag=True)
    @click.option("--dry-run", is_flag=True)
    def import_football(
        dataset: str | None,
        directory: Path,
        target: str | None,
        expect_host: str | None,
        expect_database: str | None,
        confirm_production: bool,
        dry_run: bool,
    ) -> None:
        """Import prototype CSVs or an explicitly authorized historical dataset."""
        if dataset is None:
            if target or expect_host or expect_database or confirm_production or dry_run:
                raise click.UsageError("Historical safety/dry-run options require --dataset.")
            try:
                validate_prototype_target(database.engine.url)
                with database.transaction() as session:
                    result = import_datasets(session, directory)
            except (ValueError, OSError, SQLAlchemyError):
                raise click.ClickException(
                    "Prototype import failed; verify local target and CSVs."
                ) from None
            click.echo(f"Import complete: {result}")
            return
        if dataset not in APPROVED_DATASETS:
            raise click.UsageError(
                "Unknown historical dataset; use an approved dataset identifier."
            )
        context = click.get_current_context()
        if context.get_parameter_source("directory") != click.core.ParameterSource.COMMANDLINE:
            raise click.UsageError("Historical imports require an explicit --directory.")
        authorization = ImportTarget(
            target or "", expect_host or "", expect_database or "", confirm_production
        )
        try:
            result_summary = import_historical_dataset(
                database, directory, authorization, dry_run=dry_run, dataset_id=dataset
            )
        except HistoricalImportError as exc:
            click.echo(json.dumps(exc.summary.as_dict(), sort_keys=True))
            raise click.ClickException(str(exc)) from None
        except ConfigurationError:
            raise click.ClickException("Invalid import target configuration.") from None
        click.echo(json.dumps(result_summary.as_dict(), sort_keys=True))
