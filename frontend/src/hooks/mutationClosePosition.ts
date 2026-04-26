import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import type { CloseCommandResult, ClosePositionPayload } from '@/types/close'

async function submitClosePosition(payload: ClosePositionPayload): Promise<CloseCommandResult> {
  if (!window.pywebview?.api?.close_position) {
    return { ok: false, error: 'pywebview_api_unavailable', message: 'PyWebView API indisponivel' }
  }

  try {
    return await window.pywebview.api.close_position(payload)
  } catch {
    return { ok: false, error: 'close_position_failed', message: 'Falha ao enviar close position' }
  }
}

export function useMutationClosePosition(): UseMutationResult<CloseCommandResult, never, ClosePositionPayload> {
  const queryClient = useQueryClient()

  return useMutation<CloseCommandResult, never, ClosePositionPayload>({
    mutationFn: submitClosePosition,
    onSuccess: async result => {
      if (result.ok) {
        await queryClient.invalidateQueries({ queryKey: ['positions'] })
      }
    }
  })
}
