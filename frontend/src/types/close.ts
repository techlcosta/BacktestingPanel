export interface CloseAllPayload {
  symbol?: string
}

export interface ClosePositionPayload {
  ticket?: number | string
  symbol?: string
}

export interface CloseCommandResult {
  ok: boolean
  error?: string
  message?: string
}
