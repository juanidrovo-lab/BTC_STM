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

const BOOT_LOGS: LogLine[] = [
  { ts: '—', level: 'INFO', msg: 'BTC-STM v0.3.0 inicializando...' },
  { ts: '—', level: 'OK',   msg: 'Conexión con Neon DB establecida' },
  { ts: '—', level: 'INFO', msg: 'Loop de estrategia: REST-only, 1h' },
  { ts: '—', level: 'INFO', msg: 'Activos: BTCUSDT, ETHUSDT, SOLUSDT' },
  { ts: '—', level: 'OK',   msg: 'Broker paper listo — capital: $10.000' },
  { ts: '—', level: 'INFO', msg: 'Gestor de riesgo: MAX_RISK=1% por trade' },
  { ts: '—', level: 'OK',   msg: 'Migración Alembic 003 aplicada' },
  { ts: '—', level: 'WARN', msg: 'LIVE_TRADING=false — modo demo activo' },
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

const SIMULATED = [
  'BTCUSDT vela cerrada: A=67380 M=67510 m=67310 C=67432',
  'GestorRiesgo.evaluar: APROBADO — dentro de límites',
  'EMA-200=66.891 | tendencia ALCISTA | sin cruce',
  'Snapshot de equity: $10.843,20 (+8,43%)',
  'ETHUSDT vela cerrada: A=3.521 M=3.590 m=3.498 C=3.548',
  'Portfolio PnL: realizado=$843,20 no-realizado=$0,00',
  'Ping WebSocket: 14 ms',
  'SOLUSDT: precio $142,30 | EMA200=138,50 | ALCISTA',
]

export function ConsoleCard() {
  const [logs,    setLogs]    = useState<LogLine[]>(BOOT_LOGS)
  const [fromDB,  setFromDB]  = useState(false)
  const bodyRef               = useRef<HTMLDivElement>(null)
  const lastCountRef          = useRef(0)

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
      // mantener logs actuales
    }
  }, [])

  useEffect(() => {
    fetchLogs()
    const id = setInterval(fetchLogs, 5_000)
    return () => clearInterval(id)
  }, [fetchLogs])

  useEffect(() => {
    if (fromDB) return
    let idx = 0
    const id = setInterval(() => {
      const now = new Date().toLocaleTimeString('es', { hour12: false })
      setLogs(prev => [...prev.slice(-40), { ts: now, level: 'INFO', msg: SIMULATED[idx % SIMULATED.length] }])
      idx++
    }, 2800)
    return () => clearInterval(id)
  }, [fromDB])

  return (
    <GlassCard glow="cyan" padding={false} className="flex flex-col">
      <div className="flex items-center justify-between p-4 pb-3">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-cyan-400" />
          <p className="label-xs">Consola del Sistema</p>
          {fromDB && (
            <span className="text-[9px] font-mono text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded">
              BD EN VIVO
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="flex h-2 w-2 rounded-full bg-red-500/80"     />
          <span className="flex h-2 w-2 rounded-full bg-amber-500/80"   />
          <span className="flex h-2 w-2 rounded-full bg-emerald-500/80" />
        </div>
      </div>

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

      <div className="border-t border-white/[0.06] px-4 py-2.5 font-mono text-[11px] flex items-center gap-2">
        <span className="text-emerald-400">btc-stm</span>
        <span className="text-slate-600">$</span>
        <span className="text-slate-500 animate-blink">█</span>
      </div>
    </GlassCard>
  )
}
