'use client'

import { useState, useRef, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'

export interface Asset {
  symbol:  string   // e.g. "BTCUSDT"
  label:   string   // e.g. "BTC"
  name:    string   // e.g. "Bitcoin"
  color:   string   // Tailwind text color
  border:  string   // Tailwind border color
  bg:      string   // Tailwind bg color
}

export const ASSETS: Asset[] = [
  { symbol: 'BTCUSDT', label: 'BTC', name: 'Bitcoin',  color: 'text-amber-400',   border: 'border-amber-500/30',   bg: 'bg-amber-500/10'   },
  { symbol: 'ETHUSDT', label: 'ETH', name: 'Ethereum', color: 'text-indigo-400',  border: 'border-indigo-500/30',  bg: 'bg-indigo-500/10'  },
  { symbol: 'SOLUSDT', label: 'SOL', name: 'Solana',   color: 'text-purple-400',  border: 'border-purple-500/30',  bg: 'bg-purple-500/10'  },
]

interface Props {
  value:    string
  onChange: (symbol: string) => void
}

export function SymbolSelector({ value, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const ref             = useRef<HTMLDivElement>(null)
  const current         = ASSETS.find(a => a.symbol === value) ?? ASSETS[0]

  // Cerrar al hacer click fuera
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className={`
          flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold
          border transition-all duration-200
          ${current.bg} ${current.border} ${current.color}
          hover:opacity-90 active:scale-95
        `}
      >
        <span className="font-mono tracking-wide">{current.label}</span>
        <span className="text-[10px] font-normal text-slate-500 hidden sm:inline">{current.name}</span>
        <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 z-50 w-44 rounded-xl border border-white/[0.08] bg-[#0d1117] shadow-2xl overflow-hidden">
          {ASSETS.map(asset => (
            <button
              key={asset.symbol}
              onClick={() => { onChange(asset.symbol); setOpen(false) }}
              className={`
                w-full flex items-center gap-3 px-4 py-3 text-left transition-colors
                hover:bg-white/[0.05]
                ${asset.symbol === value ? 'bg-white/[0.03]' : ''}
              `}
            >
              <span className={`text-sm font-semibold font-mono ${asset.color}`}>{asset.label}</span>
              <span className="text-xs text-slate-500">{asset.name}</span>
              {asset.symbol === value && (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-cyan-400" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
