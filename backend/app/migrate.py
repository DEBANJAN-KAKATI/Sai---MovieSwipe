"""Schema migrations (Alembic, scripts in backend/migrations). Run on API startup and by the scripts."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .config import BACKEND_DIR
from .db import engine

# Revision equal to the schema that Base.metadata.create_all produced before migrations existed.
BASELINE_REVISION = "0001_initial"


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["configure_logging"] = False
    return cfg


def upgrade_db() -> None:
    """Bring the database to the latest revision (`alembic upgrade head`)."""
    cfg = alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        tables = set(inspect(conn).get_table_names())
        if "alembic_version" not in tables and "media_items" in tables:
            # Pre-Alembic database (created by create_all): adopt it at the baseline instead of re-creating tables.
            command.stamp(cfg, BASELINE_REVISION)
        command.upgrade(cfg, "head")
