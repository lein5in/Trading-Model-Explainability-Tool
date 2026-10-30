import { describe, expect, it } from 'vitest'
import { SHAP_ADDITIVITY_LIMIT } from '../config.js'
import { ERROR_MESSAGES, describeFailure, errorMessage } from './errors.js'

describe('errorMessage', () => {
  it('maps known codes to a short message', () => {
    expect(errorMessage('rate_limited')).toBe(ERROR_MESSAGES.rate_limited)
    expect(errorMessage('timeout')).toMatch(/5-minute/)
  })

  it('maps any report_ code to the generic report message', () => {
    expect(errorMessage('report_something_new')).toBe(ERROR_MESSAGES.report_failed)
  })

  it('falls back to the backend message, then to a generic one', () => {
    expect(errorMessage('brand_new_code', 'Backend says hi.')).toBe('Backend says hi.')
    expect(errorMessage('brand_new_code', '  ')).toBe(ERROR_MESSAGES.unknown_error)
    expect(errorMessage(undefined)).toBe(ERROR_MESSAGES.unknown_error)
  })
})

describe('describeFailure', () => {
  it('shows the feature diff for a preflight feature mismatch', () => {
    const result = describeFailure({
      code: 'preflight_failed',
      message: 'raw',
      stage: 'validate',
      details: { reason: 'feature_mismatch', missing: ['rsi_14'], unexpected: ['foo'], model_features: ['rsi_14', 'vol_20d'] },
    })
    expect(result.title).toBe(ERROR_MESSAGES.preflight_failed)
    expect(result.message).toMatch(/feature names/)
    expect(result.facts).toEqual([
      { label: 'Expected by the model, not provided', value: 'rsi_14', mono: true },
      { label: 'Provided, unknown to the model', value: 'foo', mono: true },
      { label: 'Model features', value: 'rsi_14, vol_20d', mono: true },
    ])
    expect(result.stage).toBe('validate')
  })

  it('shows expected and provided counts for a feature count mismatch', () => {
    const result = describeFailure({ code: 'preflight_failed', details: { reason: 'feature_count_mismatch', expected: 8, provided: 5 } })
    expect(result.facts.map((fact) => fact.value)).toEqual(['8', '5'])
  })

  it('shows the max gap and the limit for an additivity failure', () => {
    const result = describeFailure({ code: 'shap_additivity_failed', message: 'x', details: { max_gap: 0.034 } })
    expect(result.title).toMatch(/SHAP check failed/)
    expect(result.facts).toEqual([
      { label: 'Largest gap', value: '0.034', mono: true },
      { label: 'Limit', value: String(SHAP_ADDITIVITY_LIMIT), mono: true },
    ])
  })

  it('covers timeout, interrupted, data, rate limit and daily cap codes', () => {
    expect(describeFailure({ code: 'timeout' }).title).toBe(ERROR_MESSAGES.timeout)
    expect(describeFailure({ code: 'interrupted' }).title).toBe(ERROR_MESSAGES.interrupted)
    expect(describeFailure({ code: 'data_unavailable', details: { ticker: 'XYZ' } }).facts[0].value).toBe('XYZ')
    expect(describeFailure({ code: 'rate_limited', details: { retry_after_seconds: 120 } }).facts[0].value).toBe('120 s')
    expect(describeFailure({ code: 'daily_cap_reached', details: { daily_cap: 200 } }).facts[0].value).toBe('200')
    expect(describeFailure({ code: 'report_truncated', message: 'cut' }).title).toBe(ERROR_MESSAGES.report_truncated)
  })

  it('uses the backend message as title for an unknown code', () => {
    const result = describeFailure({ code: 'mystery', message: 'Something odd happened.' })
    expect(result.title).toBe('Something odd happened.')
    expect(result.message).toBeNull()
  })

  it('handles a missing error', () => {
    expect(describeFailure(null).title).toBe(ERROR_MESSAGES.unknown_error)
  })
})
