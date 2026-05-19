"""BTC-STM FastAPI backend — Railway entry point.

Run locally:
    uvicorn main:app --reload --port 8000

Railway:
    Procfile → uvicorn main:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

# Load .env before anything else (local dev — no-op in Railway/production)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import asyncio
import io
import json
import logging
import os
import sys
import time as _time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
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
# Strategy loop state  (in-memory — intentionally reset on each deployment)
# ─────────────────────────────────────────────────────────────────────────────

_loop_state: dict = {
    "running":       False,
    "ticks":         0,
    "signals":       0,
    "orders_placed": 0,
    "last_tick_at":  None,
    "last_error":    None,
    "assets":        [],       # populated from ASSETS_TO_TRADE at loop start
    "per_symbol":    {},       # symbol → {price, ema200, trend, gap_pct, signal, tick_at}
}

# ATR multiplier for stop-loss and take-profit (gives exactly 1:2 R:R)
_ATR_SL_MULT = Decimal("1.5")   # SL distance = 1.5 × ATR-14
_ATR_TP_MULT = Decimal("3.0")   # TP distance = 3.0 × ATR-14  → R:R = 2.0
_MAX_RISK    = Decimal("0.01")  # 1% of free USDT per trade
_SL_SLIP     = Decimal("0.001") # 0.1% slippage buffer on the OCO stop-limit leg


# ─────────────────────────────────────────────────────────────────────────────
# Helpers shared by loop and endpoints
# ─────────────────────────────────────────────────────────────────────────────

async def is_system_active() -> bool:
    try:
        rows = await db_query("SELECT value FROM system_config WHERE key = 'system_active' LIMIT 1")
        if not rows:
            return True
        return str(rows[0]["value"]).lower() in ("true", "1", "active")
    except Exception:
        return True


async def set_system_state(active: bool) -> None:
    await db_execute(
        """
        INSERT INTO system_config (key, value, updated_at)
        VALUES ('system_active', $1, now())
        ON CONFLICT (key) DO UPDATE SET value = $1, updated_at = now()
        """,
        "true" if active else "false",
    )


async def get_live_trading_state() -> bool:
    """DB value overrides env var so the dashboard toggle works at runtime."""
    try:
        rows = await db_query("SELECT value FROM system_config WHERE key = 'live_trading' LIMIT 1")
        if rows:
            return str(rows[0]["value"]).lower() in ("true", "1")
    except Exception:
        pass
    return os.environ.get("ENABLE_LIVE_TRADING", "false").lower() == "true"


async def set_live_trading_state(enabled: bool) -> None:
    await db_execute(
        """
        INSERT INTO system_config (key, value, updated_at)
        VALUES ('live_trading', $1, now())
        ON CONFLICT (key) DO UPDATE SET value = $1, updated_at = now()
        """,
        "true" if enabled else "false",
    )


async def _log_event(event_type: str, message: str, meta: dict | None = None) -> None:
    """Write a system event to orchestrator_events (session_id = NULL for loop events)."""
    try:
        await db_execute(
            """
            INSERT INTO orchestrator_events (session_id, event_type, message, metadata)
            VALUES (NULL, $1, $2, $3)
            """,
            event_type.upper(),
            message[:1000],
            json.dumps(meta or {}),
        )
    except Exception as exc:
        log.warning("[log_event] failed: %s", exc)


def _secs_to_next_candle() -> float:
    """Seconds until the next loop tick.

    LOOP_INTERVAL_MINUTES env var controls frequency (default 5).
    Set to 60 to align with 1h candle closes; lower values for faster local iteration.
    """
    interval_min = int(os.environ.get("LOOP_INTERVAL_MINUTES", "5"))
    if interval_min >= 60:
        now       = _time.time()
        next_hour = (now // 3600 + 1) * 3600 + 5
        return max(next_hour - now, 1.0)
    interval_sec = interval_min * 60
    now          = _time.time()
    next_tick    = (now // interval_sec + 1) * interval_sec + 2
    return max(next_tick - now, 1.0)


def _compute_atr14(klines: list) -> float:
    """ATR-14 from raw kline rows [openTime, o, h, l, c, ...]."""
    trs = []
    for i in range(1, len(klines)):
        high       = float(klines[i][2])
        low        = float(klines[i][3])
        prev_close = float(klines[i - 1][4])
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return sum(trs[-14:]) / 14


# ─────────────────────────────────────────────────────────────────────────────
# Strategy loop core
# ─────────────────────────────────────────────────────────────────────────────

async def _strategy_tick(symbol: str) -> None:
    """One strategy evaluation cycle for a single symbol."""
    from btc_stm.exchange.binance_client import BinanceAuthError, BinanceOrderClient  # noqa: PLC0415
    from btc_stm.exchange.trade_guard import _ema, _EMA_PERIOD  # noqa: PLC0415

    live    = await get_live_trading_state()
    testnet = os.environ.get("BINANCE_TESTNET",    "true").lower()  != "false"

    # ── 1. Check kill-switch (DB, no Binance call) ────────────────────────────
    if not await is_system_active():
        log.info("[loop] system HALTED — skipping tick")
        return

    # ── 2. Fetch klines ───────────────────────────────────────────────────────
    try:
        client = await asyncio.to_thread(BinanceOrderClient.from_env)
        klines = await asyncio.to_thread(client.get_klines, symbol, "1h", 210)
        await asyncio.to_thread(client.close)
    except BinanceAuthError:
        # Credentials not yet configured — loop silently until they are.
        return
    except Exception as exc:
        err = f"klines fetch failed: {exc}"
        log.warning("[loop] %s", err)
        _loop_state["last_error"] = err
        return

    # ── 3. Compute indicators (CPU-only, no network) ──────────────────────────
    closes  = [float(k[4]) for k in klines]
    current = closes[-1]           # last (possibly incomplete) bar's close
    prev    = closes[-2]           # last fully-closed bar

    # EMA-200: exclude the live in-progress bar
    ema200  = _ema(closes[:-1], _EMA_PERIOD)
    atr14   = _compute_atr14(klines)
    gap_pct = (current - ema200) / ema200 * 100

    trend = "BULL" if current > ema200 else ("BEAR" if current < ema200 else "FLAT")

    # Crossover: previous close was on the opposite side of EMA-200
    buy_cross  = prev <= ema200 < current
    sell_cross = prev >= ema200 > current
    signal     = "BUY_CROSS" if buy_cross else ("SELL_CROSS" if sell_cross else None)
    side       = "BUY" if buy_cross else ("SELL" if sell_cross else None)

    tick_at = datetime.now(timezone.utc).isoformat()
    _loop_state["last_tick_at"] = tick_at
    _loop_state["last_error"]   = None
    _loop_state["ticks"]       += 1
    _loop_state["per_symbol"][symbol] = {
        "price":    round(current, 2),
        "ema200":   round(ema200, 2),
        "trend":    trend,
        "gap_pct":  round(gap_pct, 3),
        "signal":   signal,
        "tick_at":  tick_at,
    }

    tick_msg = (f"[loop] tick {_loop_state['ticks']}: {symbol} @ ${current:.2f} | "
                f"EMA200={ema200:.2f} | {trend} | gap={gap_pct:+.2f}% | "
                f"ATR14={atr14:.2f} | signal={signal or 'none'}")
    log.info(tick_msg)
    await _log_event("INFO", tick_msg)

    if signal is None:
        return

    _loop_state["signals"] += 1

    # ── 4. Build order parameters (CPU-only) ──────────────────────────────────
    entry_d  = Decimal(str(round(current, 2)))
    atr_d    = Decimal(str(round(atr14, 8)))
    sl_dist  = _ATR_SL_MULT * atr_d

    if side == "BUY":
        stop_loss   = entry_d - sl_dist
        take_profit = entry_d + _ATR_TP_MULT * atr_d
        stop_limit  = stop_loss * (Decimal("1") - _SL_SLIP)
    else:
        stop_loss   = entry_d + sl_dist
        take_profit = entry_d - _ATR_TP_MULT * atr_d
        stop_limit  = stop_loss * (Decimal("1") + _SL_SLIP)

    sig_msg = (f"[loop] SIGNAL {signal}: {side} {symbol} @ {entry_d} | "
               f"SL={stop_loss:.2f} TP={take_profit:.2f} ATR={atr14:.2f} "
               f"network={'TESTNET' if testnet else 'MAINNET'} live={live}")
    log.info(sig_msg)
    await _log_event("INFO", sig_msg, {
        "signal": signal, "entry": str(entry_d),
        "stop_loss": str(stop_loss), "take_profit": str(take_profit),
        "atr14": str(round(atr14, 2)), "ema200": str(round(ema200, 2)),
    })

    if not live:
        return   # paper mode: logged above, nothing sent to exchange

    # ── 5. Live execution (extra REST calls only when a signal fires) ─────────
    await _execute_loop_trade(symbol, side, entry_d, stop_loss, take_profit, stop_limit)


async def _execute_loop_trade(
    symbol:      str,
    side:        str,
    entry:       Decimal,
    stop_loss:   Decimal,
    take_profit: Decimal,
    stop_limit:  Decimal,
) -> None:
    """Place limit entry + OCO exit. 4 REST calls: account + lot-info + order + oco."""
    from btc_stm.exchange.binance_client import BinanceOrderClient  # noqa: PLC0415

    client = await asyncio.to_thread(BinanceOrderClient.from_env)
    try:
        # REST call 2: account balance
        balance_f = await asyncio.to_thread(client.get_free_balance, "USDT")
        balance   = Decimal(str(balance_f))
        if balance < Decimal("10"):
            msg = f"[loop] insufficient balance (${balance_f:.2f}) — order skipped"
            log.warning(msg)
            await _log_event("WARN", msg)
            return

        risk_usdt = balance * _MAX_RISK
        sl_dist   = abs(entry - stop_loss)
        raw_qty   = risk_usdt / sl_dist

        # REST call 3: exchange info (lot-size filter)
        qty = await asyncio.to_thread(client.round_qty, symbol, raw_qty)

        # Format prices to 2 dp (BTCUSDT tick size)
        def _p(d: Decimal) -> str:
            return str(d.quantize(Decimal("0.01"), rounding=ROUND_DOWN))

        # REST call 4: LIMIT entry
        entry_res = await asyncio.to_thread(
            client.place_limit_order, symbol, side, str(qty), _p(entry),
        )

        # REST call 5: OCO exit
        exit_side = "SELL" if side == "BUY" else "BUY"
        oco_res   = await asyncio.to_thread(
            client.place_oco_order,
            symbol, exit_side, str(qty),
            _p(take_profit), _p(stop_loss), _p(stop_limit),
        )

        _loop_state["orders_placed"] += 1
        ok_msg = (f"[loop] ORDER PLACED: {side} {qty} {symbol} @ {_p(entry)} | "
                  f"SL={_p(stop_loss)} TP={_p(take_profit)} risk=${float(risk_usdt):.2f}")
        log.info(ok_msg)
        await _log_event("OK", ok_msg, {
            "entry_order_id": entry_res.get("orderId"),
            "oco_order_id":   oco_res.get("orderListId"),
            "qty":            str(qty),
            "risk_usdt":      float(risk_usdt),
        })

    except Exception as exc:
        err_msg = f"[loop] order failed: {exc}"
        log.error(err_msg)
        _loop_state["last_error"] = str(exc)
        await _log_event("ERROR", err_msg)
    finally:
        await asyncio.to_thread(client.close)


async def _strategy_loop() -> None:
    """
    Background task: wakes up every LOOP_INTERVAL_MINUTES (default 5) and
    evaluates each asset in ASSETS_TO_TRADE independently.
    """
    assets = [
        s.strip().upper()
        for s in os.environ.get("ASSETS_TO_TRADE", "BTCUSDT").split(",")
        if s.strip()
    ]
    interval_min = int(os.environ.get("LOOP_INTERVAL_MINUTES", "5"))
    _loop_state["running"] = True
    _loop_state["assets"]  = assets
    log.info("[loop] started — assets: %s — interval: %d min", assets, interval_min)
    await _log_event("INFO", f"[loop] iniciado — activos: {', '.join(assets)} — intervalo: {interval_min} min")

    while True:
        wait = _secs_to_next_candle()
        log.info("[loop] próximo tick en %.0f s", wait)
        await asyncio.sleep(wait)

        for symbol in assets:
            try:
                await _strategy_tick(symbol)
            except asyncio.CancelledError:
                _loop_state["running"] = False
                return
            except Exception as exc:
                err = f"[loop] error en tick {symbol}: {exc}"
                log.exception(err)
                _loop_state["last_error"] = err
                try:
                    await _log_event("ERROR", err)
                except Exception:
                    pass

    _loop_state["running"] = False
    log.info("[loop] detenido")


# ─────────────────────────────────────────────────────────────────────────────
# App lifecycle
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool

    # Database pool
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        try:
            _pool = await asyncpg.create_pool(_normalize_db_url(db_url), min_size=1, max_size=5)
            log.info("DB pool ready")
        except Exception as exc:
            log.warning("DB pool failed to connect: %s", exc)
    else:
        log.warning("DATABASE_URL not set — DB endpoints will fail")

    # Strategy loop — only starts if at least BINANCE_API_KEY is configured.
    # In paper mode ENABLE_LIVE_TRADING=false the loop still runs: it logs signals
    # without placing real orders so you can verify the strategy before going live.
    loop_task: asyncio.Task | None = None
    if os.environ.get("BINANCE_API_KEY", "").strip():
        loop_task = asyncio.create_task(_strategy_loop(), name="strategy_loop")
        log.info("[loop] task created")
    else:
        log.info("[loop] BINANCE_API_KEY not set — strategy loop disabled")

    yield

    if loop_task and not loop_task.done():
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass

    if _pool:
        await _pool.close()
        log.info("DB pool closed")


# ─────────────────────────────────────────────────────────────────────────────
# App + CORS
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BTC-STM API",
    version="0.3.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

_default_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://*.vercel.app",
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
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    side:        str
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
        "version":             "0.3.0",
        "build":               "2026-05-18-D",
        "python":              sys.version.split()[0],
        "trading_mode":        os.environ.get("TRADING_MODE", "paper"),
        "persistence_backend": os.environ.get("PERSISTENCE_BACKEND", "neon"),
        "db_configured":       bool(os.environ.get("DATABASE_URL")),
        "api_key_set":         bool(os.environ.get("BINANCE_API_KEY", "").strip()),
        "loop_running":        _loop_state["running"],
        "bypass_token_set":    bool(bypass),
        "runtime":             "railway",
    }


# ── Migration ────────────────────────────────────────────────────────────────

@app.post("/api/migrate")
async def migrate(request: Request, token: str = ""):
    provided = (token or request.headers.get("X-Migration-Secret", "")).strip()
    bypass   = os.environ.get("MIGRATION_BYPASS_TOKEN", "").strip()
    secret   = os.environ.get("MIGRATION_SECRET", "").strip()

    if not bypass and not secret:
        raise HTTPException(status_code=503, detail="No migration secrets configured.")

    authorized = (secret and provided == secret) or (bypass and provided == bypass)
    if not authorized:
        raise HTTPException(status_code=403, detail={
            "error":        "Invalid token.",
            "bypass_set":   bool(bypass),
            "secret_set":   bool(secret),
            "provided_len": len(provided),
            "bypass_len":   len(bypass),
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
        qs2  = {k: v for k, v in orig.items() if k not in ("sslmode", "channel_binding")}
        if "sslmode" in orig and "ssl" not in qs2:
            qs2["ssl"] = ["require"]
        norm = urlunparse(p._replace(query=urlencode({k: v[0] for k, v in qs2.items()})))

        os.environ["DATABASE_URL"] = norm
        ini = os.path.join(_ROOT, "db", "alembic.ini")
        buf = io.StringIO()
        cfg = Config(ini, stdout=buf)
        cfg.set_main_option("sqlalchemy.url", norm)
        alembic_cmd.upgrade(cfg, "head")
        return buf.getvalue()

    try:
        output = await asyncio.to_thread(_run_alembic)
        return {"status": "ok", "output": output[-4000:] or "Migration completed (no output)."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Migration error: {exc}")


# ── Strategy loop status ──────────────────────────────────────────────────────

@app.get("/api/strategy/status")
async def strategy_status():
    secs_until_next = _secs_to_next_candle() if _loop_state["running"] else None
    live = await get_live_trading_state()
    return {
        **_loop_state,
        "live_trading":    live,
        "interval":        "1h",
        "connection_type": "REST-only",
        "next_tick_secs":  round(secs_until_next, 0) if secs_until_next else None,
    }


@app.get("/api/analytics/performance")
async def analytics_performance(symbol: str = "BTCUSDT"):
    """Métricas de rendimiento: winrate, profit factor, PnL total para un activo."""
    sym = symbol.strip().upper()
    try:
        rows = await db_query("""
            SELECT
                COUNT(*)::int                                                                      AS total_trades,
                COALESCE(SUM(CASE WHEN er.realized_pnl::float >  0 THEN 1 ELSE 0 END), 0)::int   AS winning_trades,
                COALESCE(SUM(CASE WHEN er.realized_pnl::float <  0 THEN 1 ELSE 0 END), 0)::int   AS losing_trades,
                COALESCE(SUM(CASE WHEN er.realized_pnl::float >  0 THEN er.realized_pnl::float ELSE 0 END), 0) AS gross_profit,
                COALESCE(SUM(CASE WHEN er.realized_pnl::float <= 0 THEN ABS(er.realized_pnl::float) ELSE 0 END), 0) AS gross_loss,
                COALESCE(SUM(er.realized_pnl::float), 0)                                          AS total_pnl
            FROM execution_reports er
            WHERE er.symbol = $1
        """, sym)

        r            = rows[0] if rows else {}
        total        = int(r.get("total_trades")   or 0)
        winning      = int(r.get("winning_trades")  or 0)
        losing       = int(r.get("losing_trades")   or 0)
        gross_profit = float(r.get("gross_profit")  or 0)
        gross_loss   = float(r.get("gross_loss")    or 0)
        total_pnl    = float(r.get("total_pnl")     or 0)

        winrate       = (winning / total * 100) if total > 0 else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
        avg_win       = (gross_profit / winning) if winning > 0 else 0.0
        avg_loss      = -(gross_loss  / losing)  if losing  > 0 else 0.0

        pf_str = f"{profit_factor:.2f}x" if profit_factor != float("inf") else "∞"

        return {
            "symbol":          sym,
            "total_trades":    total,
            "winning_trades":  winning,
            "losing_trades":   losing,
            "winrate":         round(winrate, 1),
            "winrate_str":     f"{winrate:.1f}%",
            "profit_factor":   round(profit_factor, 2) if profit_factor != float("inf") else None,
            "profit_factor_str": pf_str,
            "total_pnl":       round(total_pnl, 2),
            "avg_win":         round(avg_win, 2),
            "avg_loss":        round(avg_loss, 2),
            "gross_profit":    round(gross_profit, 2),
            "gross_loss":      round(gross_loss, 2),
            "source":          "neon" if total > 0 else "empty",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/strategy/toggle-live")
async def toggle_live_trading():
    """Toggle live/paper trading. State is persisted in system_config (overrides env var)."""
    current   = await get_live_trading_state()
    new_state = not current

    if new_state and os.environ.get("ENABLE_LIVE_TRADING", "false").lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="ENABLE_LIVE_TRADING=true no está en el .env — edítalo y reinicia el backend para permitir live trading.",
        )
    await set_live_trading_state(new_state)
    mode = "LIVE" if new_state else "PAPER"
    msg  = f"[control] live trading switched to {mode}"
    log.info(msg)
    await _log_event("INFO", msg)
    return {
        "live_trading": new_state,
        "mode":         mode,
        "message":      (
            "Live trading ENABLED — real orders will be placed on Binance"
            if new_state else
            "Live trading DISABLED — paper mode active, no real orders"
        ),
    }


# ── Test-order endpoint ───────────────────────────────────────────────────────

@app.post("/api/trade/test-order")
async def test_order(symbol: str = "BTCUSDT", force_live: bool = False):
    """
    Diagnóstico end-to-end: backend → Binance → Neon DB.

    Paso 1 — conectividad: obtiene klines públicos de Binance (sin auth).
    Paso 2 — indicadores: calcula EMA-200 y ATR-14 en CPU.
    Paso 3 — DB: escribe un evento en orchestrator_events (visible en el ConsoleCard).
    Paso 4 — live (opcional): con force_live=true Y ENABLE_LIVE_TRADING=true,
              ejecuta un roundtrip mínimo BUY+SELL en el exchange configurado.
    """
    from btc_stm.exchange.binance_client import BinanceAuthError, BinanceOrderClient  # noqa: PLC0415
    from btc_stm.exchange.trade_guard import _ema, _EMA_PERIOD                        # noqa: PLC0415

    sym     = symbol.strip().upper()
    live    = await get_live_trading_state()
    testnet = os.environ.get("BINANCE_TESTNET", "true").lower() != "false"
    do_live = live and force_live

    result: dict = {
        "symbol":     sym,
        "testnet":    testnet,
        "mode":       "LIVE" if do_live else "PAPER",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    # ── Paso 1: klines públicos de Binance (no requiere auth) ────────────────
    try:
        import httpx as _httpx  # noqa: PLC0415
        async with _httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": sym, "interval": "1h", "limit": 210},
            )
        resp.raise_for_status()
        klines = resp.json()
        if not isinstance(klines, list) or len(klines) < 10:
            raise ValueError(f"Respuesta inesperada de Binance: {str(klines)[:120]}")

        price = float(klines[-1][4])
        result.update({
            "binance_price":  price,
            "klines_fetched": len(klines),
            "binance_ok":     True,
        })
    except Exception as exc:
        raise HTTPException(status_code=502, detail={
            "message": "No se pudo obtener klines de Binance",
            "error":   f"{type(exc).__name__}: {exc}",
        })

    # ── Paso 2: indicadores (CPU, sin red) ───────────────────────────────────
    try:
        closes  = [float(k[4]) for k in klines]
        ema200  = _ema(closes[:-1], _EMA_PERIOD)
        atr14   = _compute_atr14(klines)
        trend   = "ALCISTA" if price > ema200 else "BAJISTA"
        gap_pct = (price - ema200) / ema200 * 100
        result.update({
            "ema200":  round(ema200, 2),
            "atr14":   round(atr14, 2),
            "trend":   trend,
            "gap_pct": round(gap_pct, 2),
        })
    except Exception as exc:
        result["indicators_error"] = str(exc)
        ema200 = price * 0.99
        atr14  = price * 0.01

    # ── Paso 3: parámetros de la orden simulada ───────────────────────────────
    entry_d     = Decimal(str(round(price, 2)))
    sl_dist     = _ATR_SL_MULT * Decimal(str(round(atr14, 8)))
    stop_loss   = entry_d - sl_dist
    take_profit = entry_d + _ATR_TP_MULT * sl_dist
    stop_limit  = stop_loss * (Decimal("1") - _SL_SLIP)

    result.update({
        "side":           "BUY",
        "entry":          str(entry_d),
        "stop_loss":      str(stop_loss.quantize(Decimal("0.01"), rounding=ROUND_DOWN)),
        "take_profit":    str(take_profit.quantize(Decimal("0.01"), rounding=ROUND_DOWN)),
        "risk_per_trade": "1% del balance libre en USDT",
        "rr_ratio":       "1:2",
    })

    # ── Paso 4a: PAPER — registrar en DB y devolver ───────────────────────────
    if not do_live:
        msg = (
            f"[test] PAPER ORDER {sym} BUY @ {entry_d} | "

            f"SL={stop_loss:.2f} TP={take_profit:.2f} | "
            f"EMA200={ema200:.2f} {trend} | ATR14={atr14:.2f}"
        )
        await asyncio.to_thread(client.close)

        # Prueba de escritura en Neon DB
        try:
            await _log_event("OK", msg, {
                "test": True, "symbol": sym, "price": price,
                "ema200": round(ema200, 2), "atr14": round(atr14, 2),
            })
            result["db_write"] = "OK — evento registrado en orchestrator_events"
        except Exception as exc:
            result["db_write"] = f"ERROR: {exc}"

        result["order_placed"] = False
        result["message"]      = (
            "✓ Prueba completada en modo PAPER. "
            "Verifica el ConsoleCard — deberías ver el evento 'OK [test] PAPER ORDER'. "
            "Para probar una orden real usa ?force_live=true con ENABLE_LIVE_TRADING=true."
        )
        return result

    # ── Paso 4b: LIVE — orden real mínima (BUY + SELL inmediato) ─────────────
    try:
        balance_f = await asyncio.to_thread(client.get_free_balance, "USDT")
        if balance_f < 6.0:
            raise ValueError(f"Balance insuficiente: ${balance_f:.2f} USDT (mínimo $6)")

        # Cantidad mínima: lot step × ceil(minNotional / price / step)
        lot   = await asyncio.to_thread(client.get_lot_size_filter, sym)
        step  = Decimal(lot["stepSize"])
        min_q = Decimal(lot["minQty"])
        # Apuntar a $6 de valor nocional
        target_qty = Decimal("6") / Decimal(str(price))
        qty = max(
            (target_qty / step).to_integral_value(ROUND_DOWN) * step,
            min_q,
        )
        result["quantity"] = str(qty)
        result["notional"] = f"~${float(qty) * price:.2f} USDT"

        # BUY de mercado
        buy_res = await asyncio.to_thread(
            client.place_market_order, sym, "BUY", str(qty)
        )
        result["buy_order"] = {
            "orderId": buy_res.get("orderId"),
            "status":  buy_res.get("status"),
        }

        # SELL de mercado inmediato (cierra la posición)
        sell_res = await asyncio.to_thread(
            client.place_market_order, sym, "SELL", str(qty)
        )
        result["sell_order"] = {
            "orderId": sell_res.get("orderId"),
            "status":  sell_res.get("status"),
        }

        result["order_placed"] = True
        ok_msg = (
            f"[test] LIVE ROUNDTRIP {sym} qty={qty} notional={result['notional']} "
            f"BUY={buy_res.get('orderId')} SELL={sell_res.get('orderId')} "
            f"network={'TESTNET' if testnet else 'MAINNET'}"
        )
        await _log_event("OK", ok_msg, {"test": True, "live": True, "symbol": sym})
        result["db_write"] = "OK"
        result["message"]  = (
            f"✓ Roundtrip real completado en {'TESTNET' if testnet else 'MAINNET'}. "
            "Verifica el ConsoleCard y el historial de órdenes en Binance."
        )

    except Exception as exc:
        result["order_placed"] = False
        result["order_error"]  = str(exc)
        await _log_event("ERROR", f"[test] LIVE ORDER FAILED {sym}: {exc}", {"test": True})
    finally:
        await asyncio.to_thread(client.close)

    return result


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
        row            = agg[0] if agg else {}
        total_trades   = int(row.get("total_trades")  or 0)
        winning        = int(row.get("winning_trades") or 0)
        initial        = float(row.get("initial_cash")   or 10000)
        current        = float(row.get("current_equity") or initial)
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
            returns = [(equities[i] - equities[i - 1]) / equities[i - 1]
                       for i in range(1, len(equities)) if equities[i - 1] != 0]
            if len(returns) > 1:
                std    = statistics.stdev(returns)
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
            ts     = r["created_at"]
            ts_str = ts.strftime("%H:%M:%S") if hasattr(ts, "strftime") else str(ts)[11:19]
            et     = str(r.get("event_type", "INFO")).upper()
            lvl    = "ERR" if et == "ERROR" else et if et in ("INFO", "OK", "WARN", "ERR") else "INFO"
            result.append({"ts": ts_str, "level": lvl, "msg": r["message"]})
        return {"logs": result, "count": len(result)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Backtest ──────────────────────────────────────────────────────────────────

@app.get("/api/backtest")
async def backtest_schema():
    return {
        "endpoint":    "/api/backtest",
        "method":      "POST",
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
        "loop_running":  _loop_state["running"],
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

        client = await asyncio.to_thread(BinanceOrderClient.from_env)

        try:
            cancelled = await asyncio.to_thread(client.cancel_all_orders, symbol)
            results["cancelled"] = len(cancelled) if isinstance(cancelled, list) else cancelled
        except Exception as exc:
            results["cancel_error"] = str(exc)

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

    await set_system_state(False)
    results["system_active"] = False

    return {
        "status":  "HALTED",
        "message": "Kill switch activated. All orders cancelled, position closed, system frozen.",
        "details": results,
    }


# ── Manual trade execution ────────────────────────────────────────────────────

@app.post("/api/trade/execute")
async def trade_execute(payload: TradeRequest):
    if not await is_system_active():
        raise HTTPException(status_code=503,
            detail="System is HALTED. Call POST /api/control/reset to re-activate.")

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

        order = await asyncio.to_thread(guard.validate, signal)

        entry_result = await asyncio.to_thread(
            client.place_limit_order,
            order.symbol, order.side, order.quantity, order.entry_price,
        )

        exit_side  = "SELL" if order.side == "BUY" else "BUY"
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
