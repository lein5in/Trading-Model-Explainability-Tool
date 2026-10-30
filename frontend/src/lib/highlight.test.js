import { describe, expect, it } from 'vitest'
import { findNumbers, highlightNumbers } from './highlight.js'

const types = (segments) => segments.filter((segment) => segment.type !== 'text').map((segment) => [segment.type, segment.text])

describe('highlightNumbers', () => {
  it('marks every number as verified when nothing is flagged', () => {
    const text = 'The strategy returned +64.2% against 112.5% for buy and hold, with a Sharpe of 0.71 over 1,759 bars.'
    expect(types(highlightNumbers(text, []))).toEqual([
      ['verified', '+64.2%'],
      ['verified', '112.5%'],
      ['verified', '0.71'],
      ['verified', '1,759'],
    ])
  })

  it('marks the flagged number as unverified, matched by sentence', () => {
    const text = 'Importance of vol_20d is 0.048. In high volatility vol_20d rises to 0.101 on 96 rows.'
    const segments = highlightNumbers(text, [{ number: '0.101', sentence: 'In high volatility vol_20d rises to 0.101 on 96 rows.' }])
    expect(types(segments)).toEqual([
      ['verified', '0.048'],
      ['unverified', '0.101'],
      ['verified', '96'],
    ])
    expect(segments.map((segment) => segment.text).join('')).toBe(text)
  })

  it('flags only as many occurrences as reported', () => {
    const text = 'It made 5 trades. Then 5 more.'
    const segments = highlightNumbers(text, [{ number: '5', sentence: 'Then 5 more.' }])
    expect(types(segments)).toEqual([
      ['verified', '5'],
      ['unverified', '5'],
    ])
  })

  it('handles signed and percent forms including the unicode minus and a space before %', () => {
    const text = 'Drawdown was −14.8% and the loss -9.5 % in high volatility.'
    const segments = highlightNumbers(text, [{ number: '-9.5 %', sentence: text }])
    expect(types(segments)).toEqual([
      ['verified', '−14.8%'],
      ['unverified', '-9.5 %'],
    ])
  })

  it('leaves identifiers, dates, years and ordinal references untouched', () => {
    const text = 'From 2018-01-02 to Dec 31, 2024, in 2020, rsi_14 and sma_ratio_20_50 led in section 3 with 0.05.'
    expect(types(highlightNumbers(text, []))).toEqual([['verified', '0.05']])
    expect(findNumbers('rsi_14 ret_lag_1').length).toBe(0)
  })

  it('returns an empty list for empty text', () => {
    expect(highlightNumbers('', [])).toEqual([])
    expect(highlightNumbers(null, [])).toEqual([])
  })
})
