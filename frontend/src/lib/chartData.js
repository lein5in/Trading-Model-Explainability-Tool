import { isNumber } from './format.js'
import { REGIME_HEX, REGIME_NAMES, hexToRgba } from './regimes.js'

export function toTime(date) {
  return typeof date === 'string' ? date.slice(0, 10) : null
}

export function equitySeries(curve) {
  if (!Array.isArray(curve)) return []
  return curve.filter((point) => toTime(point?.date) && isNumber(point.equity)).map((point) => ({ time: toTime(point.date), value: point.equity }))
}

export function drawdownSeries(curve) {
  const points = equitySeries(curve)
  let peak = null
  return points.map((point) => {
    peak = peak === null ? point.value : Math.max(peak, point.value)
    return { time: point.time, value: peak > 0 ? point.value / peak - 1 : 0 }
  })
}

export function monthlyReturns(curve) {
  const points = equitySeries(curve)
  if (points.length < 2) return []
  const monthEnds = []
  for (let index = 0; index < points.length; index += 1) {
    const month = points[index].time.slice(0, 7)
    const next = points[index + 1]
    if (!next || next.time.slice(0, 7) !== month) monthEnds.push(points[index])
  }
  let previous = points[0].value
  return monthEnds.map((point) => {
    const value = previous > 0 ? point.value / previous - 1 : 0
    previous = point.value
    return { time: point.time, value }
  })
}

const NICE_STEPS = [0.001, 0.0025, 0.005, 0.01, 0.02, 0.025, 0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 5]

function roundStep(value) {
  return Math.round(value * 1e9) / 1e9
}

export function tradeReturnHistogram(trades, maxBins = 8) {
  const values = (Array.isArray(trades) ? trades : []).map((trade) => trade?.return).filter(isNumber)
  if (!values.length) return []
  const min = Math.min(...values)
  const max = Math.max(...values)
  const step = NICE_STEPS.find((candidate) => Math.floor(max / candidate) + 1 - Math.floor(min / candidate) <= maxBins) || NICE_STEPS[NICE_STEPS.length - 1]
  const low = Math.floor(min / step)
  const high = Math.floor(max / step) + 1
  const bins = []
  for (let index = low; index < high; index += 1) bins.push({ from: roundStep(index * step), to: roundStep((index + 1) * step), count: 0 })
  values.forEach((value) => {
    const position = Math.min(bins.length - 1, Math.max(0, Math.floor(value / step) - low))
    bins[position].count += 1
  })
  return bins
}

export function regimeShading(dates, regimePerBar, alpha = 0.16) {
  if (!Array.isArray(dates) || !Array.isArray(regimePerBar)) return []
  return dates
    .map((date, index) => {
      const regime = regimePerBar[index]
      const time = toTime(date)
      if (!time) return null
      if (!REGIME_HEX[regime]) return { time }
      return { time, value: 1, color: hexToRgba(REGIME_HEX[regime], alpha) }
    })
    .filter(Boolean)
}

export function regimeProbabilityRows(dates, probabilitiesPerBar) {
  const rows = REGIME_NAMES.map(() => [])
  if (!Array.isArray(dates) || !Array.isArray(probabilitiesPerBar)) return rows
  dates.forEach((date, index) => {
    const time = toTime(date)
    if (!time) return
    const probabilities = probabilitiesPerBar[index]
    REGIME_NAMES.forEach((name, row) => {
      const probability = Array.isArray(probabilities) ? probabilities[row] : null
      if (!isNumber(probability)) rows[row].push({ time })
      else rows[row].push({ time, value: row + 1, color: hexToRgba(REGIME_HEX[name], 0.06 + probability * 0.92) })
    })
  })
  return rows
}

export function tradeWindow(barCount, trade, before, after) {
  if (!trade || !isNumber(barCount) || barCount <= 0) return null
  const signal = isNumber(trade.signal_bar_index) ? trade.signal_bar_index : trade.entry_bar_index
  const start = Math.max(0, Math.min(signal, trade.entry_bar_index) - before)
  const end = Math.min(barCount - 1, trade.exit_bar_index + after)
  return { start, end }
}

export function ohlcSlice(bars, window) {
  if (!bars || !window) return []
  const result = []
  for (let index = window.start; index <= window.end; index += 1) {
    const bar = {
      index,
      time: toTime(bars.date?.[index]),
      open: bars.open?.[index],
      high: bars.high?.[index],
      low: bars.low?.[index],
      close: bars.close?.[index],
      volume: bars.volume?.[index],
    }
    if (bar.time && [bar.open, bar.high, bar.low, bar.close].every(isNumber)) result.push(bar)
  }
  return result
}

export function volumeAtPrice(bars, binCount = 20) {
  const valid = (Array.isArray(bars) ? bars : []).filter((bar) => [bar.high, bar.low, bar.open, bar.close, bar.volume].every(isNumber))
  if (!valid.length) return null
  const low = Math.min(...valid.map((bar) => bar.low))
  const high = Math.max(...valid.map((bar) => bar.high))
  const span = high - low
  const size = span > 0 ? span / binCount : 1
  const bins = Array.from({ length: binCount }, (unused, index) => ({ from: low + index * size, to: low + (index + 1) * size, up: 0, down: 0, total: 0 }))
  const cells = []
  valid.forEach((bar, offset) => {
    const up = bar.close >= bar.open
    const range = bar.high - bar.low
    for (let index = 0; index < binCount; index += 1) {
      const bin = bins[index]
      let share
      if (range <= 0 || span <= 0) {
        const position = span > 0 ? Math.min(binCount - 1, Math.floor((bar.close - low) / size)) : 0
        share = index === position ? 1 : 0
      } else {
        const overlap = Math.max(0, Math.min(bar.high, bin.to) - Math.max(bar.low, bin.from))
        share = overlap / range
      }
      if (share <= 0) continue
      const volume = bar.volume * share
      if (up) bin.up += volume
      else bin.down += volume
      bin.total += volume
      cells.push({ offset, bin: index, volume })
    }
  })
  return { low, high, bins, cells, maxBin: Math.max(...bins.map((bin) => bin.total)), maxCell: Math.max(0, ...cells.map((cell) => cell.volume)) }
}

export function lastValue(series) {
  return Array.isArray(series) && series.length ? series[series.length - 1].value : null
}
