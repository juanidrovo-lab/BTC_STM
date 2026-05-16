# ROADMAP MAESTRO — BTC_STM SaaS Platform
**Versión:** 1.0 | **Fecha:** 2026-05-16 | **Arquitecto:** Senior Quant Engineer

> **Alcance:** Transformación del motor local de paper trading en una plataforma SaaS
> multi-usuario, escalable, segura y con interfaz premium de trading.
> Ningún archivo de `src/` será modificado hasta aprobación de este plan.

---

## ESTADO ACTUAL DEL SISTEMA (Diagnóstico Pre-Roadmap)

```
BTC_STM v0.x — Paper Trading Engine (Local)
─────────────────────────────────────────────────────────────────────
Stack:         Python 3.12+ · Pydantic v2 · httpx (sync) · pytest
Modo actual:   Paper trading / Backtesting histórico (sin WebSockets)
Fortalezas:    RiskManager 9-punto · escrituras atómicas · Decimal math
Bugs críticos: daily_pnl siempre = 0 · take-profit inexistente · 
               streaming no implementado · métricas de backtest falsas
─────────────────────────────────────────────────────────────────────
```

---

## FASE 1 — CORRECCIÓN CRÍTICA DE LÓGICA FINANCIERA (Backend)

> **Prioridad:** BLOQUEANTE. Sin esto, las fases siguientes heredan bugs financieros.
> **Tiempo estimado:** 2–3 días de ingeniería.

### 1.1 — Corrección de `daily_pnl` en `orchestration/paper_trading.py`

**Problema raíz:**  
`PortfolioState` recibe `daily_pnl=Decimal("0")` hardcodeado en cada tick.
La guarda `RISK_MAX_DAILY_LOSS_PCT` del `RiskManager` **nunca se activa**.
El sistema cree que jamás ha perdido dinero en el día, sin importar los trades.

**Solución:**

```python
# orchestration/paper_trading.py — cambios requeridos

# 1. Agregar campo al orquestador para acumular P&L diario
_session_start_equity: Decimal       # equity al inicio del día
_daily_realized_pnl: Decimal = Decimal("0")

# 2. Después de cada ExecutionReport, acumular:
if report.status == ExecutionStatus.FILLED:
    self._daily_realized_pnl += report.realized_pnl  # ya existe en ExecutionReport

# 3. Calcular daily_pnl como delta vs equity inicial de sesión:
daily_pnl = current_equity - self._session_start_equity

# 4. Pasar al PortfolioState correctamente:
portfolio_state = PortfolioState(
    ...
    daily_pnl=daily_pnl,   # <-- antes era Decimal("0")
)
```

**Archivos a modificar:** `orchestration/paper_trading.py`, `orchestration/models.py`  
**Tests a agregar:** `tests/orchestration/test_daily_pnl_accumulation.py`

---

### 1.2 — Implementación de Take-Profit en `domain.py` y `risk.py`

**Problema raíz:**  
`OrderIntent` solo tiene `stop_loss`. Sin `take_profit`, el sistema no puede:
- Forzar ratios riesgo/beneficio mínimos (ej. 1:2)
- Cerrar posiciones automáticamente en objetivo
- Reportar métricas de R:R en analytics

**Solución — Cambios en `domain.py`:**

```python
class OrderIntent(BaseModel):
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal
    stop_loss: Decimal                    # obligatorio (ya existe)
    take_profit: Decimal | None = None    # NUEVO — opcional
    
    @model_validator(mode="after")
    def validate_tp_sl_logic(self) -> "OrderIntent":
        if self.take_profit is None:
            return self
        if self.side == OrderSide.BUY:
            # take_profit debe ser MAYOR que price, stop_loss MENOR
            assert self.take_profit > self.price > self.stop_loss, \
                "BUY: stop_loss < price < take_profit requerido"
        else:
            # take_profit debe ser MENOR que price, stop_loss MAYOR
            assert self.take_profit < self.price < self.stop_loss, \
                "SELL: take_profit < price < stop_loss requerido"
        return self
```

**Cambios en `risk.py` — nueva guarda (check #10):**

```python
def _check_risk_reward_ratio(self, order: OrderIntent) -> RiskDecision | None:
    """Requiere R:R mínimo de 1:1 si take_profit está definido."""
    if order.take_profit is None:
        return None  # no aplica si no hay TP
    
    risk_distance = abs(order.price - order.stop_loss)
    reward_distance = abs(order.take_profit - order.price)
    
    if risk_distance == Decimal("0"):
        return RiskDecision.reject("División por cero en cálculo R:R")
    
    rr_ratio = reward_distance / risk_distance
    min_rr = self.settings.risk_min_reward_ratio  # default: Decimal("1.0")
    
    if rr_ratio < min_rr:
        return RiskDecision.reject(
            f"R:R {rr_ratio:.2f} menor al mínimo requerido {min_rr:.2f}"
        )
    return None
```

**Cambios en `execution/paper_broker.py` — cierre automático en TP:**

```python
def check_take_profit_triggers(
    self, 
    portfolio: PaperPortfolio, 
    current_bar: OHLCVBar
) -> list[OrderIntent]:
    """
    Llamado por el runner en cada barra.
    Si el precio toca el take_profit de una posición abierta,
    genera automáticamente la orden de cierre.
    """
    close_orders = []
    for symbol, position in portfolio.positions.items():
        if position.take_profit is None:
            continue
        # Para posiciones LONG: TP se activa si el HIGH de la barra >= TP
        if current_bar.high >= position.take_profit:
            close_orders.append(
                OrderIntent(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=position.quantity,
                    price=position.take_profit,  # fill al precio de TP
                    stop_loss=position.entry_price,  # SL nominal para validación
                )
            )
    return close_orders
```

**Archivos a modificar:** `domain.py`, `risk.py`, `execution/paper_broker.py`, `execution/models.py`, `settings.py`  
**Nuevas settings:** `RISK_MIN_REWARD_RATIO=1.0`  
**Tests a agregar:** `tests/test_take_profit_trigger.py`, `tests/risk/test_rr_ratio.py`

---

### 1.3 — Logging estructurado y manejo granular de excepciones

**Problema raíz:**  
- `except Exception` captura `KeyboardInterrupt`, `SystemExit`, errores de memoria
- Sin niveles de log (`DEBUG/INFO/WARNING/ERROR`), los errores de red son invisibles
- Imposible diagnosticar rechazos del RiskManager en producción

**Solución — Módulo de logging centralizado:**

```python
# src/btc_stm/logging_config.py — NUEVO ARCHIVO
import logging
import sys
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

def configure_logging(level: LogLevel = "INFO") -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    ))
    logger = logging.getLogger("btc_stm")
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger

# Uso en risk.py:
logger = logging.getLogger("btc_stm.risk")
logger.warning("ORDER_REJECTED | reason=%s | symbol=%s | qty=%s", 
               decision.reason, order.symbol, order.quantity)

# Uso en data/binance_public.py:
logger.error("HTTP_ERROR | status=%s | url=%s", response.status_code, str(response.url))

# Corrección del except genérico en orchestration/paper_trading.py:
try:
    ...
except (httpx.NetworkError, httpx.TimeoutException) as e:
    logger.error("NETWORK_ERROR | %s", str(e))
    self._emit_event(OrchestratorEventType.SESSION_FAILED, str(e))
    raise
except Exception as e:
    logger.critical("UNEXPECTED_ERROR | %s", str(e), exc_info=True)
    self._emit_event(OrchestratorEventType.SESSION_FAILED, str(e))
    raise
```

**Archivos a modificar:** `orchestration/paper_trading.py`, `risk.py`, `data/binance_public.py`, `settings.py`  
**Nuevo archivo:** `src/btc_stm/logging_config.py`

---

## FASE 2 — MIGRACIÓN A NEON DB & ARQUITECTURA VERCEL

> **Objetivo:** Convertir el motor local en backend SaaS multi-tenant.
> **Tiempo estimado:** 5–7 días de ingeniería.

### 2.1 — Modelo Relacional PostgreSQL (Neon DB Serverless)

```sql
-- ============================================================
-- SCHEMA: btc_stm_saas
-- Base de datos: Neon DB (PostgreSQL 16 serverless)
-- ============================================================

-- Usuarios (integra con Clerk/NextAuth)
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_id    TEXT UNIQUE NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    plan        TEXT NOT NULL DEFAULT 'free',  -- 'free' | 'pro' | 'enterprise'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Estrategias de trading configuradas por usuario
CREATE TABLE strategies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    symbol          TEXT NOT NULL DEFAULT 'BTCUSDT',
    config_json     JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sesiones de paper trading
CREATE TABLE trading_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    strategy_id     UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'running',  -- 'running'|'completed'|'failed'
    initial_cash    NUMERIC(18,8) NOT NULL,
    current_equity  NUMERIC(18,8),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ
);

-- Órdenes ejecutadas (historial completo)
CREATE TABLE execution_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES trading_sessions(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,  -- 'BUY' | 'SELL'
    order_type      TEXT NOT NULL,
    quantity        NUMERIC(18,8) NOT NULL,
    fill_price      NUMERIC(18,8),
    stop_loss       NUMERIC(18,8),
    take_profit     NUMERIC(18,8),
    status          TEXT NOT NULL,  -- 'FILLED'|'REJECTED'|'PARTIAL'
    rejection_reason TEXT,
    fee_paid        NUMERIC(18,8) DEFAULT 0,
    realized_pnl    NUMERIC(18,8) DEFAULT 0,
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Curva de equity (time series)
CREATE TABLE equity_curve (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES trading_sessions(id) ON DELETE CASCADE,
    equity          NUMERIC(18,8) NOT NULL,
    cash_balance    NUMERIC(18,8) NOT NULL,
    open_positions  INTEGER NOT NULL DEFAULT 0,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_equity_curve_session ON equity_curve(session_id, recorded_at);

-- Log de eventos del orquestador (audit trail)
CREATE TABLE orchestrator_events (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES trading_sessions(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    message         TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_events_session ON orchestrator_events(session_id, created_at);
```

**Stack de persistencia:**
- **ORM:** `asyncpg` + `sqlalchemy[asyncio]>=2.0` para queries async
- **Migraciones:** `alembic` — versionadas en `db/migrations/`
- **Connection Pool:** Pool de Neon serverless con `pool_mode=transaction`
- **Adapter Pattern:** Crear `persistence/neon_store.py` que implemente la misma interface que `LocalSessionStore`, sin romper los tests existentes

---

### 2.2 — Arquitectura Vercel (Serverless Functions + Edge)

```
┌─────────────────────────────────────────────────────────┐
│                    VERCEL PLATFORM                       │
│                                                          │
│  ┌─────────────────────┐   ┌────────────────────────┐   │
│  │   Next.js App       │   │   Python Functions     │   │
│  │   (Edge Runtime)    │   │   (Serverless)         │   │
│  │                     │   │                        │   │
│  │  /dashboard         │   │  /api/backtest         │   │
│  │  /strategy          │   │  /api/paper-trade      │   │
│  │  /analytics         │   │  /api/risk-check       │   │
│  └─────────────────────┘   └────────────────────────┘   │
│            │                          │                  │
│            └──────────────┬───────────┘                  │
│                           ▼                              │
│                    Neon DB (PostgreSQL)                   │
│                    + Vercel KV (Redis)                   │
│                    + Vercel Blob (reports PDF)           │
└─────────────────────────────────────────────────────────┘

Cron Jobs (Vercel Cron):
  - /api/cron/sync-equity     → cada 5 minutos
  - /api/cron/daily-report    → cada día a las 00:00 UTC
  - /api/cron/risk-monitor    → cada minuto (plan pro)
```

**Adaptación del loop infinito → funciones serverless:**

El `PaperTradingOrchestrator` usa un loop síncrono. Para Vercel serverless:

```python
# api/paper_trade.py — Vercel Python Function
from btc_stm.orchestration.paper_trading import PaperTradingOrchestrator

async def handler(request):
    """
    Ejecuta UN tick del orquestador por invocación.
    El estado se persiste en Neon DB entre invocaciones.
    Vercel Cron llama esto cada N segundos.
    """
    session_id = request.query_params["session_id"]
    
    # 1. Cargar estado de sesión desde Neon DB
    state = await load_session_state(session_id)
    
    # 2. Obtener barra actual desde Binance REST
    bar = await fetch_current_bar(state.symbol)
    
    # 3. Ejecutar un tick del orquestador
    events = await orchestrator.process_bar(state, bar)
    
    # 4. Persistir nuevo estado en Neon DB
    await save_session_state(session_id, state, events)
    
    return {"status": "ok", "events": len(events)}
```

---

## FASE 3 — OPTIMIZACIÓN DE ALGORITMO (Maximizar Winrate)

> **Objetivo:** Pasar de snapshots REST a señales en tiempo real con filtros avanzados.
> **Tiempo estimado:** 7–10 días de ingeniería.

### 3.1 — Migración REST → WebSockets en tiempo real

**Implementar los métodos stub en `data/binance_public.py`:**

```python
# data/binance_ws.py — NUEVO ARCHIVO
import asyncio
import json
from collections.abc import AsyncIterator
import websockets

class BinanceWebSocketClient:
    """
    Cliente async de WebSockets para streams de Binance.
    Implementa reconexión automática con backoff exponencial.
    """
    WS_BASE = "wss://stream.binance.com:9443/ws"
    
    async def stream_klines(
        self, 
        symbol: str, 
        interval: str = "1m"
    ) -> AsyncIterator[OHLCVBar]:
        """
        Stream de velas en tiempo real con reconexión automática.
        Usa el patrón async generator para integración con asyncio.
        """
        url = f"{self.WS_BASE}/{symbol.lower()}@kline_{interval}"
        backoff = 1
        
        while True:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    backoff = 1  # reset en conexión exitosa
                    async for raw_msg in ws:
                        msg = json.loads(raw_msg)
                        if msg["k"]["x"]:  # barra cerrada (is_final)
                            yield parse_kline_message(msg["k"])
            except (websockets.exceptions.ConnectionClosed, OSError) as e:
                logger.warning("WS_RECONNECT | %s | backoff=%ds", str(e), backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)  # max 60s de backoff
    
    async def stream_order_book(
        self, 
        symbol: str, 
        depth: int = 20
    ) -> AsyncIterator[OrderBookDelta]:
        """Stream de order book con manejo de gaps de secuencia."""
        ...
    
    async def stream_trades(self, symbol: str) -> AsyncIterator[TradeEvent]:
        """Stream de trades en tiempo real."""
        ...
```

### 3.2 — Filtros de volatilidad e indicadores avanzados

**Nueva capa `strategy/indicators.py`:**

```python
# strategy/indicators.py — NUEVO ARCHIVO
from decimal import Decimal
import statistics

class VolatilityFilter:
    """Filtro ATR: solo operar cuando volatilidad > umbral mínimo."""
    
    @staticmethod
    def atr(bars: list[OHLCVBar], period: int = 14) -> Decimal:
        """Average True Range — medida estándar de volatilidad."""
        true_ranges = []
        for i in range(1, len(bars)):
            tr = max(
                bars[i].high - bars[i].low,
                abs(bars[i].high - bars[i-1].close),
                abs(bars[i].low - bars[i-1].close)
            )
            true_ranges.append(tr)
        if len(true_ranges) < period:
            return Decimal("0")
        return Decimal(str(statistics.mean(true_ranges[-period:])))

class MomentumIndicators:
    """RSI, EMA, MACD para generación de señales."""
    
    @staticmethod
    def rsi(closes: list[Decimal], period: int = 14) -> Decimal:
        """RSI clásico de Wilder."""
        ...
    
    @staticmethod  
    def ema(values: list[Decimal], period: int) -> Decimal:
        """Exponential Moving Average."""
        ...
    
    @staticmethod
    def macd(
        closes: list[Decimal],
        fast: int = 12,
        slow: int = 26, 
        signal: int = 9
    ) -> tuple[Decimal, Decimal, Decimal]:
        """MACD line, Signal line, Histogram."""
        ...

class MarketRegimeDetector:
    """
    Detecta si el mercado está en tendencia o rango.
    Evita operar contrario a la tendencia macro.
    """
    
    @staticmethod
    def is_trending(bars: list[OHLCVBar], adx_period: int = 14) -> bool:
        """ADX > 25 = tendencia; < 25 = rango lateral."""
        ...
```

**Estrategia de referencia mejorada (`strategy/btc_momentum.py`):**

```python
class BTCMomentumStrategy:
    """
    Estrategia multi-filtro para BTC:
    1. Solo opera si ATR > umbral (mercado activo)
    2. Dirección alineada con EMA 200 (macro trend)
    3. Entrada en retroceso a EMA 20 con RSI < 40 (compra) o > 60 (venta)
    4. SL: 1.5x ATR por debajo del entry
    5. TP: 3x ATR por encima del entry (R:R = 2:1)
    """
    name = "btc_momentum_v1"
    
    def on_bar(self, context: StrategyContext) -> StrategyDecision:
        bars = context.history
        if len(bars) < 200:
            return StrategyDecision(orders=[])
        
        closes = [b.close for b in bars]
        atr = VolatilityFilter.atr(bars[-20:])
        ema_200 = MomentumIndicators.ema(closes, 200)
        ema_20 = MomentumIndicators.ema(closes, 20)
        rsi = MomentumIndicators.rsi(closes[-15:])
        current_price = context.current_bar.close
        
        # Filtro de volatilidad mínima
        if atr < self.min_atr_threshold:
            return StrategyDecision(orders=[])
        
        # Solo compras en mercado alcista (precio > EMA 200)
        if current_price > ema_200 and current_price < ema_20 * Decimal("1.005"):
            if rsi < Decimal("42"):
                stop_loss = current_price - (atr * Decimal("1.5"))
                take_profit = current_price + (atr * Decimal("3.0"))  # R:R 2:1
                return StrategyDecision(orders=[
                    OrderIntent(
                        symbol=context.symbol,
                        side=OrderSide.BUY,
                        order_type=OrderType.LIMIT,
                        quantity=self._size_position(context, stop_loss),
                        price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                    )
                ])
        
        return StrategyDecision(orders=[])
```

---

## FASE 4 — INTERFAZ FRONTEND PREMIUM (Next.js + Design System)

> **Objetivo:** Dashboard de trading con Bento Grid asimétrico, Glassmorphism
> y micro-interacciones reactivas a eventos de mercado.
> **Stack:** Next.js 15 · TypeScript · Tailwind CSS v4 · shadcn/ui · Framer Motion

### 4.1 — Arquitectura del Proyecto Frontend

```
frontend/
├── app/
│   ├── (auth)/
│   │   ├── sign-in/page.tsx
│   │   └── sign-up/page.tsx
│   ├── dashboard/
│   │   ├── layout.tsx          ← Sidebar + Header shell
│   │   ├── page.tsx            ← Bento Grid principal
│   │   ├── strategy/page.tsx   ← Config de estrategia
│   │   ├── analytics/page.tsx  ← Métricas profundas
│   │   └── settings/page.tsx
│   └── api/
│       ├── paper-trade/route.ts
│       ├── backtest/route.ts
│       └── analytics/route.ts
├── components/
│   ├── bento/
│   │   ├── BentoGrid.tsx       ← Grid asimétrico principal
│   │   ├── PriceCard.tsx       ← Precio BTC en tiempo real
│   │   ├── EquityCard.tsx      ← Curva de equity animada
│   │   ├── RiskMeterCard.tsx   ← Gauge de riesgo actual
│   │   ├── TradesFeedCard.tsx  ← Feed de trades recientes
│   │   ├── PnLCard.tsx         ← P&L del día con delta
│   │   └── StrategyStatusCard.tsx
│   ├── charts/
│   │   ├── EquityCurveChart.tsx  ← Recharts área con gradiente
│   │   ├── CandlestickChart.tsx  ← Chart.js OHLCV
│   │   └── DrawdownChart.tsx
│   └── ui/                     ← shadcn/ui components
├── lib/
│   ├── db.ts                   ← Neon DB + Drizzle ORM
│   ├── api.ts                  ← Cliente fetch tipado
│   └── realtime.ts             ← WebSocket hook
├── styles/
│   └── globals.css             ← CSS Variables + Dark Mode
└── tailwind.config.ts
```

### 4.2 — Sistema de Tokens CSS (Basado en ui-ux-pro-max-skill)

```css
/* styles/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* Primitivos — escala de color completa */
    --color-gray-950: 222 47% 4%;
    --color-gray-900: 222 47% 8%;
    --color-gray-800: 217 33% 14%;
    
    /* Semánticos — modo claro (fallback) */
    --background:     0 0% 100%;
    --foreground:     222 47% 11%;
    --card:           0 0% 100%;
    --border:         220 13% 91%;
    --primary:        217 91% 60%;
    --ring:           217 91% 60%;
    --radius:         0.75rem;
    
    /* Trading-specific tokens */
    --color-profit:   142 71% 45%;  /* verde de ganancia */
    --color-loss:     0 84% 60%;    /* rojo de pérdida */
    --color-neutral:  220 9% 46%;   /* gris neutro */
    --color-warning:  38 92% 50%;   /* amarillo de alerta */
    
    /* Glassmorphism */
    --glass-bg:       rgba(255, 255, 255, 0.06);
    --glass-border:   rgba(255, 255, 255, 0.10);
    --glass-blur:     20px;
    --glass-shadow:   0 8px 32px rgba(0, 0, 0, 0.37);
  }

  .dark {
    /* Dark mode — diseñado para trading nocturno */
    --background:     222 47% 4%;
    --foreground:     210 40% 98%;
    --card:           222 47% 6%;
    --border:         217 33% 14%;
    --muted:          217 33% 12%;
    --muted-foreground: 215 20% 55%;
    
    /* Glassmorphism dark mode — más pronunciado */
    --glass-bg:       rgba(255, 255, 255, 0.04);
    --glass-border:   rgba(255, 255, 255, 0.08);
  }
}
```

### 4.3 — Bento Grid Asimétrico (Patrón Extraído)

El grid de trading sigue un layout de **12 columnas** con celdas de tamaño variable,
priorizando la jerarquía visual: precio > equity > trades > métricas secundarias.

```tsx
// components/bento/BentoGrid.tsx
export function TradingBentoGrid() {
  return (
    <div
      className="
        grid grid-cols-12 gap-3 auto-rows-[120px]
        md:gap-4 lg:gap-5
      "
    >
      {/* 
        LAYOUT ASIMÉTRICO:
        ┌──────────────────┬───────────┬────────────┐
        │  PriceCard       │ PnL Day   │ Risk Meter │  row 1-2 (240px)
        │  col 1-6         │ col 7-9   │ col 10-12  │
        ├──────────────────┴───────────┴────────────┤
        │  EquityCurveChart — col 1-8               │  row 3-6 (480px)
        │                   ┌────────────────────┐  │
        │                   │ TradesFeed col 9-12│  │
        │                   └────────────────────┘  │
        ├───────────┬───────────────────┬────────────┤
        │ Strategy  │ Drawdown Chart    │ Positions  │  row 7-8 (240px)
        │ col 1-3   │ col 4-9           │ col 10-12  │
        └───────────┴───────────────────┴────────────┘
      */}

      {/* Precio BTC — protagonista */}
      <PriceCard className="col-span-6 row-span-2" />
      
      {/* P&L del día */}
      <PnLCard className="col-span-3 row-span-2" />
      
      {/* Risk Meter */}
      <RiskMeterCard className="col-span-3 row-span-2" />
      
      {/* Equity Curve — el corazón del dashboard */}
      <EquityCard className="col-span-8 row-span-4" />
      
      {/* Trades Feed — columna derecha */}
      <TradesFeedCard className="col-span-4 row-span-4" />
      
      {/* Strategy Status */}
      <StrategyStatusCard className="col-span-3 row-span-2" />
      
      {/* Drawdown Chart */}
      <DrawdownCard className="col-span-6 row-span-2" />
      
      {/* Open Positions */}
      <PositionsCard className="col-span-3 row-span-2" />
    </div>
  )
}
```

### 4.4 — Glassmorphism (Implementación Exacta)

El efecto glassmorphism en tarjetas de trading usa:
- `backdrop-filter: blur(20px)` — desenfoque del fondo
- `background: rgba(255,255,255,0.04–0.08)` — capa semitransparente
- `border: 1px solid rgba(255,255,255,0.08–0.12)` — borde de luz refractada
- `box-shadow` multicapa — profundidad y glow

```tsx
// components/bento/GlassCard.tsx
import { cn } from "@/lib/utils"

interface GlassCardProps {
  children: React.ReactNode
  className?: string
  variant?: "default" | "profit" | "loss" | "warning" | "glow"
}

export function GlassCard({ children, className, variant = "default" }: GlassCardProps) {
  const variants = {
    default: "border-white/8 shadow-[0_8px_32px_rgba(0,0,0,0.37)]",
    profit:  "border-emerald-500/20 shadow-[0_8px_32px_rgba(16,185,129,0.15)]",
    loss:    "border-red-500/20     shadow-[0_8px_32px_rgba(239,68,68,0.15)]",
    warning: "border-amber-500/20   shadow-[0_8px_32px_rgba(245,158,11,0.15)]",
    glow:    "border-blue-500/30    shadow-[0_0_40px_rgba(59,130,246,0.25),0_8px_32px_rgba(0,0,0,0.37)]",
  }

  return (
    <div
      className={cn(
        // Base glassmorphism
        "relative rounded-2xl border",
        "bg-white/[0.04] backdrop-blur-[20px]",
        // Inner highlight (borde superior más brillante)
        "before:absolute before:inset-0 before:rounded-2xl",
        "before:bg-gradient-to-b before:from-white/[0.08] before:to-transparent",
        "before:pointer-events-none",
        // Variant específico
        variants[variant],
        className
      )}
    >
      {children}
    </div>
  )
}
```

### 4.5 — Micro-interacciones y Animaciones de Estado

**Tarjetas que reaccionan a eventos de trading:**

```tsx
// Ejemplo: PriceCard con animación en cambio de precio
"use client"
import { motion, AnimatePresence } from "framer-motion"
import { useEffect, useState } from "react"

export function PriceCard({ className }: { className?: string }) {
  const [price, setPrice] = useState<number>(0)
  const [direction, setDirection] = useState<"up" | "down" | "neutral">("neutral")
  const [flash, setFlash] = useState(false)

  useEffect(() => {
    // WebSocket hook que emite eventos de precio
    const ws = new WebSocket("wss://stream.binance.com:9443/ws/btcusdt@trade")
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      const newPrice = parseFloat(data.p)
      setDirection(newPrice > price ? "up" : newPrice < price ? "down" : "neutral")
      setPrice(newPrice)
      setFlash(true)
      setTimeout(() => setFlash(false), 300)
    }
    return () => ws.close()
  }, [price])

  const flashColors = {
    up:      "shadow-[0_0_30px_rgba(16,185,129,0.6)]",
    down:    "shadow-[0_0_30px_rgba(239,68,68,0.6)]",
    neutral: "",
  }

  return (
    <GlassCard
      className={cn(
        "transition-shadow duration-300",
        flash && flashColors[direction],
        className
      )}
    >
      <div className="p-6 h-full flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-sm text-white/50 tracking-wider uppercase">
            BTC / USDT
          </span>
          {/* Indicador de dirección — vibra en cambio */}
          <motion.div
            animate={flash ? { scale: [1, 1.3, 1] } : {}}
            transition={{ duration: 0.2 }}
            className={cn(
              "w-2 h-2 rounded-full",
              direction === "up" ? "bg-emerald-400" : 
              direction === "down" ? "bg-red-400" : "bg-gray-400"
            )}
          />
        </div>

        {/* Precio principal — animación de número rodante */}
        <AnimatePresence mode="wait">
          <motion.div
            key={price}
            initial={{ y: direction === "up" ? 10 : -10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: direction === "up" ? -10 : 10, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className={cn(
              "font-mono text-4xl font-bold tracking-tight",
              direction === "up" ? "text-emerald-400" :
              direction === "down" ? "text-red-400" : "text-white"
            )}
          >
            ${price.toLocaleString("en-US", { minimumFractionDigits: 2 })}
          </motion.div>
        </AnimatePresence>
      </div>
    </GlassCard>
  )
}
```

**Ficha de Trade Ejecutado — pulso de éxito/rechazo:**

```tsx
// Micro-interacción: trade ejecutado → verde pulsante
// trade rechazado → rojo vibrante

const tradeVariants = {
  filled:   { borderColor: "rgba(16,185,129,0.5)", boxShadow: "0 0 20px rgba(16,185,129,0.3)" },
  rejected: { borderColor: "rgba(239,68,68,0.5)",  boxShadow: "0 0 20px rgba(239,68,68,0.3)" },
  pending:  { borderColor: "rgba(255,255,255,0.1)", boxShadow: "none" },
}

// Clase de animación de "shake" para rechazos (extraída de states-and-variants.md):
// keyframes: { "0%,100%": {transform:"translateX(0)"}, "25%": {transform:"translateX(-4px)"}, "75%": {transform:"translateX(4px)"} }
```

### 4.6 — Animaciones de Layout (Patrón de Stagger Extraído)

```tsx
// Entrada del Bento Grid — stagger de tarjetas
const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08 }
  }
}

const cardVariants = {
  hidden:  { opacity: 0, y: 20, scale: 0.97 },
  visible: { 
    opacity: 1, y: 0, scale: 1,
    transition: { duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }
  }
}

// Aplicado al grid:
<motion.div variants={containerVariants} initial="hidden" animate="visible">
  <motion.div variants={cardVariants}><PriceCard /></motion.div>
  <motion.div variants={cardVariants}><PnLCard /></motion.div>
  {/* ... */}
</motion.div>
```

---

## DEPENDENCIAS FINALES DEL PROYECTO

### Backend (Python)
```toml
[project.dependencies]
# Existentes
httpx = ">=0.27,<1"
pydantic = ">=2.7,<3"
pydantic-settings = ">=2.3"

# Nuevas — Fase 1
# (ninguna nueva dependencia, solo stdlib logging)

# Nuevas — Fase 2 (SaaS/DB)
asyncpg = ">=0.29"
sqlalchemy = {extras = ["asyncio"], version = ">=2.0"}
alembic = ">=1.13"
websockets = ">=12.0"

# Nuevas — Fase 3 (WebSockets)
websockets = ">=12.0"  # ya incluido arriba
```

### Frontend (Node.js)
```json
{
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "framer-motion": "^11.0.0",
    "recharts": "^2.12.0",
    "tailwindcss": "^4.0.0",
    "@clerk/nextjs": "^5.0.0",
    "drizzle-orm": "^0.30.0",
    "@neondatabase/serverless": "^0.9.0",
    "zustand": "^4.5.0",
    "zod": "^3.23.0"
  }
}
```

---

## CRONOGRAMA DE EJECUCIÓN

```
SEMANA 1  │  FASE 1: Corrección Backend
──────────┼──────────────────────────────────────────────────
Día 1-2   │  Fix daily_pnl + tests
Día 3-4   │  Take-Profit implementation + tests
Día 5     │  Logging estructurado + refactor excepciones
──────────┼──────────────────────────────────────────────────
SEMANA 2  │  FASE 2: Infraestructura SaaS
──────────┼──────────────────────────────────────────────────
Día 6-7   │  Schema NeonDB + Alembic migrations
Día 8-9   │  NeonStore adapter + API routes Vercel
Día 10    │  Auth con Clerk + deployment inicial
──────────┼──────────────────────────────────────────────────
SEMANA 3  │  FASE 3: WebSockets + Indicadores
──────────┼──────────────────────────────────────────────────
Día 11-12 │  BinanceWebSocketClient + reconexión
Día 13-14 │  Indicadores: ATR, RSI, EMA, MACD
Día 15    │  BTCMomentumStrategy + backtest de validación
──────────┼──────────────────────────────────────────────────
SEMANA 4  │  FASE 4: Frontend Premium
──────────┼──────────────────────────────────────────────────
Día 16-17 │  Setup Next.js + Tailwind tokens + GlassCard
Día 18-19 │  BentoGrid + PriceCard + EquityChart
Día 20    │  Micro-interacciones + animaciones + polish
──────────┼──────────────────────────────────────────────────
SEMANA 5  │  QA + Launch
──────────┼──────────────────────────────────────────────────
Día 21-22 │  Tests E2E + load testing
Día 23-24 │  Performance audit (Lighthouse ≥ 90)
Día 25    │  Deploy producción + monitoreo
```

---

## DECISIONES DE ARQUITECTURA CLAVE

| Decisión | Opción elegida | Alternativa descartada | Razón |
|---|---|---|---|
| Base de datos | Neon DB (PostgreSQL serverless) | Supabase | Mejor cold-start, branching para dev |
| ORM | Drizzle + asyncpg | SQLAlchemy ORM clásico | Type safety nativa con TypeScript |
| Auth | Clerk | NextAuth | Menor fricción, MFA incluido |
| Real-time | WebSockets nativos Binance | Pusher/Ably | Sin costo adicional, datos directos |
| Animaciones | Framer Motion | CSS animations puras | Física de spring, control de estado |
| Estado global | Zustand | Redux | Menor boilerplate para dashboard |
| Deploy | Vercel | AWS/Railway | Edge Functions + Cron integrado |

---

## MÉTRICAS DE ÉXITO

| KPI | Objetivo | Cómo medirlo |
|---|---|---|
| `daily_pnl` accuracy | ±0.01% vs cálculo manual | Test con 100 trades simulados |
| Latencia WebSocket | < 50ms median | Prometheus + Grafana |
| Lighthouse Score | ≥ 92 (Perf + A11y) | CI/CD con Lighthouse CI |
| Test coverage | ≥ 85% | `pytest --cov` en CI |
| API response P99 | < 200ms | Vercel Analytics |
| Risk rejection rate | Logeado 100% | Audit log en NeonDB |

---

*Roadmap sujeto a revisión tras aprobación. Ningún archivo de `src/` fue modificado.*
*Próximo paso: aprobación del plan → inicio inmediato de FASE 1.*
