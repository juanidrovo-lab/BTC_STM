'use client'

import { GlassCard } from './GlassCard'
import { Play, Activity, Database, Download, RefreshCw, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'
import { useState } from 'react'

type ActionColor  = 'cyan' | 'emerald' | 'amber' | 'slate'
type ActionStatus = 'idle' | 'loading' | 'ok' | 'error'

interface Action {
  id:      string
  label:   string
  sub:     string
  icon:    React.ElementType
  color:   ActionColor
  danger?: boolean
  call?:   () => Promise<void>
}

const colorMap: Record<ActionColor, { ring: string; icon: string; hover: string }> = {
  cyan:    { ring: 'ring-cyan-500/20',    icon: 'text-cyan-400',    hover: 'hover:bg-cyan-500/10    hover:border-cyan-500/20'    },
  emerald: { ring: 'ring-emerald-500/20', icon: 'text-emerald-400', hover: 'hover:bg-emerald-500/10 hover:border-emerald-500/20' },
  amber:   { ring: 'ring-amber-500/20',   icon: 'text-amber-400',   hover: 'hover:bg-amber-500/10   hover:border-amber-500/20'   },
  slate:   { ring: 'ring-slate-500/20',   icon: 'text-slate-400',   hover: 'hover:bg-slate-500/10   hover:border-slate-500/20'   },
}

export function ControlCard() {
  const [statuses, setStatuses] = useState<Record<string, ActionStatus>>({})

  function setStatus(id: string, s: ActionStatus) {
    setStatuses(prev => ({ ...prev, [id]: s }))
  }

  async function run(action: Action) {
    if (statuses[action.id] === 'loading') return
    setStatus(action.id, 'loading')
    try {
      if (action.call) {
        await action.call()
      } else {
        await new Promise(r => setTimeout(r, 1200))
      }
      setStatus(action.id, 'ok')
    } catch {
      setStatus(action.id, 'error')
    }
    setTimeout(() => setStatus(action.id, 'idle'), 3000)
  }

  const actions: Action[] = [
    {
      id: 'backtest', label: 'Run Backtest', sub: 'Execute strategy simulation',
      icon: Play, color: 'cyan',
      call: async () => {
        const res = await fetch('/api/backtest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bars: 100 }) })
        if (!res.ok) throw new Error()
      },
    },
    {
      id: 'health', label: 'Health Check', sub: 'Ping /api/health endpoint',
      icon: Activity, color: 'emerald',
      call: async () => {
        const res = await fetch('/api/health')
        if (!res.ok) throw new Error()
      },
    },
    {
      id: 'migrate', label: 'Run Migration', sub: 'Apply Alembic head schema',
      icon: Database, color: 'cyan',
      call: async () => {
        const res = await fetch('/api/migrate?token=btcstm2026', { method: 'POST' })
        if (!res.ok) throw new Error()
      },
    },
    {
      id: 'export',   label: 'Export Data',    sub: 'Download session CSV',     icon: Download,       color: 'emerald' },
    {
      id: 'refresh',  label: 'Sync Positions', sub: 'Reload from Neon DB',      icon: RefreshCw,      color: 'slate'   },
    {
      id: 'alert',    label: 'Risk Override',  sub: 'Bypass risk limits (dev)', icon: AlertTriangle,  color: 'amber',  danger: true },
  ]

  return (
    <GlassCard glow="emerald" padding={false} className="flex flex-col">
      {/* Header */}
      <div className="p-6 pb-4">
        <p className="label-xs mb-1.5">Control Panel</p>
        <h2 className="text-lg font-medium text-slate-100">System Actions</h2>
      </div>

      <div className="mx-6 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />

      {/* Actions grid */}
      <div className="flex-1 grid grid-cols-2 gap-2.5 p-4">
        {actions.map((action) => {
          const { id, label, sub, icon: Icon, color, danger } = action
          const c         = colorMap[color]
          const status    = statuses[id] ?? 'idle'
          const isLoading = status === 'loading'

          return (
            <button
              key={id}
              onClick={() => run(action)}
              disabled={isLoading}
              className={[
                'group relative flex flex-col items-start gap-2 rounded-xl p-3.5',
                'border border-white/[0.06] bg-white/[0.02]',
                'text-left transition-all duration-200',
                c.hover,
                isLoading && 'opacity-60 cursor-not-allowed',
                danger && 'hover:border-amber-500/30',
              ].join(' ')}
            >
              <div className={`flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.04] ring-1 ${c.ring}`}>
                {status === 'ok' ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                ) : status === 'error' ? (
                  <XCircle className="h-4 w-4 text-red-400" />
                ) : (
                  <Icon className={`h-4 w-4 transition-transform duration-200 group-hover:scale-110 ${c.icon} ${isLoading ? 'animate-spin' : ''}`} />
                )}
              </div>
              <div>
                <p className="text-xs font-medium text-slate-200 leading-tight">{label}</p>
                <p className="text-[10px] text-slate-600 mt-0.5 leading-tight">{sub}</p>
              </div>
              {isLoading && (
                <div className="absolute inset-0 rounded-xl overflow-hidden">
                  <div
                    className="absolute inset-0 opacity-20"
                    style={{
                      background: 'linear-gradient(90deg, transparent 0%, rgba(6,182,212,0.4) 50%, transparent 100%)',
                      backgroundSize: '200% 100%',
                      animation: 'shimmer 1.2s linear infinite',
                    }}
                  />
                </div>
              )}
            </button>
          )
        })}
      </div>

      {/* Status bar */}
      <div className="border-t border-white/[0.06] px-6 py-2.5 flex items-center justify-between">
        <span className="label-xs">Operator</span>
        <span className="text-[10px] font-mono text-slate-500">root@btc-stm-prod</span>
      </div>
    </GlassCard>
  )
}
