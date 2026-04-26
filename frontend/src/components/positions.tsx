import { useMutationCloseAll } from '@/hooks/mutationCloseAll'
import { useMutationClosePosition } from '@/hooks/mutationClosePosition'
import { useGetPositions } from '@/hooks/useGetPositions'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { Button } from './ui/button'
import { X } from 'lucide-react'

export function Positions() {
  const { data } = useGetPositions()
  const closeAllMutation = useMutationCloseAll()
  const closePositionMutation = useMutationClosePosition()

  async function handleClosePosition(ticket: string, symbol: string) {
    const normalizedTicket = ticket.trim()
    if (normalizedTicket !== '') {
      const result = await closePositionMutation.mutateAsync({ ticket: normalizedTicket })
      if (result.ok) {
        toast.success(formatSuccessMessage(`${result.message} closed`, 'Position closed'))
      } else {
        toast.error(resolveCloseMessage(result.message, result.error?.replace(/=/g, ' ').replace(/;/g, ' | '), 'position'))
      }
      return
    }

    if (symbol.trim() !== '') {
      const result = await closePositionMutation.mutateAsync({ symbol: symbol.trim() })
      if (result.ok) {
        toast.success(formatSuccessMessage(result.message, 'Position closed'))
      } else {
        toast.error(resolveCloseMessage(result.message, result.error?.replace(/=/g, ' ').replace(/;/g, ' | '), 'position'))
      }
    }
  }

  async function handleCloseAll() {
    const result = await closeAllMutation.mutateAsync(undefined)
    if (result.ok) {
      toast.success('All positions closed')
      return
    }
    toast.error(resolveCloseMessage(result.message, result.error?.replace(/=/g, ' ').replace(/;/g, ' | '), 'all'))
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="bg-card/70 border-border flex min-h-0 flex-1 flex-col overflow-hidden rounded border">
        <div className="min-h-0 flex-1 overflow-x-auto overflow-y-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-secondary text-muted-foreground">
                <th className="px-2 py-1.5 text-left font-semibold">#</th>
                <th className="px-2 py-1.5 text-left font-semibold">Type</th>
                <th className="px-2 py-1.5 text-right font-semibold">Lots</th>
                <th className="px-2 py-1.5 text-right font-semibold">Profit</th>
                <th className="px-2 py-1.5"></th>
              </tr>
            </thead>
            <tbody>
              {data && data.length > 0 ? (
                data.map(pos => (
                  <tr key={pos.id} className="border-border hover:bg-accent/50 border-t transition-colors">
                    <td className="text-muted-foreground px-2 py-1.5 font-mono">{pos.id}</td>

                    <td className="px-2 py-1.5">
                      <span className={cn('font-semibold', pos.type === 'BUY' ? 'text-blue-500' : 'text-red-500')}>{pos.type}</span>
                    </td>
                    <td className="text-foreground px-2 py-1.5 text-right font-mono">{pos.lot.toFixed(2)}</td>

                    <td className={cn('px-2 py-1.5 text-right font-mono font-bold', pos.profit >= 0 ? 'text-blue-500' : 'text-red-500')}>
                      {pos.profit >= 0 ? '+' : ''}
                      {pos.profit.toFixed(2)}
                    </td>

                    <td className="px-2 py-1.5">
                      <Button
                        size="icon-xs"
                        variant="destructive"
                        disabled={closeAllMutation.isPending || closePositionMutation.isPending}
                        onClick={() => void handleClosePosition(pos.id, pos.symbol)}
                        className="cursor-pointer rounded-full font-semibold transition-colors"
                      >
                        <X />
                      </Button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr className="border-border hover:bg-accent/50 border-t transition-colors">
                  <td className="text-muted-foreground px-2 py-1.5 font-mono" colSpan={5}>
                    No Positions
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <Button
        size="lg"
        variant="destructive"
        className="cursor-pointer rounded-xs"
        disabled={closeAllMutation.isPending || closePositionMutation.isPending}
        onClick={() => void handleCloseAll()}
      >
        {closeAllMutation.isPending ? 'Closing...' : 'Close All'}
      </Button>
    </div>
  )
}

function resolveCloseMessage(message: string | undefined, error: string | undefined, mode: 'position' | 'all'): string {
  const prefix = mode === 'all' ? 'Error to close all' : 'Error to close position'
  if (message && message.trim() !== '') {
    return `${prefix}: ${message}`
  }
  if (error && error.trim() !== '') {
    return `${prefix}: ${error}`
  }
  return prefix
}

function formatSuccessMessage(message: string | undefined, fallback: string): string {
  const normalized = message?.trim()
  if (!normalized) {
    return fallback
  }
  return normalized.replace(/=/g, ' ').replace(/;/g, ' | ')
}
