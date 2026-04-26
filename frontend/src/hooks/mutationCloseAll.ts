import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'

import type { CloseAllPayload, CloseCommandResult } from '@/types/close'

async function submitCloseAll(payload?: CloseAllPayload): Promise<CloseCommandResult> {
  if (!window.pywebview?.api?.close_all) {
    return { ok: false, error: 'pywebview_api_unavailable', message: 'PyWebView API indisponivel' }
  }

  try {
    return await window.pywebview.api.close_all(payload ?? {})
  } catch {
    return { ok: false, error: 'close_all_failed', message: 'Falha ao enviar close all' }
  }
}

export function useMutationCloseAll(): UseMutationResult<CloseCommandResult, never, CloseAllPayload | undefined> {
  const queryClient = useQueryClient()

  return useMutation<CloseCommandResult, never, CloseAllPayload | undefined>({
    mutationFn: submitCloseAll,
    onSuccess: async result => {
      if (result.ok) {
        await queryClient.invalidateQueries({ queryKey: ['positions'] })
      }
    }
  })
}
