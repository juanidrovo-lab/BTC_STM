from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from btc_stm.persistence.models import PersistenceConfig, SessionManifest


def test_persistence_config_normalizes_base_dir(tmp_path: Path) -> None:
    config = PersistenceConfig(base_dir=tmp_path / "store")

    assert config.base_dir.is_absolute()
    assert config.base_dir == (tmp_path / "store").resolve()


def test_session_manifest_rejects_empty_session_id() -> None:
    with pytest.raises(ValidationError, match="session_id"):
        SessionManifest(
            session_id=" ",
            symbol="BTCUSDT",
            created_at=datetime(2026, 5, 11, tzinfo=UTC),
            artifact_paths={},
            total_events=0,
            total_execution_reports=0,
            total_equity_points=0,
        )


def test_session_manifest_normalizes_symbol() -> None:
    manifest = SessionManifest(
        session_id="session-1",
        symbol="btc/usdt",
        created_at=datetime(2026, 5, 11, tzinfo=UTC),
        artifact_paths={"manifest": "sessions/session-1/manifest.json"},
        total_events=0,
        total_execution_reports=0,
        total_equity_points=0,
    )

    assert manifest.symbol == "BTCUSDT"


def test_session_manifest_rejects_absolute_artifact_paths() -> None:
    with pytest.raises(ValidationError, match="relative"):
        SessionManifest(
            session_id="session-1",
            symbol="BTCUSDT",
            created_at=datetime(2026, 5, 11, tzinfo=UTC),
            artifact_paths={"manifest": str(Path("C:/tmp/manifest.json"))},
            total_events=0,
            total_execution_reports=0,
            total_equity_points=0,
        )


def test_session_manifest_rejects_artifact_path_traversal() -> None:
    with pytest.raises(ValidationError, match="traversal"):
        SessionManifest(
            session_id="session-1",
            symbol="BTCUSDT",
            created_at=datetime(2026, 5, 11, tzinfo=UTC),
            artifact_paths={"manifest": "../manifest.json"},
            total_events=0,
            total_execution_reports=0,
            total_equity_points=0,
        )
