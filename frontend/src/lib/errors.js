import { SHAP_ADDITIVITY_LIMIT } from '../config.js'

export const ERROR_MESSAGES = {
  network_error: 'The server could not be reached. Check your connection and try again.',
  request_timeout: 'The server took too long to answer.',
  invalid_response: 'The server returned an unreadable response.',
  http_error: 'The request failed.',
  unknown_error: 'Something went wrong.',
  not_found: 'This page or resource does not exist.',
  invalid_request: 'The request is missing or has invalid fields.',
  analysis_not_found: 'This analysis does not exist or has expired.',
  analysis_not_ready: 'The analysis has no backtest yet, so there is nothing to report on.',
  invalid_section: 'This report section does not exist.',
  missing_model: 'Choose a demo model or upload a model file.',
  unknown_demo_model: 'This demo model is not available.',
  upload_disabled: 'Model uploads are disabled on this server. Choose a demo model.',
  unsupported_model_file: 'The model file must be .pkl, .pickle or .joblib.',
  model_file_too_large: 'The model file is too large.',
  csv_too_large: 'The CSV file is too large.',
  empty_file: 'The uploaded file is empty.',
  invalid_date: 'Dates must use the YYYY-MM-DD format.',
  invalid_date_range: 'The start date must be before the end date.',
  date_range_too_long: 'The date range is too long.',
  invalid_ticker: 'The ticker is not valid.',
  missing_features: 'Select at least one feature.',
  invalid_features: 'The feature list is not valid.',
  too_many_features: 'Too many features were selected.',
  unknown_feature: 'One or more features are not in the indicator catalog.',
  invalid_cost: 'Fee and slippage must be between 0 and 100 basis points.',
  rate_limited: 'Too many analyses from this address. Try again later.',
  daily_cap_reached: 'The daily number of analyses has been reached. Try again tomorrow.',
  database_unavailable: 'The database could not be reached.',
  csv_unreadable: 'The CSV file could not be read.',
  csv_duplicate_columns: 'The CSV file has duplicate column names.',
  csv_missing_columns: 'The CSV file is missing required price columns.',
  csv_no_features: 'The CSV file has no feature columns.',
  csv_empty: 'The CSV file has no rows.',
  csv_too_many_rows: 'The CSV file has too many rows.',
  csv_invalid_dates: 'The CSV file has invalid dates.',
  csv_duplicate_dates: 'The CSV file has duplicate dates.',
  csv_dates_not_increasing: 'The CSV dates must be in increasing order.',
  csv_no_valid_rows: 'The CSV file has no valid rows.',
  data_unavailable: 'Market data for this ticker and period could not be fetched.',
  insufficient_data: 'Not enough data: no bar has every feature defined.',
  preflight_failed: 'The model did not pass the preflight check.',
  validate_failed: 'The input data could not be prepared.',
  predict_failed: 'The model failed while predicting.',
  backtest_failed: 'The backtest could not be computed.',
  regimes_failed: 'Market regimes could not be detected.',
  shap_failed: 'The SHAP explanation could not be computed.',
  shap_no_rows: 'No bar could be explained with SHAP.',
  shap_additivity_failed: 'SHAP check failed, so the explanations were not shown.',
  timeout: 'The analysis exceeded the 5-minute time limit.',
  interrupted: 'The analysis was interrupted by a server restart.',
  internal_error: 'An unexpected server error stopped the analysis.',
  report_failed: 'The report could not be generated.',
  report_api_key_missing: 'The report service is not configured on this server.',
  report_truncated: 'The report was cut off before it was finished.',
  report_refused: 'The language model declined to write the report.',
  report_invalid_output: 'The language model returned a report in an unexpected format.',
  report_api_error: 'The report service could not be reached.',
}

export const PREFLIGHT_REASONS = {
  feature_mismatch: 'The feature names do not match the ones the model was trained on.',
  feature_count_mismatch: 'The model expects a different number of features.',
  unsupported_model: 'This kind of model is not supported.',
  signal_contract_violation: 'The model returned outputs that are not valid signals.',
  predict_failed: 'The model raised an error on the first rows.',
  timeout: 'The preflight check timed out.',
  sandbox_output_too_large: 'The model produced too much output.',
  sandbox_error: 'The sandbox could not run the model.',
}

export function errorMessage(code, fallback) {
  if (code && ERROR_MESSAGES[code]) return ERROR_MESSAGES[code]
  if (code && /^report_/.test(code)) return ERROR_MESSAGES.report_failed
  if (typeof fallback === 'string' && fallback.trim()) return fallback
  return ERROR_MESSAGES.unknown_error
}

function listText(values) {
  return Array.isArray(values) && values.length ? values.join(', ') : 'none'
}

export function describeFailure(error) {
  if (!error) return { title: ERROR_MESSAGES.unknown_error, message: null, facts: [] }
  const code = error.code || 'unknown_error'
  const details = error.details || {}
  const backendMessage = typeof error.message === 'string' ? error.message : null
  const known = Boolean(ERROR_MESSAGES[code]) || /^report_/.test(code)
  const title = errorMessage(code, backendMessage)
  const facts = []
  let message = known ? backendMessage : null

  if (code === 'preflight_failed') {
    message = PREFLIGHT_REASONS[details.reason] || backendMessage
    if (details.reason === 'feature_mismatch') {
      facts.push({ label: 'Expected by the model, not provided', value: listText(details.missing), mono: true })
      facts.push({ label: 'Provided, unknown to the model', value: listText(details.unexpected), mono: true })
      if (Array.isArray(details.model_features)) {
        facts.push({ label: 'Model features', value: listText(details.model_features), mono: true })
      }
    } else if (details.reason === 'feature_count_mismatch') {
      facts.push({ label: 'Expected', value: String(details.expected), mono: true })
      facts.push({ label: 'Provided', value: String(details.provided), mono: true })
    }
  } else if (code === 'shap_additivity_failed') {
    message = 'The contributions did not add up to the model output. Rather than show numbers that cannot be trusted, TME stopped this step. The backtest and regimes are saved.'
    facts.push({ label: 'Largest gap', value: details.max_gap == null ? 'n/a' : String(details.max_gap), mono: true })
    const limit = typeof details.epsilon === 'number' && Number.isFinite(details.epsilon) ? details.epsilon : SHAP_ADDITIVITY_LIMIT
    facts.push({ label: 'Limit', value: String(limit), mono: true })
  } else if (code === 'rate_limited' && details.retry_after_seconds != null) {
    facts.push({ label: 'Retry after', value: `${details.retry_after_seconds} s`, mono: true })
  } else if (code === 'daily_cap_reached' && details.daily_cap != null) {
    facts.push({ label: 'Daily cap', value: String(details.daily_cap), mono: true })
  } else if (code === 'data_unavailable' && details.ticker) {
    facts.push({ label: 'Ticker', value: String(details.ticker), mono: true })
  }

  if (message === title) message = null
  return { code, title, message, facts, stage: error.stage || null }
}
