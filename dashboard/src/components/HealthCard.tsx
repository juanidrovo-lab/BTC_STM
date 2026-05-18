'use client'

import { GlassCard } from './GlassCard'
import { Server, CheckCircle2, Circle, AlertTriangle, RefreshCw } from 'lucide-react'
import { useEffect, useState, useCallback } from 'react'

interface HealthData {
  status:              string
  service:             string
  version:             string
  python:              string
  trading_mode:        string
  persistence_backend: string
  db_configured:       boolean
  loop_running:        boolean
}

const accentMap: Record<string, string> = {
  emerald: 'text-emerald-400',
  cyan:    'text-cyan-400',
  amber:   'text-amber-400',
  red:     'text-red-400',
}

export function HealthCard() {
  const [data,    setData]    = useState<HealthData | null>(null)
  const [pingMs,  setPingMs]  = useState<number | null>(null)
  const [error,   setError]   = useState(false)
  const [loading, setLoading] = useState(true)

  const fetchHealth = useCallback(async () => {
    const t0 = performance.now()
    try {
      const res = await fetch('/api/health')
      const ms  = Math.round(performance.now() - t0)
      if (!res.ok) throw new Error()
      const json: HealthData = await res.json()
      setData(json)
      setPingMs(ms)
      setError(false)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    const id = setInterval(fetchHealth, 30_000)
    return () => clearInterval(id)
  }, [fetchHealth])

  const modeLabel = (m: string) => m === 'paper' ? 'DEMO' : m.toUpperCase()

  const metrics = data ? [
    { label: 'Estado',      value: data.status === 'ok' ? 'Operativo' : 'Error',         accent: data.status === 'ok' ? 'emerald' : 'red' },
    { label: 'Servicio',    value: data.service,                                           accent: 'cyan'    },
    { label: 'Versión',     value: data.version,                                           accent: undefined },
    { label: 'Python',      value: data.python,                                            accent: undefined },
    { label: 'Modo',        value: modeLabel(data.trading_mode),                           accent: 'amber'   },
    { label: 'Persistencia',value: data.persistence_backend.toUpperCase(),                 accent: 'cyan'    },
    { label: 'Base de Datos',value: data.db_configured ? 'Conectado' : 'Desconectado',    accent: data.db_configured ? 'emerald' : 'red' },
    { label: 'Loop Activo', value: data.loop_running   ? 'Corriendo'  : 'Detenido',       accent: data.loop_running   ? 'emerald' : 'amber' },
  ] : []

  const healthy = !error && data?.status === 'ok'

  return (
    <GlassCard glow="emerald" padding={false} className="flex flex-col">
      <div className="flex items-center justify-between p-6 pb-4">
        <div>
          <p className="label-xs mb-1.5">Estado del Sistema</p>
          <div className="flex items-center gap-2">
            {loading ? (
              <RefreshCw className="h-4 w-4 text-slate-500 animate-spin" />
            ) : healthy ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-red-400" />
            )}
            <h2 className="text-lg font-medium text-slate-100">
              {loading ? 'Verificando…' : healthy ? 'Todo Operativo' : 'Degradado'}
            </h2>
          </div>
        </div>
        <button
          onClick={fetchHealth}
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 ring-1 ring-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
          title="Actualizar"
        >
          <Server className="h-5 w-5 text-emerald-400" />
        </button>
      </div>

      <div className="mx-6 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />

      <div className="flex-1 divide-y divide-white/[0.04] px-2 py-2 overflow-auto">
        {loading && metrics.length === 0 ? (
          <div className="flex items-center justify-center h-full text-xs text-slate-600 py-8">
            Consultando /api/health…
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full text-xs text-red-400 py-8">
            API no disponible
          </div>
        ) : (
          metrics.map(({ label, value, accent }) => (
            <div
              key={label}
              className="flex items-center justify-between px-4 py-2.5 rounded-lg hover:bg-white/[0.03] transition-colors duration-150"
            >
              <span className="label-xs">{label}</span>
              <div className="flex items-center gap-2">
                {accent === 'emerald' && (
                  <Circle className="h-2 w-2 fill-emerald-400 text-emerald-400 animate-pulse" />
                )}
                {accent === 'red' && (
                  <Circle className="h-2 w-2 fill-red-400 text-red-400" />
                )}
                <span className={`text-xs font-mono font-medium ${accent ? accentMap[accent] : 'text-slate-300'}`}>
                  {value}
                </span>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="border-t border-white/[0.06] px-6 py-3 flex items-center justify-between">
        <span className="label-xs">Última consulta</span>
        <span className="text-xs font-mono text-slate-500">
          {pingMs !== null ? `${pingMs} ms · Neon IAD1` : '—'}
        </span>
      </div>
    </GlassCard>
  )
}
