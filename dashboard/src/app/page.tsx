import { Header }        from '@/components/Header'
import { ActivityChart } from '@/components/ActivityChart'
import { HealthCard }    from '@/components/HealthCard'
import { KPICard }       from '@/components/KPICard'
import { ConsoleCard }   from '@/components/ConsoleCard'
import { ControlCard }   from '@/components/ControlCard'

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-[#070a13] text-slate-100">
      {/* ── Ambient background orbs ──────────────────────────────────────── */}
      <div aria-hidden className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-48 -left-48 h-[700px] w-[700px] rounded-full bg-cyan-500/[0.07] blur-[120px]" />
        <div className="absolute top-1/3 -right-48 h-[500px] w-[500px] rounded-full bg-cyan-400/[0.05] blur-[100px]" />
        <div className="absolute -bottom-24 left-1/4  h-[500px] w-[500px] rounded-full bg-emerald-500/[0.06] blur-[120px]" />
        <div className="absolute bottom-1/3 right-1/4 h-[300px] w-[300px] rounded-full bg-cyan-300/[0.04] blur-[80px]" />
      </div>

      <Header />

      <main className="relative mx-auto max-w-[1600px] px-4 sm:px-6 lg:px-8 pt-6 pb-12">
        {/* Page title */}
        <div className="mb-6 animate-fade-in">
          <h1 className="text-2xl font-light tracking-tight text-slate-100">
            Trading <span className="text-cyan-400">Dashboard</span>
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Paper trading engine · Real-time monitoring · Neon DB
          </p>
        </div>

        {/* ── Bento Grid ────────────────────────────────────────────────── */}
        <div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4"
          style={{ gridAutoRows: '200px' }}
        >
          {/* Activity Chart — 4 col × 2 row */}
          <div className="col-span-1 sm:col-span-2 lg:col-span-4 row-span-1 lg:row-span-2 animate-slide-up" style={{ animationDelay: '0ms' }}>
            <ActivityChart />
          </div>

          {/* Health — 2 col × 2 row */}
          <div className="col-span-1 sm:col-span-2 lg:col-span-2 row-span-1 lg:row-span-2 animate-slide-up" style={{ animationDelay: '80ms' }}>
            <HealthCard />
          </div>

          {/* KPIs — 2 col × 2 row */}
          <div className="col-span-1 sm:col-span-1 lg:col-span-2 row-span-1 lg:row-span-2 animate-slide-up" style={{ animationDelay: '160ms' }}>
            <KPICard />
          </div>

          {/* Console — 2 col × 2 row */}
          <div className="col-span-1 sm:col-span-1 lg:col-span-2 row-span-1 lg:row-span-2 animate-slide-up" style={{ animationDelay: '240ms' }}>
            <ConsoleCard />
          </div>

          {/* Control — 2 col × 2 row */}
          <div className="col-span-1 sm:col-span-2 lg:col-span-2 row-span-1 lg:row-span-2 animate-slide-up" style={{ animationDelay: '320ms' }}>
            <ControlCard />
          </div>
        </div>
      </main>
    </div>
  )
}
