import { cn } from '@/lib/utils'
import { ReactNode } from 'react'

type GlowVariant = 'cyan' | 'emerald' | 'none'

interface GlassCardProps {
  children: ReactNode
  className?: string
  glow?: GlowVariant
  padding?: boolean
  as?: 'div' | 'section' | 'article'
}

const glowClasses: Record<GlowVariant, string> = {
  cyan:    'hover:shadow-[0_8px_48px_rgba(0,0,0,0.55),0_0_40px_rgba(6,182,212,0.13)] hover:border-cyan-500/[0.18]',
  emerald: 'hover:shadow-[0_8px_48px_rgba(0,0,0,0.55),0_0_40px_rgba(16,185,129,0.13)] hover:border-emerald-500/[0.18]',
  none:    'hover:shadow-[0_8px_48px_rgba(0,0,0,0.55)]',
}

export function GlassCard({
  children,
  className,
  glow = 'none',
  padding = true,
  as: Tag = 'div',
}: GlassCardProps) {
  return (
    <Tag
      className={cn(
        'relative overflow-hidden rounded-2xl',
        'bg-slate-900/60 backdrop-blur-md',
        'border border-white/[0.08]',
        'shadow-[0_4px_32px_rgba(0,0,0,0.45),inset_0_1px_0_rgba(255,255,255,0.06)]',
        'transition-all duration-300 ease-out',
        glowClasses[glow],
        padding && 'p-6',
        'h-full',
        className,
      )}
    >
      {/* Glass top highlight — refractive edge */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.14] to-transparent"
      />
      {children}
    </Tag>
  )
}
