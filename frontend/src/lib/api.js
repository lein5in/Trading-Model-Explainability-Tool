const API_BASE_URL = 'http://127.0.0.1:8000'
const TOKEN_STORAGE_KEY = 'tme_access_token'

export function setAccessToken(token) {
  localStorage.setItem(TOKEN_STORAGE_KEY, token)
}

export function getAccessToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY)
}

export function clearAccessToken() {
  localStorage.removeItem(TOKEN_STORAGE_KEY)
}

function authHeaders() {
  const token = getAccessToken()
  if (!token) {
    return {}
  }
  return { Authorization: `Bearer ${token}` }
}

export async function signUp({ email, password }) {
  const response = await fetch(`${API_BASE_URL}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(errorBody.detail || `Sign up failed with status ${response.status}`)
  }

  const data = await response.json()
  if (data.session) {
    setAccessToken(data.session.access_token)
  }
  return data
}

export async function signIn({ email, password }) {
  const response = await fetch(`${API_BASE_URL}/auth/signin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(errorBody.detail || `Sign in failed with status ${response.status}`)
  }

  const data = await response.json()
  setAccessToken(data.session.access_token)
  return data
}

export function signOut() {
  clearAccessToken()
}

export async function uploadModel({ name, signalType, expectedColumns, file }) {
  const formData = new FormData()
  formData.append('name', name)
  formData.append('signal_type', signalType)
  formData.append('expected_columns', expectedColumns.join(','))
  formData.append('file', file)

  const response = await fetch(`${API_BASE_URL}/models/upload`, {
    method: 'POST',
    headers: { ...authHeaders() },
    body: formData,
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(errorBody.detail || `Upload failed with status ${response.status}`)
  }

  return response.json()
}

export async function runAnalysis({ modelId, ticker, start, end, signalType, featureColumns }) {
  const response = await fetch(`${API_BASE_URL}/analysis/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      model_id: modelId,
      ticker,
      start,
      end,
      signal_type: signalType,
      feature_columns: featureColumns,
    }),
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(errorBody.detail || `Analysis failed with status ${response.status}`)
  }

  return response.json()
}

export async function getAnalysis({ analysisId }) {
  const response = await fetch(`${API_BASE_URL}/analysis/${analysisId}`, {
    headers: { ...authHeaders() },
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(errorBody.detail || `Fetching analysis failed with status ${response.status}`)
  }

  return response.json()
}

export async function explainSection({ analysisId, sectionName, tradeIndex }) {
  const response = await fetch(`${API_BASE_URL}/analysis/explain-section`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      analysis_id: analysisId,
      section_name: sectionName,
      trade_index: tradeIndex ?? null,
    }),
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(errorBody.detail || `Section explanation failed with status ${response.status}`)
  }

  return response.json()
}