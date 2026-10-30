import { isNumber } from './format.js'

export function buildWaterfall(tradeRow, topN = 5) {
  if (!tradeRow || !isNumber(tradeRow.base_value) || !tradeRow.contributions) return null
  const entries = Object.entries(tradeRow.contributions).filter(([, value]) => isNumber(value))
  const ranked = [...entries].sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]) || a[0].localeCompare(b[0]))
  const top = ranked.slice(0, topN)
  const rest = ranked.slice(topN)
  let running = tradeRow.base_value
  const items = top.map(([feature, delta]) => {
    const start = running
    running += delta
    return { kind: 'feature', feature, value: tradeRow.feature_values?.[feature] ?? null, delta, start, end: running }
  })
  if (rest.length) {
    const delta = rest.reduce((sum, [, value]) => sum + value, 0)
    const start = running
    running += delta
    items.push({ kind: 'other', feature: null, count: rest.length, value: null, delta, start, end: running })
  }
  const output = isNumber(tradeRow.output) ? tradeRow.output : null
  const points = [tradeRow.base_value, running, ...items.flatMap((item) => [item.start, item.end])]
  if (output !== null) points.push(output)
  return {
    base: tradeRow.base_value,
    items,
    final: running,
    output,
    gap: output === null ? null : output - running,
    min: Math.min(...points),
    max: Math.max(...points),
  }
}

export function waterfallDomain(waterfall, threshold, clampUnit) {
  if (!waterfall) return [0, 1]
  const points = [waterfall.min, waterfall.max]
  if (isNumber(threshold)) points.push(threshold)
  let low = Math.min(...points)
  let high = Math.max(...points)
  const pad = (high - low || Math.abs(high) || 1) * 0.1
  low -= pad
  high += pad
  if (clampUnit) {
    low = Math.max(0, low)
    high = Math.min(1, high)
  }
  return [low, high]
}

export function domainPercent(value, domain) {
  const [low, high] = domain
  if (high === low) return 50
  return Math.max(0, Math.min(100, ((value - low) / (high - low)) * 100))
}
