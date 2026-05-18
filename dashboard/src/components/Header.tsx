'use client'

import { Activity, Lock, Zap } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { LiveToggle } from './LiveToggle'

interface TickerData {
  price:    string
  change:   string
  positive: boolean
}

const NAV_ITEMS = [
  { label: 'Dashboard', active: true  },
  { label: 'Trading',   active: false },
  { label: 'Analytics', active: false },
  { label: 'Settings',  active: false },
]

export function Header() {
  const [time,   setTime]   = useState('')
  const [ticker, setTicker] = useState<TickerData>({ price: '—', change: '—', positive: true })
  const wsRef = useRef<WebSocket | null>(null)

  // Clock
  useEffect(() => {
    const tick = () => setTime(new Date().toLocaleTimeString('en-US', { hour12: false }))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  // BTC price — Binance public miniTicker WebSocket (browser-direct, no proxy)
  useEffect(() => {
    function connect() {
      const ws = new WebSocket('wss://stream.binance.com:9443/ws/btcusdt@miniTicker')
      wsRef.current = ws
      ws.onmessage = (e) => {
        try {
          const d        = JSON.parse(e.data)
          const price    = parseFloat(d.c)
          const open     = parseFloat(d.o)
          const pct      = ((price - open) / open) * 100
          const positive = pct >= 0
          setTicker({
            price:    price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
            change:   `${positive ? '+' : ''}${pct.toFixed(2)}%`,
            positive,
          })
        } catch {}
      }
      ws.onclose = () => setTimeout(connect, 3000)
    }
    connect()
    return () => { wsRef.current?.close(); wsRef.current = null }
  }, [])

  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-[#070a13]/80 backdrop-blur-xl">
      <div className="mx-auto max-w-[1600px] px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between gap-4">

          {/* ── Logo ── */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-500/10 ring-1 ring-cyan-500/20">
              <Activity className="h-5 w-5 text-cyan-400" />
            </div>
            <div>
              <span className="text-sm font-semibold tracking-tight text-slate-100">BTC</span>
              <span className="text-sm font-light text-cyan-400">-STM</span>
            </div>
          </div>

          {/* ── Nav ── */}
          <nav className="hidden md:flex items-center gap-1">
            {NAV_ITEMS.map(({ label, active }) =>
              active ? (
                <button
                  key={label}
                  className="px-4 py-1.5 rounded-lg text-xs font-medium uppercase tracking-wider bg-cyan-500/10 text-cyan-400 ring-1 ring-cyan-500/20"
                >
                  {label}
                </button>
              ) : (
                <button
                  key={label}
                  disabled
                  title="Próximamente"
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium uppercase tracking-wider text-slate-600 cursor-not-allowed opacity-50"
                >
                  <Lock className="h-2.5 w-2.5" />
                  {label}
                </button>
              )
            )}
          </nav>

          {/* ── Right side ── */}
          <div className="flex items-center gap-3 flex-shrink-0">

            {/* BTC price */}
            <div className="hidden sm:flex items-center gap-2 rounded-lg bg-white/[0.03] border border-white/[0.06] px-3 py-1.5">
              <Zap className="h-3.5 w-3.5 text-amber-400" />
              <span className="text-xs font-mono font-medium text-slate-300">
                {ticker.price === '—' ? '…' : `$${ticker.price}`}
              </span>
              <span className={`text-[10px] font-medium ${ticker.positive ? 'text-emerald-400' : 'text-red-400'}`}>
                {ticker.change}
              </span>
            </div>

            {/* Live / Paper toggle */}
            <LiveToggle />

            {/* Connected indicator */}
            <div className="flex items-center gap-2 rounded-lg bg-emerald-500/[0.06] border border-emerald-500/[0.12] px-3 py-1.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
              </span>
              <span className="text-xs font-medium text-emerald-400 tracking-wide">
                Connected
              </span>
            </div>

            {/* Clock */}
            <span className="hidden lg:block text-xs font-mono text-slate-600 tabular-nums">
              {time}
            </span>
          </div>

        </div>
      </div>
    </header>
  )
}
