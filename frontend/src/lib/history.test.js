import { describe, expect, it } from 'vitest'
import { HISTORY_KEY, HISTORY_MAX } from '../config.js'
import { createHistoryStore, readHistory, withEntry, writeHistory } from './history.js'

function memoryStorage(initial = {}) {
  const data = { ...initial }
  return {
    data,
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      data[key] = String(value)
    },
  }
}

function failingStorage() {
  return {
    getItem: () => {
      throw new Error('denied')
    },
    setItem: () => {
      throw new Error('quota')
    },
  }
}

const entry = (id, patch = {}) => ({
  id,
  ticker: 'SPY',
  model: 'XGBoost',
  startDate: '2018-01-02',
  endDate: '2024-12-31',
  createdAt: '2026-10-30T10:00:00Z',
  totalReturn: null,
  sharpe: null,
  ...patch,
})

describe('history storage', () => {
  it('returns an empty list when storage is missing, empty, corrupt or throws', () => {
    expect(readHistory(null)).toEqual([])
    expect(readHistory(memoryStorage())).toEqual([])
    expect(readHistory(memoryStorage({ [HISTORY_KEY]: '{not json' }))).toEqual([])
    expect(readHistory(memoryStorage({ [HISTORY_KEY]: '{"a":1}' }))).toEqual([])
    expect(readHistory(failingStorage())).toEqual([])
  })

  it('drops malformed entries and non-finite metrics', () => {
    const raw = JSON.stringify([{ nope: true }, entry('a', { totalReturn: 'x', sharpe: 1.2 })])
    const result = readHistory(memoryStorage({ [HISTORY_KEY]: raw }))
    expect(result).toHaveLength(1)
    expect(result[0].totalReturn).toBeNull()
    expect(result[0].sharpe).toBe(1.2)
  })

  it('reports write failures instead of throwing', () => {
    expect(writeHistory(failingStorage(), [])).toBe(false)
    expect(writeHistory(null, [])).toBe(false)
    expect(writeHistory(memoryStorage(), [])).toBe(true)
  })

  it('keeps at most 20 entries, newest first, without duplicates', () => {
    let list = []
    for (let index = 0; index < HISTORY_MAX + 5; index += 1) list = withEntry(list, entry(`id-${index}`))
    expect(HISTORY_MAX).toBe(20)
    expect(list).toHaveLength(20)
    expect(list[0].id).toBe('id-24')
    list = withEntry(list, entry('id-10'))
    expect(list[0].id).toBe('id-10')
    expect(list.filter((item) => item.id === 'id-10')).toHaveLength(1)
  })
})

describe('history store', () => {
  it('adds, updates metrics, removes and persists', () => {
    const storage = memoryStorage()
    const store = createHistoryStore(() => storage)
    let notified = 0
    store.subscribe(() => {
      notified += 1
    })
    store.add(entry('a'))
    store.update('a', { totalReturn: 0.25, sharpe: 0.8 })
    expect(store.getSnapshot()[0]).toMatchObject({ id: 'a', totalReturn: 0.25, sharpe: 0.8 })
    expect(JSON.parse(storage.data[HISTORY_KEY])[0].totalReturn).toBe(0.25)
    store.update('missing', { totalReturn: 1 })
    expect(store.getSnapshot()).toHaveLength(1)
    store.remove('a')
    expect(store.getSnapshot()).toEqual([])
    expect(notified).toBe(3)
  })

  it('keeps working in memory when storage is unavailable', () => {
    const store = createHistoryStore(() => failingStorage())
    store.add(entry('a'))
    expect(store.getSnapshot().map((item) => item.id)).toEqual(['a'])
    const none = createHistoryStore(() => null)
    none.add(entry('b'))
    expect(none.getSnapshot()).toHaveLength(1)
  })
})
