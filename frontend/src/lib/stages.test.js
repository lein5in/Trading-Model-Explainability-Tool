import { describe, expect, it } from 'vitest'
import { activeStepIndex, buildRunLog, buildSteps, elapsedSeconds, statusFromAnalysis, stepTimeLabel } from './stages.js'

const pending = { state: 'pending', duration_ms: null }

function payload(status, stages, error = null) {
  return {
    status,
    stage: null,
    stages: { validate: pending, predict: pending, backtest: pending, regimes: pending, shap: pending, report: pending, ...stages },
    error,
  }
}

describe('stage to stepper mapping', () => {
  it('merges validate and predict into the Predict step', () => {
    const steps = buildSteps(payload('running', { validate: { state: 'done', duration_ms: 1200 }, predict: { state: 'running', duration_ms: null } }))
    expect(steps.map((step) => step.state)).toEqual(['running', 'pending', 'pending', 'pending', 'pending'])
    expect(steps[0].number).toBe('01')
    expect(activeStepIndex(steps)).toBe(0)
  })

  it('treats a half-done step as running between two stage transitions', () => {
    const steps = buildSteps(payload('running', { validate: { state: 'done', duration_ms: 1200 } }))
    expect(steps[0].state).toBe('running')
  })

  it('sums durations of a done step', () => {
    const steps = buildSteps(
      payload('running', {
        validate: { state: 'done', duration_ms: 1200 },
        predict: { state: 'done', duration_ms: 2900 },
        backtest: { state: 'done', duration_ms: 1300 },
        regimes: { state: 'running', duration_ms: null },
      }),
    )
    expect(steps.map((step) => step.state)).toEqual(['done', 'done', 'running', 'pending', 'pending'])
    expect(steps[0].durationMs).toBe(4100)
    expect(stepTimeLabel(steps[0], false)).toBe('4.1 s')
    expect(stepTimeLabel(steps[3], false)).toBe('waiting')
    expect(stepTimeLabel(steps[3], true)).toBe('not run')
    expect(activeStepIndex(steps)).toBe(2)
  })

  it('marks the failed step and points at it', () => {
    const steps = buildSteps(
      payload('partial', {
        validate: { state: 'done', duration_ms: 1 },
        predict: { state: 'done', duration_ms: 1 },
        backtest: { state: 'done', duration_ms: 1 },
        regimes: { state: 'done', duration_ms: 1 },
        shap: { state: 'failed', duration_ms: 7000 },
        report: { state: 'done', duration_ms: 1 },
      }),
    )
    expect(steps.map((step) => step.state)).toEqual(['done', 'done', 'done', 'failed', 'done'])
    expect(activeStepIndex(steps)).toBe(3)
    expect(stepTimeLabel(steps[3], true)).toBe('failed')
  })

  it('maps a failed validate stage to the Predict step', () => {
    const steps = buildSteps(payload('failed', { validate: { state: 'failed', duration_ms: 500 } }))
    expect(steps[0].state).toBe('failed')
  })
})

describe('run log', () => {
  it('builds lines only from stage states and durations', () => {
    const lines = buildRunLog(
      payload('running', {
        validate: { state: 'done', duration_ms: 2000 },
        predict: { state: 'done', duration_ms: 2100 },
        backtest: { state: 'running', duration_ms: null },
      }),
    )
    expect(lines).toEqual([
      { seconds: 2, text: 'Validate: data loaded and preflight check passed in 2.0 s', tone: 'ok' },
      { seconds: 4.1, text: 'Predict: done in 2.1 s', tone: 'ok' },
      { seconds: 4.1, text: 'Backtest: running…', tone: 'active' },
    ])
  })

  it('names the error code on the failed stage', () => {
    const lines = buildRunLog(
      payload('failed', { validate: { state: 'failed', duration_ms: 800 } }, { code: 'preflight_failed', stage: 'validate', message: 'x' }),
    )
    expect(lines).toEqual([{ seconds: 0.8, text: 'Validate: failed in 0.8 s (preflight_failed)', tone: 'error' }])
  })

  it('adds a stop line when the failure has no stage state', () => {
    const lines = buildRunLog(payload('failed', {}, { code: 'interrupted', stage: 'predict' }))
    expect(lines).toEqual([{ seconds: 0, text: 'Analysis stopped (interrupted)', tone: 'error' }])
  })

  it('shows a single queued line', () => {
    expect(buildRunLog(payload('queued', {}))).toHaveLength(1)
  })

  it('ends with a completion line', () => {
    const lines = buildRunLog(payload('completed', { validate: { state: 'done', duration_ms: 1000 } }))
    expect(lines.at(-1)).toEqual({ seconds: 1, text: 'Analysis completed', tone: 'ok' })
  })
})

describe('elapsed time', () => {
  it('adds finished durations and the time spent in the running stage', () => {
    const status = payload('running', { validate: { state: 'done', duration_ms: 3000 }, predict: { state: 'running', duration_ms: null } })
    expect(elapsedSeconds(status, 10000, 14500)).toBe(7.5)
    expect(elapsedSeconds(status, null, 14500)).toBe(3)
  })
})

describe('statusFromAnalysis', () => {
  it('builds a status payload from a stored analysis', () => {
    const result = statusFromAnalysis({ id: 'a', status: 'failed', stage: 'validate', result: null, error: { code: 'x' } })
    expect(result.status).toBe('failed')
    expect(result.stages.validate.state).toBe('pending')
    expect(result.error.code).toBe('x')
  })
})
