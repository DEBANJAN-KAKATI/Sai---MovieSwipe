"""Alembic environment: targets app.models on the app's own engine (DATABASE_URL, SQLite by default)."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.config import settings
from app.db import Base, engine

config = context.config

# The API calls migrations in-process and keeps its own logging; only the CLI configures it.
if config.config_file_name and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _configure(**kw) -> None:
    context.configure(
        target_metadata=target_metadata,
        # SQLite can't ALTER most things in place; batch mode recreates the table instead.
        render_as_batch=True,
        compare_type=True,
        **kw,
    )


def run_migrations_offline() -> None:
    _configure(url=settings.database_url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:  # shared by app.migrate
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
        return
    with engine.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
