import darkLogo from '@/assets/dark.svg'
import lightLogo from '@/assets/ligth.svg'
import { Positions } from '@/components/positions'
import { ToggleTheme } from '@/components/toogleThema'
import { Trade } from '@/components/trade'
import { Separator } from '@/components/ui/separator'
import { Toaster } from '@/components/ui/sonner'
import { usePersistState } from '@/hooks/usePersistState'

type PersistedLots = {
  lot1: number
  lot2: number
  lot3: number
  lot4: number
  lot5: number
}

const DEFAULT_LOTS: PersistedLots = {
  lot1: 0.01,
  lot2: 0.02,
  lot3: 0.04,
  lot4: 0.06,
  lot5: 0.08
}

export function Layout() {
  const [persistedLots, setPersistedLots] = usePersistState<PersistedLots>('trade-default-values', DEFAULT_LOTS)

  return (
    <main className="grid h-screen grid-cols-1 grid-rows-[auto_1fr] overflow-hidden">
      <Toaster />
      <header className="border-border bg-secondary/10 relative z-10 flex items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-1">
          <h1 className="font-russo bg-linear-to-r from-cyan-500 via-blue-500 to-emerald-500 bg-clip-text text-2xl font-semibold text-transparent dark:from-cyan-300 dark:via-blue-300 dark:to-green-300">
            Panel
          </h1>
        </div>
        <ToggleTheme />
      </header>
      <section className="grid min-h-0 w-full grid-cols-[auto_1fr] gap-2 overflow-hidden p-2">
        <div className="flex w-full max-w-56 flex-col gap-4 overflow-hidden py-2">
          <Trade defaultValue={persistedLots.lot1} onDefaultValueChange={value => setPersistedLots(prev => ({ ...prev, lot1: value }))} />
          <Separator className="bg-slate-400" />
          <Trade defaultValue={persistedLots.lot2} onDefaultValueChange={value => setPersistedLots(prev => ({ ...prev, lot2: value }))} />
          <Separator className="bg-slate-400" />
          <Trade defaultValue={persistedLots.lot3} onDefaultValueChange={value => setPersistedLots(prev => ({ ...prev, lot3: value }))} />
          <Separator className="bg-slate-400" />
          <Trade defaultValue={persistedLots.lot4} onDefaultValueChange={value => setPersistedLots(prev => ({ ...prev, lot4: value }))} />
          <Separator className="bg-slate-400" />
          <Trade defaultValue={persistedLots.lot5} onDefaultValueChange={value => setPersistedLots(prev => ({ ...prev, lot5: value }))} />
        </div>
        <div className="relative h-full min-h-0 w-full overflow-hidden py-2">
          <img src={lightLogo} alt="" aria-hidden="true" className="pointer-events-none absolute inset-0 z-0 m-auto h-[80vh] w-auto opacity-40 select-none dark:hidden" />
          <img src={darkLogo} alt="" aria-hidden="true" className="pointer-events-none absolute inset-0 z-0 m-auto hidden h-[80vh] w-auto opacity-30 select-none dark:block" />

          <div className="relative z-10 h-full min-h-0">
            <Positions />
          </div>
        </div>
      </section>
    </main>
  )
}
