import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import type { TradePayload, TradeResult } from '@/types/trade'

async function submitTrade(payload: TradePayload): Promise<TradeResult> {
  if (!window.pywebview?.api?.trade) {
    return { ok: false, error: 'pywebview_api_unavailable', message: 'PyWebView API indisponivel' }
  }

  try {
    return await window.pywebview.api.trade(payload)
  } catch {
    return { ok: false, error: 'trade_failed', message: 'Falha ao enviar comando de trade' }
  }
}

export function useMutationTrade(): UseMutationResult<TradeResult, never, TradePayload> {
  const queryClient = useQueryClient()

  return useMutation<TradeResult, never, TradePayload>({
    mutationFn: submitTrade,
    onSuccess: async result => {
      if (result.ok) {
        await queryClient.invalidateQueries({ queryKey: ['positions'] })
      }
    }
  })
}
