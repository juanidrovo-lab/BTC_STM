"""Application settings with secure defaults."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    """Centralized runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "btc-stm"
    trading_mode: TradingMode = TradingMode.PAPER
    enable_live_trading: bool = False

    risk_max_daily_loss_pct: float = Field(default=5.0, gt=0.0, le=100.0)
    risk_max_open_positions: int = Field(default=3, ge=1)
    risk_max_risk_per_trade_pct: float = Field(default=1.0, gt=0.0, le=100.0)
    risk_max_position_notional: float = Field(default=10_000.0, gt=0.0)
    risk_kill_switch: bool = False

    database_url: str | None = None        # Neon DB connection string
    persistence_backend: str = "local"     # "local" | "neon"

    @model_validator(mode="after")
    def enforce_live_safety(self) -> "Settings":
        if self.trading_mode is TradingMode.LIVE and not self.enable_live_trading:
            raise ValueError(
                "LIVE trading is blocked unless ENABLE_LIVE_TRADING=true is explicitly set."
            )
        return self


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]
