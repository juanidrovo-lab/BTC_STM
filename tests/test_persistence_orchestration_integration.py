from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from btc_stm.data.models import OHLCVBar
from btc_stm.domain import SymbolFilters
from btc_stm.orchestration.models import PaperTradingConfig
from btc_stm.orchestration.paper_trading import PaperTradingOrchestrator
from btc_stm.persistence.local_store import LocalSessionStore
from btc_stm.persistence.models import PersistenceConfig, PersistedSession
from btc_stm.risk import RiskManager
from btc_stm.settings import Settings
from btc_stm.strategy.examples import NoOpStrategy


def make_bar(open_time: datetime) -> OHLCVBar:
    close_time = open_time + timedelta(minutes=1)
    return OHLCVBar(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=close_time,
        open=Decimal("100"),
        high=Decimal("100"),
        low=Decimal("100"),
        close=Decimal("100"),
        volume=Decimal("1"),
        event_time=close_time,
        local_receive_time=close_time,
    )


def make_filters() -> SymbolFilters:
    return SymbolFilters(
        symbol="BTCUSDT",
        price_min=Decimal("1"),
        price_max=Decimal("1000000"),
        price_tick_size=Decimal("0.01"),
        qty_min=Decimal("0.001"),
        qty_max=Decimal("100"),
        qty_step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )


def test_persistence_round_trip_summary_with_orchestrator_result(tmp_path: Path) -> None:
    start = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    settings = Settings()
    result = PaperTradingOrchestrator(
        settings=settings,
        risk_manager=RiskManager(settings),
        filters=make_filters(),
        strategy=NoOpStrategy(),
    ).run(
        PaperTradingConfig(
            symbol="BTCUSDT",
            initial_cash=Decimal("10000"),
            fee_rate_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        ),
        [make_bar(start), make_bar(start + timedelta(minutes=1))],
    )
    store = LocalSessionStore(PersistenceConfig(base_dir=tmp_path))

    store.save_session("noop-session", result)
    summary = store.load_session_summary("noop-session")

    assert isinstance(summary, PersistedSession)
    assert summary.config.initial_cash == Decimal("10000")
    assert summary.performance_report.trades.total_reports == 0
    assert summary.manifest.total_equity_points == 2
