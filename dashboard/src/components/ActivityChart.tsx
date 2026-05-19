'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { GlassCard } from './GlassCard'
import { TrendingUp, TrendingDown, RefreshCw, CandlestickChart } from 'lucide-react'

interface PriceStats {
  last:    number
  open24h: number
  high24h: number
  low24h:  number
  vol24h:  number
  pct24h:  number
}

interface Props {
  symbol?: string  // e.g. "BTCUSDT"
}

export function ActivityChart({ symbol = 'BTCUSDT' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef     = useRef<any>(null)
  const candleRef    = useRef<any>(null)
  const volRef       = useRef<any>(null)
  const symbolRef    = useRef(symbol)

  const [stats,   setStats]   = useState<PriceStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)

  // ── Fetch klines y actualizar series ─────────────────────────────────────
  const fetchAndUpdate = useCallback(async (sym: string) => {
    try {
      const res = await fetch(
        `https://api.binance.com/api/v3/klines?symbol=${sym}&interval=1h&limit=200`
      )
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const raw: string[][] = await res.json()

      const candles = raw.map(k => ({
        time:  Math.floor(Number(k[0]) / 1000) as any,
        open:  parseFloat(k[1]),
        high:  parseFloat(k[2]),
        low:   parseFloat(k[3]),
        close: parseFloat(k[4]),
      }))
      const volumes = raw.map(k => {
        const bull = parseFloat(k[4]) >= parseFloat(k[1])
        return {
          time:  Math.floor(Number(k[0]) / 1000) as any,
          value: parseFloat(k[5]),
          color: bull ? 'rgba(16,185,129,0.45)' : 'rgba(244,63,94,0.45)',
        }
      })

      if (candleRef.current) candleRef.current.setData(candles)
      if (volRef.current)    volRef.current.setData(volumes)
      if (chartRef.current)  chartRef.current.timeScale().fitContent()

      const last  = candles[candles.length - 1]
      const first = candles[0]
      const vols  = raw.map(k => parseFloat(k[5]))
      const highs = raw.map(k => parseFloat(k[2]))
      const lows  = raw.map(k => parseFloat(k[3]))
      setStats({
        last:    last.close,
        open24h: first.open,
        high24h: Math.max(...highs),
        low24h:  Math.min(...lows),
        vol24h:  vols.reduce((a, b) => a + b, 0),
        pct24h:  ((last.close - first.open) / first.open) * 100,
      })
      setError(null)
    } catch {
      setError('No se pudo cargar el gráfico')
    } finally {
      setLoading(false)
    }
  }, [])

  // ── Construir gráfico al montar ───────────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    import('lightweight-charts').then(({ createChart, ColorType, CrosshairMode }) => {
      const chart = createChart(el, {
        layout: {
          background: { type: ColorType.Solid, color: 'transparent' },
          textColor:  '#475569',
          fontSize:   11,
        },
        grid: {
          vertLines: { color: 'rgba(255,255,255,0.03)' },
          horzLines: { color: 'rgba(255,255,255,0.03)' },
        },
        crosshair: {
          mode:     CrosshairMode.Normal,
          vertLine: { color: 'rgba(100,216,255,0.35)', labelBackgroundColor: '#0f172a' },
          horzLine: { color: 'rgba(100,216,255,0.35)', labelBackgroundColor: '#0f172a' },
        },
        rightPriceScale: {
          borderColor:  'rgba(255,255,255,0.06)',
          textColor:    '#475569',
          scaleMargins: { top: 0.05, bottom: 0.22 },
        },
        timeScale: {
          borderColor:    'rgba(255,255,255,0.06)',
          timeVisible:    true,
          secondsVisible: false,
        },
        handleScroll: true,
        handleScale:  true,
        width:  el.clientWidth,
        height: el.clientHeight,
      })

      const candle = chart.addCandlestickSeries({
        upColor:         '#10b981',
        downColor:       '#f43f5e',
        borderUpColor:   '#10b981',
        borderDownColor: '#f43f5e',
        wickUpColor:     '#6ee7b7',
        wickDownColor:   '#fca5a5',
      })

      const vol = chart.addHistogramSeries({
        priceFormat:  { type: 'volume' },
        priceScaleId: 'vol',
      })
      chart.priceScale('vol').applyOptions({
        scaleMargins:  { top: 0.78, bottom: 0 },
        ticksVisible:  false,
        borderVisible: false,
      })

      chartRef.current  = chart
      candleRef.current = candle
      volRef.current    = vol

      fetchAndUpdate(symbolRef.current)

      const ro = new ResizeObserver(() => {
        if (el) chart.applyOptions({ width: el.clientWidth, height: el.clientHeight })
      })
      ro.observe(el)
      ;(chart as any).__ro = ro
    })

    return () => {
      ;(chartRef.current as any)?.__ro?.disconnect()
      chartRef.current?.remove()
      chartRef.current  = null
      candleRef.current = null
      volRef.current    = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Recargar cuando cambia el símbolo ────────────────────────────────────
  useEffect(() => {
    symbolRef.current = symbol
    setLoading(true)
    setStats(null)
    if (candleRef.current) fetchAndUpdate(symbol)
  }, [symbol, fetchAndUpdate])

  // ── Poll REST cada 60 s (sin WebSocket) ───────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => {
      if (candleRef.current) fetchAndUpdate(symbolRef.current)
    }, 60_000)
    return () => clearInterval(id)
  }, [fetchAndUpdate])

  const up   = (stats?.pct24h ?? 0) >= 0
  const sign = up ? '+' : ''
  const base = symbol.replace('USDT', '')

  return (
    <GlassCard glow="cyan" padding={false} className="flex flex-col">

      {/* ── Cabecera ── */}
      <div className="flex items-start justify-between p-5 pb-3 flex-shrink-0">
        <div>
          <p className="label-xs mb-1">Gráfico de Velas · {symbol} · 1h</p>
          <div className="flex items-baseline gap-3">
            <span className="text-2xl font-light tracking-tight text-slate-100 font-mono">
              {stats
                ? `$${stats.last.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                : '—'}
            </span>
            {stats && (
              <span className={`flex items-center gap-1 text-sm font-medium ${up ? 'text-emerald-400' : 'text-red-400'}`}>
                {up ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
                {sign}{stats.pct24h.toFixed(2)}%
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {stats && (
            <div className="hidden sm:flex gap-4">
              {[
                { label: 'MAX', value: `$${stats.high24h.toLocaleString('en-US', { maximumFractionDigits: 0 })}`, cls: 'text-emerald-400' },
                { label: 'MÍN', value: `$${stats.low24h.toLocaleString('en-US',  { maximumFractionDigits: 0 })}`, cls: 'text-red-400'     },
                { label: 'VOL', value: `${stats.vol24h.toFixed(0)} ${base}`,                                       cls: 'text-slate-400'  },
              ].map(({ label, value, cls }) => (
                <div key={label} className="text-right">
                  <p className="text-[9px] text-slate-600 uppercase tracking-wider">{label}</p>
                  <p className={`text-xs font-mono font-medium ${cls}`}>{value}</p>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-1.5">
            {loading
              ? <RefreshCw className="h-3.5 w-3.5 text-cyan-400 animate-spin" />
              : <CandlestickChart className="h-3.5 w-3.5 text-cyan-400" />}
            <span className="text-[11px] font-medium text-cyan-400 tracking-wide">
              {error ? 'ERROR' : 'VIVO'}
            </span>
            {!error && <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />}
          </div>
        </div>
      </div>

      <div className="mx-5 h-px bg-gradient-to-r from-transparent via-white/[0.05] to-transparent flex-shrink-0" />

      {/* ── Gráfico ── */}
      <div className="relative flex-1 min-h-0">
        {error && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <div className="text-center">
              <p className="text-sm text-slate-500">{error}</p>
              <button
                onClick={() => fetchAndUpdate(symbolRef.current)}
                className="mt-2 text-xs text-cyan-400 hover:text-cyan-300 underline"
              >
                Reintentar
              </button>
            </div>
          </div>
        )}
        <div ref={containerRef} className="absolute inset-0" />
      </div>

    </GlassCard>
  )
}
