"""Persistence models for local session storage."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from btc_stm.analytics.models import PerformanceReport
from btc_stm.orchestration.models import PaperTradingConfig
from btc_stm.strategy.models import normalize_strategy_symbol


class PersistenceConfig(BaseModel):
    base_dir: Path
    overwrite: bool = False

    @field_validator("base_dir")
    @classmethod
    def validate_base_dir(cls, value: Path) -> Path:
        if not str(value).strip():
            raise ValueError("base_dir must not be empty.")
        return value.expanduser().resolve()


class SessionManifest(BaseModel):
    session_id: str
    symbol: str
    created_at: datetime
    artifact_paths: dict[str, str]
    total_events: int = Field(ge=0)
    total_execution_reports: int = Field(ge=0)
    total_equity_points: int = Field(ge=0)

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("session_id must not be empty.")
        return value

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return normalize_strategy_symbol(value)

    @model_validator(mode="after")
    def validate_artifact_paths(self) -> Self:
        for artifact_path in self.artifact_paths.values():
            path = Path(artifact_path)
            if path.is_absolute():
                raise ValueError("artifact_paths must be relative paths.")
            if ".." in path.parts:
                raise ValueError("artifact_paths must not contain path traversal.")
        return self


class PersistedSession(BaseModel):
    manifest: SessionManifest
    config: PaperTradingConfig
    performance_report: PerformanceReport
