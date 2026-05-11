"""Stable CLI output formatting."""

from __future__ import annotations

from btc_stm.orchestration.models import PaperTradingSessionResult
from btc_stm.persistence.models import PersistedSession, SessionManifest


def format_manifest(manifest: SessionManifest) -> str:
    return "\n".join(
        [
            f"session_id: {manifest.session_id}",
            f"symbol: {manifest.symbol}",
            f"created_at: {manifest.created_at.isoformat()}",
            f"total_events: {manifest.total_events}",
            f"total_execution_reports: {manifest.total_execution_reports}",
            f"total_equity_points: {manifest.total_equity_points}",
        ]
    )


def format_session_summary(session: PersistedSession) -> str:
    equity = session.performance_report.equity
    return "\n".join(
        [
            f"session_id: {session.manifest.session_id}",
            f"symbol: {session.manifest.symbol}",
            f"created_at: {session.manifest.created_at.isoformat()}",
            f"total_events: {session.manifest.total_events}",
            f"total_execution_reports: {session.manifest.total_execution_reports}",
            f"total_equity_points: {session.manifest.total_equity_points}",
            f"starting_equity: {equity.starting_equity}",
            f"ending_equity: {equity.ending_equity}",
            f"total_return_pct: {equity.total_return_pct}",
            f"max_drawdown_pct: {equity.max_drawdown_pct}",
        ]
    )


def format_demo_result(
    manifest: SessionManifest,
    result: PaperTradingSessionResult,
) -> str:
    return "\n".join(
        [
            f"session_id: {manifest.session_id}",
            f"execution_reports: {len(result.execution_reports)}",
            f"equity_points: {len(result.equity_curve)}",
            f"ending_equity: {result.performance_report.equity.ending_equity}",
            f"warnings: {len(result.performance_report.warnings)}",
        ]
    )
