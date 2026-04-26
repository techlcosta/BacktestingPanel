export type TradeSide = 'buy' | 'sell'

export interface TradePayload {
  type: TradeSide
  symbol?: string
  volume: number
  sl?: number
  tp?: number
  comment?: string
  deviation?: number
}

export interface TradeResult {
  ok: boolean
  error?: string
  message?: string
}
