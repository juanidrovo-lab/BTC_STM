"""System config table — persistent kill-switch and runtime flags.

Revision ID: 002
Revises: 001
Create Date: 2026-05-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision      = "002"
down_revision = "001"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "system_config",
        sa.Column("key",        sa.Text,                     primary_key=True),
        sa.Column("value",      sa.Text,                     nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),  nullable=False,
                  server_default=sa.text("now()")),
    )
    # Seed default: system is active
    op.execute("INSERT INTO system_config (key, value) VALUES ('system_active', 'true')")


def downgrade() -> None:
    op.drop_table("system_config")
