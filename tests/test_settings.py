from pydantic import ValidationError

from btc_stm.settings import Settings, TradingMode


def test_defaults_are_safe() -> None:
    settings = Settings()
    assert settings.trading_mode is TradingMode.PAPER
    assert settings.enable_live_trading is False


def test_live_requires_explicit_activation() -> None:
    try:
        Settings(trading_mode=TradingMode.LIVE, enable_live_trading=False)
    except ValidationError:
        pass
    else:
        raise AssertionError("Expected validation error")
