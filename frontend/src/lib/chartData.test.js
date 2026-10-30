import { describe, expect, it } from 'vitest'
import {
  drawdownSeries,
  equitySeries,
  monthlyReturns,
  ohlcSlice,
  regimeProbabilityRows,
  regimeShading,
  tradeReturnHistogram,
  tradeWindow,
  volumeAtPrice,
} from './chartData.js'

const curve = [
  { date: '2024-01-30', equity: 100 },
  { date: '2024-01-31', equity: 110 },
  { date: '2024-02-01', equity: 99 },
  { date: '2024-02-29', equity: 121 },
  { date: '2024-03-01', equity: null },
  { date: '2024-03-04', equity: 108.9 },
]

describe('equity and drawdown adapters', () => {
  it('keeps finite points with business-day times', () => {
    expect(equitySeries(curve)).toEqual([
      { time: '2024-01-30', value: 100 },
      { time: '2024-01-31', value: 110 },
      { time: '2024-02-01', value: 99 },
      { time: '2024-02-29', value: 121 },
      { time: '2024-03-04', value: 108.9 },
    ])
    expect(equitySeries(null)).toEqual([])
  })

  it('computes drawdown from the running peak', () => {
    const values = drawdownSeries(curve).map((point) => point.value)
    expect(values[0]).toBe(0)
    expect(values[1]).toBe(0)
    expect(values[2]).toBeCloseTo(-0.1, 12)
    expect(values[3]).toBe(0)
    expect(values[4]).toBeCloseTo(-0.1, 12)
  })

  it('computes month-end to month-end returns, the first month from the first value', () => {
    const months = monthlyReturns(curve)
    expect(months.map((point) => point.time)).toEqual(['2024-01-31', '2024-02-29', '2024-03-04'])
    expect(months[0].value).toBeCloseTo(0.1, 12)
    expect(months[1].value).toBeCloseTo(0.1, 12)
    expect(months[2].value).toBeCloseTo(-0.1, 12)
    expect(monthlyReturns(curve.slice(0, 1))).toEqual([])
  })
})

describe('trade return histogram', () => {
  it('uses nice bins and counts every trade once', () => {
    const trades = [-0.05, -0.031, -0.01, 0, 0.004, 0.019, 0.02, 0.07].map((value) => ({ return: value }))
    const bins = tradeReturnHistogram(trades, 8)
    expect(bins[0].from).toBeCloseTo(-0.06, 12)
    expect(bins.at(-1).to).toBeCloseTo(0.08, 12)
    expect(bins).toHaveLength(7)
    expect(bins.reduce((sum, bin) => sum + bin.count, 0)).toBe(trades.length)
    const bin = bins.find((item) => Math.abs(item.from) < 1e-12)
    expect(bin.count).toBe(3)
  })

  it('handles a single value and empty input', () => {
    expect(tradeReturnHistogram([{ return: 0.01 }])).toHaveLength(1)
    expect(tradeReturnHistogram([{ return: null }])).toEqual([])
  })
})

describe('regime builders', () => {
  it('maps filtered probabilities to three rows, brighter when more likely', () => {
    const rows = regimeProbabilityRows(['2024-01-02', '2024-01-03'], [null, [1, 0, 0]])
    expect(rows).toHaveLength(3)
    expect(rows[0][0]).toEqual({ time: '2024-01-02' })
    expect(rows[0][1]).toEqual({ time: '2024-01-03', value: 1, color: 'rgba(76, 141, 246, 0.98)' })
    expect(rows[1][1]).toEqual({ time: '2024-01-03', value: 2, color: 'rgba(155, 123, 240, 0.06)' })
    expect(rows[2][1].value).toBe(3)
  })

  it('shades each bar with its regime color and leaves unlabeled bars empty', () => {
    const shading = regimeShading(['2024-01-02', '2024-01-03'], [null, 'High vol'])
    expect(shading).toEqual([{ time: '2024-01-02' }, { time: '2024-01-03', value: 1, color: 'rgba(240, 138, 60, 0.16)' }])
  })
})

describe('trade window and volume at price', () => {
  const bars = {
    date: ['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05'],
    open: [10, 11, 12, 13],
    high: [12, 12, 14, 14],
    low: [10, 10, 12, 12],
    close: [11, 10.5, 13, 12.5],
    volume: [100, 200, 300, 400],
  }

  it('clamps the window around the trade', () => {
    expect(tradeWindow(4, { signal_bar_index: 1, entry_bar_index: 2, exit_bar_index: 3 }, 5, 5)).toEqual({ start: 0, end: 3 })
    expect(tradeWindow(100, { signal_bar_index: 49, entry_bar_index: 50, exit_bar_index: 60 }, 20, 10)).toEqual({ start: 29, end: 70 })
  })

  it('slices OHLCV bars', () => {
    const slice = ohlcSlice(bars, { start: 1, end: 2 })
    expect(slice.map((bar) => bar.index)).toEqual([1, 2])
    expect(slice[0]).toMatchObject({ time: '2024-01-03', open: 11, close: 10.5, volume: 200 })
  })

  it('spreads each bar volume over the bins its range covers, split up and down', () => {
    const profile = volumeAtPrice(ohlcSlice(bars, { start: 0, end: 3 }), 4)
    expect(profile.low).toBe(10)
    expect(profile.high).toBe(14)
    const total = profile.bins.reduce((sum, bin) => sum + bin.total, 0)
    expect(total).toBeCloseTo(1000, 9)
    expect(profile.bins[0].up).toBeCloseTo(50, 9)
    expect(profile.bins[0].down).toBeCloseTo(100, 9)
    expect(profile.bins[3].up).toBeCloseTo(150, 9)
    expect(profile.bins[3].down).toBeCloseTo(200, 9)
    expect(profile.cells.filter((cell) => cell.offset === 2).map((cell) => cell.bin)).toEqual([2, 3])
    expect(profile.maxBin).toBeCloseTo(350, 9)
  })

  it('returns null without valid bars', () => {
    expect(volumeAtPrice([])).toBeNull()
  })
})
