from decimal import Decimal

from btc_stm.domain import OrderIntent, OrderSide, OrderType, PortfolioState, SymbolFilters
from btc_stm.execution.engine import PaperExecutionEngine
from btc_stm.execution.models import ExecutionReport, ExecutionStatus, PaperPortfolio
from btc_stm.execution.paper_broker import PaperBroker
from btc_stm.risk import RiskManager
from btc_stm.settings import Settings, TradingMode


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


def make_order(stop_loss: Decimal | None = Decimal("90")) -> OrderIntent:
    return OrderIntent(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1"),
        price=Decimal("100"),
        stop_loss=stop_loss,
    )


def make_engine(settings: Settings | None = None) -> PaperExecutionEngine:
    settings = settings or Settings()
    return PaperExecutionEngine(
        settings=settings,
        risk_manager=RiskManager(settings),
        broker=PaperBroker(fee_rate_bps=Decimal("0")),
        slippage_bps=Decimal("10"),
    )


def execute_with_market_price(
    engine: PaperExecutionEngine,
    market_price: Decimal,
) -> tuple[PaperPortfolio, ExecutionReport]:
    portfolio = PaperPortfolio(cash_balance=Decimal("1000"))
    return engine.execute_order(
        order=make_order(),
        paper_portfolio=portfolio,
        risk_portfolio=PortfolioState(
            equity=Decimal("1000"),
            daily_pnl=Decimal("0"),
            open_positions=0,
        ),
        filters=make_filters(),
        market_price=market_price,
    )


def test_paper_execution_engine_has_no_real_order_methods() -> None:
    engine = make_engine()

    for method_name in ("buy", "sell", "create_order", "cancel_order", "place_order"):
        assert not hasattr(engine, method_name)


def test_paper_execution_engine_rejects_when_risk_manager_rejects() -> None:
    engine = make_engine()
    portfolio = PaperPortfolio(cash_balance=Decimal("1000"))

    updated, report = engine.execute_order(
        order=make_order(stop_loss=None),
        paper_portfolio=portfolio,
        risk_portfolio=PortfolioState(
            equity=Decimal("1000"),
            daily_pnl=Decimal("0"),
            open_positions=0,
        ),
        filters=make_filters(),
        market_price=Decimal("100"),
    )

    assert updated == portfolio
    assert report.status is ExecutionStatus.REJECTED
    assert report.reason is not None
    assert "stop-loss" in report.reason


def test_paper_execution_engine_returns_filled_when_risk_approves() -> None:
    engine = make_engine()
    portfolio = PaperPortfolio(cash_balance=Decimal("1000"))

    updated, report = engine.execute_order(
        order=make_order(),
        paper_portfolio=portfolio,
        risk_portfolio=PortfolioState(
            equity=Decimal("1000"),
            daily_pnl=Decimal("0"),
            open_positions=0,
        ),
        filters=make_filters(),
        market_price=Decimal("100"),
    )

    assert report.status is ExecutionStatus.FILLED
    assert report.average_fill_price == Decimal("100.100")
    assert updated.cash_balance == Decimal("899.900")
    assert updated.positions["BTCUSDT"].quantity == Decimal("1")


def test_paper_execution_engine_rejects_live_mode() -> None:
    settings = Settings(trading_mode=TradingMode.LIVE, enable_live_trading=True)
    engine = make_engine(settings)
    portfolio = PaperPortfolio(cash_balance=Decimal("1000"))

    updated, report = engine.execute_order(
        order=make_order(),
        paper_portfolio=portfolio,
        risk_portfolio=PortfolioState(
            equity=Decimal("1000"),
            daily_pnl=Decimal("0"),
            open_positions=0,
        ),
        filters=make_filters(),
        market_price=Decimal("100"),
    )

    assert updated == portfolio
    assert report.status is ExecutionStatus.REJECTED
    assert report.reason is not None
    assert "paper mode" in report.reason


def test_paper_execution_engine_rejects_non_finite_market_price() -> None:
    engine = make_engine()

    for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        updated, report = execute_with_market_price(engine, value)

        assert updated == PaperPortfolio(cash_balance=Decimal("1000"))
        assert report.status is ExecutionStatus.REJECTED
        assert report.reason is not None
        assert "market price" in report.reason


def test_paper_execution_engine_rejects_non_positive_market_price() -> None:
    engine = make_engine()

    updated, report = execute_with_market_price(engine, Decimal("0"))

    assert updated == PaperPortfolio(cash_balance=Decimal("1000"))
    assert report.status is ExecutionStatus.REJECTED
    assert report.reason is not None
    assert "market price" in report.reason


def test_paper_execution_engine_rejects_non_finite_slippage_bps() -> None:
    settings = Settings()

    for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        try:
            PaperExecutionEngine(
                settings=settings,
                risk_manager=RiskManager(settings),
                slippage_bps=value,
            )
        except ValueError as exc:
            assert "finite decimal" in str(exc)
        else:
            raise AssertionError("Expected ValueError")
