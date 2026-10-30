import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { DEFAULT_DEMO_MODEL_ID, DEFAULT_FORM, JOB_TIMEOUT_SECONDS, LIMITS, MODEL_EXTENSIONS } from '../config.js'
import { CloseIcon, UploadIcon } from '../components/Icons.jsx'
import { ErrorAlert, Main, PointInTimeNotice, Segmented, Skeleton } from '../components/ui.jsx'
import { useDocumentTitle } from '../hooks/useDocumentTitle.js'
import { useHistory } from '../hooks/useHistory.js'
import { api } from '../lib/api.js'
import { describeFailure } from '../lib/errors.js'
import { formatBytes, formatSignedPercent, relativeTime, signColor } from '../lib/format.js'
import { historyStore } from '../lib/history.js'
import { buildRunFormData, normalizeTicker, validateForm } from '../lib/validation.js'

function initialForm(state) {
  const base = {
    modelSource: 'demo',
    demoModelId: DEFAULT_DEMO_MODEL_ID,
    modelFile: null,
    featureSource: 'catalog',
    featureIds: [],
    csvFile: null,
    ...DEFAULT_FORM,
  }
  return state && state.form ? { ...base, ...state.form } : base
}

function useLoad(loader) {
  const [state, setState] = useState({ loading: true, error: null, data: null })
  useEffect(() => {
    let active = true
    loader()
      .then((data) => active && setState({ loading: false, error: null, data }))
      .catch((error) => active && setState({ loading: false, error, data: null }))
    return () => {
      active = false
    }
  }, [loader])
  return state
}

const loadDemoModels = () => api.demoModels().then((body) => (Array.isArray(body?.models) ? body.models : []))
const loadIndicators = () => api.indicators().then((body) => (Array.isArray(body?.indicators) ? body.indicators : []))

function SectionTitle({ number, children }) {
  return (
    <h2 className="m-0 text-[17px] font-semibold">
      <span className="mono mr-2.5 text-ac">{number}</span>
      {children}
    </h2>
  )
}

function FilePicker({ id, accept, file, onFile, onClear, title, hint, icon = false }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  return (
    <div
      className={`flex flex-wrap items-center gap-4 rounded-[10px] border-[1.5px] border-dashed bg-bg px-5 py-[18px] ${dragging ? 'border-ac' : 'border-bd'}`}
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        const dropped = event.dataTransfer?.files?.[0]
        if (dropped) onFile(dropped)
      }}
    >
      {icon && <UploadIcon size={28} stroke="var(--color-mu)" />}
      <div className="flex min-w-0 flex-[1_1_280px] flex-col gap-1">
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-[13px] leading-[1.45] text-mu">{hint}</span>
        {file && (
          <span className="mt-1 flex items-center gap-2 text-[13px]">
            <span className="mono truncate text-tx">{file.name}</span>
            <span className="mono text-mu">{formatBytes(file.size)}</span>
            <button type="button" className="btn btn-sm h-7 px-2" onClick={onClear} aria-label={`Remove ${file.name}`}>
              <CloseIcon size={14} />
            </button>
          </span>
        )}
      </div>
      <input
        ref={inputRef}
        id={id}
        type="file"
        accept={accept}
        aria-label={title}
        tabIndex={-1}
        className="sr-only"
        onChange={(event) => {
          const picked = event.target.files?.[0]
          if (picked) onFile(picked)
          event.target.value = ''
        }}
      />
      <button type="button" className="btn" onClick={() => inputRef.current?.click()} aria-controls={id}>
        Browse files
      </button>
    </div>
  )
}

function DemoCard({ model, selected, onSelect }) {
  const trained = model.trained_on || {}
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      className={`flex min-w-0 flex-[1_1_220px] flex-col gap-2 rounded-[10px] border-[1.5px] bg-bg p-4 text-left text-tx ${selected ? 'border-ac' : 'border-bd hover:border-mu'}`}
    >
      <span className="flex w-full items-center justify-between gap-2">
        <span className="mono truncate text-[11px] tracking-[.08em] text-mu uppercase">{model.family}</span>
        <span
          className={`h-2.5 w-2.5 flex-none rounded-full ${selected ? 'bg-ac' : 'border-[1.5px] border-mu'}`}
          aria-hidden="true"
        />
      </span>
      <span className="text-[15px] font-semibold">{model.name}</span>
      <span className="text-[13px] leading-[1.45] text-mu">
        Explains <span className="mono text-tx">{model.explained_output}</span> · {model.feature_columns?.length ?? 0} features
        {trained.ticker && (
          <>
            {' '}
            · trained on <span className="mono">{trained.ticker}</span> <span className="mono">{trained.start}</span> →{' '}
            <span className="mono">{trained.end}</span>
          </>
        )}
      </span>
    </button>
  )
}

function Field({ label, error, children, className = '' }) {
  return (
    <label className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <span className="lbl">{label}</span>
      {children}
      {error && <span className="text-xs text-neg">{error}</span>}
    </label>
  )
}

function HistoryPanel({ entries, expired, onRemove }) {
  return (
    <section id="history" className="card flex scroll-mt-4 flex-col py-2" aria-labelledby="history-title">
      <div className="flex items-baseline justify-between gap-2 px-6 pt-4 pb-2">
        <h2 id="history-title" className="lbl m-0">
          Recent analyses
        </h2>
        <span className="text-xs text-mu">Saved in this browser</span>
      </div>
      {entries.length === 0 && <p className="m-0 border-t border-bd px-6 py-4 text-[13px] text-mu">No analyses yet. Runs you start here are listed for quick access.</p>}
      {entries.map((entry) => {
        const isExpired = expired.has(entry.id)
        const body = (
          <>
            <span className="flex justify-between gap-2">
              <span className="mono text-sm font-semibold">{entry.ticker || 'CSV data'}</span>
              {isExpired ? (
                <span className="mono text-[13px] text-mu">expired</span>
              ) : (
                <span className={`mono text-[13px] ${signColor(entry.totalReturn)}`}>{formatSignedPercent(entry.totalReturn)}</span>
              )}
            </span>
            <span className="flex justify-between gap-2 text-[12.5px] text-mu">
              <span className="truncate">
                {entry.model || 'Model'}
                {entry.startDate && entry.endDate ? ` · ${entry.startDate.slice(0, 4)} to ${entry.endDate.slice(0, 4)}` : ''}
              </span>
              <span className="flex-none">{relativeTime(entry.createdAt)}</span>
            </span>
          </>
        )
        return isExpired ? (
          <div key={entry.id} className="flex items-center gap-3 border-t border-bd px-6 py-3">
            <div className="flex min-w-0 flex-1 flex-col gap-1">{body}</div>
            <button type="button" className="btn btn-sm" onClick={() => onRemove(entry.id)} aria-label={`Remove expired analysis ${entry.ticker || entry.id} from history`}>
              Remove
            </button>
          </div>
        ) : (
          <Link key={entry.id} to={`/analysis/${entry.id}`} className="flex flex-col gap-1 border-t border-bd px-6 py-3 text-tx no-underline hover:bg-s2">
            {body}
          </Link>
        )
      })}
    </section>
  )
}

function useHistoryChecks(entries) {
  const [expired, setExpired] = useState(() => new Set())
  const checked = useRef(new Set())
  useEffect(() => {
    let active = true
    entries.forEach((entry) => {
      if (checked.current.has(entry.id)) return
      checked.current.add(entry.id)
      api
        .status(entry.id)
        .then((status) => {
          const terminal = status?.status === 'completed' || status?.status === 'partial'
          if (!terminal || entry.totalReturn != null) return null
          return api.analysis(entry.id).then((analysis) => {
            const metrics = analysis?.result?.backtest?.metrics?.strategy
            if (metrics) historyStore.update(entry.id, { totalReturn: metrics.total_return, sharpe: metrics.sharpe })
          })
        })
        .catch((error) => {
          if (active && error?.status === 404) setExpired((previous) => new Set(previous).add(entry.id))
        })
    })
    return () => {
      active = false
    }
  }, [entries])
  return expired
}

export default function HomePage() {
  useDocumentTitle('new analysis')
  const location = useLocation()
  const navigate = useNavigate()
  const [form, setForm] = useState(() => initialForm(location.state))
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [touched, setTouched] = useState(false)
  const demos = useLoad(loadDemoModels)
  const indicators = useLoad(loadIndicators)
  const history = useHistory()
  const expired = useHistoryChecks(history)

  useEffect(() => {
    if (location.hash === '#history') document.getElementById('history')?.scrollIntoView({ block: 'start' })
  }, [location.hash])

  const demoList = useMemo(() => demos.data || [], [demos.data])
  const indicatorList = useMemo(() => indicators.data || [], [indicators.data])
  const selectedDemo = form.modelSource === 'demo' ? demoList.find((model) => model.id === form.demoModelId) : null
  const validation = useMemo(() => validateForm(form), [form])
  const isDemo = form.modelSource === 'demo'

  const update = (patch) => {
    setForm((previous) => ({ ...previous, ...patch }))
    setSubmitError(null)
  }

  const toggleFeature = (featureId) => {
    setForm((previous) => {
      const has = previous.featureIds.includes(featureId)
      return { ...previous, featureIds: has ? previous.featureIds.filter((item) => item !== featureId) : [...previous.featureIds, featureId] }
    })
  }

  const submit = async (event) => {
    event.preventDefault()
    setTouched(true)
    if (!validation.valid || submitting) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const body = await api.runAnalysis(buildRunFormData(form))
      const id = body?.analysis_id
      if (!id) throw new Error('missing analysis id')
      historyStore.add({
        id,
        ticker: normalizeTicker(form.ticker) || null,
        model: isDemo ? selectedDemo?.name || form.demoModelId : form.modelFile?.name,
        startDate: form.startDate || null,
        endDate: form.endDate || null,
        createdAt: new Date().toISOString(),
        totalReturn: null,
        sharpe: null,
      })
      navigate(`/analysis/${id}`)
    } catch (error) {
      setSubmitError(describeFailure(error))
      setSubmitting(false)
    }
  }

  const fieldError = (name) => (touched || String(form[name] ?? '') !== '' ? validation.errors[name] : null)
  const featureSummary = isDemo
    ? `${selectedDemo?.feature_columns?.length ?? 0} model features`
    : form.featureSource === 'csv'
      ? 'CSV columns'
      : `${form.featureIds.length} indicators`
  const modelName = isDemo ? (selectedDemo ? `${selectedDemo.name} (demo)` : 'none') : form.modelFile?.name || 'none'
  const usesCsv = !isDemo && form.featureSource === 'csv'

  return (
    <Main className="gap-8 pt-10">
      <div className="flex max-w-[760px] flex-col gap-3">
        <h1 className="m-0 text-[30px] leading-[1.12] font-semibold tracking-[-.02em] sm:text-[38px]">Explain how a trading model behaves.</h1>
        <p className="m-0 text-base leading-[1.55] text-mu">
          Pick a demo model or upload your own. TME backtests it, detects market regimes, explains each decision with SHAP and writes a report in which every
          number is checked against the data.
        </p>
      </div>

      <form className="flex flex-wrap items-start gap-6" onSubmit={submit} noValidate>
        <div className="flex min-w-0 flex-[999_1_640px] flex-col gap-6">
          <section className="card flex flex-col gap-5 p-6" aria-labelledby="model-title">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <span id="model-title">
                <SectionTitle number="01">Model</SectionTitle>
              </span>
              <span className="text-[13px] text-mu">Try a demo in one click</span>
            </div>
            <div className="flex flex-wrap gap-3" role="group" aria-label="Demo models">
              {demos.loading && [0, 1, 2, 3].map((key) => <Skeleton key={key} className="h-[132px] flex-[1_1_220px]" />)}
              {demos.error && <p className="m-0 text-[13px] text-neg">Demo models could not be loaded: {describeFailure(demos.error).title}</p>}
              {!demos.loading && !demos.error && demoList.length === 0 && <p className="m-0 text-[13px] text-mu">No demo models are available.</p>}
              {demoList.map((model) => (
                <DemoCard
                  key={model.id}
                  model={model}
                  selected={isDemo && form.demoModelId === model.id}
                  onSelect={() => update({ modelSource: 'demo', demoModelId: model.id })}
                />
              ))}
            </div>
            <FilePicker
              id="model-file"
              icon
              accept={MODEL_EXTENSIONS.join(',')}
              file={form.modelFile}
              onFile={(file) => update({ modelSource: 'upload', modelFile: file })}
              onClear={() => update({ modelFile: null, modelSource: demoList.length ? 'demo' : 'upload' })}
              title="Or upload your own model"
              hint={
                <>
                  <span className="mono">.pkl</span>, <span className="mono">.pickle</span> or <span className="mono">.joblib</span> · scikit-learn, XGBoost, LightGBM ·
                  max {formatBytes(LIMITS.maxModelBytes)}. It runs in an isolated sandbox with no network access and is deleted after the analysis.
                </>
              }
            />
            {!isDemo && form.modelFile && <p className="m-0 text-[13px] text-mu">Uploaded model selected. Pick a demo card to switch back.</p>}
            {(touched || form.modelFile) && validation.errors.model && <p className="m-0 text-xs text-neg">{validation.errors.model}</p>}
          </section>

          <section className="card flex flex-col gap-5 p-6" aria-labelledby="data-title">
            <span id="data-title">
              <SectionTitle number="02">Market data and costs</SectionTitle>
            </span>
            <div className="flex flex-wrap gap-4">
              <Field label={usesCsv ? 'Ticker (optional)' : 'Ticker'} error={fieldError('ticker')} className="flex-[1_1_140px]">
                <input
                  className="field uppercase"
                  value={form.ticker}
                  onChange={(event) => update({ ticker: event.target.value })}
                  autoComplete="off"
                  spellCheck={false}
                  aria-invalid={Boolean(fieldError('ticker'))}
                />
              </Field>
              <Field label="Start date" error={fieldError('startDate')} className="flex-[1_1_170px]">
                <input
                  className="field"
                  value={form.startDate}
                  placeholder="YYYY-MM-DD"
                  onChange={(event) => update({ startDate: event.target.value })}
                  aria-invalid={Boolean(fieldError('startDate'))}
                />
              </Field>
              <Field label="End date" error={fieldError('endDate')} className="flex-[1_1_170px]">
                <input
                  className="field"
                  value={form.endDate}
                  placeholder="YYYY-MM-DD"
                  onChange={(event) => update({ endDate: event.target.value })}
                  aria-invalid={Boolean(fieldError('endDate'))}
                />
              </Field>
              <Field label="Fee (bps)" error={fieldError('feeBps')} className="flex-[1_1_110px]">
                <input
                  className="field"
                  inputMode="decimal"
                  value={form.feeBps}
                  onChange={(event) => update({ feeBps: event.target.value })}
                  aria-invalid={Boolean(fieldError('feeBps'))}
                />
              </Field>
              <Field label="Slippage (bps)" error={fieldError('slippageBps')} className="flex-[1_1_110px]">
                <input
                  className="field"
                  inputMode="decimal"
                  value={form.slippageBps}
                  onChange={(event) => update({ slippageBps: event.target.value })}
                  aria-invalid={Boolean(fieldError('slippageBps'))}
                />
              </Field>
            </div>
            <p className="m-0 text-[13px] leading-normal text-mu">
              Daily bars from Yahoo Finance via yfinance. Maximum range: {LIMITS.maxYears} years. Costs apply on entry and on exit.
              {usesCsv && ' With a CSV upload, the ticker and dates are optional: leave both dates empty to use the whole file.'}
            </p>
          </section>

          <section className="card flex flex-col gap-5 p-6" aria-labelledby="features-title">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span id="features-title">
                <SectionTitle number="03">Features</SectionTitle>
              </span>
              {!isDemo && (
                <Segmented
                  label="Feature source"
                  value={form.featureSource}
                  onChange={(value) => update({ featureSource: value })}
                  options={[
                    { value: 'catalog', label: 'Indicator catalog' },
                    { value: 'csv', label: 'CSV upload' },
                  ]}
                />
              )}
            </div>
            {isDemo && (
              <div className="flex flex-col gap-3.5">
                <p className="m-0 text-[13px] leading-normal text-mu">
                  Demo models use the features they were trained on, in the same order. They are computed server-side from the indicator catalog.
                </p>
                <ul className="m-0 flex list-none flex-wrap gap-2 p-0" aria-label="Model features">
                  {(selectedDemo?.feature_columns || []).map((feature) => (
                    <li key={feature} className="mono flex h-[34px] items-center rounded-md border border-bd bg-s2 px-3 text-[13px] text-tx">
                      {feature}
                    </li>
                  ))}
                </ul>
                <span className="mono text-xs text-mu">{selectedDemo?.feature_columns?.length ?? 0} features, read-only</span>
              </div>
            )}
            {!isDemo && form.featureSource === 'catalog' && (
              <div className="flex flex-col gap-3.5">
                <p className="m-0 text-[13px] leading-normal text-mu">
                  The model needs the same columns it was trained on, in the same order. TME checks this before the run starts.
                </p>
                <div className="flex flex-wrap gap-2" role="group" aria-label="Indicators">
                  {indicators.loading && [0, 1, 2, 3, 4].map((key) => <Skeleton key={key} className="h-[34px] w-28" />)}
                  {indicators.error && <p className="m-0 text-[13px] text-neg">Indicators could not be loaded: {describeFailure(indicators.error).title}</p>}
                  {indicatorList.map((indicator) => (
                    <button
                      key={indicator.id}
                      type="button"
                      className="pill"
                      aria-pressed={form.featureIds.includes(indicator.id)}
                      title={`${indicator.label}: ${indicator.description}`}
                      onClick={() => toggleFeature(indicator.id)}
                    >
                      {indicator.id}
                    </button>
                  ))}
                </div>
                <span className="mono text-xs text-mu">
                  {form.featureIds.length} of {indicatorList.length} selected
                </span>
              </div>
            )}
            {!isDemo && form.featureSource === 'csv' && (
              <FilePicker
                id="csv-file"
                accept=".csv,text/csv"
                file={form.csvFile}
                onFile={(file) => update({ csvFile: file })}
                onClear={() => update({ csvFile: null })}
                title="Upload a CSV with prices and features"
                hint={
                  <>
                    Required columns: <span className="mono">date, open, high, low, close, volume</span>, then one column per feature. Daily bars only. Max{' '}
                    {formatBytes(LIMITS.maxCsvBytes)}.
                  </>
                }
              />
            )}
            {touched && !isDemo && validation.errors.features && <p className="m-0 text-xs text-neg">{validation.errors.features}</p>}
            <PointInTimeNotice />
          </section>
        </div>

        <aside className="flex min-w-0 flex-[1_1_340px] flex-col gap-6">
          <section className="card flex flex-col gap-[18px] p-6" aria-labelledby="summary-title">
            <h2 id="summary-title" className="lbl m-0">
              Run summary
            </h2>
            <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-3 text-sm">
              <dt className="text-mu">Model</dt>
              <dd className="mono m-0 truncate text-right">{modelName}</dd>
              <dt className="text-mu">Data</dt>
              <dd className="mono m-0 text-right">{usesCsv ? `CSV${normalizeTicker(form.ticker) ? ` · ${normalizeTicker(form.ticker)}` : ''}` : `${normalizeTicker(form.ticker) || '?'} · daily`}</dd>
              <dt className="text-mu">Period</dt>
              <dd className="mono m-0 text-right">{form.startDate || form.endDate ? `${form.startDate || '?'} → ${form.endDate || '?'}` : 'whole file'}</dd>
              <dt className="text-mu">Features</dt>
              <dd className="mono m-0 text-right">{featureSummary}</dd>
              <dt className="text-mu">Costs</dt>
              <dd className="mono m-0 text-right">
                {form.feeBps || '?'} + {form.slippageBps || '?'} bps per side
              </dd>
              <dt className="text-mu">Execution</dt>
              <dd className="mono m-0 text-right">next-bar open</dd>
              <dt className="text-mu">Position</dt>
              <dd className="mono m-0 text-right">100% equity, long/short</dd>
            </dl>
            <button type="submit" className="btn btn-pri h-[46px] text-[15px]" disabled={!validation.valid || submitting} aria-describedby="run-reason">
              {submitting ? 'Starting…' : 'Run analysis'}
            </button>
            {!validation.valid && (
              <p id="run-reason" className="m-0 text-[12.5px] leading-normal text-ac">
                {validation.reason}
              </p>
            )}
            <p className="m-0 text-[12.5px] leading-normal text-mu">
              Runs in the background with a {Math.round(JOB_TIMEOUT_SECONDS / 60)}-minute limit. You get a private link to the result that you can share.
            </p>
          </section>
          {submitError && <ErrorAlert title={submitError.title} message={submitError.message} facts={submitError.facts} />}
          <HistoryPanel entries={history} expired={expired} onRemove={(id) => historyStore.remove(id)} />
        </aside>
      </form>
    </Main>
  )
}
