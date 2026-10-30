import { Link } from 'react-router-dom'
import { JOB_TIMEOUT_SECONDS } from '../../config.js'
import { useDocumentTitle } from '../../hooks/useDocumentTitle.js'
import { useNow } from '../../hooks/useNow.js'
import { describeFailure } from '../../lib/errors.js'
import { formatClock } from '../../lib/format.js'
import { isTerminal } from '../../lib/polling.js'
import { activeStepIndex, buildRunLog, buildSteps, elapsedSeconds, stepForStage, stepTimeLabel } from '../../lib/stages.js'
import { ErrorAlert, Main } from '../ui.jsx'

function StepIcon({ state }) {
  if (state === 'done') {
    return (
      <svg width="26" height="26" viewBox="0 0 26 26" role="img" aria-label="Done">
        <circle cx="13" cy="13" r="12" className="fill-pos" />
        <path d="M7.5 13.5l3.7 3.6 7.3-7.6" fill="none" className="stroke-bg" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }
  if (state === 'running') {
    return (
      <svg className="spin" width="26" height="26" viewBox="0 0 26 26" role="img" aria-label="Running">
        <circle cx="13" cy="13" r="11" fill="none" className="stroke-bd" strokeWidth="3" />
        <path d="M13 2a11 11 0 0 1 11 11" fill="none" className="stroke-ac" strokeWidth="3" strokeLinecap="round" />
      </svg>
    )
  }
  if (state === 'failed') {
    return (
      <svg width="26" height="26" viewBox="0 0 26 26" role="img" aria-label="Failed">
        <circle cx="13" cy="13" r="12" className="fill-neg" />
        <path d="M8.5 8.5l9 9M17.5 8.5l-9 9" fill="none" className="stroke-bg" strokeWidth="2.4" strokeLinecap="round" />
      </svg>
    )
  }
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" role="img" aria-label="Waiting">
      <circle cx="13" cy="13" r="11" fill="none" className="stroke-bd" strokeWidth="2" />
    </svg>
  )
}

function headline(status, steps) {
  const index = activeStepIndex(steps) + 1
  const total = steps.length
  if (status === 'queued') return { title: 'Analysis queued', sub: 'It starts as soon as a worker is free. You can leave this page open or come back later with the link.' }
  if (status === 'running') return { title: `Analysis running: step ${index} of ${total}`, sub: 'You can leave this page open or come back later with the link.' }
  if (status === 'partial') return { title: `Analysis finished with a failed step: step ${index} of ${total}`, sub: 'Part of the result is available. Nothing was shown that failed a check.' }
  if (status === 'completed') return { title: 'Analysis completed', sub: 'Opening the dashboard.' }
  return { title: `Analysis stopped at step ${index} of ${total}`, sub: 'Nothing was shown that failed a check.' }
}

function inputsFrom(analysis) {
  const params = analysis?.params || {}
  const meta = analysis?.model_meta || {}
  const model = meta.source === 'demo' ? `${meta.name || meta.demo_model_id} (demo)` : meta.filename || 'n/a'
  const data = params.data_source_kind === 'csv' ? `CSV${params.ticker ? ` · ${params.ticker}` : ''}` : `${params.ticker || 'n/a'} · daily`
  const period = params.start_date && params.end_date ? `${params.start_date} → ${params.end_date}` : 'whole file'
  const featureCount = Array.isArray(meta.feature_columns) ? meta.feature_columns.length : Array.isArray(params.feature_ids) ? params.feature_ids.length : null
  return [
    ['Model', model],
    ['Data', data],
    ['Period', period],
    ['Features', featureCount == null ? 'n/a' : `${featureCount} ${params.data_source_kind === 'csv' ? 'CSV columns' : 'features'}`],
    ['Costs', params.fee_bps == null ? 'n/a' : `${params.fee_bps} + ${params.slippage_bps} bps per side`],
  ]
}

const toneClass = { ok: 'text-tx', active: 'text-ac', error: 'text-neg' }

export default function ProgressScreen({ analysis, status, poll, onRetryPolling, onOpenResult, canOpenResult, tryAgainState }) {
  const steps = buildSteps(status)
  const terminal = isTerminal(status?.status)
  const head = headline(status?.status, steps)
  useDocumentTitle(terminal ? 'run stopped' : 'run in progress')
  const now = useNow(1000, !terminal)
  const elapsed = elapsedSeconds(status, poll?.stageSince, now)
  const share = Math.min(100, (elapsed / JOB_TIMEOUT_SECONDS) * 100)
  const log = buildRunLog(status)
  const failure = terminal && status?.status !== 'completed' ? describeFailure(status?.error) : null
  const failedStep = failure && status?.error?.stage ? stepForStage(status.error.stage) : null
  const connection = poll?.phase === 'retrying' ? 'retrying' : poll?.phase === 'failed' ? 'lost' : null

  return (
    <Main className="gap-7 pt-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-2.5">
          <span className="lbl">
            Analysis <span className="mono break-all tracking-normal normal-case">{analysis?.id || status?.analysis_id}</span>
          </span>
          <h1 className="m-0 text-[28px] font-semibold tracking-[-.02em] sm:text-[32px]">{head.title}</h1>
          <p className="m-0 max-w-[640px] text-[15px] leading-normal text-mu">{head.sub}</p>
        </div>
        <Link className="btn" to="/">
          Back to home
        </Link>
      </div>

      {connection === 'retrying' && (
        <div role="status" className="rounded-[10px] border border-ac bg-s1 px-5 py-3 text-sm">
          Connection lost, retrying ({poll.retries})…
        </div>
      )}
      {connection === 'lost' && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-neg bg-s1 px-5 py-3 text-sm">
          <span>The status could not be fetched: {describeFailure(poll.error).title}</span>
          <button type="button" className="btn btn-sm" onClick={onRetryPolling}>
            Retry now
          </button>
        </div>
      )}

      {failure && (
        <ErrorAlert
          title={failure.title}
          message={[failedStep ? `Failed step: ${failedStep.name}.` : null, failure.message].filter(Boolean).join(' ')}
          facts={failure.facts}
        >
          {canOpenResult && (
            <button type="button" className="btn btn-pri" onClick={onOpenResult}>
              Open partial result
            </button>
          )}
          <Link className="btn" to="/" state={tryAgainState}>
            Try again
          </Link>
        </ErrorAlert>
      )}

      <div className="flex flex-wrap items-start gap-6">
        <div className="flex min-w-0 flex-[999_1_620px] flex-col gap-6">
          <section className="card flex flex-col" aria-label="Progress">
            <ol className="m-0 list-none p-0">
              {steps.map((step, index) => (
                <li
                  key={step.id}
                  className={`flex items-start gap-4 px-6 py-5 ${index < steps.length - 1 ? 'border-b border-bd' : ''}`}
                  aria-current={step.state === 'running' ? 'step' : undefined}
                >
                  <span className="flex h-7 w-7 flex-none items-center justify-center">
                    <StepIcon state={step.state} />
                  </span>
                  <span className="flex min-w-0 flex-[1_1_0] flex-col gap-1">
                    <span className="text-base font-semibold">
                      <span className="mono mr-2.5 font-medium text-mu">{step.number}</span>
                      {step.name}
                    </span>
                    <span className="text-[13.5px] leading-normal text-mu">{step.description}</span>
                  </span>
                  <span className="mono text-[13px] whitespace-nowrap text-mu">{stepTimeLabel(step, terminal)}</span>
                </li>
              ))}
            </ol>
          </section>

          <section className="card flex flex-col" aria-labelledby="log-title">
            <div className="flex justify-between gap-2 border-b border-bd px-6 py-4">
              <h2 id="log-title" className="lbl m-0">
                Run log
              </h2>
              <span className="mono text-xs text-mu">from the status endpoint</span>
            </div>
            <div className="mono overflow-x-auto px-6 py-4 text-[12.5px] leading-[1.9] text-mu" aria-live="polite">
              {log.length === 0 && <div>Waiting for the first status…</div>}
              {log.map((line, index) => (
                <div key={`${index}-${line.text}`} className="whitespace-nowrap">
                  <span className="mr-3.5">{formatClock(line.seconds)}</span>
                  <span className={toneClass[line.tone]}>{line.text}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="flex min-w-0 flex-[1_1_320px] flex-col gap-6">
          <section className="card flex flex-col gap-3.5 p-6" aria-labelledby="budget-title">
            <div className="flex items-baseline justify-between">
              <h2 id="budget-title" className="lbl m-0">
                Time budget
              </h2>
              <span className="mono text-[13px]">
                {formatClock(elapsed)} / {formatClock(JOB_TIMEOUT_SECONDS)}
              </span>
            </div>
            <div
              className="h-2 overflow-hidden rounded bg-s2"
              role="progressbar"
              aria-label="Time used against the server limit"
              aria-valuemin={0}
              aria-valuemax={JOB_TIMEOUT_SECONDS}
              aria-valuenow={Math.round(elapsed)}
            >
              <div className="h-full rounded bg-ac" style={{ width: `${share}%` }} />
            </div>
            <p className="m-0 text-[12.5px] leading-normal text-mu">
              Runs stop at {Math.round(JOB_TIMEOUT_SECONDS / 60)} minutes. If only the report fails, everything else is kept and the report can be regenerated.
            </p>
          </section>
          <section className="card flex flex-col gap-4 p-6" aria-labelledby="inputs-title">
            <h2 id="inputs-title" className="lbl m-0">
              Inputs
            </h2>
            <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-3 text-sm">
              {inputsFrom(analysis).map(([label, value]) => (
                <div key={label} className="contents">
                  <dt className="text-mu">{label}</dt>
                  <dd className="mono m-0 truncate text-right" title={value}>
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
          <section className="card flex flex-col gap-2 px-6 py-5">
            <span className="lbl">Bookmark this page</span>
            <p className="m-0 text-[13px] leading-normal text-mu">
              The link to this analysis is private and does not need a login. You can close the tab and come back to it.
            </p>
          </section>
        </aside>
      </div>
    </Main>
  )
}
