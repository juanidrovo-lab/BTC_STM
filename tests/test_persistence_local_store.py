import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from btc_stm.data.models import OHLCVBar
from btc_stm.domain import OrderIntent, OrderSide, OrderType, SymbolFilters
from btc_stm.orchestration.models import PaperTradingConfig, PaperTradingSessionResult
from btc_stm.orchestration.paper_trading import PaperTradingOrchestrator
from btc_stm.persistence.local_store import LocalSessionStore
from btc_stm.persistence.models import PersistenceConfig
from btc_stm.risk import RiskManager
from btc_stm.settings import Settings
from btc_stm.strategy.models import StrategyContext, StrategyDecision


def make_bar(open_time: datetime, close_price: Decimal = Decimal("100")) -> OHLCVBar:
    close_time = open_time + timedelta(minutes=1)
    return OHLCVBar(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=close_time,
        open=close_price,
        high=close_price,
        low=close_price,
        close=close_price,
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


def make_order() -> OrderIntent:
    return OrderIntent(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1"),
        price=Decimal("100"),
        stop_loss=Decimal("90"),
    )


class OneDecisionStrategy:
    name = "one_decision"

    def __init__(self) -> None:
        self.called = False

    def on_bar(self, context: StrategyContext) -> StrategyDecision:
        orders = []
        if not self.called:
            orders = [make_order()]
            self.called = True
        return StrategyDecision(
            strategy_name=self.name,
            timestamp=context.current_bar.open_time,
            orders=orders,
        )


def make_session_result() -> PaperTradingSessionResult:
    start = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)
    settings = Settings()
    return PaperTradingOrchestrator(
        settings=settings,
        risk_manager=RiskManager(settings),
        filters=make_filters(),
        strategy=OneDecisionStrategy(),
    ).run(
        PaperTradingConfig(
            symbol="BTCUSDT",
            initial_cash=Decimal("10000"),
            fee_rate_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        ),
        [make_bar(start), make_bar(start + timedelta(minutes=1), Decimal("110"))],
    )


def test_local_session_store_saves_real_paper_trading_session(tmp_path: Path) -> None:
    result = make_session_result()
    store = LocalSessionStore(PersistenceConfig(base_dir=tmp_path))

    manifest = store.save_session("session-1", result)

    assert manifest.total_events == len(result.events)
    assert manifest.total_execution_reports == len(result.execution_reports)
    assert manifest.total_equity_points == len(result.equity_curve)


def test_local_session_store_creates_manifest_and_artifacts(tmp_path: Path) -> None:
    result = make_session_result()
    store = LocalSessionStore(PersistenceConfig(base_dir=tmp_path))

    manifest = store.save_session("session-1", result)

    for artifact_path in manifest.artifact_paths.values():
        assert (tmp_path / artifact_path).exists()
    assert (tmp_path / manifest.artifact_paths["manifest"]).exists()
    assert (tmp_path / manifest.artifact_paths["events"]).exists()
    assert (tmp_path / manifest.artifact_paths["execution_reports"]).exists()
    assert (tmp_path / manifest.artifact_paths["equity_curve"]).exists()


def test_local_session_store_writes_jsonl_rows(tmp_path: Path) -> None:
    result = make_session_result()
    store = LocalSessionStore(PersistenceConfig(base_dir=tmp_path))

    manifest = store.save_session("session-1", result)
    events_path = tmp_path / manifest.artifact_paths["events"]

    rows = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == manifest.total_events


def test_local_session_store_load_manifest(tmp_path: Path) -> None:
    result = make_session_result()
    store = LocalSessionStore(PersistenceConfig(base_dir=tmp_path))
    store.save_session("session-1", result)

    manifest = store.load_manifest("session-1")

    assert manifest.session_id == "session-1"
    assert manifest.symbol == "BTCUSDT"


def test_local_session_store_load_session_summary(tmp_path: Path) -> None:
    result = make_session_result()
    store = LocalSessionStore(PersistenceConfig(base_dir=tmp_path))
    store.save_session("session-1", result)

    summary = store.load_session_summary("session-1")

    assert summary.manifest.session_id == "session-1"
    assert summary.config.symbol == "BTCUSDT"
    assert summary.performance_report.trades.filled_reports == 1


def test_local_session_store_list_sessions(tmp_path: Path) -> None:
    result = make_session_result()
    store = LocalSessionStore(PersistenceConfig(base_dir=tmp_path))
    store.save_session("session-1", result)
    store.save_session("session-2", result)

    sessions = store.list_sessions()

    assert [session.session_id for session in sessions] == ["session-1", "session-2"]


def test_local_session_store_respects_overwrite_false(tmp_path: Path) -> None:
    result = make_session_result()
    store = LocalSessionStore(PersistenceConfig(base_dir=tmp_path))
    store.save_session("session-1", result)

    with pytest.raises(FileExistsError):
        store.save_session("session-1", result)


def test_local_session_store_allows_overwrite_true(tmp_path: Path) -> None:
    result = make_session_result()
    store = LocalSessionStore(PersistenceConfig(base_dir=tmp_path, overwrite=True))
    store.save_session("session-1", result)

    manifest = store.save_session("session-1", result)

    assert manifest.session_id == "session-1"


def test_local_session_store_sanitizes_session_id(tmp_path: Path) -> None:
    result = make_session_result()
    store = LocalSessionStore(PersistenceConfig(base_dir=tmp_path))

    manifest = store.save_session("../bad session", result)

    assert manifest.session_id == "___bad_session"
    assert (tmp_path / "sessions" / "___bad_session" / "manifest.json").exists()
