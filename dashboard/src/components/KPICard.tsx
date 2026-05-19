'use client'

import { GlassCard } from './GlassCard'
import { ArrowUpRight, ArrowDownRight, Minus, RefreshCw } from 'lucide-react'
import { useEffect, useState, useCallback } from 'react'

interface PortfolioMetrics {
  total_return_str: string
  total_return:     number
  max_drawdown_str: string
  win_rate_str:     string
  win_rate:         number
  sharpe_str:       string
  sharpe:           number
  total_trades:     number
  current_equity:   number
  source:           string
}

const colorMap = {
  emerald: { value: 'text-emerald-400', badge: 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20' },
  red:     { value: 'text-red-400',     badge: 'bg-red-500/10    text-red-400    ring-red-500/20'       },
  cyan:    { value: 'text-cyan-400',    badge: 'bg-cyan-500/10   text-cyan-400   ring-cyan-500/20'      },
  slate:   { value: 'text-slate-300',   badge: 'bg-slate-500/10  text-slate-400  ring-slate-500/20'     },
}

const iconMap = {
  up:      <ArrowUpRight   className="h-3 w-3" />,
  down:    <ArrowDownRight className="h-3 w-3" />,
  neutral: <Minus          className="h-3 w-3" />,
}

function kpiList(m: PortfolioMetrics) {
  return [
    {
      label:     'Retorno Total',
      value:     m.total_return_str,
      subtext:   `Equity $${m.current_equity.toLocaleString()}`,
      direction: (m.total_return >= 0 ? 'up' : 'down') as 'up' | 'down',
      color:     m.total_return >= 0 ? 'emerald' : 'red',
    },
    {
      label:     'Drawdown Máximo',
      value:     m.max_drawdown_str,
      subtext:   'Pico a valle',
      direction: 'down' as const,
      color:     'red',
    },
    {
      label:     'Tasa de Aciertos',
      value:     m.win_rate_str,
      subtext:   `${m.total_trades} operaciones`,
      direction: (m.win_rate >= 50 ? 'up' : 'down') as 'up' | 'down',
      color:     'cyan',
    },
    {
      label:     'Ratio de Sharpe',
      value:     m.sharpe_str,
      subtext:   'Ajustado al riesgo',
      direction: 'neutral' as const,
      color:     'slate',
    },
  ]
}

const EMPTY_METRICS: PortfolioMetrics = {
  total_return_str: '+0.00%', total_return: 0,
  max_drawdown_str: '-0.00%',
  win_rate_str: '0.0%',       win_rate: 0,
  sharpe_str: '0.00',         sharpe: 0,
  total_trades: 0,
  current_equity: 10000,
  source: 'empty',
}

export function KPICard() {
  const [metrics, setMetrics] = useState<PortfolioMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(false)

  const fetch_ = useCallback(async () => {
    try {
      const res = await fetch('/api/portfolio/metrics')
      if (!res.ok) throw new Error()
      const data: PortfolioMetrics = await res.json()
      setMetrics(data)
      setError(false)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch_()
    const id = setInterval(fetch_, 30_000)
    return () => clearInterval(id)
  }, [fetch_])

  const display = metrics ?? EMPTY_METRICS
  const kpis    = kpiList(display)
  const isEmpty = display.source === 'empty'

  return (
    <GlassCard glow="cyan" padding={false} className="flex flex-col">
      <div className="p-6 pb-4 flex items-start justify-between">
        <div>
          <p className="label-xs mb-1.5">Indicadores Clave</p>
          <h2 className="text-lg font-medium text-slate-100">Métricas de Cartera</h2>
        </div>
        {loading && <RefreshCw className="h-4 w-4 text-slate-600 animate-spin mt-1" />}
      </div>

      <div className="mx-6 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />

      <div className="flex-1 grid grid-cols-2 gap-3 p-4">
        {kpis.map(({ label, value, subtext, direction, color }) => {
          const c = colorMap[color as keyof typeof colorMap]
          return (
            <div
              key={label}
              className="flex flex-col justify-between rounded-xl bg-white/[0.02] border border-white/[0.05] p-4
                         hover:bg-white/[0.04] hover:border-white/[0.08] transition-all duration-200"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="label-xs">{label}</span>
                <span className={`flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${c.badge}`}>
                  {iconMap[direction]}
                </span>
              </div>
              <p className={`text-2xl font-light tracking-tight ${isEmpty ? 'text-slate-600' : c.value}`}>
                {value}
              </p>
              <p className="mt-1 text-[10px] text-slate-600">
                {error ? 'Error de API' : isEmpty ? 'Sin sesiones aún' : subtext}
              </p>
            </div>
          )
        })}
      </div>
    </GlassCard>
  )
}
