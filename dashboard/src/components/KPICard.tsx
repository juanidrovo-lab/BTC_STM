import { GlassCard } from './GlassCard'
import { TrendingUp, TrendingDown, Minus, ArrowUpRight, ArrowDownRight } from 'lucide-react'

const kpis = [
  {
    label:     'Total Return',
    value:     '+12.47%',
    subtext:   'Since inception',
    direction: 'up' as const,
    color:     'emerald',
  },
  {
    label:     'Max Drawdown',
    value:     '-2.84%',
    subtext:   'Peak to trough',
    direction: 'down' as const,
    color:     'red',
  },
  {
    label:     'Win Rate',
    value:     '67.3%',
    subtext:   '142 total trades',
    direction: 'up' as const,
    color:     'cyan',
  },
  {
    label:     'Sharpe Ratio',
    value:     '1.84',
    subtext:   'Risk-adjusted',
    direction: 'neutral' as const,
    color:     'slate',
  },
]

const colorMap = {
  emerald: { value: 'text-emerald-400', badge: 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20' },
  red:     { value: 'text-red-400',     badge: 'bg-red-500/10    text-red-400    ring-red-500/20'     },
  cyan:    { value: 'text-cyan-400',    badge: 'bg-cyan-500/10   text-cyan-400   ring-cyan-500/20'    },
  slate:   { value: 'text-slate-300',   badge: 'bg-slate-500/10  text-slate-400  ring-slate-500/20'   },
}

const iconMap = {
  up:      <ArrowUpRight   className="h-3 w-3" />,
  down:    <ArrowDownRight className="h-3 w-3" />,
  neutral: <Minus          className="h-3 w-3" />,
}

export function KPICard() {
  return (
    <GlassCard glow="cyan" padding={false} className="flex flex-col">
      {/* Header */}
      <div className="p-6 pb-4">
        <p className="label-xs mb-1.5">Performance KPIs</p>
        <h2 className="text-lg font-medium text-slate-100">Portfolio Metrics</h2>
      </div>

      <div className="mx-6 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />

      {/* KPI grid */}
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
              <p className={`text-2xl font-light tracking-tight ${c.value}`}>{value}</p>
              <p className="mt-1 text-[10px] text-slate-600">{subtext}</p>
            </div>
          )
        })}
      </div>
    </GlassCard>
  )
}
