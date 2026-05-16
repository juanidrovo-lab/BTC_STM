"""Single FastAPI entrypoint for Vercel Python runtime.

All /api/* routes live here. Vercel's @vercel/python builder bundles the
project files but does not always install local packages from pyproject.toml,
so we ensure src/ is on sys.path before any btc_stm import.

Vercel config:  vercel.json → builds[0].src = "api/index.py"
pyproject.toml: [tool.vercel] entrypoint = "api/index.py"
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys

# ── Path fix (must come BEFORE any btc_stm import) ──────────────────────────
# Vercel bundles all project files but may not run `pip install -e .`.
# Inserting src/ ensures `from btc_stm.xxx import ...` resolves correctly
# regardless of whether the package was pip-installed or not.
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
# ─────────────────────────────────────────────────────────────────────────────

from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, HTTPException, Request
from mangum import Mangum

# Docs are served at /api/docs so they are reachable through Vercel's
# /api/(.*) route rule. openapi_url must match for the Swagger UI to load.
app = FastAPI(
    title="BTC-STM API",
    version="0.2.0",
    description=(
        "Paper trading engine — Vercel serverless backend. "
        "All financial values are Decimal strings to avoid float precision loss."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


# ─────────────────────────────────────────────
# GET /api/health
# ─────────────────────────────────────────────

@app.get("/api/health", tags=["ops"])
async def health() -> dict:
    """Liveness probe — always returns 200 when the function is reachable."""
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
# POST /api/paper-trade (session status lookup)
# ─────────────────────────────────────────────

@app.get("/api/paper-trade", tags=["trading"])
async def paper_trade_schema() -> dict:
    return {
        "endpoint": "/api/paper-trade",
        "method": "POST",
        "body": {
            "session_id": "string (required)",
            "symbol": "string (default: BTCUSDT)",
        },
        "response": {"status": "ok", "session_id": "string", "events": "integer"},
    }


@app.post("/api/paper-trade", tags=["trading"])
async def paper_trade(request: Request) -> dict:
    """Look up an existing paper trading session from Neon DB."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise HTTPException(
            status_code=503,
            detail=(
                "DATABASE_URL not configured. "
                "Add it in Vercel → Project Settings → Environment Variables."
            ),
        )

    try:
        body: dict = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")

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
                "total_events": manifest.total_events,
                "total_trades": manifest.total_execution_reports,
                "equity_points": manifest.total_equity_points,
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
# POST /api/backtest (deterministic backtest)
# ─────────────────────────────────────────────

_BACKTEST_SCHEMA = {
    "endpoint": "/api/backtest",
    "POST_body": {
        "symbol": "string — e.g. 'BTCUSDT'",
        "initial_cash": "decimal string — e.g. '10000'",
        "fee_rate_bps": "decimal string, optional, default '10'",
        "slippage_bps": "decimal string, optional, default '5'",
        "execute_on": "'open' | 'close', optional, default 'close'",
        "bars": [
            {
                "symbol": "string — must match top-level symbol",
                "interval": "string — e.g. '1m', '1h'",
                "open_time": "ISO-8601 with timezone — e.g. '2024-01-01T00:00:00+00:00'",
                "close_time": "ISO-8601 with timezone",
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
        "symbol": "string",
        "bar_count": "integer",
        "metrics": {
            "total_return_pct": "string",
            "max_drawdown_pct": "string",
            "total_trades": "integer",
            "total_fees_paid": "string",
        },
    },
}


@app.get("/api/backtest", tags=["backtesting"])
async def backtest_schema() -> dict:
    """Returns the expected request/response shape for POST /api/backtest."""
    return _BACKTEST_SCHEMA


@app.post("/api/backtest", tags=["backtesting"])
async def run_backtest(request: Request) -> dict:
    """Run a deterministic paper-trading backtest over historical bars.

    Uses ``PaperTradingOrchestrator`` with ``NoOpStrategy`` (hold only) so
    all provided bars are processed and equity curve + metrics are returned.
    Swap ``NoOpStrategy`` for a custom strategy to get signal-driven results.
    """
    try:
        body: dict = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")

    symbol = str(body.get("symbol", "BTCUSDT")).strip().upper()
    execute_on = str(body.get("execute_on", "close")).strip().lower()
    bars_raw = body.get("bars", [])

    if execute_on not in {"open", "close"}:
        raise HTTPException(status_code=400, detail="execute_on must be 'open' or 'close'.")
    if not isinstance(bars_raw, list) or len(bars_raw) < 2:
        raise HTTPException(status_code=400, detail="bars must be a JSON array with ≥ 2 entries.")

    def _dec(v: object, field: str) -> Decimal:
        try:
            result = Decimal(str(v))
            if not result.is_finite():
                raise ValueError
            return result
        except (InvalidOperation, ValueError):
            raise HTTPException(status_code=400, detail=f"Invalid decimal for '{field}': {v!r}")

    initial_cash = _dec(body.get("initial_cash", "10000"), "initial_cash")
    fee_rate_bps = _dec(body.get("fee_rate_bps", "10"), "fee_rate_bps")
    slippage_bps = _dec(body.get("slippage_bps", "5"), "slippage_bps")

    # ── Import btc_stm modules (lazy to isolate ImportError from 400/422 errors)
    try:
        from btc_stm.data.models import OHLCVBar  # noqa: PLC0415
        from btc_stm.domain import SymbolFilters  # noqa: PLC0415
        from btc_stm.orchestration.models import PaperTradingConfig  # noqa: PLC0415
        from btc_stm.orchestration.paper_trading import (  # noqa: PLC0415
            PaperTradingOrchestrator,
        )
        from btc_stm.persistence.serialization import to_jsonable  # noqa: PLC0415
        from btc_stm.risk import RiskManager  # noqa: PLC0415
        from btc_stm.settings import Settings  # noqa: PLC0415
        from btc_stm.strategy.examples import NoOpStrategy  # noqa: PLC0415
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"btc_stm package import failed: {exc}. Check Vercel build logs.",
        )

    # ── Parse bars
    try:
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
            for b in bars_raw
        ]
    except HTTPException:
        raise
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid bar data: {exc}")

    # ── Run backtest via PaperTradingOrchestrator (correct public API)
    try:
        settings = Settings()
        orchestrator = PaperTradingOrchestrator(
            settings=settings,
            risk_manager=RiskManager(settings),
            filters=SymbolFilters(
                symbol=symbol,
                price_min=Decimal("0.01"),
                price_max=Decimal("9999999"),
                price_tick_size=Decimal("0.01"),
                qty_min=Decimal("0.00001"),
                qty_max=Decimal("9000"),
                qty_step_size=Decimal("0.00001"),
                min_notional=Decimal("1"),
            ),
            strategy=NoOpStrategy(),
        )
        config = PaperTradingConfig(
            symbol=symbol,
            initial_cash=initial_cash,
            fee_rate_bps=fee_rate_bps,
            slippage_bps=slippage_bps,
            execute_on=execute_on,
        )
        result = orchestrator.run(config=config, bars=bars)
        return {
            "status": "ok",
            "symbol": symbol,
            "bar_count": len(bars),
            "metrics": to_jsonable(result.performance_report),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}")


# ─────────────────────────────────────────────
# POST /api/migrate  (run Alembic migrations)
# ─────────────────────────────────────────────

@app.post("/api/migrate", tags=["ops"])
async def run_migrations(request: Request) -> dict:
    """Run ``alembic upgrade head`` from inside Vercel (has direct Neon access).

    Protected by ``X-Migration-Secret`` header — set ``MIGRATION_SECRET`` in
    Vercel → Project Settings → Environment Variables before calling this.
    """
    secret = os.environ.get("MIGRATION_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="MIGRATION_SECRET env var not set.")
    if request.headers.get("X-Migration-Secret", "") != secret:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Migration-Secret header.")

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured.")

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_ini = os.path.join(project_root, "db", "alembic.ini")

    def _run_alembic() -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", alembic_ini, "upgrade", "head"],
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": database_url},
            cwd=project_root,
            timeout=60,
        )

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _run_alembic)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Migration timed out after 60 s.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Migration subprocess error: {exc}")

    return {
        "status": "ok" if result.returncode == 0 else "error",
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:] if result.stdout else "",
        "stderr": result.stderr[-4000:] if result.stderr else "",
    }


# ── AWS Lambda / Vercel adapter ───────────────────────────────────────────────
# Mangum wraps the ASGI app so Vercel's @vercel/python runtime (which runs on
# AWS Lambda) can invoke it via the Lambda handler protocol.
handler = Mangum(app, lifespan="off")
