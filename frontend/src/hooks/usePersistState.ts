import { useEffect, useState, type Dispatch, type SetStateAction } from 'react'

type PersistStateResponse<T> = [T, Dispatch<SetStateAction<T>>]

export function usePersistState<T>(key: string, initialState: T): PersistStateResponse<T> {
  const [state, setState] = useState<T>(() => {
    if (typeof window === 'undefined') {
      return initialState
    }

    const storageValue = window.localStorage.getItem(key)
    if (!storageValue) {
      return initialState
    }

    try {
      return JSON.parse(storageValue) as T
    } catch {
      return initialState
    }
  })

  useEffect(() => {
    window.localStorage.setItem(key, JSON.stringify(state))
  }, [key, state])

  return [state, setState]
}
