import { LIMITS, MODEL_EXTENSIONS } from '../config.js'

export const TICKER_PATTERN = /^[A-Z0-9][A-Z0-9.\-^=]{0,14}$/
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

export function normalizeTicker(value) {
  return String(value ?? '').trim().toUpperCase()
}

export function parseIsoDate(value) {
  const match = ISO_DATE.exec(String(value ?? '').trim())
  if (!match) return null
  const [year, month, day] = match.slice(1).map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null
  return date
}

export function addYears(date, years) {
  const year = date.getUTCFullYear() + years
  const month = date.getUTCMonth()
  const day = date.getUTCDate()
  const candidate = new Date(Date.UTC(year, month, day))
  if (candidate.getUTCMonth() !== month) return new Date(Date.UTC(year, month, 28))
  return candidate
}

export function fileExtension(name) {
  const match = /\.[^.]+$/.exec(String(name ?? ''))
  return match ? match[0].toLowerCase() : ''
}

function megabytes(bytes) {
  return `${Math.round(bytes / (1024 * 1024))} MB`
}

function checkCost(value, label) {
  const text = String(value ?? '').trim()
  if (text === '') return `${label} is required.`
  const number = Number(text)
  if (!Number.isFinite(number) || number < 0 || number > LIMITS.maxCostBps) {
    return `${label} must be between 0 and ${LIMITS.maxCostBps} bps.`
  }
  return null
}

function checkDates(startDate, endDate, required, limits) {
  const errors = {}
  const hasStart = String(startDate ?? '').trim() !== ''
  const hasEnd = String(endDate ?? '').trim() !== ''
  if (!required && !hasStart && !hasEnd) return errors
  const start = parseIsoDate(startDate)
  const end = parseIsoDate(endDate)
  if (!start) errors.startDate = 'Start date must be a valid date (YYYY-MM-DD).'
  if (!end) errors.endDate = 'End date must be a valid date (YYYY-MM-DD).'
  if (start && end) {
    if (start >= end) errors.endDate = 'End date must be after the start date.'
    else if (end > addYears(start, limits.maxYears)) errors.endDate = `The range must not exceed ${limits.maxYears} years.`
  }
  return errors
}

export function validateForm(form, limits = LIMITS) {
  const errors = {}
  const isDemo = form.modelSource === 'demo'

  if (isDemo) {
    if (!form.demoModelId) errors.model = 'Choose a demo model or upload a model file.'
  } else if (!form.modelFile) {
    errors.model = 'Choose a demo model or upload a model file.'
  } else if (!MODEL_EXTENSIONS.includes(fileExtension(form.modelFile.name))) {
    errors.model = `The model file must be ${MODEL_EXTENSIONS.join(', ')}.`
  } else if (form.modelFile.size > limits.maxModelBytes) {
    errors.model = `The model file must be at most ${megabytes(limits.maxModelBytes)}.`
  } else if (form.modelFile.size === 0) {
    errors.model = 'The model file is empty.'
  }

  const usesCsv = !isDemo && form.featureSource === 'csv'
  const ticker = normalizeTicker(form.ticker)
  if (ticker === '') {
    if (!usesCsv) errors.ticker = 'Ticker is required.'
  } else if (!TICKER_PATTERN.test(ticker)) {
    errors.ticker = "Ticker must be 1 to 15 characters: letters, digits, '.', '-', '^' or '='."
  }

  Object.assign(errors, checkDates(form.startDate, form.endDate, !usesCsv, limits))

  const feeError = checkCost(form.feeBps, 'Fee')
  if (feeError) errors.feeBps = feeError
  const slippageError = checkCost(form.slippageBps, 'Slippage')
  if (slippageError) errors.slippageBps = slippageError

  if (!isDemo) {
    if (usesCsv) {
      if (!form.csvFile) errors.features = 'Upload a CSV file with prices and features.'
      else if (fileExtension(form.csvFile.name) !== '.csv') errors.features = 'The data file must be a .csv file.'
      else if (form.csvFile.size > limits.maxCsvBytes) errors.features = `The CSV file must be at most ${megabytes(limits.maxCsvBytes)}.`
    } else {
      const count = Array.isArray(form.featureIds) ? form.featureIds.length : 0
      if (count === 0) errors.features = 'Select at least one feature.'
      else if (count > limits.maxFeatures) errors.features = `Select at most ${limits.maxFeatures} features.`
    }
  }

  const order = ['model', 'ticker', 'startDate', 'endDate', 'feeBps', 'slippageBps', 'features']
  const first = order.find((key) => errors[key])
  return { valid: !first, errors, reason: first ? errors[first] : null }
}

export function formFromAnalysis(analysis) {
  const params = analysis?.params || {}
  const meta = analysis?.model_meta || {}
  const form = {}
  if (meta.source === 'demo' && meta.demo_model_id) {
    form.modelSource = 'demo'
    form.demoModelId = meta.demo_model_id
  } else if (meta.source === 'upload') {
    form.modelSource = 'upload'
    form.modelFile = null
  }
  if (typeof params.ticker === 'string') form.ticker = params.ticker
  if (typeof params.start_date === 'string') form.startDate = params.start_date
  if (typeof params.end_date === 'string') form.endDate = params.end_date
  if (params.fee_bps != null) form.feeBps = String(params.fee_bps)
  if (params.slippage_bps != null) form.slippageBps = String(params.slippage_bps)
  if (meta.source === 'upload') {
    if (params.data_source_kind === 'csv') {
      form.featureSource = 'csv'
      form.startDate = params.start_date || ''
      form.endDate = params.end_date || ''
    } else if (Array.isArray(params.feature_ids)) {
      form.featureSource = 'catalog'
      form.featureIds = [...params.feature_ids]
    }
  }
  return form
}

export function buildRunFormData(form) {
  const data = new FormData()
  const isDemo = form.modelSource === 'demo'
  if (isDemo) data.append('demo_model_id', form.demoModelId)
  else data.append('model_file', form.modelFile)
  const ticker = normalizeTicker(form.ticker)
  if (ticker) data.append('ticker', ticker)
  if (String(form.startDate ?? '').trim()) data.append('start_date', String(form.startDate).trim())
  if (String(form.endDate ?? '').trim()) data.append('end_date', String(form.endDate).trim())
  data.append('fee_bps', String(Number(form.feeBps)))
  data.append('slippage_bps', String(Number(form.slippageBps)))
  if (!isDemo) {
    if (form.featureSource === 'csv') data.append('csv_file', form.csvFile)
    else data.append('feature_ids', JSON.stringify(form.featureIds))
  }
  return data
}
