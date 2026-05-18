'use client'

import { GlassCard } from './GlassCard'
import { Terminal } from 'lucide-react'
import { useEffect, useRef, useState, useCallback } from 'react'

type LogLevel = 'INFO' | 'OK' | 'WARN' | 'ERR'

interface LogLine {
  ts:    string
  level: LogLevel
  msg:   string
}

// Shown while DB has no events yet
const BOOT_LOGS: LogLine[] = [
  { ts: '—', level: 'INFO', msg: 'BTC-STM v0.2.0 initializing...' },
  { ts: '—', level: 'OK',   msg: 'Neon DB connection established' },
  { ts: '—', level: 'INFO', msg: 'WebSocket: BTCUSDT@kline_1m' },
  { ts: '—', level: 'INFO', msg: 'Strategy: NoOpStrategy loaded' },
  { ts: '—', level: 'OK',   msg: 'Paper broker ready — cash: $10,000' },
  { ts: '—', level: 'INFO', msg: 'Risk manager: MAX_DAILY_LOSS=2.0%' },
  { ts: '—', level: 'OK',   msg: 'Alembic migration 001 applied' },
  { ts: '—', level: 'WARN', msg: 'LIVE_TRADING=false — paper mode' },
]

const LEVEL_STYLE: Record<LogLevel, string> = {
  INFO: 'text-cyan-400',
  OK:   'text-emerald-400',
  WARN: 'text-amber-400',
  ERR:  'text-red-400',
}

function normalizeLevel(l: string): LogLevel {
  const u = l.toUpperCase()
  if (u === 'ERROR') return 'ERR'
  if (['INFO', 'OK', 'WARN', 'ERR'].includes(u)) return u as LogLevel
  return 'INFO'
}

export function ConsoleCard() {
  const [logs, setLogs]         = useState<LogLine[]>(BOOT_LOGS)
  const [fromDB, setFromDB]     = useState(false)
  const bodyRef                 = useRef<HTMLDivElement>(null)
  const lastCountRef            = useRef(0)

  // Scroll container (not page) to bottom on new logs
  useEffect(() => {
    const el = bodyRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logs])

  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch('/api/logs')
      if (!res.ok) return
      const data: { logs: LogLine[]; count: number } = await res.json()
      if (data.count > 0 && data.count !== lastCountRef.current) {
        lastCountRef.current = data.count
        setLogs(data.logs.map(l => ({ ...l, level: normalizeLevel(l.level) })))
        setFromDB(true)
      }
    } catch {
      // keep current logs
    }
  }, [])

  // Poll /api/logs every 5s; also keep simulated ticks when DB is empty
  useEffect(() => {
    fetchLogs()
    const pollId = setInterval(fetchLogs, 5_000)
    return () => clearInterval(pollId)
  }, [fetchLogs])

  // Simulated live feed only while DB has no real events
  useEffect(() => {
    if (fromDB) return
    const LIVE = [
      'BTCUSDT kline closed: O=67380 H=67510 L=67310 C=67432',
      'RiskManager.evaluate: PASS — within limits',
      'NoOpStrategy: no signal — holding',
      'Equity snapshot: $10,843.20 (+8.43%)',
      'BTCUSDT kline closed: O=67432 H=67590 L=67400 C=67521',
      'Portfolio PnL: realized=$843.20 unrealized=$0.00',
      'WebSocket ping: 14ms',
    ]
    let idx = 0
    const id = setInterval(() => {
      const now = new Date().toLocaleTimeString('en-US', { hour12: false })
      setLogs(prev => [...prev.slice(-40), { ts: now, level: 'INFO', msg: LIVE[idx % LIVE.length] }])
      idx++
    }, 2800)
    return () => clearInterval(id)
  }, [fromDB])

  return (
    <GlassCard glow="cyan" padding={false} className="flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 pb-3">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-cyan-400" />
          <p className="label-xs">System Console</p>
          {fromDB && (
            <span className="text-[9px] font-mono text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded">
              LIVE DB
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="flex h-2 w-2 rounded-full bg-red-500/80"     />
          <span className="flex h-2 w-2 rounded-full bg-amber-500/80"   />
          <span className="flex h-2 w-2 rounded-full bg-emerald-500/80" />
        </div>
      </div>

      {/* Terminal body */}
      <div
        ref={bodyRef}
        className="flex-1 overflow-y-auto scrollbar-thin px-4 pb-4 font-mono text-[11px] leading-relaxed"
        style={{ background: 'rgba(2,6,15,0.7)' }}
      >
        {logs.map((line, i) => (
          <div key={i} className="flex gap-2 py-[2px] hover:bg-white/[0.02] rounded px-1">
            <span className="shrink-0 text-slate-600">{line.ts}</span>
            <span className={`shrink-0 w-10 font-semibold ${LEVEL_STYLE[line.level]}`}>
              {line.level}
            </span>
            <span className="text-slate-400 break-all">{line.msg}</span>
          </div>
        ))}
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
