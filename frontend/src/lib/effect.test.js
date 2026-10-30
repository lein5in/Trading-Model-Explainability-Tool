import { describe, expect, it } from 'vitest'
import { correlation, effectDirection, effectsBySample } from './effect.js'

describe('effect direction', () => {
  it('computes the Pearson correlation', () => {
    expect(correlation([1, 2, 3], [2, 4, 6])).toBeCloseTo(1, 12)
    expect(correlation([1, 2, 3], [3, 2, 1])).toBeCloseTo(-1, 12)
  })

  it('says raises for a positive and lowers for a negative relation', () => {
    expect(effectDirection([1, 2, 3, 4], [-0.1, 0, 0.05, 0.2]).direction).toBe('raises')
    expect(effectDirection([1, 2, 3, 4], [0.2, 0.1, 0, -0.3]).direction).toBe('lowers')
  })

  it('returns no direction with too few points or no variance', () => {
    expect(effectDirection([1, 2], [1, 2])).toEqual({ direction: null, correlation: null })
    expect(effectDirection([1, 1, 1], [1, 2, 3])).toEqual({ direction: null, correlation: null })
    expect(effectDirection([1, 2, 3], [0, 0, 0]).direction).toBeNull()
  })

  it('skips non-finite pairs', () => {
    expect(effectDirection([1, null, 2, 3, NaN], [1, 5, 2, 3, 9]).direction).toBe('raises')
  })

  it('computes one direction per feature from the stored sample', () => {
    const shap = {
      feature_names: ['x', 'y'],
      sample: {
        feature_values: [
          [1, 10],
          [2, 20],
          [3, 30],
        ],
        contributions: [
          [0.1, 0.3],
          [0.2, 0.2],
          [0.3, 0.1],
        ],
      },
    }
    const effects = effectsBySample(shap)
    expect(effects.x.direction).toBe('raises')
    expect(effects.y.direction).toBe('lowers')
  })
})
