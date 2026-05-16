"""Single FastAPI entrypoint for Vercel Python runtime.

All /api/* routes are defined here so Vercel has one clear Python
entrypoint to build and deploy.

Vercel config:  vercel.json  →  builds[0].src = "api/index.py"
pyproject.toml: [tool.vercel] entrypoint = "api/index.py"
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI(
    title="BTC-STM API",
    version="0.2.0",
    description="Paper trading engine — Vercel serverless backend",
)


# ─────────────────────────────────────────────
# GET /api/health
# ─────────────────────────────────────────────

@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "btc-stm",
        "version": "0.2.0",
        "trading_mode": os.environ.get("TRADING_MODE", "paper"),
        "persistence_backend": os.environ.get("PERSISTENCE_BACKEND", "local"),
        "db_configured": bool(os.environ.get("DATABASE_URL")),
    }


# ─────────────────────────────────────────────
# GET /api/paper-trade  (schema)
# POST /api/paper-trade (single-tick status)
# ─────────────────────────────────────────────

@app.get("/api/paper-trade")
async def paper_trade_schema() -> dict:
    return {
        "endpoint": "/api/paper-trade",
        "method": "POST",
        "body": {"session_id": "string (required)", "symbol": "string (default: BTCUSDT)"},
        "response": {"status": "ok", "session_id": "string", "events": "integer"},
    }


@app.post("/api/paper-trade")
async def paper_trade(request: Request) -> dict:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL not configured — set it in Vercel environment variables.",
        )

    try:
        body: dict = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    session_id = str(body.get("session_id", "")).strip()
    symbol = str(body.get("symbol", "BTCUSDT")).strip().upper()

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")

    try:
        from btc_stm.persistence.neon_store import NeonSessionStore  # noqa: PLC0415

        store = NeonSessionStore(database_url=database_url)
        try:
            manifest = await store.load_manifest(session_id)
            return {
                "status": "ok",
                "session_id": session_id,
                "symbol": symbol,
                "events": manifest.total_events,
            }
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        finally:
            await store.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────
# GET /api/backtest  (schema)
# POST /api/backtest (run deterministic backtest)
# ─────────────────────────────────────────────

_BACKTEST_SCHEMA = {
    "endpoint": "/api/backtest",
    "POST_body": {
        "symbol": "string — e.g. 'BTCUSDT'",
        "initial_cash": "decimal string — e.g. '10000'",
        "fee_rate_bps": "decimal string, optional, default '10'",
        "slippage_bps": "decimal string, optional, default '5'",
        "bars": [
            {
                "open_time": "ISO-8601 datetime with timezone",
                "close_time": "ISO-8601 datetime with timezone",
                "open": "decimal string",
                "high": "decimal string",
                "low": "decimal string",
                "close": "decimal string",
                "volume": "decimal string",
            }
        ],
    },
    "response": {
        "status": "ok",
        "metrics": {
            "total_return_pct": "string",
            "max_drawdown_pct": "string",
            "total_trades": "int",
            "total_fees_paid": "string",
        },
    },
}


@app.get("/api/backtest")
async def backtest_schema() -> dict:
    return _BACKTEST_SCHEMA


@app.post("/api/backtest")
async def run_backtest(request: Request) -> dict:
    try:
        body: dict = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    symbol = str(body.get("symbol", "BTCUSDT")).strip().upper()
    bars_raw = body.get("bars", [])

    if not isinstance(bars_raw, list) or len(bars_raw) < 2:
        raise HTTPException(status_code=400, detail="bars must be an array with at least 2 entries.")

    def _dec(v: object) -> Decimal:
        try:
            result = Decimal(str(v))
            if not result.is_finite():
                raise ValueError
            return result
        except (InvalidOperation, ValueError):
            raise HTTPException(status_code=400, detail=f"Invalid decimal value: {v!r}")

    try:
        initial_cash = _dec(body.get("initial_cash", "10000"))
        fee_rate_bps = _dec(body.get("fee_rate_bps", "10"))
        slippage_bps = _dec(body.get("slippage_bps", "5"))
    except HTTPException:
        raise

    try:
        from btc_stm.data.models import OHLCVBar  # noqa: PLC0415
        from btc_stm.backtesting.models import BacktestConfig  # noqa: PLC0415
        from btc_stm.backtesting.engine import BacktestEngine  # noqa: PLC0415
        from btc_stm.strategy.examples import NoOpStrategy  # noqa: PLC0415
        from btc_stm.settings import Settings  # noqa: PLC0415
        from btc_stm.risk import RiskManager  # noqa: PLC0415
        from btc_stm.domain import SymbolFilters  # noqa: PLC0415
        from btc_stm.persistence.serialization import to_jsonable  # noqa: PLC0415
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"Import error: {exc}")

    try:
        bars = [
            OHLCVBar(
                symbol=symbol,
                interval=str(b.get("interval", "1m")),
                open_time=datetime.fromisoformat(str(b["open_time"])),
                close_time=datetime.fromisoformat(str(b["close_time"])),
                open=_dec(b["open"]),
                high=_dec(b["high"]),
                low=_dec(b["low"]),
                close=_dec(b["close"]),
                volume=_dec(b["volume"]),
            )
            for b in bars_raw
        ]

        settings = Settings()
        risk_manager = RiskManager(settings)
        filters = SymbolFilters(
            symbol=symbol,
            price_min=Decimal("0.01"),
            price_max=Decimal("9999999"),
            price_tick_size=Decimal("0.01"),
            qty_min=Decimal("0.00001"),
            qty_max=Decimal("9000"),
            qty_step_size=Decimal("0.00001"),
            min_notional=Decimal("1"),
        )
        config = BacktestConfig(
            symbol=symbol,
            initial_cash=initial_cash,
            fee_rate_bps=fee_rate_bps,
            slippage_bps=slippage_bps,
        )
        engine = BacktestEngine(
            settings=settings,
            risk_manager=risk_manager,
            filters=filters,
            strategy=NoOpStrategy(),
        )
        result = engine.run(config=config, bars=bars)
        return {
            "status": "ok",
            "symbol": symbol,
            "bar_count": len(bars),
            "metrics": to_jsonable(result.metrics),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}")
