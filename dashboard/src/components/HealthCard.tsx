import { GlassCard } from './GlassCard'
import { Server, CheckCircle2, Circle } from 'lucide-react'

const metrics: { label: string; value: string; accent?: string }[] = [
  { label: 'Status',      value: 'OK',       accent: 'emerald' },
  { label: 'Service',     value: 'btc-stm',  accent: 'cyan'    },
  { label: 'Version',     value: '0.2.0'                       },
  { label: 'Python',      value: '3.12.13'                     },
  { label: 'Mode',        value: 'PAPER',    accent: 'amber'   },
  { label: 'Persistence', value: 'NEON',     accent: 'cyan'    },
  { label: 'Database',    value: 'Connected', accent: 'emerald' },
]

const accentMap: Record<string, string> = {
  emerald: 'text-emerald-400',
  cyan:    'text-cyan-400',
  amber:   'text-amber-400',
}

export function HealthCard() {
  return (
    <GlassCard glow="emerald" padding={false} className="flex flex-col">
      <div className="flex items-center justify-between p-6 pb-4">
        <div>
          <p className="label-xs mb-1.5">System Health</p>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <h2 className="text-lg font-medium text-slate-100">All Systems Go</h2>
          </div>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 ring-1 ring-emerald-500/20">
          <Server className="h-5 w-5 text-emerald-400" />
        </div>
      </div>

      <div className="mx-6 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />

      <div className="flex-1 divide-y divide-white/[0.04] px-2 py-2 overflow-auto">
        {metrics.map(({ label, value, accent }) => (
          <div
            key={label}
            className="flex items-center justify-between px-4 py-2.5 rounded-lg hover:bg-white/[0.03] transition-colors duration-150"
          >
            <span className="label-xs">{label}</span>
            <div className="flex items-center gap-2">
              {accent === 'emerald' && (
                <Circle className="h-2 w-2 fill-emerald-400 text-emerald-400 animate-pulse" />
              )}
              <span className={`text-xs font-mono font-medium ${accent ? accentMap[accent] : 'text-slate-300'}`}>
                {value}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-white/[0.06] px-6 py-3 flex items-center justify-between">
        <span className="label-xs">Last ping</span>
        <span className="text-xs font-mono text-slate-500">0ms · Neon IAD1</span>
      </div>
    </GlassCard>
  )
}
