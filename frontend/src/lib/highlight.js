const ISO_DATE = /\b\d{4}-\d{2}(?:-\d{2})?\b/g
const MONTH_DATE =
  /\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(?:\d{1,2},?\s+)?\d{4}\b/gi
const ORDINAL_REFERENCE = /\b(?:section|step|stage|part|item|figure|table|chapter|state)\s+\d+\b/gi
const NUMBER = /(?<![\w.])([+\-−]?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(\s?%)?(?![\w])/g
const SENTENCE_BOUNDARY = /(?<=[.!?])\s+/g

function mask(text, pattern) {
  return text.replace(pattern, (match) => ' '.repeat(match.length))
}

export function sentenceAt(text, position) {
  let start = 0
  for (const boundary of text.matchAll(SENTENCE_BOUNDARY)) {
    if (boundary.index >= position) return text.slice(start, boundary.index).trim()
    start = boundary.index + boundary[0].length
  }
  return text.slice(start).trim()
}

function isBareYear(sign, integer, fraction, percent) {
  if (sign || fraction || percent || integer.includes(',')) return false
  const value = Number(integer)
  return value >= 1900 && value <= 2100
}

export function findNumbers(text) {
  const masked = mask(mask(mask(text, ISO_DATE), MONTH_DATE), ORDINAL_REFERENCE)
  const found = []
  for (const match of masked.matchAll(NUMBER)) {
    const [raw, sign, integer, fraction, percent] = match
    const trimmed = raw.trim()
    const start = match.index + raw.indexOf(trimmed)
    found.push({ text: trimmed, start, end: start + trimmed.length, year: isBareYear(sign, integer, fraction, percent) })
  }
  return found
}

export function highlightNumbers(text, unverified = []) {
  if (typeof text !== 'string' || !text) return []
  const pending = (Array.isArray(unverified) ? unverified : []).filter((item) => item && typeof item.number === 'string').map((item) => ({ ...item, used: false }))
  const numbers = findNumbers(text).map((number) => ({ ...number, sentence: sentenceAt(text, number.start), flagged: false }))
  for (const number of numbers) {
    const match = pending.find((item) => !item.used && item.number === number.text && item.sentence === number.sentence)
    if (match) {
      match.used = true
      number.flagged = true
    }
  }
  for (const item of pending.filter((entry) => !entry.used)) {
    const number = numbers.find((candidate) => !candidate.flagged && candidate.text === item.number)
    if (number) {
      item.used = true
      number.flagged = true
    }
  }
  const segments = []
  let cursor = 0
  for (const number of numbers) {
    const type = number.flagged ? 'unverified' : number.year ? null : 'verified'
    if (!type) continue
    if (number.start > cursor) segments.push({ type: 'text', text: text.slice(cursor, number.start) })
    segments.push({ type, text: text.slice(number.start, number.end) })
    cursor = number.end
  }
  if (cursor < text.length) segments.push({ type: 'text', text: text.slice(cursor) })
  return segments
}
