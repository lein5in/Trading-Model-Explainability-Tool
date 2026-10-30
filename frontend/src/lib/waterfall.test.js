import { describe, expect, it } from 'vitest'
import { buildWaterfall, domainPercent, waterfallDomain } from './waterfall.js'

const row = {
  base_value: 0.52,
  output: 0.76,
  contributions: { a: 0.1, b: -0.04, c: 0.12, d: 0.03, e: 0.02, f: 0.011, g: 0.009, h: -0.01 },
  feature_values: { a: 1.5, b: -2, c: 70, d: 0.01, e: 3, f: 4, g: 5, h: 6 },
}

describe('buildWaterfall', () => {
  it('ranks by absolute contribution and groups the rest', () => {
    const result = buildWaterfall(row, 5)
    expect(result.items.map((item) => item.feature)).toEqual(['c', 'a', 'b', 'd', 'e', null])
    expect(result.items[0]).toMatchObject({ value: 70, delta: 0.12, start: 0.52 })
    expect(result.items.at(-1)).toMatchObject({ kind: 'other', count: 3 })
    expect(result.items.at(-1).delta).toBeCloseTo(0.01, 12)
  })

  it('chains cumulative values from the base value to the final probability', () => {
    const result = buildWaterfall(row, 5)
    result.items.forEach((item, index) => {
      const previousEnd = index === 0 ? result.base : result.items[index - 1].end
      expect(item.start).toBe(previousEnd)
    })
    expect(Math.abs(result.items.at(-1).end - result.final)).toBeLessThan(1e-9)
    expect(Math.abs(result.final - 0.76)).toBeLessThan(1e-9)
    expect(Math.abs(result.gap)).toBeLessThan(1e-9)
  })

  it('has no other row when every feature fits', () => {
    const result = buildWaterfall({ base_value: 0.5, output: 0.6, contributions: { a: 0.1 } }, 5)
    expect(result.items).toHaveLength(1)
    expect(Math.abs(result.final - 0.6)).toBeLessThan(1e-9)
  })

  it('returns null without a trade row', () => {
    expect(buildWaterfall(null)).toBeNull()
    expect(buildWaterfall({ base_value: null, contributions: {} })).toBeNull()
  })

  it('builds a padded domain that includes the threshold', () => {
    const result = buildWaterfall(row, 5)
    const domain = waterfallDomain(result, 0.5, true)
    expect(domain[0]).toBeLessThanOrEqual(0.5)
    expect(domain[1]).toBeGreaterThanOrEqual(0.76)
    expect(domain[1]).toBeLessThanOrEqual(1)
    expect(domainPercent(domain[0], domain)).toBe(0)
    expect(domainPercent(domain[1], domain)).toBe(100)
  })
})
