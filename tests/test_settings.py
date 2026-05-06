import pytest

from btc_stm.settings import Settings, get_settings


def test_defaults_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRADING_MODE", raising=False)
    monkeypatch.delenv("ENABLE_LIVE_TRADING", raising=False)
    monkeypatch.delenv("LIVE_TRADING_OPT_IN", raising=False)

    settings = Settings()

    assert settings.trading_mode == "paper"
    assert settings.enable_live_trading is False
    assert settings.live_trading_opt_in is False


def test_live_trading_blocked_without_full_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("ENABLE_LIVE_TRADING", "true")
    monkeypatch.delenv("LIVE_TRADING_OPT_IN", raising=False)

    with pytest.raises(ValueError, match="Live trading is blocked"):
        get_settings()


def test_live_trading_allowed_with_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("ENABLE_LIVE_TRADING", "true")
    monkeypatch.setenv("LIVE_TRADING_OPT_IN", "true")

    settings = get_settings()

    assert settings.trading_mode.lower() == "live"
    assert settings.enable_live_trading is True
    assert settings.live_trading_opt_in is True
