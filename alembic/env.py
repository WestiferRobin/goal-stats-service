"""Python migration environment sharing the application model metadata."""

from alembic import context
from sqlalchemy.engine import Connection

import models.action  # noqa: F401 — populate migration metadata
import models.football  # noqa: F401
import models.item  # noqa: F401
from infra.resources.db import Database
from models.base import Base
from settings.environment import load_application

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=load_application().database.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied = context.config.attributes.get("connection")
    if isinstance(supplied, Connection):
        context.configure(connection=supplied, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    database = Database(load_application().database)
    try:
        with database.engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        database.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
