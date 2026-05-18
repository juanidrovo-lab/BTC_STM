'use client'

import { Activity, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'

export function Header() {
  const [time, setTime] = useState('')
  const [btcPrice, setBtcPrice] = useState('67,432.10')

  useEffect(() => {
    const tick = () => {
      const now = new Date()
      setTime(now.toLocaleTimeString('en-US', { hour12: false }))
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  // Simulate price tick
  useEffect(() => {
    const id = setInterval(() => {
      const base = 67432.10
      const delta = (Math.random() - 0.5) * 80
      setBtcPrice((base + delta).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
    }, 3000)
    return () => clearInterval(id)
  }, [])

  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-[#070a13]/80 backdrop-blur-xl">
      <div className="mx-auto max-w-[1600px] px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between gap-4">
          {/* Logo */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-500/10 ring-1 ring-cyan-500/20">
              <Activity className="h-5 w-5 text-cyan-400" />
            </div>
            <div>
              <span className="text-sm font-semibold tracking-tight text-slate-100">BTC</span>
              <span className="text-sm font-light text-cyan-400">-STM</span>
            </div>
          </div>

          {/* Nav */}
          <nav className="hidden md:flex items-center gap-1">
            {['Dashboard', 'Trading', 'Analytics', 'Settings'].map((item, i) => (
              <button
                key={item}
                className={`px-4 py-1.5 rounded-lg text-xs font-medium uppercase tracking-wider transition-all duration-200 ${
                  i === 0
                    ? 'bg-cyan-500/10 text-cyan-400 ring-1 ring-cyan-500/20'
                    : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]'
                }`}
              >
                {item}
              </button>
            ))}
          </nav>

          {/* Right side */}
          <div className="flex items-center gap-4 flex-shrink-0">
            {/* BTC Price */}
            <div className="hidden sm:flex items-center gap-2 rounded-lg bg-white/[0.03] border border-white/[0.06] px-3 py-1.5">
              <Zap className="h-3.5 w-3.5 text-amber-400" />
              <span className="text-xs font-mono font-medium text-slate-300">
                ${btcPrice}
              </span>
              <span className="text-[10px] text-emerald-400 font-medium">+0.84%</span>
            </div>

            {/* Connected indicator */}
            <div className="flex items-center gap-2 rounded-lg bg-emerald-500/[0.06] border border-emerald-500/[0.12] px-3 py-1.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
              </span>
              <span className="text-xs font-medium text-emerald-400 tracking-wide">Connected</span>
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
