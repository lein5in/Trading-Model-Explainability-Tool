export const REGIME_NAMES = ['Low vol', 'Mid vol', 'High vol']

export const REGIME_HEX = {
  'Low vol': '#4C8DF6',
  'Mid vol': '#9B7BF0',
  'High vol': '#F08A3C',
}

export const REGIME_VARS = {
  'Low vol': 'var(--color-r1)',
  'Mid vol': 'var(--color-r2)',
  'High vol': 'var(--color-r3)',
}

export function regimeColorVar(regime) {
  return REGIME_VARS[regime] || 'var(--color-mu)'
}

export function hexToRgba(hex, alpha) {
  const value = hex.replace('#', '')
  const r = parseInt(value.slice(0, 2), 16)
  const g = parseInt(value.slice(2, 4), 16)
  const b = parseInt(value.slice(4, 6), 16)
  const a = Math.max(0, Math.min(1, alpha))
  return `rgba(${r}, ${g}, ${b}, ${Number(a.toFixed(3))})`
}
