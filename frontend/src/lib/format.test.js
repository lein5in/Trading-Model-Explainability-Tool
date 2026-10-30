import { describe, expect, it } from 'vitest'
import {
  formatBytes,
  formatClock,
  formatDate,
  formatInt,
  formatNumber,
  formatPercent,
  formatPoints,
  formatPrice,
  formatRatio,
  formatSeconds,
  formatSignedNumber,
  formatSignedPercent,
  formatSmall,
  relativeTime,
} from './format.js'

describe('format', () => {
  it('renders missing values as n/a, never 0 or NaN', () => {
    for (const value of [null, undefined, NaN, Infinity, '0.5']) {
      expect(formatPercent(value)).toBe('n/a')
      expect(formatSignedPercent(value)).toBe('n/a')
      expect(formatPrice(value)).toBe('n/a')
      expect(formatRatio(value)).toBe('n/a')
      expect(formatInt(value)).toBe('n/a')
    }
  })

  it('formats percentages from fractions', () => {
    expect(formatPercent(0.642)).toBe('64.2%')
    expect(formatPercent(-0.148, 1)).toBe('-14.8%')
    expect(formatPercent(0.5361, 2)).toBe('53.61%')
    expect(formatPercent(-0.00001)).toBe('0.0%')
  })

  it('formats signed percentages', () => {
    expect(formatSignedPercent(0.642)).toBe('+64.2%')
    expect(formatSignedPercent(-0.081)).toBe('-8.1%')
    expect(formatSignedPercent(0)).toBe('0.0%')
    expect(formatSignedPercent(0.00001)).toBe('0.0%')
  })

  it('formats prices, ratios and integers with thousands separators', () => {
    expect(formatPrice(1234.5)).toBe('1,234.50')
    expect(formatRatio(0.7149)).toBe('0.71')
    expect(formatRatio(-0.125, 3)).toBe('-0.125')
    expect(formatInt(1759)).toBe('1,759')
    expect(formatInt(1234567.4)).toBe('1,234,567')
    expect(formatNumber(0.0344, 3)).toBe('0.034')
  })

  it('switches tiny values to scientific notation instead of showing zero', () => {
    expect(formatSmall(0.0000012)).toBe('1.2e-6')
    expect(formatSmall(0)).toBe('0.0000')
    expect(formatSmall(0.0042)).toBe('0.0042')
    expect(formatSmall(null)).toBe('n/a')
  })

  it('formats signed numbers and points', () => {
    expect(formatSignedNumber(0.0341, 3)).toBe('+0.034')
    expect(formatSignedNumber(-0.0341, 3)).toBe('-0.034')
    expect(formatPoints(-0.483)).toBe('-48.3 pts')
    expect(formatPoints(0.189)).toBe('+18.9 pts')
  })

  it('formats dates as YYYY-MM-DD', () => {
    expect(formatDate('2024-12-31')).toBe('2024-12-31')
    expect(formatDate('2024-12-31T15:00:00+00:00')).toBe('2024-12-31')
    expect(formatDate(new Date(Date.UTC(2020, 0, 2)))).toBe('2020-01-02')
    expect(formatDate('yesterday')).toBe('n/a')
    expect(formatDate(null)).toBe('n/a')
  })

  it('formats durations and clocks', () => {
    expect(formatSeconds(4100)).toBe('4.1 s')
    expect(formatClock(19.9)).toBe('00:19')
    expect(formatClock(300)).toBe('05:00')
    expect(formatClock(-3)).toBe('00:00')
    expect(formatBytes(10 * 1024 * 1024)).toBe('10.0 MB')
  })

  it('describes relative times', () => {
    const now = Date.parse('2026-10-30T12:00:00Z')
    expect(relativeTime('2026-10-30T11:59:30Z', now)).toBe('Just now')
    expect(relativeTime('2026-10-30T10:00:00Z', now)).toBe('2 h ago')
    expect(relativeTime('2026-10-29T10:00:00Z', now)).toBe('Yesterday')
    expect(relativeTime('2026-10-01T10:00:00Z', now)).toBe('2026-10-01')
    expect(relativeTime(null, now)).toBe('n/a')
  })
})
