"""Initial schema — all 5 tables for BTC_STM SaaS.

Revision ID: 001
Revises: (none)
Create Date: 2026-05-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Text, primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column("clerk_id", sa.Text, nullable=False, unique=True),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("plan", sa.Text, nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "strategies",
        sa.Column("id", sa.Text, primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column("user_id", sa.Text, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("symbol", sa.Text, nullable=False, server_default="BTCUSDT"),
        sa.Column("config_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_strategies_user", "strategies", ["user_id"])

    op.create_table(
        "trading_sessions",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Text, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("strategy_id", sa.Text, sa.ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="running"),
        sa.Column("initial_cash", sa.Numeric(18, 8), nullable=False),
        sa.Column("current_equity", sa.Numeric(18, 8), nullable=True),
        sa.Column("total_events", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_execution_reports", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_equity_points", sa.Integer, nullable=False, server_default="0"),
        sa.Column("config_json", sa.JSON, nullable=True),
        sa.Column("performance_json", sa.JSON, nullable=True),
        sa.Column("artifact_paths", sa.JSON, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_sessions_user", "trading_sessions", ["user_id", "started_at"])
    op.create_index("idx_sessions_status", "trading_sessions", ["status"])

    op.create_table(
        "execution_reports",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("session_id", sa.Text, sa.ForeignKey("trading_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("side", sa.Text, nullable=False),
        sa.Column("order_type", sa.Text, nullable=True),
        sa.Column("quantity", sa.Numeric(18, 8), nullable=False),
        sa.Column("fill_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("stop_loss", sa.Numeric(18, 8), nullable=True),
        sa.Column("take_profit", sa.Numeric(18, 8), nullable=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("fee_paid", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("realized_pnl", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("report_json", sa.JSON, nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_reports_session", "execution_reports", ["session_id", "executed_at"])
    op.create_index("idx_reports_status", "execution_reports", ["session_id", "status"])

    op.create_table(
        "equity_curve",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Text, sa.ForeignKey("trading_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("equity", sa.Numeric(18, 8), nullable=False),
        sa.Column("cash_balance", sa.Numeric(18, 8), nullable=False),
        sa.Column("position_value", sa.Numeric(18, 8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(18, 8), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_equity_session", "equity_curve", ["session_id", "recorded_at"])

    op.create_table(
        "orchestrator_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Text, sa.ForeignKey("trading_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_events_session", "orchestrator_events", ["session_id", "created_at"])
    op.create_index("idx_events_type", "orchestrator_events", ["event_type", "created_at"])


def downgrade() -> None:
    # Drop in reverse FK dependency order
    op.drop_table("orchestrator_events")
    op.drop_table("equity_curve")
    op.drop_table("execution_reports")
    op.drop_table("trading_sessions")
    op.drop_table("strategies")
    op.drop_table("users")
