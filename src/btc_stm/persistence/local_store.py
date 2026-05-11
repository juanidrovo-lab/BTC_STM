"""Local filesystem store for paper trading sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from btc_stm.analytics.models import PerformanceReport
from btc_stm.orchestration.models import PaperTradingConfig, PaperTradingSessionResult
from btc_stm.persistence.models import PersistenceConfig, PersistedSession, SessionManifest
from btc_stm.persistence.paths import resolve_safe_path, sanitize_session_id
from btc_stm.persistence.serialization import read_json, write_json_atomic, write_jsonl_atomic


class LocalSessionStore:
    def __init__(self, config: PersistenceConfig) -> None:
        self.config = config
        self.base_dir = config.base_dir

    def save_session(
        self,
        session_id: str,
        result: PaperTradingSessionResult,
    ) -> SessionManifest:
        safe_session_id = sanitize_session_id(session_id)
        session_dir = resolve_safe_path(self.base_dir, f"sessions/{safe_session_id}")
        if session_dir.exists() and not self.config.overwrite:
            raise FileExistsError(f"Session already exists: {safe_session_id}")

        artifact_paths = {
            "manifest": f"sessions/{safe_session_id}/manifest.json",
            "config": f"sessions/{safe_session_id}/config.json",
            "performance_report": f"sessions/{safe_session_id}/performance_report.json",
            "events": f"sessions/{safe_session_id}/events.jsonl",
            "execution_reports": f"sessions/{safe_session_id}/execution_reports.jsonl",
            "equity_curve": f"sessions/{safe_session_id}/equity_curve.jsonl",
            "decisions": f"sessions/{safe_session_id}/decisions.jsonl",
        }
        manifest = SessionManifest(
            session_id=safe_session_id,
            symbol=result.config.symbol,
            created_at=datetime.now(UTC),
            artifact_paths=artifact_paths,
            total_events=len(result.events),
            total_execution_reports=len(result.execution_reports),
            total_equity_points=len(result.equity_curve),
        )

        write_json_atomic(self._artifact_path(artifact_paths["config"]), result.config)
        write_json_atomic(
            self._artifact_path(artifact_paths["performance_report"]),
            result.performance_report,
        )
        write_jsonl_atomic(self._artifact_path(artifact_paths["events"]), result.events)
        write_jsonl_atomic(
            self._artifact_path(artifact_paths["execution_reports"]),
            result.execution_reports,
        )
        write_jsonl_atomic(
            self._artifact_path(artifact_paths["equity_curve"]),
            result.equity_curve,
        )
        write_jsonl_atomic(self._artifact_path(artifact_paths["decisions"]), result.decisions)
        write_json_atomic(self._artifact_path(artifact_paths["manifest"]), manifest)
        return manifest

    def load_manifest(self, session_id: str) -> SessionManifest:
        safe_session_id = sanitize_session_id(session_id)
        path = resolve_safe_path(self.base_dir, f"sessions/{safe_session_id}/manifest.json")
        return SessionManifest.model_validate(read_json(path))

    def load_session_summary(self, session_id: str) -> PersistedSession:
        manifest = self.load_manifest(session_id)
        config_path = self._artifact_path(manifest.artifact_paths["config"])
        report_path = self._artifact_path(manifest.artifact_paths["performance_report"])
        return PersistedSession(
            manifest=manifest,
            config=PaperTradingConfig.model_validate(read_json(config_path)),
            performance_report=PerformanceReport.model_validate(read_json(report_path)),
        )

    def list_sessions(self) -> list[SessionManifest]:
        sessions_dir = resolve_safe_path(self.base_dir, "sessions")
        if not sessions_dir.exists():
            return []
        manifests: list[SessionManifest] = []
        for manifest_path in sorted(sessions_dir.glob("*/manifest.json")):
            manifests.append(SessionManifest.model_validate(read_json(manifest_path)))
        return manifests

    def _artifact_path(self, relative_path: str) -> Path:
        return resolve_safe_path(self.base_dir, relative_path)
