"""Deterministic local demo paper session."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from btc_stm.data.models import OHLCVBar
from btc_stm.domain import SymbolFilters
from btc_stm.orchestration.models import PaperTradingConfig, PaperTradingSessionResult
from btc_stm.orchestration.paper_trading import PaperTradingOrchestrator
from btc_stm.persistence.local_store import LocalSessionStore
from btc_stm.persistence.models import PersistenceConfig, SessionManifest
from btc_stm.risk import RiskManager
from btc_stm.settings import Settings
from btc_stm.strategy.examples import OneShotBuyStrategy


def build_demo_bars(symbol: str = "BTCUSDT") -> list[OHLCVBar]:
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    closes = [Decimal("100"), Decimal("105"), Decimal("110")]
    bars: list[OHLCVBar] = []
    for index, close in enumerate(closes):
        open_time = start + timedelta(minutes=index)
        close_time = open_time + timedelta(minutes=1)
        bars.append(
            OHLCVBar(
                symbol=symbol,
                interval="1m",
                open_time=open_time,
                close_time=close_time,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=Decimal("1"),
                event_time=close_time,
                local_receive_time=close_time,
            )
        )
    return bars


def run_demo_paper_session(
    base_dir: Path,
    session_id: str,
    *,
    overwrite: bool = False,
) -> tuple[SessionManifest, PaperTradingSessionResult]:
    settings = Settings()
    risk_manager = RiskManager(settings)
    symbol = "BTCUSDT"
    result = PaperTradingOrchestrator(
        settings=settings,
        risk_manager=risk_manager,
        filters=_demo_filters(symbol),
        strategy=OneShotBuyStrategy(
            symbol=symbol,
            quantity=Decimal("1"),
            stop_loss_pct=Decimal("5"),
        ),
    ).run(
        PaperTradingConfig(
            symbol=symbol,
            initial_cash=Decimal("10000"),
            fee_rate_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        ),
        build_demo_bars(symbol),
    )
    manifest = LocalSessionStore(
        PersistenceConfig(base_dir=base_dir, overwrite=overwrite)
    ).save_session(session_id, result)
    return manifest, result


def _demo_filters(symbol: str) -> SymbolFilters:
    return SymbolFilters(
        symbol=symbol,
        price_min=Decimal("1"),
        price_max=Decimal("1000000"),
        price_tick_size=Decimal("0.01"),
        qty_min=Decimal("0.001"),
        qty_max=Decimal("100"),
        qty_step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )
