import { HISTORY_KEY, HISTORY_MAX } from '../config.js'

export function browserStorage() {
  try {
    return typeof window !== 'undefined' && window.localStorage ? window.localStorage : null
  } catch {
    return null
  }
}

function finiteOrNull(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function textOrNull(value) {
  return typeof value === 'string' && value ? value : null
}

export function normalizeEntry(raw) {
  if (!raw || typeof raw !== 'object' || typeof raw.id !== 'string' || !raw.id) return null
  return {
    id: raw.id,
    ticker: textOrNull(raw.ticker),
    model: textOrNull(raw.model),
    startDate: textOrNull(raw.startDate),
    endDate: textOrNull(raw.endDate),
    createdAt: textOrNull(raw.createdAt),
    totalReturn: finiteOrNull(raw.totalReturn),
    sharpe: finiteOrNull(raw.sharpe),
  }
}

export function readHistory(storage) {
  if (!storage) return []
  try {
    const raw = storage.getItem(HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.map(normalizeEntry).filter(Boolean).slice(0, HISTORY_MAX)
  } catch {
    return []
  }
}

export function writeHistory(storage, entries) {
  if (!storage) return false
  try {
    storage.setItem(HISTORY_KEY, JSON.stringify(entries))
    return true
  } catch {
    return false
  }
}

export function withEntry(entries, entry) {
  const normalized = normalizeEntry(entry)
  if (!normalized) return entries
  return [normalized, ...entries.filter((item) => item.id !== normalized.id)].slice(0, HISTORY_MAX)
}

export function withUpdate(entries, id, patch) {
  return entries.map((item) => (item.id === id ? normalizeEntry({ ...item, ...patch, id }) : item))
}

export function withoutEntry(entries, id) {
  return entries.filter((item) => item.id !== id)
}

export function createHistoryStore(getStorage = browserStorage) {
  let entries = readHistory(getStorage())
  const listeners = new Set()

  function commit(next) {
    entries = next
    writeHistory(getStorage(), entries)
    listeners.forEach((listener) => listener())
    return entries
  }

  return {
    getSnapshot: () => entries,
    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    add: (entry) => commit(withEntry(entries, entry)),
    update(id, patch) {
      if (!entries.some((item) => item.id === id)) return entries
      return commit(withUpdate(entries, id, patch))
    },
    remove: (id) => commit(withoutEntry(entries, id)),
  }
}

export const historyStore = createHistoryStore()
