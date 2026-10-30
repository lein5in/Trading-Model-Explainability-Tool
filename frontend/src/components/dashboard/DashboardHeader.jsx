import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { modelLabel, tickerLabel } from '../../lib/analysis.js'
import { formatInt } from '../../lib/format.js'
import { CheckIcon, LinkIcon, WarningIcon } from '../Icons.jsx'

function shareUrl(id) {
  return `${window.location.origin}/analysis/${id}`
}

function legacyCopy(text) {
  try {
    const area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(area)
    return ok
  } catch {
    return false
  }
}

function CopyLinkButton({ id }) {
  const [state, setState] = useState('idle')
  const timer = useRef(null)
  useEffect(() => () => clearTimeout(timer.current), [])
  const url = shareUrl(id)

  const copy = async () => {
    let ok = false
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url)
        ok = true
      }
    } catch {
      ok = false
    }
    if (!ok) ok = legacyCopy(url)
    setState(ok ? 'copied' : 'manual')
    clearTimeout(timer.current)
    if (ok) timer.current = setTimeout(() => setState('idle'), 2500)
  }

  return (
    <span className="flex flex-col items-end gap-1">
      <button type="button" className="btn" onClick={copy}>
        {state === 'copied' ? <CheckIcon size={16} stroke="var(--color-pos)" /> : <LinkIcon size={16} />}
        {state === 'copied' ? 'Link copied' : 'Copy link'}
      </button>
      <span className="sr-only" aria-live="polite">
        {state === 'copied' ? 'Link copied to the clipboard' : ''}
      </span>
      {state === 'manual' && (
        <label className="flex items-center gap-2 text-xs text-mu">
          Copy it manually
          <input className="field h-8 w-64 text-xs" readOnly value={url} onFocus={(event) => event.target.select()} autoFocus />
        </label>
      )}
    </span>
  )
}

function VerifiedBadge({ analysis }) {
  const report = analysis.report
  const verification = report?.verification
  const to = `/analysis/${analysis.id}/report`
  if (!report || report.status !== 'ok' || !verification) {
    return (
      <Link to={to} className="chip h-10 border-bd px-3.5 text-tx no-underline" title={report?.error?.message || 'No report was generated for this analysis.'}>
        <WarningIcon size={16} stroke="var(--color-mu)" />
        <span className="mono font-medium">Report unavailable</span>
      </Link>
    )
  }
  const flaggedCount = verification.numbers_total - verification.numbers_verified
  const flagged = Boolean(verification.flagged)
  return (
    <Link to={to} className={`chip h-10 px-3.5 text-tx no-underline ${flagged ? 'border-ac' : 'border-pos'}`}>
      {flagged ? <WarningIcon size={16} stroke="var(--color-ac)" /> : <CheckIcon size={16} stroke="var(--color-pos)" />}
      <span className="mono font-medium">
        Numbers verified {formatInt(verification.numbers_verified)}/{formatInt(verification.numbers_total)}
        {flagged ? ` · ${formatInt(flaggedCount)} flagged` : ''}
      </span>
    </Link>
  )
}

export default function DashboardHeader({ analysis }) {
  const data = analysis.result?.data || {}
  const params = analysis.params || {}
  const backtest = analysis.result?.backtest || {}
  const model = modelLabel(analysis)
  const ticker = tickerLabel(analysis)
  const featureCount = (analysis.model_meta?.feature_columns || data.feature_columns || []).length
  const ignored = backtest.ignored_bar_count

  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-3">
        <h1 className="m-0 text-[24px] font-semibold tracking-[-.02em] break-words sm:text-[28px]">
          <span className="mono">{ticker || 'CSV data'}</span> <span className="font-normal text-mu">with</span> {model.name}{' '}
          <span className="text-lg font-normal text-mu">({model.kind})</span>
        </h1>
        <ul className="m-0 flex list-none flex-wrap gap-2 p-0" aria-label="Analysis facts">
          <li className="chip mono">
            {data.effective_start || 'n/a'} → {data.end || 'n/a'}
          </li>
          <li className="chip mono">{formatInt(data.n_bars)} daily bars</li>
          <li className="chip mono">{formatInt(featureCount)} features</li>
          <li className="chip mono">
            {params.fee_bps ?? backtest.fee_bps ?? 'n/a'} + {params.slippage_bps ?? backtest.slippage_bps ?? 'n/a'} bps per side
          </li>
          <li className="chip" title="Bars where the model returned no signal (missing features or NaN output)">
            <span className="mono">{formatInt(ignored)}</span> bars ignored (NaN signal)
          </li>
          {data.data_source === 'bundled' && (
            <li className="chip border-ac text-tx" title="Yahoo Finance could not be reached, so a dataset bundled with the server was used">
              Bundled dataset (yfinance unavailable)
            </li>
          )}
          {data.data_source === 'csv' && <li className="chip">Uploaded CSV</li>}
          {data.warmup_dropped > 0 && (
            <li className="chip" title="Leading bars dropped because an indicator was not defined yet">
              <span className="mono">{formatInt(data.warmup_dropped)}</span> warmup bars dropped
            </li>
          )}
          {data.invalid_count > 0 && (
            <li className="chip" title="Rows removed by the OHLCV schema check">
              <span className="mono">{formatInt(data.invalid_count)}</span> invalid rows removed
            </li>
          )}
        </ul>
      </div>
      <div className="flex flex-wrap items-start gap-2.5">
        <VerifiedBadge analysis={analysis} />
        <CopyLinkButton id={analysis.id} />
        <Link className="btn btn-pri" to="/">
          New analysis
        </Link>
      </div>
    </div>
  )
}
