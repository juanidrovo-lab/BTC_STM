'use client'

import { useEffect, useState, useCallback } from 'react'
import { AlertTriangle, ShieldOff, ShieldCheck, Loader2 } from 'lucide-react'

type Mode = 'PAPER' | 'LIVE'

interface ToggleState {
  mode:    Mode
  loading: boolean
  error:   string | null
}

export function LiveToggle() {
  const [state,       setState]       = useState<ToggleState>({ mode: 'PAPER', loading: true, error: null })
  const [showConfirm, setShowConfirm] = useState(false)
  const [switching,   setSwitching]   = useState(false)

  // ── Fetch current mode from backend ─────────────────────────────────────
  const fetchState = useCallback(async () => {
    try {
      const res  = await fetch('/api/strategy/status')
      if (!res.ok) throw new Error()
      const data = await res.json()
      setState({ mode: data.live_trading ? 'LIVE' : 'PAPER', loading: false, error: null })
    } catch {
      setState(s => ({ ...s, loading: false, error: 'No se pudo obtener el estado' }))
    }
  }, [])

  useEffect(() => { fetchState() }, [fetchState])

  // ── Handle toggle click ──────────────────────────────────────────────────
  const handleToggleClick = () => {
    if (state.loading || switching) return
    // Going LIVE requires explicit confirmation
    if (state.mode === 'PAPER') {
      setShowConfirm(true)
    } else {
      doSwitch()
    }
  }

  const doSwitch = async () => {
    setShowConfirm(false)
    setSwitching(true)
    try {
      const res  = await fetch('/api/strategy/toggle-live', { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setState({ mode: data.live_trading ? 'LIVE' : 'PAPER', loading: false, error: null })
    } catch (e: any) {
      setState(s => ({ ...s, error: 'Error al cambiar modo' }))
    } finally {
      setSwitching(false)
    }
  }

  const isLive = state.mode === 'LIVE'

  // ── Pill visual ──────────────────────────────────────────────────────────
  return (
    <>
      <button
        onClick={handleToggleClick}
        disabled={state.loading || switching}
        title={isLive ? 'Click para volver a PAPER' : 'Click para activar LIVE'}
        className={`
          relative flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium
          border transition-all duration-300 select-none
          disabled:opacity-50 disabled:cursor-not-allowed
          ${isLive
            ? 'bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20'
            : 'bg-slate-800/60 border-white/[0.08] text-slate-400 hover:border-cyan-500/30 hover:text-cyan-400'
          }
        `}
      >
        {/* Icon */}
        {(state.loading || switching) ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : isLive ? (
          <ShieldOff className="h-3.5 w-3.5" />
        ) : (
          <ShieldCheck className="h-3.5 w-3.5" />
        )}

        {/* Label */}
        <span className="tracking-wide">
          {state.loading || switching ? '…' : isLive ? 'LIVE' : 'PAPER'}
        </span>

        {/* Pulsing dot only in LIVE mode */}
        {isLive && !switching && (
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-70" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" />
          </span>
        )}
      </button>

      {/* ── Confirmation modal ────────────────────────────────────────────── */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setShowConfirm(false)}
          />

          {/* Dialog */}
          <div className="relative z-10 w-full max-w-sm rounded-2xl border border-red-500/30 bg-[#0d1117] p-6 shadow-2xl shadow-red-900/20">
            {/* Glow */}
            <div className="pointer-events-none absolute inset-0 rounded-2xl bg-red-500/[0.04]" />

            <div className="flex flex-col items-center text-center gap-4">
              {/* Warning icon */}
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-500/10 ring-1 ring-red-500/30">
                <AlertTriangle className="h-7 w-7 text-red-400" />
              </div>

              <div>
                <h3 className="text-base font-semibold text-slate-100 tracking-tight">
                  ¿Activar LIVE TRADING?
                </h3>
                <p className="mt-2 text-sm text-slate-400 leading-relaxed">
                  Las siguientes órdenes serán ejecutadas con{' '}
                  <span className="text-red-400 font-medium">fondos reales</span> en Binance.
                  El bot operará con un riesgo del{' '}
                  <span className="text-amber-400 font-medium">1% por trade</span>.
                </p>
              </div>

              {/* Warning list */}
              <ul className="w-full rounded-xl bg-red-500/[0.06] border border-red-500/20 px-4 py-3 text-left text-xs text-slate-400 space-y-1.5">
                {[
                  'Las órdenes se ejecutan automáticamente cada hora',
                  'Utiliza el kill-switch para detener en emergencias',
                  'Verifica que BINANCE_API_KEY está configurada',
                ].map(t => (
                  <li key={t} className="flex items-start gap-2">
                    <span className="mt-0.5 text-red-500">▸</span>
                    {t}
                  </li>
                ))}
              </ul>

              {/* Buttons */}
              <div className="flex w-full gap-3 pt-1">
                <button
                  onClick={() => setShowConfirm(false)}
                  className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:bg-white/[0.08]"
                >
                  Cancelar
                </button>
                <button
                  onClick={doSwitch}
                  className="flex-1 rounded-xl bg-red-500/80 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-red-500 active:scale-95"
                >
                  Activar LIVE
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
