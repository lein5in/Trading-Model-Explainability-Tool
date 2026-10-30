import { TRADES_PER_PAGE } from '../config.js'

export const TRADE_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'long', label: 'Long' },
  { value: 'short', label: 'Short' },
  { value: 'winners', label: 'Winners' },
  { value: 'losers', label: 'Losers' },
]

export function filterTrades(trades, filter) {
  const list = Array.isArray(trades) ? trades : []
  if (filter === 'long') return list.filter((trade) => trade.side === 'long')
  if (filter === 'short') return list.filter((trade) => trade.side === 'short')
  if (filter === 'winners') return list.filter((trade) => trade.pnl > 0)
  if (filter === 'losers') return list.filter((trade) => trade.pnl < 0)
  return list
}

export function paginate(list, page, perPage = TRADES_PER_PAGE) {
  const total = list.length
  const pageCount = Math.max(1, Math.ceil(total / perPage))
  const current = Math.min(Math.max(1, Math.floor(page) || 1), pageCount)
  const startIndex = (current - 1) * perPage
  const items = list.slice(startIndex, startIndex + perPage)
  return {
    items,
    page: current,
    pageCount,
    total,
    from: total ? startIndex + 1 : 0,
    to: startIndex + items.length,
    hasPrevious: current > 1,
    hasNext: current < pageCount,
  }
}
