from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    trading_mode: str = Field(default="paper", alias="TRADING_MODE")
    enable_live_trading: bool = Field(default=False, alias="ENABLE_LIVE_TRADING")
    live_trading_opt_in: bool = Field(default=False, alias="LIVE_TRADING_OPT_IN")

    def validate_live_trading_safety(self) -> None:
        """Enforce explicit two-step opt-in before allowing live trading."""
        mode = self.trading_mode.lower().strip()
        if mode == "live":
            if not self.enable_live_trading or not self.live_trading_opt_in:
                raise ValueError(
                    "Live trading is blocked. Set ENABLE_LIVE_TRADING=true and "
                    "LIVE_TRADING_OPT_IN=true to explicitly opt in."
                )


def get_settings() -> Settings:
    """Build and validate runtime settings."""
    settings = Settings()
    settings.validate_live_trading_safety()
    return settings
