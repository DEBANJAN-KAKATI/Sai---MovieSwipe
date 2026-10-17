"""Artwork fields: wide logos (TV wordmarks) and where an image came from.

Revision ID: 0002_media_artwork
Revises: 0001_initial
Create Date: 2026-10-17 21:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_media_artwork"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("media_items") as batch:
        batch.add_column(sa.Column("logo_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("image_source", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("media_items") as batch:
        batch.drop_column("image_source")
        batch.drop_column("logo_url")
