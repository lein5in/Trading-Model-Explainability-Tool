import { describe, expect, it } from 'vitest'
import { addYears, buildRunFormData, fileExtension, formFromAnalysis, parseIsoDate, validateForm } from './validation.js'

const limits = { maxModelBytes: 1000, maxCsvBytes: 500, maxYears: 10, maxFeatures: 3, maxCostBps: 100 }

function demoForm(patch = {}) {
  return {
    modelSource: 'demo',
    demoModelId: 'demo_xgboost',
    modelFile: null,
    ticker: 'SPY',
    startDate: '2018-01-02',
    endDate: '2024-12-31',
    feeBps: '5',
    slippageBps: '2',
    featureSource: 'catalog',
    featureIds: [],
    csvFile: null,
    ...patch,
  }
}

function uploadForm(patch = {}) {
  return demoForm({ modelSource: 'upload', modelFile: { name: 'model.pkl', size: 100 }, featureIds: ['rsi_14'], ...patch })
}

describe('parseIsoDate', () => {
  it('accepts real dates and rejects impossible ones', () => {
    expect(parseIsoDate('2024-02-29')).not.toBeNull()
    expect(parseIsoDate('2023-02-29')).toBeNull()
    expect(parseIsoDate('2024-13-01')).toBeNull()
    expect(parseIsoDate('24-01-01')).toBeNull()
  })

  it('adds years like the backend, clamping Feb 29 to Feb 28', () => {
    expect(addYears(parseIsoDate('2020-02-29'), 1).toISOString().slice(0, 10)).toBe('2021-02-28')
    expect(addYears(parseIsoDate('2014-01-02'), 10).toISOString().slice(0, 10)).toBe('2024-01-02')
  })
})

describe('validateForm', () => {
  it('accepts a valid demo submission without features', () => {
    expect(validateForm(demoForm(), limits)).toEqual({ valid: true, errors: {}, reason: null })
  })

  it('validates the ticker format', () => {
    expect(validateForm(demoForm({ ticker: ' brk.b ' }), limits).valid).toBe(true)
    expect(validateForm(demoForm({ ticker: '^GSPC' }), limits).errors.ticker).toBeTruthy()
    expect(validateForm(demoForm({ ticker: 'TOO_LONG_TICKER_NAME' }), limits).errors.ticker).toMatch(/1 to 15/)
    expect(validateForm(demoForm({ ticker: '' }), limits).errors.ticker).toBe('Ticker is required.')
  })

  it('requires the end date after the start date', () => {
    const result = validateForm(demoForm({ startDate: '2024-01-01', endDate: '2024-01-01' }), limits)
    expect(result.errors.endDate).toBe('End date must be after the start date.')
    expect(result.reason).toBe('End date must be after the start date.')
  })

  it('caps the range at the configured number of years', () => {
    expect(validateForm(demoForm({ startDate: '2014-01-02', endDate: '2024-01-02' }), limits).valid).toBe(true)
    expect(validateForm(demoForm({ startDate: '2014-01-02', endDate: '2024-01-03' }), limits).errors.endDate).toMatch(/10 years/)
  })

  it('rejects malformed dates', () => {
    expect(validateForm(demoForm({ startDate: '2018/01/02' }), limits).errors.startDate).toMatch(/YYYY-MM-DD/)
  })

  it('checks costs between 0 and 100 bps', () => {
    expect(validateForm(demoForm({ feeBps: '-1' }), limits).errors.feeBps).toBeTruthy()
    expect(validateForm(demoForm({ slippageBps: '101' }), limits).errors.slippageBps).toBeTruthy()
    expect(validateForm(demoForm({ feeBps: '' }), limits).errors.feeBps).toBe('Fee is required.')
    expect(validateForm(demoForm({ feeBps: '0', slippageBps: '100' }), limits).valid).toBe(true)
  })

  it('checks the uploaded model extension and size', () => {
    expect(validateForm(uploadForm({ modelFile: { name: 'model.onnx', size: 10 } }), limits).errors.model).toMatch(/\.pkl/)
    expect(validateForm(uploadForm({ modelFile: { name: 'MODEL.JOBLIB', size: 10 } }), limits).valid).toBe(true)
    expect(validateForm(uploadForm({ modelFile: { name: 'model.pkl', size: 1001 } }), limits).errors.model).toMatch(/at most/)
    expect(validateForm(uploadForm({ modelFile: null }), limits).errors.model).toBeTruthy()
  })

  it('requires between one and the maximum number of catalog features for uploads', () => {
    expect(validateForm(uploadForm({ featureIds: [] }), limits).errors.features).toBe('Select at least one feature.')
    expect(validateForm(uploadForm({ featureIds: ['a', 'b', 'c', 'd'] }), limits).errors.features).toMatch(/at most 3/)
  })

  it('requires a csv file in csv mode and makes ticker and dates optional', () => {
    const missing = validateForm(uploadForm({ featureSource: 'csv', ticker: '', startDate: '', endDate: '' }), limits)
    expect(missing.errors).toEqual({ features: 'Upload a CSV file with prices and features.' })
    const ok = validateForm(uploadForm({ featureSource: 'csv', ticker: '', startDate: '', endDate: '', csvFile: { name: 'd.csv', size: 10 } }), limits)
    expect(ok.valid).toBe(true)
    const oneDate = validateForm(uploadForm({ featureSource: 'csv', endDate: '', csvFile: { name: 'd.csv', size: 10 } }), limits)
    expect(oneDate.errors.endDate).toBeTruthy()
  })

  it('reports the first error in form order as the reason', () => {
    const result = validateForm(demoForm({ demoModelId: '', ticker: '' }), limits)
    expect(result.reason).toBe('Choose a demo model or upload a model file.')
  })
})

describe('formFromAnalysis', () => {
  it('rebuilds the demo form from stored params', () => {
    const form = formFromAnalysis({
      params: { ticker: 'QQQ', start_date: '2019-01-02', end_date: '2024-12-31', fee_bps: 5, slippage_bps: 2, data_source_kind: 'ticker', feature_ids: ['a'] },
      model_meta: { source: 'demo', demo_model_id: 'demo_mlp' },
    })
    expect(form).toEqual({ modelSource: 'demo', demoModelId: 'demo_mlp', ticker: 'QQQ', startDate: '2019-01-02', endDate: '2024-12-31', feeBps: '5', slippageBps: '2' })
  })

  it('keeps the catalog selection for uploads and asks for the file again', () => {
    const form = formFromAnalysis({
      params: { ticker: 'SPY', start_date: '2018-01-02', end_date: '2020-01-02', fee_bps: 1, slippage_bps: 0, data_source_kind: 'ticker', feature_ids: ['rsi_14'] },
      model_meta: { source: 'upload', filename: 'm.pkl' },
    })
    expect(form).toMatchObject({ modelSource: 'upload', modelFile: null, featureSource: 'catalog', featureIds: ['rsi_14'] })
  })

  it('returns an empty form without an analysis', () => {
    expect(formFromAnalysis(null)).toEqual({})
  })
})

describe('buildRunFormData', () => {
  it('sends only the demo id and market fields for demos', () => {
    const data = buildRunFormData(demoForm({ ticker: 'spy', featureIds: ['x'] }))
    expect(data.get('demo_model_id')).toBe('demo_xgboost')
    expect(data.get('ticker')).toBe('SPY')
    expect(data.get('feature_ids')).toBeNull()
    expect(data.get('fee_bps')).toBe('5')
  })

  it('sends feature ids as a JSON list for uploads', () => {
    const file = new Blob(['x'])
    const data = buildRunFormData(uploadForm({ modelFile: file, featureIds: ['rsi_14', 'vol_20d'] }))
    expect(data.get('demo_model_id')).toBeNull()
    expect(data.get('feature_ids')).toBe('["rsi_14","vol_20d"]')
    expect(data.get('model_file')).toBeInstanceOf(Blob)
  })

  it('reads file extensions case-insensitively', () => {
    expect(fileExtension('a.b.PKL')).toBe('.pkl')
    expect(fileExtension('noext')).toBe('')
  })
})
