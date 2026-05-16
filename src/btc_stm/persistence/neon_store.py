"""Async NeonDB session store backed by SQLAlchemy 2.0 + asyncpg."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from btc_stm.orchestration.models import PaperTradingSessionResult
from btc_stm.persistence.models import PersistedSession, SessionManifest
from btc_stm.persistence.serialization import to_jsonable

if TYPE_CHECKING:  # pragma: no cover
    pass


def _require_sqlalchemy() -> Any:
    """Lazily import SQLAlchemy and raise a helpful error when [db] extras are missing."""
    try:
        import sqlalchemy  # noqa: PLC0415
        return sqlalchemy
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ImportError(
            "SQLAlchemy is not installed.  Install the [db] extras:\n"
            "    pip install btc-stm[db]"
        ) from exc


def _require_asyncpg() -> Any:
    """Lazily import asyncpg and raise a helpful error when [db] extras are missing."""
    try:
        import asyncpg  # noqa: PLC0415
        return asyncpg
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ImportError(
            "asyncpg is not installed.  Install the [db] extras:\n"
            "    pip install btc-stm[db]"
        ) from exc


def _build_metadata() -> Any:
    """Build SQLAlchemy MetaData with table definitions for the trading schema."""
    sa = _require_sqlalchemy()
    _require_asyncpg()  # ensure asyncpg is available when building engine later

    meta = sa.MetaData()

    sa.Table(
        "trading_sessions",
        meta,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="running"),
        sa.Column("initial_cash", sa.Numeric(18, 8), nullable=False),
        sa.Column("current_equity", sa.Numeric(18, 8), nullable=False),
        sa.Column("total_events", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_execution_reports", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_equity_points", sa.Integer, nullable=False, server_default="0"),
        sa.Column("config_json", sa.JSON, nullable=True),
        sa.Column("performance_json", sa.JSON, nullable=True),
        sa.Column("artifact_paths", sa.JSON, nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )

    sa.Table(
        "execution_reports",
        meta,
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "session_id",
            sa.Text,
            sa.ForeignKey("trading_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    sa.Table(
        "equity_curve",
        meta,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Text,
            sa.ForeignKey("trading_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("equity", sa.Numeric(18, 8), nullable=False),
        sa.Column("cash_balance", sa.Numeric(18, 8), nullable=False),
        sa.Column("position_value", sa.Numeric(18, 8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(18, 8), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    sa.Table(
        "orchestrator_events",
        meta,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Text,
            sa.ForeignKey("trading_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    return meta


class NeonSessionStore:
    """Async session store backed by a Neon DB (PostgreSQL) database.

    Uses SQLAlchemy 2.0 async engine with the asyncpg dialect.  All methods
    are coroutines so they must be awaited.

    Example::

        store = NeonSessionStore(database_url=settings.database_url)
        manifest = await store.save_session(session_id, result)
        await store.close()
    """

    def __init__(self, database_url: str) -> None:
        sa = _require_sqlalchemy()

        try:
            from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "SQLAlchemy asyncio extension is not available.  "
                "Install the [db] extras:\n    pip install btc-stm[db]"
            ) from exc

        self._engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
        )
        self._meta = _build_metadata()
        self._sa = sa

    # ------------------------------------------------------------------
    # Table accessors (resolved lazily to avoid forward-ref issues)
    # ------------------------------------------------------------------

    @property
    def _sessions_table(self) -> Any:
        return self._meta.tables["trading_sessions"]

    @property
    def _reports_table(self) -> Any:
        return self._meta.tables["execution_reports"]

    @property
    def _equity_table(self) -> Any:
        return self._meta.tables["equity_curve"]

    @property
    def _events_table(self) -> Any:
        return self._meta.tables["orchestrator_events"]

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def save_session(
        self,
        session_id: str,
        result: PaperTradingSessionResult,
    ) -> SessionManifest:
        """Persist a completed trading session to Neon DB.

        ``daily_pnl`` flows from ``PaperBroker`` into
        ``PaperTradingSessionResult.equity_curve`` as ``EquityPoint.realized_pnl``
        on each bar.  ``save_session`` converts every ``EquityPoint`` via
        ``to_jsonable()`` and inserts a row into ``equity_curve`` with the
        ``realized_pnl`` column set to that value.  The final equity value is
        also stored as ``current_equity`` on the ``trading_sessions`` row.
        """
        sa = self._sa
        now = datetime.now(UTC)
        artifact_paths: dict[str, str] = {}  # no filesystem artifacts for neon backend

        # Determine final equity from the equity curve
        final_equity: Decimal = result.config.initial_cash
        if result.equity_curve:
            final_equity = result.equity_curve[-1].equity

        manifest = SessionManifest(
            session_id=session_id,
            symbol=result.config.symbol,
            created_at=now,
            artifact_paths=artifact_paths,
            total_events=len(result.events),
            total_execution_reports=len(result.execution_reports),
            total_equity_points=len(result.equity_curve),
        )

        config_json = to_jsonable(result.config)
        performance_json = to_jsonable(result.performance_report)

        async with self._engine.begin() as conn:
            # Upsert the trading session row
            existing = await conn.execute(
                sa.select(self._sessions_table.c.id).where(
                    self._sessions_table.c.id == session_id
                )
            )
            if existing.fetchone():
                await conn.execute(
                    sa.update(self._sessions_table)
                    .where(self._sessions_table.c.id == session_id)
                    .values(
                        status="completed",
                        current_equity=str(final_equity),
                        total_events=len(result.events),
                        total_execution_reports=len(result.execution_reports),
                        total_equity_points=len(result.equity_curve),
                        config_json=config_json,
                        performance_json=performance_json,
                        artifact_paths=artifact_paths,
                        ended_at=now,
                    )
                )
                # Remove old child rows to replace them
                await conn.execute(
                    sa.delete(self._reports_table).where(
                        self._reports_table.c.session_id == session_id
                    )
                )
                await conn.execute(
                    sa.delete(self._equity_table).where(
                        self._equity_table.c.session_id == session_id
                    )
                )
                await conn.execute(
                    sa.delete(self._events_table).where(
                        self._events_table.c.session_id == session_id
                    )
                )
            else:
                await conn.execute(
                    sa.insert(self._sessions_table).values(
                        id=session_id,
                        symbol=result.config.symbol,
                        status="completed",
                        initial_cash=str(result.config.initial_cash),
                        current_equity=str(final_equity),
                        total_events=len(result.events),
                        total_execution_reports=len(result.execution_reports),
                        total_equity_points=len(result.equity_curve),
                        config_json=config_json,
                        performance_json=performance_json,
                        artifact_paths=artifact_paths,
                        started_at=now,
                        ended_at=now,
                    )
                )

            # Insert execution reports
            if result.execution_reports:
                report_rows = []
                for report in result.execution_reports:
                    report_json = to_jsonable(report)
                    report_rows.append(
                        {
                            "id": str(uuid.uuid4()),
                            "session_id": session_id,
                            "symbol": report.symbol,
                            "side": report.side.value if hasattr(report.side, "value") else str(report.side),
                            "order_type": None,
                            "quantity": str(report.requested_quantity),
                            "fill_price": str(report.average_fill_price) if report.average_fill_price else None,
                            "stop_loss": None,
                            "take_profit": None,
                            "status": report.status.value if hasattr(report.status, "value") else str(report.status),
                            "rejection_reason": report.reason,
                            "fee_paid": str(report.total_fee),
                            "realized_pnl": "0",
                            "report_json": report_json,
                            "executed_at": report.created_at,
                        }
                    )
                await conn.execute(sa.insert(self._reports_table), report_rows)

            # Insert equity curve — realized_pnl column carries daily_pnl from PaperBroker
            if result.equity_curve:
                equity_rows = [
                    {
                        "session_id": session_id,
                        "equity": str(point.equity),
                        "cash_balance": str(point.cash_balance),
                        "position_value": str(point.position_value),
                        "realized_pnl": str(point.realized_pnl),  # <-- daily_pnl flows here
                        "recorded_at": point.timestamp,
                    }
                    for point in result.equity_curve
                ]
                await conn.execute(sa.insert(self._equity_table), equity_rows)

            # Insert orchestrator events
            if result.events:
                event_rows = [
                    {
                        "session_id": session_id,
                        "event_type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
                        "message": event.message,
                        "metadata": to_jsonable(event.metadata),
                        "created_at": event.timestamp,
                    }
                    for event in result.events
                ]
                await conn.execute(sa.insert(self._events_table), event_rows)

        return manifest

    async def load_manifest(self, session_id: str) -> SessionManifest:
        """Return the ``SessionManifest`` for a stored session."""
        sa = self._sa

        async with self._engine.connect() as conn:
            row = (
                await conn.execute(
                    sa.select(self._sessions_table).where(
                        self._sessions_table.c.id == session_id
                    )
                )
            ).fetchone()

        if row is None:
            raise KeyError(f"Session not found: {session_id}")

        return SessionManifest(
            session_id=str(row.id),
            symbol=str(row.symbol),
            created_at=row.started_at,
            artifact_paths=row.artifact_paths or {},
            total_events=int(row.total_events),
            total_execution_reports=int(row.total_execution_reports),
            total_equity_points=int(row.total_equity_points),
        )

    async def load_session_summary(self, session_id: str) -> PersistedSession:
        """Return a ``PersistedSession`` for a stored session."""
        sa = self._sa

        async with self._engine.connect() as conn:
            row = (
                await conn.execute(
                    sa.select(self._sessions_table).where(
                        self._sessions_table.c.id == session_id
                    )
                )
            ).fetchone()

        if row is None:
            raise KeyError(f"Session not found: {session_id}")

        from btc_stm.analytics.models import PerformanceReport  # noqa: PLC0415
        from btc_stm.orchestration.models import PaperTradingConfig  # noqa: PLC0415

        manifest = SessionManifest(
            session_id=str(row.id),
            symbol=str(row.symbol),
            created_at=row.started_at,
            artifact_paths=row.artifact_paths or {},
            total_events=int(row.total_events),
            total_execution_reports=int(row.total_execution_reports),
            total_equity_points=int(row.total_equity_points),
        )
        config = PaperTradingConfig.model_validate(row.config_json)
        performance_report = PerformanceReport.model_validate(row.performance_json)

        return PersistedSession(
            manifest=manifest,
            config=config,
            performance_report=performance_report,
        )

    async def list_sessions(self) -> list[SessionManifest]:
        """Return manifests for all sessions ordered by ``started_at`` ascending."""
        sa = self._sa

        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(
                    sa.select(self._sessions_table).order_by(
                        self._sessions_table.c.started_at.asc()
                    )
                )
            ).fetchall()

        return [
            SessionManifest(
                session_id=str(row.id),
                symbol=str(row.symbol),
                created_at=row.started_at,
                artifact_paths=row.artifact_paths or {},
                total_events=int(row.total_events),
                total_execution_reports=int(row.total_execution_reports),
                total_equity_points=int(row.total_equity_points),
            )
            for row in rows
        ]

    async def close(self) -> None:
        """Dispose the underlying async engine and release all connections."""
        await self._engine.dispose()
