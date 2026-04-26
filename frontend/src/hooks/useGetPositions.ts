import type { Position } from '@/types/position'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

export function useGetPositions(): UseQueryResult<Position[], Error> {
  const [isReady, setIsReady] = useState(false)

  useEffect(() => {
    function checkReady() {
      if (window.pywebview?.api) setIsReady(true)
    }

    checkReady()
    window.addEventListener('pywebviewready', checkReady)

    return () => {
      window.removeEventListener('pywebviewready', checkReady)
    }
  }, [])

  return useQuery<Position[], Error>({
    queryKey: ['positions'],
    queryFn: async (): Promise<Position[]> => {
      return await window.pywebview.api.positions()
    },
    refetchInterval: 500,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    staleTime: 0,
    retry: 3,
    gcTime: 0,
    enabled: isReady,
    notifyOnChangeProps: ['data', 'dataUpdatedAt', 'error']
  })
}
