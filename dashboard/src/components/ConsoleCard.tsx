'use client'

import { GlassCard } from './GlassCard'
import { Terminal, Circle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

type LogLevel = 'INFO' | 'OK' | 'WARN' | 'ERR'

interface LogLine {
  ts: string
  level: LogLevel
  msg: string
}

const INITIAL_LOGS: LogLine[] = [
  { ts: '18:00:01', level: 'INFO', msg: 'BTC-STM v0.2.0 initializing...' },
  { ts: '18:00:01', level: 'OK',   msg: 'Neon DB connection established' },
  { ts: '18:00:02', level: 'INFO', msg: 'WebSocket: BTCUSDT@kline_1m' },
  { ts: '18:00:02', level: 'INFO', msg: 'Strategy: NoOpStrategy loaded' },
  { ts: '18:00:03', level: 'OK',   msg: 'Paper broker ready — cash: $10,000' },
  { ts: '18:00:03', level: 'INFO', msg: 'Risk manager: MAX_DAILY_LOSS=2.0%' },
  { ts: '18:00:04', level: 'OK',   msg: 'Alembic migration 001 applied' },
  { ts: '18:00:05', level: 'WARN', msg: 'LIVE_TRADING=false — paper mode' },
  { ts: '18:00:06', level: 'INFO', msg: 'BTCUSDT: $67,432.10 (+0.84%)' },
]

const LIVE_LINES: string[] = [
  'BTCUSDT kline closed: O=67380 H=67510 L=67310 C=67432',
  'RiskManager.evaluate: PASS — within limits',
  'NoOpStrategy: no signal — holding',
  'Equity snapshot: $10,843.20 (+8.43%)',
  'BTCUSDT kline closed: O=67432 H=67590 L=67400 C=67521',
  'Portfolio PnL: realized=$843.20 unrealized=$0.00',
  'WebSocket ping: 14ms',
  'BTCUSDT kline closed: O=67521 H=67620 L=67480 C=67558',
]

const levelStyle: Record<LogLevel, string> = {
  INFO: 'text-cyan-400',
  OK:   'text-emerald-400',
  WARN: 'text-amber-400',
  ERR:  'text-red-400',
}

function now() {
  return new Date().toLocaleTimeString('en-US', { hour12: false })
}

export function ConsoleCard() {
  const [logs, setLogs] = useState<LogLine[]>(INITIAL_LOGS)
  const bottomRef = useRef<HTMLDivElement>(null)
  let liveIdx = useRef(0)

  useEffect(() => {
    const id = setInterval(() => {
      const msg = LIVE_LINES[liveIdx.current % LIVE_LINES.length]
      liveIdx.current++
      setLogs(prev => [...prev.slice(-40), { ts: now(), level: 'INFO', msg }])
    }, 2800)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <GlassCard glow="cyan" padding={false} className="flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 pb-3">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-cyan-400" />
          <p className="label-xs">System Console</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex h-2 w-2 rounded-full bg-red-500/80"    />
          <span className="flex h-2 w-2 rounded-full bg-amber-500/80"  />
          <span className="flex h-2 w-2 rounded-full bg-emerald-500/80"/>
        </div>
      </div>

      {/* Terminal body */}
      <div
        className="flex-1 overflow-y-auto scrollbar-thin px-4 pb-4 font-mono text-[11px] leading-relaxed"
        style={{ background: 'rgba(2,6,15,0.7)' }}
      >
        {logs.map((line, i) => (
          <div key={i} className="flex gap-2 py-[2px] hover:bg-white/[0.02] rounded px-1">
            <span className="shrink-0 text-slate-600">{line.ts}</span>
            <span className={`shrink-0 w-10 font-semibold ${levelStyle[line.level]}`}>
              {line.level}
            </span>
            <span className="text-slate-400 break-all">{line.msg}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Prompt line */}
      <div className="border-t border-white/[0.06] px-4 py-2.5 font-mono text-[11px] flex items-center gap-2">
        <span className="text-emerald-400">btc-stm</span>
        <span className="text-slate-600">$</span>
        <span className="text-slate-500 animate-blink">█</span>
      </div>
    </GlassCard>
  )
}
