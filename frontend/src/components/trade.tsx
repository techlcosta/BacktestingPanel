import { useState } from 'react'

import { useMutationTrade } from '@/hooks/mutationTrade'
import { toast } from 'sonner'

import { LotSize } from './lotSize'
import { Button } from './ui/button'

interface TradeProps {
  defaultValue: number
  onDefaultValueChange?: (nextValue: number) => void
}

export function Trade({ defaultValue, onDefaultValueChange }: TradeProps) {
  const [volume, setVolume] = useState<number>(defaultValue)
  const tradeMutation = useMutationTrade()

  function handleLotSizeChange(nextValue: number) {
    setVolume(nextValue)
    onDefaultValueChange?.(nextValue)
  }

  async function handleBuy() {
    const result = await tradeMutation.mutateAsync({ type: 'buy', volume })
    if (result.ok) {
      toast.success(`Buy sent (${volume.toFixed(2)} lot)`)
      return
    }

    toast.error(resolveTradeMessage(result.message, result.error, 'buy'))
  }

  async function handleSell() {
    const result = await tradeMutation.mutateAsync({ type: 'sell', volume })
    if (result.ok) {
      toast.success(`Sell sent (${volume.toFixed(2)} lot)`)
      return
    }

    toast.error(resolveTradeMessage(result.message, result.error, 'sell'))
  }

  return (
    <div className="flex w-full flex-col">
      <LotSize value={volume} onValueChange={handleLotSizeChange} />
      <div className="grid h-12 grid-cols-2">
        <Button disabled={tradeMutation.isPending} onClick={() => void handleBuy()} className="h-full w-full cursor-pointer rounded-xs bg-blue-500 text-white hover:bg-blue-700">
          BUY
        </Button>
        <Button disabled={tradeMutation.isPending} onClick={() => void handleSell()} className="h-full w-full cursor-pointer rounded-xs bg-red-500 text-white hover:bg-red-700">
          SELL
        </Button>
      </div>
    </div>
  )
}

function resolveTradeMessage(message: string | undefined, error: string | undefined, side: 'buy' | 'sell'): string {
  const prefix = side === 'buy' ? 'Error to send BUY' : 'Error to send SELL'
  if (message && message.trim() !== '') {
    return `${prefix}: ${message}`.replace(/=/g, ' ').replace(/;/g, ' | ')
  }
  if (error && error.trim() !== '') {
    return `${prefix}: ${error}`.replace(/=/g, ' ').replace(/;/g, ' | ')
  }
  return prefix
}
