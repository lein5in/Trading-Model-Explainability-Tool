import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadModel, runAnalysis } from '../lib/api'
import { useAnalysis } from '../lib/AnalysisContext'

function UploadPage() {
  const navigate = useNavigate()
  const { setAnalysisResult, setRegisteredModel } = useAnalysis()

  const [modelName, setModelName] = useState('')
  const [signalType, setSignalType] = useState('discrete')
  const [expectedColumns, setExpectedColumns] = useState('open,close')
  const [file, setFile] = useState(null)

  const [ticker, setTicker] = useState('AAPL')
  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2024-12-01')

  const [status, setStatus] = useState('idle')
  const [errorMessage, setErrorMessage] = useState(null)

  async function handleSubmit(event) {
    event.preventDefault()
    setErrorMessage(null)

    if (!file) {
      setErrorMessage('A model file is required.')
      return
    }

    const columnsList = expectedColumns
      .split(',')
      .map((c) => c.trim())
      .filter((c) => c.length > 0)

    try {
      setStatus('uploading')
      const registered = await uploadModel({
        name: modelName,
        signalType,
        expectedColumns: columnsList,
        file,
      })
      setRegisteredModel(registered)

      setStatus('analyzing')
      const result = await runAnalysis({
        modelId: registered.id,
        ticker,
        start: startDate,
        end: endDate,
        signalType,
        featureColumns: columnsList,
      })
      setAnalysisResult(result)

      setStatus('done')
      navigate(`/dashboard/${result.analysis_id}`)
    } catch (err) {
      setStatus('error')
      setErrorMessage(err.message)
    }
  }

  const isBusy = status === 'uploading' || status === 'analyzing'

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 font-mono">
      <div className="max-w-2xl mx-auto px-6 py-12">
        <h1 className="text-xl font-bold tracking-tight text-neutral-100 mb-1">
          Trading Explainability Tool
        </h1>
        <p className="text-sm text-neutral-500 mb-8">
          Upload a model and run a full backtest and explainability analysis.
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <fieldset className="border border-neutral-800 rounded p-4 space-y-4">
            <legend className="px-2 text-xs uppercase tracking-wider text-neutral-500">
              Model
            </legend>

            <div>
              <label className="block text-xs text-neutral-400 mb-1">Model name</label>
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                required
                className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-neutral-500"
              />
            </div>

            <div>
              <label className="block text-xs text-neutral-400 mb-1">Signal type</label>
              <select
                value={signalType}
                onChange={(e) => setSignalType(e.target.value)}
                className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-neutral-500"
              >
                <option value="discrete">Discrete (-1 / 0 / 1)</option>
                <option value="continuous">Continuous [-1, 1]</option>
              </select>
            </div>

            <div>
              <label className="block text-xs text-neutral-400 mb-1">
                Expected feature columns (comma-separated)
              </label>
              <input
                type="text"
                value={expectedColumns}
                onChange={(e) => setExpectedColumns(e.target.value)}
                required
                className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-neutral-500"
              />
            </div>

            <div>
              <label className="block text-xs text-neutral-400 mb-1">
                Model file (.pkl or .joblib)
              </label>
              <input
                type="file"
                accept=".pkl,.joblib"
                onChange={(e) => setFile(e.target.files[0])}
                required
                className="w-full text-sm text-neutral-300 file:mr-3 file:py-2 file:px-3 file:rounded file:border file:border-neutral-700 file:bg-neutral-900 file:text-neutral-200 file:text-sm"
              />
            </div>
          </fieldset>

          <fieldset className="border border-neutral-800 rounded p-4 space-y-4">
            <legend className="px-2 text-xs uppercase tracking-wider text-neutral-500">
              Data
            </legend>

            <div>
              <label className="block text-xs text-neutral-400 mb-1">Ticker</label>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                required
                className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-neutral-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-neutral-400 mb-1">Start date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  required
                  className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-neutral-500"
                />
              </div>
              <div>
                <label className="block text-xs text-neutral-400 mb-1">End date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  required
                  className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-neutral-500"
                />
              </div>
            </div>
          </fieldset>

          {errorMessage && (
            <div className="border border-red-900 bg-red-950 text-red-400 text-sm rounded px-3 py-2">
              {errorMessage}
            </div>
          )}

          <button
            type="submit"
            disabled={isBusy}
            className="w-full bg-neutral-100 text-neutral-950 font-semibold text-sm rounded px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white transition-colors"
          >
            {status === 'uploading' && 'Uploading model...'}
            {status === 'analyzing' && 'Running analysis...'}
            {(status === 'idle' || status === 'error') && 'Run Analysis'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default UploadPage