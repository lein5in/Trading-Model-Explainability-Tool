import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, createApiClient, isNetworkError, resolveBaseUrl } from './api.js'

function jsonResponse(status, body) {
  return new Response(body === undefined ? '' : typeof body === 'string' ? body : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.useRealTimers()
})

describe('resolveBaseUrl', () => {
  it('uses the local default and strips trailing slashes', () => {
    expect(resolveBaseUrl(undefined)).toBe('http://127.0.0.1:8000')
    expect(resolveBaseUrl('  ')).toBe('http://127.0.0.1:8000')
    expect(resolveBaseUrl('https://api.example.org//')).toBe('https://api.example.org')
  })
})

describe('api client', () => {
  it('calls the base url and returns parsed JSON', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(200, { status: 'ok' }))
    const client = createApiClient({ baseUrl: 'http://host:1', fetchImpl })
    await expect(client.health()).resolves.toEqual({ status: 'ok' })
    expect(fetchImpl).toHaveBeenCalledWith('http://host:1/health', expect.objectContaining({ method: 'GET' }))
    const init = fetchImpl.mock.calls[0][1]
    expect(init.headers.Authorization).toBeUndefined()
  })

  it('parses backend error bodies into ApiError', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(429, { code: 'rate_limited', message: 'Too many.', details: { retry_after_seconds: 30 } }))
    const client = createApiClient({ fetchImpl })
    const error = await client.status('abc').catch((caught) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 429, code: 'rate_limited', message: 'Too many.', details: { retry_after_seconds: 30 } })
  })

  it('maps a non-JSON error body to http_error', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response('<html>bad gateway</html>', { status: 502 }))
    const error = await createApiClient({ fetchImpl }).analysis('x').catch((caught) => caught)
    expect(error).toMatchObject({ status: 502, code: 'http_error' })
  })

  it('flags an unreadable success body', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response('not json', { status: 200 }))
    const error = await createApiClient({ fetchImpl }).analysis('x').catch((caught) => caught)
    expect(error.code).toBe('invalid_response')
  })

  it('maps a fetch rejection to network_error', async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    const error = await createApiClient({ fetchImpl }).health().catch((caught) => caught)
    expect(error.code).toBe('network_error')
    expect(isNetworkError(error)).toBe(true)
  })

  it('aborts after the timeout and reports request_timeout', async () => {
    vi.useFakeTimers()
    const fetchImpl = vi.fn(
      (url, init) =>
        new Promise((resolve, reject) => {
          init.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
        }),
    )
    const client = createApiClient({ fetchImpl })
    const pending = client.request('/slow', { timeoutMs: 1000 }).catch((caught) => caught)
    await vi.advanceTimersByTimeAsync(999)
    expect(fetchImpl.mock.calls[0][1].signal.aborted).toBe(false)
    await vi.advanceTimersByTimeAsync(1)
    const error = await pending
    expect(error.code).toBe('request_timeout')
    expect(isNetworkError(error)).toBe(true)
  })

  it('uses a 30 s timeout by default and 120 s for uploads', async () => {
    vi.useFakeTimers()
    const hang = (url, init) =>
      new Promise((resolve, reject) => {
        init.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
      })
    const fetchImpl = vi.fn(hang)
    const client = createApiClient({ fetchImpl })
    const normal = client.indicators().catch((caught) => caught)
    const upload = client.runAnalysis(new FormData()).catch((caught) => caught)
    await vi.advanceTimersByTimeAsync(30000)
    expect((await normal).code).toBe('request_timeout')
    expect(fetchImpl.mock.calls[1][1].signal.aborted).toBe(false)
    await vi.advanceTimersByTimeAsync(90000)
    expect((await upload).code).toBe('request_timeout')
  })

  it('sends JSON for explain-section and multipart for runs', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { ok: true }))
    const client = createApiClient({ fetchImpl })
    await client.explainSection('id 1', 'summary')
    const [url, init] = fetchImpl.mock.calls[0]
    expect(url).toBe('http://127.0.0.1:8000/analysis/id%201/explain-section')
    expect(init.method).toBe('POST')
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(init.body)).toEqual({ section_id: 'summary' })
    const form = new FormData()
    await client.runAnalysis(form)
    expect(fetchImpl.mock.calls[1][1].body).toBe(form)
    expect(fetchImpl.mock.calls[1][1].headers['Content-Type']).toBeUndefined()
  })
})
