export const NA = 'n/a'

export function isNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

const formatters = new Map()

function formatter(minimum, maximum = minimum) {
  const key = `${minimum}:${maximum}`
  if (!formatters.has(key)) {
    formatters.set(key, new Intl.NumberFormat('en-US', { minimumFractionDigits: minimum, maximumFractionDigits: maximum, useGrouping: true }))
  }
  return formatters.get(key)
}

function fixed(value, digits) {
  const text = formatter(digits).format(value)
  return /^-0(\.0+)?$/.test(text) ? text.slice(1) : text
}

export function formatNumber(value, digits = 2) {
  return isNumber(value) ? fixed(value, digits) : NA
}

export function formatSmall(value, digits = 4) {
  if (!isNumber(value)) return NA
  if (value !== 0 && Math.abs(value) < 10 ** -digits) return value.toExponential(1)
  return fixed(value, digits)
}

export function formatSignedNumber(value, digits = 2) {
  if (!isNumber(value)) return NA
  const text = fixed(value, digits)
  return value > 0 && !/^0(\.0+)?$/.test(text) ? `+${text}` : text
}

export function formatPercent(value, digits = 1) {
  return isNumber(value) ? `${fixed(value * 100, digits)}%` : NA
}

export function formatSignedPercent(value, digits = 1) {
  return isNumber(value) ? `${formatSignedNumber(value * 100, digits)}%` : NA
}

export function formatPrice(value) {
  return formatNumber(value, 2)
}

export function formatRatio(value, digits = 2) {
  return formatNumber(value, digits)
}

export function formatInt(value) {
  return isNumber(value) ? fixed(Math.round(value), 0) : NA
}

export function formatDate(value) {
  if (typeof value === 'string') {
    const match = /^(\d{4}-\d{2}-\d{2})/.exec(value)
    return match ? match[1] : NA
  }
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value.toISOString().slice(0, 10)
  return NA
}

export function formatSeconds(milliseconds) {
  return isNumber(milliseconds) ? `${fixed(milliseconds / 1000, 1)} s` : NA
}

export function formatClock(seconds) {
  if (!isNumber(seconds) || seconds < 0) return '00:00'
  const total = Math.floor(seconds)
  const minutes = Math.floor(total / 60)
  const rest = total % 60
  return `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}

export function formatPoints(value, digits = 1) {
  return isNumber(value) ? `${formatSignedNumber(value * 100, digits)} pts` : NA
}

export function formatBytes(bytes) {
  if (!isNumber(bytes)) return NA
  if (bytes < 1024) return `${fixed(bytes, 0)} B`
  if (bytes < 1024 * 1024) return `${fixed(bytes / 1024, 1)} KB`
  return `${fixed(bytes / (1024 * 1024), 1)} MB`
}

export function signColor(value) {
  if (!isNumber(value) || value === 0) return 'text-tx'
  return value > 0 ? 'text-pos' : 'text-neg'
}

export function relativeTime(iso, now = Date.now()) {
  const time = typeof iso === 'string' ? Date.parse(iso) : NaN
  if (!Number.isFinite(time)) return NA
  const seconds = Math.max(0, Math.round((now - time) / 1000))
  if (seconds < 60) return 'Just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days} days ago`
  return formatDate(new Date(time))
}
