from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from models.base import Base

pytestmark = pytest.mark.postgres


def test_fresh_alembic_history_upgrade_downgrade_and_model_agreement(
    postgres_app, postgres_config, monkeypatch
):
    for name in ["APP_ENV", "DATABASE_URL", "LOG_LEVEL", "OPENAPI_ENABLED"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in postgres_config.items():
        monkeypatch.setenv(name, value)
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    command.heads(config)
    command.history(config)
    command.downgrade(config, "base")
    assert postgres_app.test_client().get("/ready").status_code == 503
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    command.current(config)
    command.check(config)
    assert set(Base.metadata.tables) == {
        "items",
        "actions",
        "football_teams",
        "football_history",
        "football_snapshots",
    }
    assert set(inspect(postgres_app.extensions["goalstats_database"].engine).get_table_names()) == {
        "alembic_version",
        "football_teams",
        "football_history",
        "football_snapshots",
        "items",
        "actions",
    }
