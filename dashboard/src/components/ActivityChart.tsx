'use client'

import { GlassCard } from './GlassCard'
import { TrendingUp, TrendingDown, BarChart2, RefreshCw } from 'lucide-react'
import { useEffect, useState, useCallback } from 'react'

interface KlineBar {
  pct:    number
  label:  string
  volume: string
  close:  number
  open:   number
}

// Fallback deterministic bars while loading
const FALLBACK_RAW = [42,58,35,71,88,52,63,45,79,93,67,48,82,56,70,44,86,61,73,39,95,54,68,47,84,60,76,43,89,65]

function buildFallback(): KlineBar[] {
  const max = Math.max(...FALLBACK_RAW)
  return FALLBACK_RAW.map((v, i) => ({
    pct:    Math.round((v / max) * 100),
    label:  `${String(17 + Math.floor(i / 2)).padStart(2, '0')}:${i % 2 === 0 ? '00' : '30'}`,
    volume: (v * 0.23 + 12).toFixed(2),
    close:  0,
    open:   0,
  }))
}

function parseBinanceKlines(raw: number[][]): KlineBar[] {
  if (!raw.length) return buildFallback()
  const closes = raw.map(k => parseFloat(String(k[4])))
  const volumes = raw.map(k => parseFloat(String(k[5])))
  const maxVol = Math.max(...volumes) || 1
  return raw.map((k, i) => {
    const open  = parseFloat(String(k[1]))
    const close = parseFloat(String(k[4]))
    const vol   = parseFloat(String(k[5]))
    const ts    = new Date(k[0])
    const hh    = String(ts.getHours()).padStart(2, '0')
    const mm    = String(ts.getMinutes()).padStart(2, '0')
    return {
      pct:    Math.max(4, Math.round((vol / maxVol) * 100)),
      label:  `${hh}:${mm}`,
      volume: vol.toFixed(2),
      close,
      open,
    }
  })
}

interface BarProps { bar: KlineBar; index: number; total: number }

function Bar({ bar, index, total }: BarProps) {
  const [hovered, setHovered] = useState(false)
  const bullish = bar.close >= bar.open || bar.close === 0
  return (
    <div
      className="group relative flex flex-1 flex-col items-center justify-end gap-1"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {hovered && (
        <div className="absolute -top-10 left-1/2 -translate-x-1/2 z-10 whitespace-nowrap rounded-lg bg-slate-800 border border-white/10 px-2.5 py-1 text-[10px] font-mono text-cyan-400 shadow-xl">
          {bar.volume} BTC
        </div>
      )}
      <div
        className="relative w-full origin-bottom rounded-t-sm transition-all duration-300 ease-out"
        style={{
          height: `${bar.pct}%`,
          background: hovered
            ? bullish
              ? 'linear-gradient(to top, rgba(6,182,212,0.5), rgba(34,211,238,0.8))'
              : 'linear-gradient(to top, rgba(239,68,68,0.5), rgba(248,113,113,0.8))'
            : bullish
              ? 'linear-gradient(to top, rgba(6,182,212,0.15), rgba(34,211,238,0.45))'
              : 'linear-gradient(to top, rgba(239,68,68,0.1), rgba(248,113,113,0.3))',
          boxShadow: hovered ? `0 0 12px ${bullish ? 'rgba(6,182,212,0.4)' : 'rgba(239,68,68,0.3)'}` : 'none',
        }}
      />
      {index % Math.ceil(total / 6) === 0 && (
        <span className="absolute -bottom-5 text-[9px] font-mono text-slate-600 whitespace-nowrap">
          {bar.label}
        </span>
      )}
    </div>
  )
}

export function ActivityChart() {
  const [bars, setBars]         = useState<KlineBar[]>(buildFallback())
  const [loading, setLoading]   = useState(true)
  const [change24h, setChange]  = useState<{ pct: string; up: boolean } | null>(null)
  const [avgVol, setAvgVol]     = useState('—')
  const [peakVol, setPeakVol]   = useState('—')

  const fetchKlines = useCallback(async () => {
    try {
      const res  = await fetch('https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=30')
      const data: number[][] = await res.json()
      const parsed = parseBinanceKlines(data)
      setBars(parsed)

      // Stats
      const vols = data.map(k => parseFloat(String(k[5])))
      setAvgVol((vols.reduce((a, b) => a + b, 0) / vols.length).toFixed(1))
      setPeakVol(Math.max(...vols).toFixed(1))

      // 24h change from ticker
      const t = await fetch('https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT')
      const td = await t.json()
      const pct = parseFloat(td.priceChangePercent)
      setChange({ pct: `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`, up: pct >= 0 })
    } catch {
      // keep fallback bars
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchKlines()
    const id = setInterval(fetchKlines, 60_000)
    return () => clearInterval(id)
  }, [fetchKlines])

  return (
    <GlassCard glow="cyan" padding={false} className="flex flex-col">
      {/* Header */}
      <div className="flex items-start justify-between p-6 pb-4">
        <div>
          <p className="label-xs mb-1.5">Trading Activity</p>
          <div className="flex items-baseline gap-2">
            <h2 className="text-3xl font-light tracking-tight text-slate-100">BTCUSDT</h2>
            {change24h && (
              <span className={`flex items-center gap-1 text-sm font-medium ${change24h.up ? 'text-emerald-400' : 'text-red-400'}`}>
                {change24h.up ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
                {change24h.pct}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-sm text-slate-500">Last 30 hours · 1h bars · Binance</p>
        </div>
        <div className="flex items-center gap-2 rounded-lg bg-cyan-500/10 border border-cyan-500/20 px-3 py-1.5">
          {loading
            ? <RefreshCw className="h-3.5 w-3.5 text-cyan-400 animate-spin" />
            : <BarChart2  className="h-3.5 w-3.5 text-cyan-400" />
          }
          <span className="text-xs font-medium text-cyan-400">LIVE</span>
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-blink" />
        </div>
      </div>

      <div className="mx-6 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />

      {/* Chart */}
      <div className="flex-1 px-6 pt-4 pb-8">
        <div className="flex h-full items-end gap-[3px]">
          {bars.map((b, i) => (
            <Bar key={i} bar={b} index={i} total={bars.length} />
          ))}
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 divide-x divide-white/[0.06] border-t border-white/[0.06]">
        {[
          { label: 'Avg Volume', value: avgVol === '—' ? '—' : `${avgVol} BTC` },
          { label: 'Peak',       value: peakVol === '—' ? '—' : `${peakVol} BTC` },
          { label: 'Interval',   value: '1h · 30 bars' },
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
