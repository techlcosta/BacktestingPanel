export interface Position {
  id: string
  lot: number
  symbol: string
  profit: number
  type: 'SELL' | 'BUY'
}
