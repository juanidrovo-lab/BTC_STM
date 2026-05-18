'use client'

import { GlassCard } from './GlassCard'
import { TrendingUp, BarChart2 } from 'lucide-react'
import { useState } from 'react'

// 30 realistic-looking activity bars (deterministic, no Math.random)
const RAW = [42,58,35,71,88,52,63,45,79,93,67,48,82,56,70,44,86,61,73,39,95,54,68,47,84,60,76,43,89,65]
const MAX = Math.max(...RAW)
const bars = RAW.map((v, i) => ({
  pct: Math.round((v / MAX) * 100),
  label: `${String(17 + Math.floor(i / 2)).padStart(2,'0')}:${i % 2 === 0 ? '00' : '30'}`,
  volume: (v * 0.23 + 12).toFixed(2),
}))

interface BarProps { pct: number; label: string; volume: string; index: number }

function Bar({ pct, label, volume, index }: BarProps) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      className="group relative flex flex-1 flex-col items-center justify-end gap-1"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Tooltip */}
      {hovered && (
        <div className="absolute -top-10 left-1/2 -translate-x-1/2 z-10 whitespace-nowrap rounded-lg bg-slate-800 border border-white/10 px-2.5 py-1 text-[10px] font-mono text-cyan-400 shadow-xl">
          {volume} BTC
        </div>
      )}

      {/* Bar */}
      <div
        className="relative w-full origin-bottom rounded-t-sm transition-all duration-300 ease-out"
        style={{
          height: `${pct}%`,
          animationDelay: `${index * 30}ms`,
          background: hovered
            ? 'linear-gradient(to top, rgba(6,182,212,0.5), rgba(34,211,238,0.8))'
            : 'linear-gradient(to top, rgba(6,182,212,0.15), rgba(34,211,238,0.45))',
          boxShadow: hovered ? '0 0 12px rgba(6,182,212,0.4)' : 'none',
        }}
      />

      {/* X-label (every 5th) */}
      {index % 5 === 0 && (
        <span className="absolute -bottom-5 text-[9px] font-mono text-slate-600 whitespace-nowrap">
          {label}
        </span>
      )}
    </div>
  )
}

export function ActivityChart() {
  return (
    <GlassCard glow="cyan" padding={false} className="flex flex-col">
      {/* Header */}
      <div className="flex items-start justify-between p-6 pb-4">
        <div>
          <p className="label-xs mb-1.5">Trading Activity</p>
          <div className="flex items-baseline gap-2">
            <h2 className="text-3xl font-light tracking-tight text-slate-100">BTCUSDT</h2>
            <span className="flex items-center gap-1 text-sm font-medium text-emerald-400">
              <TrendingUp className="h-3.5 w-3.5" />
              +12.47%
            </span>
          </div>
          <p className="mt-0.5 text-sm text-slate-500">Last 30 minutes · 1m bars</p>
        </div>
        <div className="flex items-center gap-2 rounded-lg bg-cyan-500/10 border border-cyan-500/20 px-3 py-1.5">
          <BarChart2 className="h-3.5 w-3.5 text-cyan-400" />
          <span className="text-xs font-medium text-cyan-400">LIVE</span>
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-blink" />
        </div>
      </div>

      {/* Divider with subtle gradient */}
      <div className="mx-6 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />

      {/* Chart */}
      <div className="flex-1 px-6 pt-4 pb-8">
        <div className="flex h-full items-end gap-[3px]">
          {bars.map((b, i) => (
            <Bar key={i} {...b} index={i} />
          ))}
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 divide-x divide-white/[0.06] border-t border-white/[0.06]">
        {[
          { label: 'Avg Volume', value: '18.4 BTC' },
          { label: 'Peak',       value: '95.0 BTC' },
          { label: 'Sessions',  value: '3 Active' },
        ].map(({ label, value }) => (
          <div key={label} className="px-6 py-3 text-center">
            <p className="label-xs mb-0.5">{label}</p>
            <p className="text-sm font-medium text-slate-200">{value}</p>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}
