from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from btc_stm.orchestration.models import (
    OrchestratorEvent,
    OrchestratorEventType,
    PaperTradingConfig,
)


def test_paper_trading_config_rejects_initial_cash_less_than_or_equal_to_zero() -> None:
    with pytest.raises(ValidationError):
        PaperTradingConfig(
            symbol="BTCUSDT",
            initial_cash=Decimal("0"),
            fee_rate_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        )


def test_paper_trading_config_normalizes_symbol() -> None:
    config = PaperTradingConfig(
        symbol="btc/usdt",
        initial_cash=Decimal("1000"),
        fee_rate_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
    )

    assert config.symbol == "BTCUSDT"


def test_paper_trading_config_rejects_non_finite_decimals() -> None:
    with pytest.raises(ValidationError, match="finite"):
        PaperTradingConfig(
            symbol="BTCUSDT",
            initial_cash=Decimal("1000"),
            fee_rate_bps=Decimal("NaN"),
            slippage_bps=Decimal("0"),
        )


def test_paper_trading_config_rejects_invalid_execute_on() -> None:
    with pytest.raises(ValidationError, match="execute_on"):
        PaperTradingConfig(
            symbol="BTCUSDT",
            initial_cash=Decimal("1000"),
            fee_rate_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
            execute_on="mid",
        )


def test_orchestrator_event_rejects_empty_message() -> None:
    with pytest.raises(ValidationError, match="message"):
        OrchestratorEvent(
            event_type=OrchestratorEventType.BAR_RECEIVED,
            timestamp=datetime(2026, 5, 8, tzinfo=UTC),
            message=" ",
        )
