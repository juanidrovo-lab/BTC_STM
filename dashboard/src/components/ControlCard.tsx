'use client'

import { GlassCard } from './GlassCard'
import { Play, Activity, Database, Download, RefreshCw, AlertTriangle } from 'lucide-react'
import { useState } from 'react'

type ActionColor = 'cyan' | 'emerald' | 'amber' | 'slate'

interface Action {
  id:    string
  label: string
  sub:   string
  icon:  React.ElementType
  color: ActionColor
}

const actions: Action[] = [
  { id: 'backtest', label: 'Run Backtest',   sub: 'Execute strategy simulation', icon: Play,          color: 'cyan'    },
  { id: 'health',   label: 'Health Check',   sub: 'Ping /api/health endpoint',   icon: Activity,      color: 'emerald' },
  { id: 'migrate',  label: 'Run Migration',  sub: 'Apply Alembic head schema',   icon: Database,      color: 'cyan'    },
  { id: 'export',   label: 'Export Data',    sub: 'Download session CSV',        icon: Download,      color: 'emerald' },
  { id: 'refresh',  label: 'Sync Positions', sub: 'Reload from Neon DB',         icon: RefreshCw,     color: 'slate'   },
  { id: 'alert',    label: 'Risk Override',  sub: 'Bypass risk limits (dev)',    icon: AlertTriangle, color: 'amber'   },
]

const colorMap: Record<ActionColor, { ring: string; icon: string; hover: string }> = {
  cyan:    { ring: 'ring-cyan-500/20',    icon: 'text-cyan-400',    hover: 'hover:bg-cyan-500/10    hover:border-cyan-500/20'    },
  emerald: { ring: 'ring-emerald-500/20', icon: 'text-emerald-400', hover: 'hover:bg-emerald-500/10 hover:border-emerald-500/20' },
  amber:   { ring: 'ring-amber-500/20',   icon: 'text-amber-400',   hover: 'hover:bg-amber-500/10   hover:border-amber-500/20'   },
  slate:   { ring: 'ring-slate-500/20',   icon: 'text-slate-400',   hover: 'hover:bg-white/[0.04]   hover:border-white/[0.10]'   },
}

export function ControlCard() {
  const [loading, setLoading] = useState<string | null>(null)

  const handleAction = (id: string) => {
    setLoading(id)
    setTimeout(() => setLoading(null), 1800)
  }

  return (
    <GlassCard glow="emerald" padding={false} className="flex flex-col">
      <div className="p-6 pb-4">
        <p className="label-xs mb-1.5">Control Panel</p>
        <h2 className="text-lg font-medium text-slate-100">System Actions</h2>
      </div>

      <div className="mx-6 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />

      <div className="flex-1 grid grid-cols-2 gap-2.5 p-4">
        {actions.map(({ id, label, sub, icon: Icon, color }) => {
          const c = colorMap[color]
          const isLoading = loading === id
          return (
            <button
              key={id}
              onClick={() => handleAction(id)}
              disabled={isLoading}
              className={[
                'group relative flex flex-col items-start gap-2 rounded-xl p-3.5',
                'border border-white/[0.06] bg-white/[0.02] text-left',
                'transition-all duration-200',
                c.hover,
                isLoading ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer',
              ].join(' ')}
            >
              <div className={`flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.04] ring-1 ${c.ring}`}>
                <Icon className={`h-4 w-4 transition-transform duration-200 group-hover:scale-110 ${c.icon} ${isLoading ? 'animate-spin' : ''}`} />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-200 leading-tight">{label}</p>
                <p className="text-[10px] text-slate-600 mt-0.5 leading-tight">{sub}</p>
              </div>
            </button>
          )
        })}
      </div>

      <div className="border-t border-white/[0.06] px-6 py-2.5 flex items-center justify-between">
        <span className="label-xs">Operator</span>
        <span className="text-[10px] font-mono text-slate-500">root@btc-stm-prod</span>
      </div>
    </GlassCard>
  )
}
