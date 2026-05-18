"""BTC-STM FastAPI backend — Railway entry point.

Run locally:
    uvicorn main:app --reload --port 8000

Railway:
    Procfile → uvicorn main:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
from typing import Any

import asyncpg
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Path: make src/btc_stm importable ────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("btc_stm.api")


# ─────────────────────────────────────────────────────────────────────────────
# Database pool
# ─────────────────────────────────────────────────────────────────────────────

_pool: asyncpg.Pool | None = None


def _normalize_db_url(url: str) -> str:
    """Strip channel_binding and map sslmode→ssl for asyncpg."""
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse  # noqa: PLC0415
    p      = urlparse(url)
    scheme = "postgresql" if p.scheme in ("postgresql", "postgres", "postgresql+asyncpg") else p.scheme
    orig   = parse_qs(p.query)
    qs     = {k: v for k, v in orig.items() if k not in ("sslmode", "channel_binding")}
    if "sslmode" in orig and "ssl" not in qs:
        qs["ssl"] = ["require"]
    return urlunparse(p._replace(scheme=scheme, query=urlencode({k: v[0] for k, v in qs.items()})))


async def _get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise HTTPException(status_code=503, detail="Database pool not initialised.")
    return _pool


async def db_query(sql: str, *args: Any) -> list[dict]:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
        return [dict(r) for r in rows]


async def db_execute(sql: str, *args: Any) -> str:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(sql, *args)


# ─────────────────────────────────────────────────────────────────────────────
# App lifecycle
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        try:
            _pool = await asyncpg.create_pool(_normalize_db_url(db_url), min_size=1, max_size=5)
            log.info("DB pool ready")
        except Exception as exc:
            log.warning("DB pool failed to connect: %s", exc)
    else:
        log.warning("DATABASE_URL not set — DB endpoints will fail")
    yield
    if _pool:
        await _pool.close()
        log.info("DB pool closed")


# ─────────────────────────────────────────────────────────────────────────────
# App + CORS
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BTC-STM API",
    version="0.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS — allow Vercel frontend + local dev.
# Set CORS_ORIGINS env var in Railway to override (comma-separated list).
_default_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://*.vercel.app",          # all Vercel preview/prod deployments
]
_env_origins = os.environ.get("CORS_ORIGINS", "")
_allowed_origins = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",   # covers all *.vercel.app dynamically
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# System state helpers (persisted in Neon system_config table)
# ─────────────────────────────────────────────────────────────────────────────

async def is_system_active() -> bool:
    try:
        rows = await db_query("SELECT value FROM system_config WHERE key = 'system_active' LIMIT 1")
        if not rows:
            return True
        return str(rows[0]["value"]).lower() in ("true", "1", "active")
    except Exception:
        return True   # default active if table missing (pre-migration 002)


async def set_system_state(active: bool) -> None:
    await db_execute(
        """
        INSERT INTO system_config (key, value, updated_at)
        VALUES ('system_active', $1, now())
        ON CONFLICT (key) DO UPDATE SET value = $1, updated_at = now()
        """,
        "true" if active else "false",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    symbol:       str     = "BTCUSDT"
    initial_cash: str     = "10000"
    fee_rate_bps: str     = "10"
    slippage_bps: str     = "5"
    execute_on:   str     = "close"
    bars:         list[dict]


class TradeRequest(BaseModel):
    symbol:      str
    side:        str         # "BUY" | "SELL"
    entry:       str
    stop_loss:   str
    take_profit: str


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    bypass = os.environ.get("MIGRATION_BYPASS_TOKEN", "")
    return {
        "status":              "ok",
        "service":             "btc-stm",
        "version":             "0.2.1",
        "build":               "2026-05-18-C",
        "python":              sys.version.split()[0],
        "trading_mode":        os.environ.get("TRADING_MODE", "paper"),
        "persistence_backend": os.environ.get("PERSISTENCE_BACKEND", "neon"),
        "db_configured":       bool(os.environ.get("DATABASE_URL")),
        "bypass_token_set":    bool(bypass),
        "bypass_token_len":    len(bypass.strip()),
        "runtime":             "railway",
    }


# ── Migration ────────────────────────────────────────────────────────────────

@app.post("/api/migrate")
async def migrate(request: Request, token: str = ""):
    # Auth: ?token= query param (FastAPI native) or X-Migration-Secret header
    provided = (token or request.headers.get("X-Migration-Secret", "")).strip()
    bypass   = os.environ.get("MIGRATION_BYPASS_TOKEN", "").strip()
    secret   = os.environ.get("MIGRATION_SECRET", "").strip()

    if not bypass and not secret:
        raise HTTPException(status_code=503, detail="No migration secrets set in Railway env vars (MIGRATION_BYPASS_TOKEN / MIGRATION_SECRET).")

    authorized = (secret and provided == secret) or (bypass and provided == bypass)
    if not authorized:
        raise HTTPException(status_code=403, detail={
            "error":          "Invalid token.",
            "bypass_set":     bool(bypass),
            "secret_set":     bool(secret),
            "provided_len":   len(provided),
            "bypass_len":     len(bypass),
        })

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured.")

    def _run_alembic() -> str:
        from urllib.parse import parse_qs as pqs, urlencode, urlparse, urlunparse  # noqa: PLC0415
        from alembic import command as alembic_cmd  # noqa: PLC0415
        from alembic.config import Config  # noqa: PLC0415

        p = urlparse(db_url)
        if p.scheme in ("postgresql", "postgres"):
            p = p._replace(scheme="postgresql+asyncpg")
        orig = pqs(p.query)
        qs2 = {k: v for k, v in orig.items() if k not in ("sslmode", "channel_binding")}
        if "sslmode" in orig and "ssl" not in qs2:
            qs2["ssl"] = ["require"]
        norm = urlunparse(p._replace(query=urlencode({k: v[0] for k, v in qs2.items()})))

        os.environ["DATABASE_URL"] = norm
        ini   = os.path.join(_ROOT, "db", "alembic.ini")
        buf   = io.StringIO()
        cfg   = Config(ini, stdout=buf)
        cfg.set_main_option("sqlalchemy.url", norm)
        alembic_cmd.upgrade(cfg, "head")
        return buf.getvalue()

    try:
        output = await asyncio.to_thread(_run_alembic)
        return {"status": "ok", "output": output[-4000:] or "Migration completed (no output)."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Migration error: {exc}")


# ── Portfolio metrics ─────────────────────────────────────────────────────────

@app.get("/api/portfolio/metrics")
async def portfolio_metrics():
    try:
        agg = await db_query("""
            SELECT
                COUNT(er.id)::int                                                        AS total_trades,
                COALESCE(SUM(CASE WHEN er.realized_pnl > 0 THEN 1 ELSE 0 END), 0)::int AS winning_trades,
                COALESCE(SUM(er.realized_pnl::float), 0)                                AS total_pnl,
                COALESCE(MAX(ts.initial_cash::float), 10000)                             AS initial_cash,
                COALESCE(
                    (SELECT current_equity::float FROM trading_sessions
                     WHERE current_equity IS NOT NULL ORDER BY started_at DESC LIMIT 1),
                    10000
                )                                                                        AS current_equity,
                COUNT(DISTINCT ts.id)::int                                               AS total_sessions
            FROM trading_sessions ts
            LEFT JOIN execution_reports er ON er.session_id = ts.id
        """)
        row           = agg[0] if agg else {}
        total_trades  = int(row.get("total_trades")  or 0)
        winning       = int(row.get("winning_trades") or 0)
        initial       = float(row.get("initial_cash")   or 10000)
        current       = float(row.get("current_equity") or initial)
        total_sessions = int(row.get("total_sessions") or 0)

        win_rate     = (winning / total_trades * 100) if total_trades > 0 else 0.0
        total_return = ((current - initial) / initial * 100) if initial > 0 else 0.0

        eq_rows = await db_query("""
            SELECT equity::float FROM equity_curve
            WHERE session_id = (SELECT id FROM trading_sessions ORDER BY started_at DESC LIMIT 1)
            ORDER BY recorded_at ASC LIMIT 500
        """)
        max_drawdown = sharpe = 0.0
        if len(eq_rows) > 1:
            import statistics  # noqa: PLC0415
            equities = [r["equity"] for r in eq_rows]
            peak = equities[0]
            for e in equities:
                peak = max(peak, e)
                if peak > 0:
                    max_drawdown = max(max_drawdown, (peak - e) / peak * 100)
            returns = [(equities[i] - equities[i-1]) / equities[i-1]
                       for i in range(1, len(equities)) if equities[i-1] != 0]
            if len(returns) > 1:
                std = statistics.stdev(returns)
                sharpe = round((statistics.mean(returns) / std) * (252 ** 0.5), 2) if std > 0 else 0.0

        sign = "+" if total_return >= 0 else ""
        return {
            "total_return":     round(total_return, 2),
            "total_return_str": f"{sign}{total_return:.2f}%",
            "max_drawdown":     round(-abs(max_drawdown), 2),
            "max_drawdown_str": f"-{max_drawdown:.2f}%",
            "win_rate":         round(win_rate, 1),
            "win_rate_str":     f"{win_rate:.1f}%",
            "sharpe":           sharpe,
            "sharpe_str":       str(sharpe),
            "total_trades":     total_trades,
            "current_equity":   round(current, 2),
            "initial_cash":     round(initial, 2),
            "total_sessions":   total_sessions,
            "source":           "neon" if total_sessions > 0 else "empty",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Logs ─────────────────────────────────────────────────────────────────────

@app.get("/api/logs")
async def logs():
    try:
        rows = await db_query("""
            SELECT event_type, message, created_at
            FROM orchestrator_events
            ORDER BY created_at DESC LIMIT 60
        """)
        result = []
        for r in reversed(rows):
            ts  = r["created_at"]
            ts_str = ts.strftime("%H:%M:%S") if hasattr(ts, "strftime") else str(ts)[11:19]
            et  = str(r.get("event_type", "INFO")).upper()
            lvl = "ERR" if et == "ERROR" else et if et in ("INFO", "OK", "WARN", "ERR") else "INFO"
            result.append({"ts": ts_str, "level": lvl, "msg": r["message"]})
        return {"logs": result, "count": len(result)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Backtest ──────────────────────────────────────────────────────────────────

@app.get("/api/backtest")
async def backtest_schema():
    return {
        "endpoint":   "/api/backtest",
        "method":     "POST",
        "body_fields": ["symbol", "initial_cash", "fee_rate_bps", "slippage_bps", "execute_on", "bars"],
    }


@app.post("/api/backtest")
async def backtest(payload: BacktestRequest):
    from datetime import datetime  # noqa: PLC0415

    symbol     = payload.symbol.strip().upper()
    execute_on = payload.execute_on.strip().lower()
    if execute_on not in {"open", "close"}:
        raise HTTPException(status_code=400, detail="execute_on must be 'open' or 'close'.")
    if len(payload.bars) < 2:
        raise HTTPException(status_code=400, detail="bars must have ≥ 2 entries.")

    def _dec(v: Any, field: str) -> Decimal:
        try:
            r = Decimal(str(v))
            if not r.is_finite():
                raise ValueError
            return r
        except (InvalidOperation, ValueError):
            raise HTTPException(status_code=400, detail=f"Invalid decimal for '{field}': {v!r}")

    try:
        initial_cash = _dec(payload.initial_cash, "initial_cash")
        fee_rate_bps = _dec(payload.fee_rate_bps, "fee_rate_bps")
        slippage_bps = _dec(payload.slippage_bps, "slippage_bps")

        from btc_stm.data.models import OHLCVBar  # noqa: PLC0415
        from btc_stm.domain import SymbolFilters  # noqa: PLC0415
        from btc_stm.orchestration.models import PaperTradingConfig  # noqa: PLC0415
        from btc_stm.orchestration.paper_trading import PaperTradingOrchestrator  # noqa: PLC0415
        from btc_stm.persistence.serialization import to_jsonable  # noqa: PLC0415
        from btc_stm.risk import RiskManager  # noqa: PLC0415
        from btc_stm.settings import Settings  # noqa: PLC0415
        from btc_stm.strategy.examples import NoOpStrategy  # noqa: PLC0415

        bars = [
            OHLCVBar(
                symbol=symbol,
                interval=str(b.get("interval", "1m")),
                open_time=datetime.fromisoformat(str(b["open_time"])),
                close_time=datetime.fromisoformat(str(b["close_time"])),
                open=_dec(b["open"], "open"),
                high=_dec(b["high"], "high"),
                low=_dec(b["low"], "low"),
                close=_dec(b["close"], "close"),
                volume=_dec(b["volume"], "volume"),
            )
            for b in payload.bars
        ]
        settings     = Settings()
        orchestrator = PaperTradingOrchestrator(
            settings=settings,
            risk_manager=RiskManager(settings),
            filters=SymbolFilters(
                symbol=symbol,
                price_min=Decimal("0.01"), price_max=Decimal("9999999"),
                price_tick_size=Decimal("0.01"),
                qty_min=Decimal("0.00001"), qty_max=Decimal("9000"),
                qty_step_size=Decimal("0.00001"), min_notional=Decimal("1"),
            ),
            strategy=NoOpStrategy(),
        )
        config = PaperTradingConfig(
            symbol=symbol, initial_cash=initial_cash,
            fee_rate_bps=fee_rate_bps, slippage_bps=slippage_bps,
            execute_on=execute_on,
        )
        result = await asyncio.to_thread(orchestrator.run, config=config, bars=bars)
        return {"status": "ok", "symbol": symbol, "bar_count": len(bars),
                "metrics": to_jsonable(result.performance_report)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}")


# ── System control ────────────────────────────────────────────────────────────

@app.get("/api/control/status")
async def system_status():
    active  = await is_system_active()
    testnet = os.environ.get("BINANCE_TESTNET", "true").lower() != "false"
    return {
        "system_active": active,
        "testnet":       testnet,
        "network":       "TESTNET" if testnet else "MAINNET",
        "api_key_set":   bool(os.environ.get("BINANCE_API_KEY")),
        "secret_set":    bool(os.environ.get("BINANCE_API_SECRET")),
        "live_trading":  os.environ.get("ENABLE_LIVE_TRADING", "false").lower() == "true",
        "runtime":       "railway",
    }


@app.post("/api/control/reset")
async def system_reset():
    await set_system_state(True)
    return {"status": "ACTIVE", "message": "System re-activated. Trading is unblocked."}


@app.post("/api/control/kill-switch")
async def kill_switch():
    results: dict = {}
    symbol = os.environ.get("KILL_SWITCH_SYMBOL", "BTCUSDT")

    async def _exchange_ops() -> None:
        from btc_stm.exchange.binance_client import BinanceOrderClient  # noqa: PLC0415
        from decimal import Decimal  # noqa: PLC0415

        client = await asyncio.to_thread(BinanceOrderClient.from_env)

        # 1. Cancel all open orders
        try:
            cancelled = await asyncio.to_thread(client.cancel_all_orders, symbol)
            results["cancelled"] = len(cancelled) if isinstance(cancelled, list) else cancelled
        except Exception as exc:
            results["cancel_error"] = str(exc)

        # 2. Close open BTC position at market
        btc = await asyncio.to_thread(client.get_total_balance, "BTC")
        if btc > 0.00001:
            try:
                qty = await asyncio.to_thread(client.round_qty, symbol, Decimal(str(btc)))
                res = await asyncio.to_thread(client.place_market_order, symbol, "SELL", str(qty))
                results["position_closed"] = {"qty": str(qty), "order_id": res.get("orderId")}
            except Exception as exc:
                results["close_error"] = str(exc)
        else:
            results["position_closed"] = "no_open_position"

        await asyncio.to_thread(client.close)

    try:
        await _exchange_ops()
    except Exception as exc:
        results["exchange_error"] = str(exc)

    # Persist HALTED state regardless of exchange errors
    await set_system_state(False)
    results["system_active"] = False

    return {
        "status":  "HALTED",
        "message": "Kill switch activated. All orders cancelled, position closed, system frozen.",
        "details": results,
    }


# ── Live trade execution ──────────────────────────────────────────────────────

@app.post("/api/trade/execute")
async def trade_execute(payload: TradeRequest):
    # Gate 1: system not halted
    if not await is_system_active():
        raise HTTPException(status_code=503,
            detail="System is HALTED. Call POST /api/control/reset to re-activate.")

    # Gate 2: live trading flag
    if os.environ.get("ENABLE_LIVE_TRADING", "false").lower() != "true":
        raise HTTPException(status_code=403,
            detail="Live trading is disabled. Set ENABLE_LIVE_TRADING=true in Railway env vars.")

    try:
        entry       = Decimal(payload.entry)
        stop_loss   = Decimal(payload.stop_loss)
        take_profit = Decimal(payload.take_profit)
    except InvalidOperation as exc:
        raise HTTPException(status_code=400, detail=f"Invalid decimal: {exc}")

    side = payload.side.strip().upper()
    if side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="side must be 'BUY' or 'SELL'.")

    try:
        from btc_stm.exchange.binance_client import BinanceAuthError, BinanceOrderClient  # noqa: PLC0415
        from btc_stm.exchange.trade_guard import TradeGuard, TradeSignal  # noqa: PLC0415

        client = await asyncio.to_thread(BinanceOrderClient.from_env)
        guard  = TradeGuard(client)
        signal = TradeSignal(
            symbol=payload.symbol.upper(), side=side,
            entry=entry, stop_loss=stop_loss, take_profit=take_profit,
        )

        # TradeGuard: EMA-200 trend filter + 1% sizing + ≥1:2 R:R (all sync I/O)
        order = await asyncio.to_thread(guard.validate, signal)

        # Place LIMIT entry
        entry_result = await asyncio.to_thread(
            client.place_limit_order,
            order.symbol, order.side, order.quantity, order.entry_price,
        )

        # Place OCO exit (TP limit + SL stop-limit)
        exit_side = "SELL" if order.side == "BUY" else "BUY"
        oco_result = await asyncio.to_thread(
            client.place_oco_order,
            order.symbol, exit_side, order.quantity,
            order.take_profit_price, order.stop_loss_price, order.stop_limit_price,
        )

        await asyncio.to_thread(client.close)

        testnet = os.environ.get("BINANCE_TESTNET", "true").lower() != "false"
        return {
            "status":      "ok",
            "entry_order": entry_result,
            "oco_order":   oco_result,
            "risk_usdt":   round(order.risk_usdt, 4),
            "rr_ratio":    round(order.rr_ratio, 2),
            "quantity":    order.quantity,
            "ema200":      round(order.ema200, 2),
            "network":     "TESTNET" if testnet else "MAINNET",
        }

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Trade execution failed: {exc}")
