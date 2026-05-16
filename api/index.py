"""Minimal diagnostic — single FastAPI route, zero btc_stm imports."""

from __future__ import annotations

import os
import sys

from fastapi import FastAPI
from mangum import Mangum

app = FastAPI(title="BTC-STM API", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "python": sys.version,
        "trading_mode": os.environ.get("TRADING_MODE", "paper"),
        "db_configured": bool(os.environ.get("DATABASE_URL")),
    }


handler = Mangum(app, lifespan="off")
