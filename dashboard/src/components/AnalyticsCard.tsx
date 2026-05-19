'use client'

import { useEffect, useState, useCallback } from 'react'
import { GlassCard } from './GlassCard'
import { TrendingUp, RefreshCw, BarChart3 } from 'lucide-react'

interface PerfData {
  symbol:              string
  total_trades:        number
  winning_trades:      number
  losing_trades:       number
  winrate:             number
  winrate_str:         string
  profit_factor:       number | null
  profit_factor_str:   string
  total_pnl:           number
  avg_win:             number
  avg_loss:            number
  source:              string
}

const EMPTY: PerfData = {
  symbol: 'BTCUSDT', total_trades: 0, winning_trades: 0, losing_trades: 0,
  winrate: 0, winrate_str: '0.0%', profit_factor: 0, profit_factor_str: '0.00x',
  total_pnl: 0, avg_win: 0, avg_loss: 0, source: 'empty',
}

interface Props { symbol?: string }

export function AnalyticsCard({ symbol = 'BTCUSDT' }: Props) {
  const [data,    setData]    = useState<PerfData>(EMPTY)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(false)

  const fetchData = useCallback(async (sym: string) => {
    setLoading(true)
    try {
      const res = await fetch(`/api/analytics/performance?symbol=${sym}`)
      if (!res.ok) throw new Error()
      const json: PerfData = await res.json()
      setData(json)
      setError(false)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData(symbol) }, [symbol, fetchData])
  useEffect(() => {
    const id = setInterval(() => fetchData(symbol), 30_000)
    return () => clearInterval(id)
  }, [symbol, fetchData])

  const isEmpty = data.source === 'empty'
  const winPct  = data.total_trades > 0 ? (data.winning_trades / data.total_trades) * 100 : 0

  const metrics = [
    {
      label:   'Tasa de Aciertos',
      value:   isEmpty ? '—' : data.winrate_str,
      sub:     isEmpty ? 'Sin operaciones' : `${data.winning_trades} ganadoras de ${data.total_trades}`,
      color:   data.winrate >= 50 ? 'text-emerald-400' : 'text-amber-400',
      badge:   data.winrate >= 50 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400',
    },
    {
      label:   'Factor de Ganancia',
      value:   isEmpty ? '—' : data.profit_factor_str,
      sub:     isEmpty ? 'Sin datos' : (data.profit_factor && data.profit_factor >= 1 ? 'Rentable' : 'Por mejorar'),
      color:   (data.profit_factor ?? 0) >= 1 ? 'text-cyan-400' : 'text-red-400',
      badge:   (data.profit_factor ?? 0) >= 1 ? 'bg-cyan-500/10 text-cyan-400' : 'bg-red-500/10 text-red-400',
    },
    {
      label:   'Operaciones Totales',
      value:   isEmpty ? '0' : String(data.total_trades),
      sub:     isEmpty ? 'Sin historial' : `${data.losing_trades} perdedoras`,
      color:   'text-slate-300',
      badge:   'bg-slate-500/10 text-slate-400',
    },
    {
      label:   'PnL Neto',
      value:   isEmpty ? '—' : `${data.total_pnl >= 0 ? '+' : ''}$${data.total_pnl.toFixed(2)}`,
      sub:     isEmpty ? 'Sin datos' : `Avg ganancia $${data.avg_win.toFixed(0)} · Avg pérdida $${Math.abs(data.avg_loss).toFixed(0)}`,
      color:   data.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400',
      badge:   data.total_pnl >= 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400',
    },
  ]

  return (
    <GlassCard glow="cyan" padding={false} className="flex flex-col">
      {/* Cabecera */}
      <div className="flex items-center justify-between px-5 py-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/10 ring-1 ring-cyan-500/20">
            <BarChart3 className="h-4 w-4 text-cyan-400" />
          </div>
          <div>
            <p className="label-xs">Rendimiento Histórico</p>
            <p className="text-sm font-medium text-slate-200">{symbol}</p>
          </div>
        </div>
        {loading && <RefreshCw className="h-3.5 w-3.5 text-slate-600 animate-spin" />}
      </div>

      <div className="mx-5 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent flex-shrink-0" />

      {/* Métricas */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 p-4 flex-1">
        {metrics.map(({ label, value, sub, color, badge }) => (
          <div
            key={label}
            className="flex flex-col justify-between rounded-xl bg-white/[0.02] border border-white/[0.05] p-3.5
                       hover:bg-white/[0.04] transition-all duration-200"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="label-xs text-[9px]">{label}</span>
              <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${badge}`}>
                <TrendingUp className="h-2.5 w-2.5 inline" />
              </span>
            </div>
            <p className={`text-xl font-light tracking-tight ${isEmpty ? 'text-slate-600' : color}`}>
              {value}
            </p>
            <p className="mt-1 text-[10px] text-slate-600 leading-tight">{sub}</p>
          </div>
        ))}
      </div>

      {/* Barra de ratio ganancias/pérdidas */}
      {!isEmpty && data.total_trades > 0 && (
        <div className="px-5 pb-4 flex-shrink-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-slate-600">Ganadoras</span>
            <span className="text-[10px] text-slate-600">Perdedoras</span>
          </div>
          <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-500"
              style={{ width: `${winPct}%` }}
            />
          </div>
          <div className="flex items-center justify-between mt-1">
            <span className="text-[10px] font-mono text-emerald-400">{data.winning_trades}</span>
            <span className="text-[10px] font-mono text-red-400">{data.losing_trades}</span>
          </div>
        </div>
      )}
    </GlassCard>
  )
}
