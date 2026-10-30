import { isNumber } from './format.js'

export const EFFECT_MIN_POINTS = 3

export function correlation(xs, ys) {
  const pairs = []
  const length = Math.min(xs?.length ?? 0, ys?.length ?? 0)
  for (let index = 0; index < length; index += 1) {
    if (isNumber(xs[index]) && isNumber(ys[index])) pairs.push([xs[index], ys[index]])
  }
  if (pairs.length < EFFECT_MIN_POINTS) return null
  const meanX = pairs.reduce((sum, [x]) => sum + x, 0) / pairs.length
  const meanY = pairs.reduce((sum, [, y]) => sum + y, 0) / pairs.length
  let covariance = 0
  let varianceX = 0
  let varianceY = 0
  pairs.forEach(([x, y]) => {
    covariance += (x - meanX) * (y - meanY)
    varianceX += (x - meanX) ** 2
    varianceY += (y - meanY) ** 2
  })
  if (varianceX <= 1e-18 || varianceY <= 1e-18) return null
  return covariance / Math.sqrt(varianceX * varianceY)
}

export function effectDirection(values, contributions) {
  const r = correlation(values, contributions)
  if (r === null) return { direction: null, correlation: null }
  if (r > 0) return { direction: 'raises', correlation: r }
  if (r < 0) return { direction: 'lowers', correlation: r }
  return { direction: null, correlation: r }
}

export function featureColumn(sample, featureIndex, key) {
  const rows = sample?.[key]
  return Array.isArray(rows) ? rows.map((row) => (Array.isArray(row) ? row[featureIndex] : null)) : []
}

export function effectsBySample(shap) {
  const names = Array.isArray(shap?.feature_names) ? shap.feature_names : []
  return Object.fromEntries(
    names.map((name, index) => [name, effectDirection(featureColumn(shap.sample, index, 'feature_values'), featureColumn(shap.sample, index, 'contributions'))]),
  )
}
