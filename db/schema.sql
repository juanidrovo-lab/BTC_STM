-- ============================================================
-- BTC_STM SaaS — Neon DB (PostgreSQL 16) Schema
-- ============================================================
-- Deploy: psql $DATABASE_URL -f db/schema.sql
-- Managed via Alembic: db/migrations/versions/
-- ============================================================

-- Users managed by Clerk; this table stores only what the
-- trading engine needs (plan tier for feature gating, etc.)
CREATE TABLE IF NOT EXISTS users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_id   TEXT NOT NULL UNIQUE,
    email      TEXT NOT NULL UNIQUE,
    plan       TEXT NOT NULL DEFAULT 'free',   -- 'free' | 'pro' | 'enterprise'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One strategy config per user (extensible to many later)
CREATE TABLE IF NOT EXISTS strategies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    symbol      TEXT NOT NULL DEFAULT 'BTCUSDT',
    config_json JSONB NOT NULL DEFAULT '{}',
    is_active   BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_strategies_user ON strategies(user_id);

-- One row per paper-trading or backtest session
CREATE TABLE IF NOT EXISTS trading_sessions (
    id                      TEXT PRIMARY KEY,        -- sanitized session_id from orchestrator
    user_id                 UUID REFERENCES users(id) ON DELETE SET NULL,
    strategy_id             UUID REFERENCES strategies(id) ON DELETE SET NULL,
    symbol                  TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'running',  -- 'running'|'completed'|'failed'
    initial_cash            NUMERIC(18, 8) NOT NULL,
    current_equity          NUMERIC(18, 8),
    total_events            INTEGER NOT NULL DEFAULT 0,
    total_execution_reports INTEGER NOT NULL DEFAULT 0,
    total_equity_points     INTEGER NOT NULL DEFAULT 0,
    config_json             JSONB,
    performance_json        JSONB,
    artifact_paths          JSONB,
    started_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at                TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON trading_sessions(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON trading_sessions(status);

-- Every order attempt (filled or rejected) with full detail
CREATE TABLE IF NOT EXISTS execution_reports (
    id               TEXT PRIMARY KEY,
    session_id       TEXT NOT NULL REFERENCES trading_sessions(id) ON DELETE CASCADE,
    symbol           TEXT NOT NULL,
    side             TEXT NOT NULL,        -- 'buy' | 'sell'
    order_type       TEXT,
    quantity         NUMERIC(18, 8) NOT NULL,
    fill_price       NUMERIC(18, 8),
    stop_loss        NUMERIC(18, 8),
    take_profit      NUMERIC(18, 8),
    status           TEXT NOT NULL,        -- 'filled' | 'rejected' | 'partially_filled'
    rejection_reason TEXT,
    fee_paid         NUMERIC(18, 8) NOT NULL DEFAULT 0,
    realized_pnl     NUMERIC(18, 8) NOT NULL DEFAULT 0,
    report_json      JSONB NOT NULL,
    executed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reports_session ON execution_reports(session_id, executed_at);
CREATE INDEX IF NOT EXISTS idx_reports_status ON execution_reports(session_id, status);

-- Time-series equity snapshots — one row per bar processed
-- realized_pnl here = PaperPortfolio.realized_pnl at that point in time,
-- which is the same value fed to RiskManager as daily_pnl after Phase 1 fix.
CREATE TABLE IF NOT EXISTS equity_curve (
    id             BIGSERIAL PRIMARY KEY,
    session_id     TEXT NOT NULL REFERENCES trading_sessions(id) ON DELETE CASCADE,
    equity         NUMERIC(18, 8) NOT NULL,
    cash_balance   NUMERIC(18, 8) NOT NULL,
    position_value NUMERIC(18, 8) NOT NULL,
    realized_pnl   NUMERIC(18, 8) NOT NULL,   -- cumulative closed-trade P&L
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_equity_session ON equity_curve(session_id, recorded_at);

-- Structured audit log — mirrors OrchestratorEventType enum
CREATE TABLE IF NOT EXISTS orchestrator_events (
    id         BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES trading_sessions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    message    TEXT NOT NULL,
    metadata   JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_session ON orchestrator_events(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_type ON orchestrator_events(event_type, created_at DESC);
