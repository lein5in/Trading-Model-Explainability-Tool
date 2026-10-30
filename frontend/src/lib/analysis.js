import { describeFailure } from './errors.js'

export function collectErrors(analysis) {
  const errors = Array.isArray(analysis?.result?.errors) ? analysis.result.errors : []
  if (errors.length) return errors
  return analysis?.error ? [analysis.error] : []
}

export function stageError(analysis, stage) {
  return collectErrors(analysis).find((error) => error?.stage === stage) || null
}

export function unavailableReason(analysis, stage, fallback) {
  const error = stageError(analysis, stage)
  if (error) {
    const failure = describeFailure(error)
    return failure.message ? `${failure.title} ${failure.message}` : failure.title
  }
  const state = analysis?.result?.stages?.[stage]?.state
  if (state && state !== 'done') return `This step did not run (${state}).`
  return fallback
}

export function modelLabel(analysis) {
  const meta = analysis?.model_meta || {}
  if (meta.source === 'demo') return { name: meta.name || meta.demo_model_id || 'Demo model', kind: 'demo model' }
  return { name: meta.filename || 'Uploaded model', kind: 'uploaded model' }
}

export function tickerLabel(analysis) {
  return analysis?.result?.data?.ticker || analysis?.params?.ticker || null
}

export function explainedOutput(analysis) {
  return analysis?.result?.shap?.explained_output || analysis?.result?.predictions?.explained_output || analysis?.model_meta?.explained_output || 'model output'
}
