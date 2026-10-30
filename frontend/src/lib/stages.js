import { formatSeconds, isNumber } from './format.js'

export const BACKEND_STAGES = ['validate', 'predict', 'backtest', 'regimes', 'shap', 'report']

export const STAGE_LABELS = {
  validate: 'Validate',
  predict: 'Predict',
  backtest: 'Backtest',
  regimes: 'Regimes',
  shap: 'SHAP',
  report: 'Report',
}

export const STEPS = [
  {
    id: 'predict',
    name: 'Predict',
    stages: ['validate', 'predict'],
    description: 'Checks the model against your features, then runs it in the sandbox to get one signal per bar.',
  },
  {
    id: 'backtest',
    name: 'Backtest',
    stages: ['backtest'],
    description: 'Executes at the next bar open, applies costs on entry and exit, marks equity to market every day.',
  },
  {
    id: 'regimes',
    name: 'Regimes',
    stages: ['regimes'],
    description: 'Fits a 3-state HMM and labels each bar from filtered probabilities, forward pass only.',
  },
  {
    id: 'shap',
    name: 'SHAP',
    stages: ['shap'],
    description: 'Explains the model output on a stratified sample and checks that contributions add up.',
  },
  {
    id: 'report',
    name: 'Report',
    stages: ['report'],
    description: 'Writes five sections from the computed numbers, then verifies every number it used.',
  },
]

export function stepForStage(stage) {
  return STEPS.find((step) => step.stages.includes(stage)) || null
}

function stageState(stages, name) {
  return stages?.[name]?.state || 'pending'
}

export function stepState(stages, step, status) {
  const states = step.stages.map((name) => stageState(stages, name))
  if (states.includes('failed')) return 'failed'
  if (states.every((value) => value === 'done')) return 'done'
  if (states.includes('running')) return 'running'
  if (states.includes('done') && (status === 'running' || status === 'queued')) return 'running'
  return 'pending'
}

export function buildSteps(statusPayload) {
  const stages = statusPayload?.stages || {}
  const status = statusPayload?.status
  return STEPS.map((step, index) => {
    const state = stepState(stages, step, status)
    const durations = step.stages.map((name) => stages[name]?.duration_ms).filter(isNumber)
    return {
      ...step,
      number: String(index + 1).padStart(2, '0'),
      state,
      durationMs: state === 'done' && durations.length ? durations.reduce((sum, value) => sum + value, 0) : null,
    }
  })
}

export function activeStepIndex(steps) {
  const failed = steps.findIndex((step) => step.state === 'failed')
  if (failed >= 0) return failed
  const running = steps.findIndex((step) => step.state === 'running')
  if (running >= 0) return running
  const pending = steps.findIndex((step) => step.state === 'pending')
  return pending >= 0 ? pending : steps.length - 1
}

export function stepTimeLabel(step, terminal) {
  if (step.state === 'done') return step.durationMs == null ? 'done' : formatSeconds(step.durationMs)
  if (step.state === 'running') return 'running'
  if (step.state === 'failed') return 'failed'
  return terminal ? 'not run' : 'waiting'
}

export function completedMs(statusPayload) {
  const stages = statusPayload?.stages || {}
  return BACKEND_STAGES.reduce((sum, name) => {
    const stage = stages[name]
    return stage && stage.state !== 'running' && isNumber(stage.duration_ms) ? sum + stage.duration_ms : sum
  }, 0)
}

export function runningStage(statusPayload) {
  const stages = statusPayload?.stages || {}
  return BACKEND_STAGES.find((name) => stages[name]?.state === 'running') || null
}

export function elapsedSeconds(statusPayload, stageSince, now) {
  const base = completedMs(statusPayload) / 1000
  if (!runningStage(statusPayload) || !isNumber(stageSince) || !isNumber(now)) return base
  return base + Math.max(0, now - stageSince) / 1000
}

export function buildRunLog(statusPayload) {
  if (!statusPayload) return []
  const stages = statusPayload.stages || {}
  const error = statusPayload.error
  const lines = []
  if (statusPayload.status === 'queued') {
    lines.push({ seconds: 0, text: 'Queued, waiting for a free worker', tone: 'active' })
    return lines
  }
  let cumulative = 0
  for (const name of BACKEND_STAGES) {
    const stage = stages[name]
    if (!stage || stage.state === 'pending') continue
    const label = STAGE_LABELS[name]
    const duration = isNumber(stage.duration_ms) ? stage.duration_ms : 0
    if (stage.state === 'running') {
      lines.push({ seconds: cumulative / 1000, text: `${label}: running…`, tone: 'active' })
      continue
    }
    cumulative += duration
    const took = isNumber(stage.duration_ms) ? ` in ${formatSeconds(stage.duration_ms)}` : ''
    if (stage.state === 'done') {
      const text = name === 'validate' ? `Validate: data loaded and preflight check passed${took}` : `${label}: done${took}`
      lines.push({ seconds: cumulative / 1000, text, tone: 'ok' })
    } else if (stage.state === 'failed') {
      const code = error && error.stage === name && error.code ? ` (${error.code})` : ''
      lines.push({ seconds: cumulative / 1000, text: `${label}: failed${took}${code}`, tone: 'error' })
    }
  }
  const failedShown = lines.some((line) => line.tone === 'error')
  if (statusPayload.status === 'completed') lines.push({ seconds: cumulative / 1000, text: 'Analysis completed', tone: 'ok' })
  if (statusPayload.status === 'partial') lines.push({ seconds: cumulative / 1000, text: 'Analysis finished with a failed step; the rest is saved', tone: 'error' })
  if (statusPayload.status === 'failed' && !failedShown) {
    lines.push({ seconds: cumulative / 1000, text: `Analysis stopped${error?.code ? ` (${error.code})` : ''}`, tone: 'error' })
  }
  return lines
}

export function statusFromAnalysis(analysis) {
  if (!analysis) return null
  const stages = analysis.result?.stages || Object.fromEntries(BACKEND_STAGES.map((name) => [name, { state: 'pending', duration_ms: null }]))
  return { analysis_id: analysis.id, status: analysis.status, stage: analysis.stage, stages, error: analysis.error || null }
}

export function hasResult(analysis) {
  return Boolean(analysis?.result?.backtest)
}
