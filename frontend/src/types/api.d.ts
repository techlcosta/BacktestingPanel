import type { Position } from './position'
import type { CloseAllPayload, CloseCommandResult, ClosePositionPayload } from './close'
import type { TradePayload, TradeResult } from './trade'

interface API {
  positions: () => Promise<Position[]>
  trade: (payload: TradePayload) => Promise<TradeResult>
  close_all: (payload?: CloseAllPayload) => Promise<CloseCommandResult>
  close_position: (payload: ClosePositionPayload) => Promise<CloseCommandResult>
}

declare global {
  interface Window {
    pywebview: {
      api: API
    }
  }
}
