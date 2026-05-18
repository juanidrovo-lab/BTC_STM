"""Allow orchestrator_events without a session — strategy loop system logs.

Without this, the background strategy loop cannot write to orchestrator_events
because it does not belong to any user trading session.

Revision ID: 003
Revises: 002
Create Date: 2026-05-18
"""
from __future__ import annotations

from alembic import op

revision      = "003"
down_revision = "002"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # Make session_id nullable; keeps ON DELETE CASCADE for existing rows.
    op.alter_column("orchestrator_events", "session_id", nullable=True)


def downgrade() -> None:
    op.alter_column("orchestrator_events", "session_id", nullable=False)
