import { POLL_INTERVAL_MS, POLL_MAX_RETRIES } from '../config.js'
import { isNetworkError } from './api.js'

export const TERMINAL_STATUSES = ['completed', 'partial', 'failed']
export const MAX_BACKOFF_MS = 10000

export function isTerminal(status) {
  return TERMINAL_STATUSES.includes(status)
}

function retryable(error) {
  return isNetworkError(error) || (typeof error?.status === 'number' && error.status >= 500)
}

export function createPoller({
  fetchStatus,
  onUpdate = () => {},
  intervalMs = POLL_INTERVAL_MS,
  maxRetries = POLL_MAX_RETRIES,
  isHidden = () => false,
  now = () => Date.now(),
  setTimer = (callback, delay) => setTimeout(callback, delay),
  clearTimer = (handle) => clearTimeout(handle),
}) {
  let timer = null
  let stopped = true
  let inFlight = false
  let generation = 0
  let state = { phase: 'idle', status: null, error: null, retries: 0, stageKey: null, stageSince: null, paused: false }

  function emit(patch) {
    state = { ...state, ...patch }
    onUpdate(state)
  }

  function schedule(delay) {
    if (stopped) return
    timer = setTimer(tick, delay)
  }

  function stageKeyOf(status) {
    if (!status) return null
    const running = Object.entries(status.stages || {}).find(([, value]) => value?.state === 'running')
    return `${status.status}:${running ? running[0] : status.stage}`
  }

  async function tick() {
    timer = null
    if (stopped) return
    if (isHidden()) {
      emit({ paused: true })
      return
    }
    const current = generation
    inFlight = true
    try {
      const status = await fetchStatus()
      inFlight = false
      if (stopped || current !== generation) return
      const key = stageKeyOf(status)
      const stagePatch = key !== state.stageKey ? { stageKey: key, stageSince: now() } : {}
      if (isTerminal(status?.status)) {
        stopped = true
        emit({ phase: 'done', status, error: null, retries: 0, paused: false, ...stagePatch })
        return
      }
      emit({ phase: 'polling', status, error: null, retries: 0, paused: false, ...stagePatch })
      schedule(intervalMs)
    } catch (error) {
      inFlight = false
      if (stopped || current !== generation) return
      if (retryable(error) && state.retries < maxRetries) {
        const retries = state.retries + 1
        emit({ phase: 'retrying', error, retries })
        schedule(Math.min(intervalMs * 2 ** (retries - 1), MAX_BACKOFF_MS))
        return
      }
      stopped = true
      emit({ phase: 'failed', error })
    }
  }

  return {
    start() {
      if (!stopped) return
      stopped = false
      generation += 1
      emit({ phase: state.phase === 'idle' ? 'starting' : state.phase, retries: 0, error: null, paused: false })
      tick()
    },
    stop() {
      stopped = true
      generation += 1
      if (timer !== null) clearTimer(timer)
      timer = null
    },
    resume() {
      if (stopped || !state.paused) return
      emit({ paused: false })
      if (timer === null && !inFlight) tick()
    },
    getState: () => state,
  }
}
