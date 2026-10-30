import { REPORT_TIMEOUT_MS, REQUEST_TIMEOUT_MS, UPLOAD_TIMEOUT_MS } from '../config.js'

export const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

export function resolveBaseUrl(value) {
  const base = typeof value === 'string' && value.trim() ? value.trim() : DEFAULT_API_BASE_URL
  return base.replace(/\/+$/, '')
}

export class ApiError extends Error {
  constructor({ status = 0, code = 'unknown_error', message = 'Unexpected error.', details = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export const NETWORK_CODES = ['network_error', 'request_timeout']

export function isNetworkError(error) {
  return error instanceof ApiError && NETWORK_CODES.includes(error.code)
}

async function readJson(response) {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return undefined
  }
}

export function parseErrorBody(status, body) {
  if (body && typeof body === 'object' && typeof body.code === 'string') {
    return new ApiError({
      status,
      code: body.code,
      message: typeof body.message === 'string' ? body.message : `Request failed with status ${status}.`,
      details: body.details ?? null,
    })
  }
  return new ApiError({ status, code: 'http_error', message: `Request failed with status ${status}.` })
}

export function createApiClient({ baseUrl, fetchImpl } = {}) {
  const root = resolveBaseUrl(baseUrl)
  const doFetch = fetchImpl || ((...args) => globalThis.fetch(...args))

  async function request(path, { method = 'GET', json, formData, timeoutMs = REQUEST_TIMEOUT_MS } = {}) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    const init = { method, signal: controller.signal, headers: { Accept: 'application/json' } }
    if (json !== undefined) {
      init.headers['Content-Type'] = 'application/json'
      init.body = JSON.stringify(json)
    } else if (formData !== undefined) {
      init.body = formData
    }
    let response
    try {
      response = await doFetch(`${root}${path}`, init)
    } catch (error) {
      if (controller.signal.aborted || error?.name === 'AbortError') {
        throw new ApiError({ code: 'request_timeout', message: `The server did not answer within ${Math.round(timeoutMs / 1000)} seconds.` })
      }
      throw new ApiError({ code: 'network_error', message: 'The server could not be reached.' })
    } finally {
      clearTimeout(timer)
    }
    const body = await readJson(response).catch(() => undefined)
    if (!response.ok) throw parseErrorBody(response.status, body)
    if (body === undefined) {
      throw new ApiError({ status: response.status, code: 'invalid_response', message: 'The server returned an unreadable response.' })
    }
    return body
  }

  const id = (value) => encodeURIComponent(value)

  return {
    baseUrl: root,
    request,
    health: () => request('/health'),
    indicators: () => request('/indicators'),
    demoModels: () => request('/demo-models'),
    runAnalysis: (formData) => request('/analysis/run', { method: 'POST', formData, timeoutMs: UPLOAD_TIMEOUT_MS }),
    status: (analysisId) => request(`/analysis/${id(analysisId)}/status`),
    analysis: (analysisId) => request(`/analysis/${id(analysisId)}`),
    regenerateReport: (analysisId) => request(`/analysis/${id(analysisId)}/report`, { method: 'POST', timeoutMs: REPORT_TIMEOUT_MS }),
    explainSection: (analysisId, sectionId) =>
      request(`/analysis/${id(analysisId)}/explain-section`, { method: 'POST', json: { section_id: sectionId }, timeoutMs: REPORT_TIMEOUT_MS }),
  }
}

export const api = createApiClient({ baseUrl: import.meta.env.VITE_API_BASE_URL })
