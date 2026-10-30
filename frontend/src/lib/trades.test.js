import { describe, expect, it } from 'vitest'
import { filterTrades, paginate } from './trades.js'

const trades = Array.from({ length: 30 }, (unused, index) => ({
  id: index + 1,
  side: index % 2 === 0 ? 'long' : 'short',
  pnl: index % 3 === 0 ? -1 : index % 3 === 1 ? 2 : 0,
}))

describe('trade filters', () => {
  it('filters by side and by outcome', () => {
    expect(filterTrades(trades, 'all')).toHaveLength(30)
    expect(filterTrades(trades, 'long').every((trade) => trade.side === 'long')).toBe(true)
    expect(filterTrades(trades, 'short')).toHaveLength(15)
    expect(filterTrades(trades, 'winners').every((trade) => trade.pnl > 0)).toBe(true)
    expect(filterTrades(trades, 'losers')).toHaveLength(10)
    expect(filterTrades(null, 'all')).toEqual([])
  })
})

describe('pagination', () => {
  it('splits into pages of 12', () => {
    const first = paginate(trades, 1)
    expect(first).toMatchObject({ page: 1, pageCount: 3, total: 30, from: 1, to: 12, hasPrevious: false, hasNext: true })
    const last = paginate(trades, 3)
    expect(last.items.map((trade) => trade.id)).toEqual([25, 26, 27, 28, 29, 30])
    expect(last).toMatchObject({ from: 25, to: 30, hasNext: false })
  })

  it('clamps out-of-range pages and handles empty lists', () => {
    expect(paginate(trades, 99).page).toBe(3)
    expect(paginate(trades, 0).page).toBe(1)
    expect(paginate([], 1)).toMatchObject({ page: 1, pageCount: 1, from: 0, to: 0, items: [] })
  })
})
