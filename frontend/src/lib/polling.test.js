import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from './api.js'
import { createPoller } from './polling.js'

const running = (stage = 'predict') => ({
  status: 'running',
  stage,
  stages: { validate: { state: 'done', duration_ms: 1000 }, [stage]: { state: 'running', duration_ms: null } },
  error: null,
})
const completed = { status: 'completed', stage: 'done', stages: {}, error: null }
const failed = { status: 'failed', stage: 'predict', stages: {}, error: { code: 'predict_failed', stage: 'predict' } }
const networkError = () => new ApiError({ code: 'network_error', message: 'down' })

function setup(responses, options = {}) {
  const queue = [...responses]
  const fetchStatus = vi.fn(async () => {
    const next = queue.shift()
    if (next instanceof Error) throw next
    return next
  })
  const updates = []
  const poller = createPoller({ fetchStatus, onUpdate: (state) => updates.push(state), intervalMs: 1500, maxRetries: 3, ...options })
  return { poller, fetchStatus, updates }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('status poller', () => {
  it('polls every 1.5 s until completed, then stops', async () => {
    const { poller, fetchStatus, updates } = setup([running(), running('backtest'), completed])
    poller.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(fetchStatus).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1499)
    expect(fetchStatus).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(fetchStatus).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(1500)
    expect(fetchStatus).toHaveBeenCalledTimes(3)
    expect(poller.getState().phase).toBe('done')
    expect(poller.getState().status.status).toBe('completed')
    await vi.advanceTimersByTimeAsync(10000)
    expect(fetchStatus).toHaveBeenCalledTimes(3)
    expect(updates.map((state) => state.phase)).toEqual(['starting', 'polling', 'polling', 'done'])
  })

  it('goes from running to failed and stops on the terminal status', async () => {
    const { poller, fetchStatus } = setup([running(), failed])
    poller.start()
    await vi.advanceTimersByTimeAsync(1500)
    expect(poller.getState()).toMatchObject({ phase: 'done', status: { status: 'failed' } })
    await vi.advanceTimersByTimeAsync(6000)
    expect(fetchStatus).toHaveBeenCalledTimes(2)
  })

  it('retries on network errors with backoff, then recovers', async () => {
    const { poller, fetchStatus, updates } = setup([running(), networkError(), networkError(), running(), completed])
    poller.start()
    await vi.advanceTimersByTimeAsync(1500)
    expect(poller.getState()).toMatchObject({ phase: 'retrying', retries: 1 })
    await vi.advanceTimersByTimeAsync(1500)
    expect(poller.getState()).toMatchObject({ phase: 'retrying', retries: 2 })
    await vi.advanceTimersByTimeAsync(2999)
    expect(fetchStatus).toHaveBeenCalledTimes(3)
    await vi.advanceTimersByTimeAsync(1)
    expect(poller.getState()).toMatchObject({ phase: 'polling', retries: 0, error: null })
    await vi.advanceTimersByTimeAsync(1500)
    expect(poller.getState().phase).toBe('done')
    expect(updates.some((state) => state.phase === 'failed')).toBe(false)
  })

  it('gives up after the bounded number of retries', async () => {
    const { poller, fetchStatus } = setup([networkError(), networkError(), networkError(), networkError(), running()])
    poller.start()
    await vi.advanceTimersByTimeAsync(60000)
    expect(poller.getState().phase).toBe('failed')
    expect(poller.getState().error.code).toBe('network_error')
    expect(fetchStatus).toHaveBeenCalledTimes(4)
  })

  it('fails immediately on a 404', async () => {
    const { poller, fetchStatus } = setup([new ApiError({ status: 404, code: 'analysis_not_found' })])
    poller.start()
    await vi.advanceTimersByTimeAsync(10000)
    expect(poller.getState()).toMatchObject({ phase: 'failed', error: { status: 404 } })
    expect(fetchStatus).toHaveBeenCalledTimes(1)
  })

  it('stops polling when stopped (unmount)', async () => {
    const { poller, fetchStatus, updates } = setup([running(), running(), running()])
    poller.start()
    await vi.advanceTimersByTimeAsync(0)
    poller.stop()
    await vi.advanceTimersByTimeAsync(10000)
    expect(fetchStatus).toHaveBeenCalledTimes(1)
    expect(updates).toHaveLength(2)
  })

  it('ignores a response that arrives after stop', async () => {
    let resolve
    const fetchStatus = vi.fn(() => new Promise((done) => (resolve = done)))
    const updates = []
    const poller = createPoller({ fetchStatus, onUpdate: (state) => updates.push(state) })
    poller.start()
    poller.stop()
    resolve(completed)
    await vi.advanceTimersByTimeAsync(0)
    expect(updates.map((state) => state.phase)).toEqual(['starting'])
  })

  it('pauses while hidden and resumes on demand', async () => {
    let hidden = false
    const { poller, fetchStatus } = setup([running(), running(), completed], { isHidden: () => hidden })
    poller.start()
    await vi.advanceTimersByTimeAsync(0)
    hidden = true
    await vi.advanceTimersByTimeAsync(10000)
    expect(fetchStatus).toHaveBeenCalledTimes(1)
    expect(poller.getState().paused).toBe(true)
    hidden = false
    poller.resume()
    await vi.advanceTimersByTimeAsync(0)
    expect(fetchStatus).toHaveBeenCalledTimes(2)
    expect(poller.getState().paused).toBe(false)
  })

  it('records when the current stage was first seen', async () => {
    let clock = 1000
    const { poller } = setup([running('predict'), running('predict'), running('backtest')], { now: () => clock })
    poller.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(poller.getState().stageSince).toBe(1000)
    clock = 2500
    await vi.advanceTimersByTimeAsync(1500)
    expect(poller.getState().stageSince).toBe(1000)
    clock = 4000
    await vi.advanceTimersByTimeAsync(1500)
    expect(poller.getState().stageSince).toBe(4000)
  })
})
