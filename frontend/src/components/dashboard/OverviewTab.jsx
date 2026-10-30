import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useHistory } from '../../hooks/useHistory.js'
import { explainedOutput, unavailableReason } from '../../lib/analysis.js'
import {
  drawdownSeries,
  equitySeries,
  lastValue,
  monthlyReturns,
  regimeProbabilityRows,
  regimeShading,
  tradeReturnHistogram,
} from '../../lib/chartData.js'
import { describeFailure } from '../../lib/errors.js'
import {
  NA,
  formatInt,
  formatNumber,
  formatPercent,
  formatPoints,
  formatRatio,
  formatSignedNumber,
  formatSignedPercent,
  formatSmall,
  isNumber,
  relativeTime,
  signColor,
} from '../../lib/format.js'
import { REGIME_NAMES, regimeColorVar } from '../../lib/regimes.js'
import DrawdownChart from '../charts/DrawdownChart.jsx'
import EquityChart from '../charts/EquityChart.jsx'
import { DefinitionList, RegimeDot, Segmented, Unavailable } from '../ui.jsx'
import HighlightedText from './HighlightedText.jsx'

function difference(a, b) {
  return isNumber(a) && isNumber(b) ? a - b : null
}

function MetricCard({ label, value, valueTitle, sub, delta, deltaClass = 'text-mu' }) {
  return (
    <div className="card flex min-w-0 flex-[1_1_200px] flex-col gap-2 px-5 py-[18px]">
      <span className="lbl">{label}</span>
      <span className="mono text-[28px] font-semibold tracking-[-.02em] text-tx" title={valueTitle}>
        {value}
      </span>
      <span className="mono text-[12.5px] text-mu">{sub}</span>
      <span className={`mono text-[12.5px] ${deltaClass}`}>{delta}</span>
    </div>
  )
}

function MetricCards({ metrics }) {
  const s = metrics.strategy || {}
  const b = metrics.benchmark || {}
  const pointsDelta = (key) => {
    const value = difference(s[key], b[key])
    return { delta: value === null ? `${NA} vs B&H` : `${formatPoints(value)} vs B&H`, deltaClass: signColor(value) }
  }
  const ratioDelta = (key) => {
    const value = difference(s[key], b[key])
    return { delta: value === null ? `${NA} vs B&H` : `${formatSignedNumber(value, 2)} vs B&H`, deltaClass: signColor(value) }
  }
  const cards = [
    { label: 'Total return', value: formatSignedPercent(s.total_return), sub: `Buy & Hold ${formatSignedPercent(b.total_return)}`, ...pointsDelta('total_return') },
    {
      label: 'CAGR',
      value: formatPercent(s.cagr),
      valueTitle: s.cagr == null ? 'CAGR is hidden when the period is under one year.' : undefined,
      sub: `Buy & Hold ${formatPercent(b.cagr)}`,
      ...pointsDelta('cagr'),
    },
    {
      label: 'Sharpe ratio',
      value: formatRatio(s.sharpe),
      valueTitle: s.sharpe == null ? 'Not defined: the daily returns have no variance.' : undefined,
      sub: `Buy & Hold ${formatRatio(b.sharpe)}`,
      ...ratioDelta('sharpe'),
    },
    { label: 'Max drawdown', value: formatPercent(s.max_drawdown), sub: `Buy & Hold ${formatPercent(b.max_drawdown)}`, ...pointsDelta('max_drawdown') },
    {
      label: 'Win rate',
      value: formatPercent(s.win_rate),
      valueTitle: s.win_rate == null ? 'No trade was made.' : undefined,
      sub: `of ${formatInt(s.n_trades)} trades`,
      delta: `Profit factor ${formatRatio(s.profit_factor)}`,
    },
    {
      label: 'Trades',
      value: formatInt(s.n_trades),
      sub: `${formatInt(s.n_long)} long, ${formatInt(s.n_short)} short`,
      delta: `Avg ${formatNumber(s.avg_bars_held, 1)} bars held`,
    },
  ]
  return (
    <section aria-label="Key metrics" className="flex flex-wrap gap-4">
      {cards.map((card) => (
        <MetricCard key={card.label} {...card} />
      ))}
    </section>
  )
}

function LegendLine({ color, dashed, children }) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg width="22" height="10" aria-hidden="true">
        <line x1="0" y1="5" x2="22" y2="5" stroke={color} strokeWidth={dashed ? 2 : 2.5} strokeDasharray={dashed ? '5 4' : undefined} />
      </svg>
      {children}
    </span>
  )
}

function LegendSwatch({ color, opacity = 0.25, children }) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg width="14" height="14" aria-hidden="true">
        <rect width="14" height="14" rx="3" fill={color} fillOpacity={opacity} />
      </svg>
      {children}
    </span>
  )
}

function TradeAnalysis({ trades, metrics }) {
  const bins = useMemo(() => tradeReturnHistogram(trades), [trades])
  const max = Math.max(1, ...bins.map((bin) => bin.count))
  const s = metrics.strategy || {}
  const digits = bins.length && bins[0].to - bins[0].from < 0.01 ? 1 : 0
  return (
    <div className="flex flex-wrap items-start gap-7">
      <div className="flex min-w-0 flex-[999_1_420px] flex-col gap-2.5">
        <span className="lbl">Distribution of trade returns ({formatInt(trades.length)} trades)</span>
        {bins.length === 0 ? (
          <Unavailable title="No trades" reason="The strategy never entered a position, so there is no trade to analyze." />
        ) : (
          <>
            <div className="flex h-[240px] items-end gap-2.5 border-b border-bd px-1" role="img" aria-label={`Histogram of ${trades.length} trade returns in ${bins.length} bins`}>
              {bins.map((bin) => (
                <div key={bin.from} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
                  <span className="mono text-xs text-mu">{bin.count}</span>
                  <div className={`w-full rounded-t-[3px] ${bin.to <= 0 ? 'bg-neg' : 'bg-pos'}`} style={{ height: `${Math.round((bin.count / max) * 190)}px` }} />
                </div>
              ))}
            </div>
            <div className="mono flex gap-2.5 px-1 text-[11px] text-mu">
              {bins.map((bin) => (
                <span key={bin.from} className="flex-1 text-center">
                  {formatNumber(bin.from * 100, digits)} to {formatNumber(bin.to * 100, digits)}
                </span>
              ))}
            </div>
            <span className="text-xs text-mu">Bins in percent of equity per trade.</span>
          </>
        )}
      </div>
      <DefinitionList
        className="flex-[1_1_220px]"
        items={[
          { label: 'Average win', value: formatSignedPercent(s.avg_win), className: 'text-pos' },
          { label: 'Average loss', value: formatSignedPercent(s.avg_loss), className: 'text-neg' },
          { label: 'Best / worst', value: `${formatSignedPercent(s.best_trade)} / ${formatSignedPercent(s.worst_trade)}` },
          { label: 'Profit factor', value: formatRatio(s.profit_factor) },
          { label: 'Avg bars held', value: formatNumber(s.avg_bars_held, 1) },
          { label: 'Long / short', value: `${formatInt(s.n_long)} / ${formatInt(s.n_short)}` },
        ]}
      />
    </div>
  )
}

function PerformanceCard({ analysis }) {
  const [view, setView] = useState('equity')
  const result = analysis.result
  const backtest = result.backtest
  const regimes = result.regimes
  const showRegimes = Boolean(regimes?.regimes_available)
  const metrics = backtest.metrics || {}

  const equityData = useMemo(() => {
    const dates = result.bars?.date || []
    return {
      strategy: equitySeries(backtest.equity_curve),
      benchmark: equitySeries(backtest.benchmark_equity_curve),
      shading: showRegimes ? regimeShading(dates, regimes.regime_per_bar) : [],
      monthly: monthlyReturns(backtest.equity_curve),
      heatRows: showRegimes ? regimeProbabilityRows(dates, regimes.probabilities_per_bar) : [[], [], []],
    }
  }, [result.bars, backtest, regimes, showRegimes])

  const drawdownData = useMemo(
    () => ({ strategy: drawdownSeries(backtest.equity_curve), benchmark: drawdownSeries(backtest.benchmark_equity_curve) }),
    [backtest],
  )

  const lastStrategy = lastValue(equityData.strategy)
  const lastBenchmark = lastValue(equityData.benchmark)
  const regimeReason = regimes ? regimes.reason : unavailableReason(analysis, 'regimes', 'Regimes were not computed.')

  return (
    <section className="card flex min-w-0 flex-[999_1_640px] flex-col gap-[18px] p-6" aria-labelledby="perf-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="perf-title" className="m-0 text-[17px] font-semibold">
          Backtest performance
        </h2>
        <Segmented
          label="Chart"
          value={view}
          onChange={setView}
          options={[
            { value: 'equity', label: 'Equity curve' },
            { value: 'drawdown', label: 'Drawdown' },
            { value: 'trades', label: 'Trade analysis' },
          ]}
        />
      </div>

      {view === 'equity' && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-5 text-[13px] text-mu">
            <LegendLine color="var(--color-ac)">
              Strategy <span className="mono text-tx">{formatInt(lastStrategy)}</span>{' '}
              <span className={`mono ${signColor(metrics.strategy?.total_return)}`}>{formatSignedPercent(metrics.strategy?.total_return, 2)}</span>
            </LegendLine>
            <LegendLine color="var(--color-bh)" dashed>
              Buy &amp; Hold <span className="mono text-tx">{formatInt(lastBenchmark)}</span>{' '}
              <span className={`mono ${signColor(metrics.benchmark?.total_return)}`}>{formatSignedPercent(metrics.benchmark?.total_return, 2)}</span>
            </LegendLine>
            {showRegimes &&
              REGIME_NAMES.map((name) => (
                <LegendSwatch key={name} color={regimeColorVar(name)}>
                  {name}
                </LegendSwatch>
              ))}
          </div>
          <EquityChart
            data={equityData}
            showRegimes={showRegimes}
            ariaLabel={`Equity curve of the strategy, ending at ${formatInt(lastStrategy)}, against buy and hold, ending at ${formatInt(lastBenchmark)}, with monthly P&L${showRegimes ? ' and filtered regime probabilities' : ''}`}
          />
          <p className="m-0 text-[12.5px] leading-normal text-mu">
            Panes, top to bottom: equity marked to market every bar from a starting capital of <span className="mono">{formatInt(backtest.initial_capital)}</span>, costs
            included; monthly P&amp;L in percent of equity
            {showRegimes
              ? '; filtered regime probabilities, one row per regime (low vol at the bottom, high vol at the top), brighter means more likely. Shading behind the equity shows the regime label of each bar, computed from past bars only.'
              : '.'}
          </p>
          {!showRegimes && <p className="m-0 text-[12.5px] text-ac">Regime shading and the regime pane are unavailable: {regimeReason}</p>}
        </div>
      )}

      {view === 'drawdown' && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-5 text-[13px] text-mu">
            <LegendSwatch color="var(--color-neg)" opacity={0.45}>
              Strategy drawdown (max <span className="mono">{formatPercent(metrics.strategy?.max_drawdown)}</span>)
            </LegendSwatch>
            <LegendLine color="var(--color-bh)" dashed>
              Buy &amp; Hold (max <span className="mono">{formatPercent(metrics.benchmark?.max_drawdown)}</span>)
            </LegendLine>
          </div>
          <DrawdownChart
            data={drawdownData}
            ariaLabel={`Drawdown of the strategy, maximum ${formatPercent(metrics.strategy?.max_drawdown)}, against buy and hold, maximum ${formatPercent(metrics.benchmark?.max_drawdown)}`}
          />
        </div>
      )}

      {view === 'trades' && <TradeAnalysis trades={backtest.trades || []} metrics={metrics} />}
    </section>
  )
}

const CIRCUMFERENCE = 2 * Math.PI * 76

function RegimesCard({ analysis }) {
  const regimes = analysis.result.regimes
  if (!regimes || !regimes.regimes_available) {
    const reason = regimes ? regimes.reason : unavailableReason(analysis, 'regimes', 'Regimes were not computed.')
    return (
      <section className="card flex min-w-0 flex-[1_1_340px] flex-col gap-[18px] p-6" aria-labelledby="regimes-title">
        <h2 id="regimes-title" className="m-0 text-[17px] font-semibold">
          Market regimes
        </h2>
        <Unavailable title="Regimes unavailable" reason={reason} />
      </section>
    )
  }
  const total = regimes.n_valid_bars
  const lengths = REGIME_NAMES.map((name) => (total > 0 ? ((regimes.n_bars?.[name] || 0) / total) * CIRCUMFERENCE : 0))
  const arcs = REGIME_NAMES.map((name, index) => ({
    name,
    dash: Math.max(0, lengths[index] - (lengths[index] > 4 ? 2 : 0)),
    offset: lengths.slice(0, index).reduce((sum, value) => sum + value, 0),
  }))
  const performance = regimes.performance || {}
  const summary = REGIME_NAMES.map((name) => `${name} ${formatPercent(regimes.time_in_regime_pct?.[name])}`).join(', ')

  return (
    <section className="card flex min-w-0 flex-[1_1_340px] flex-col gap-[18px] p-6" aria-labelledby="regimes-title">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="regimes-title" className="m-0 text-[17px] font-semibold">
          Market regimes
        </h2>
        <span className="mono text-xs text-mu">HMM, {regimes.n_states} states</span>
      </div>
      <div className="relative mx-auto h-[200px] w-[200px]">
        <svg width="200" height="200" viewBox="0 0 200 200" role="img" aria-label={`Share of bars per regime: ${summary}`}>
          <g transform="rotate(-90 100 100)" fill="none" strokeWidth="22">
            <circle cx="100" cy="100" r="76" stroke="var(--color-s2)" />
            {arcs.map((arc) => (
              <circle
                key={arc.name}
                cx="100"
                cy="100"
                r="76"
                stroke={regimeColorVar(arc.name)}
                strokeDasharray={`${arc.dash} ${CIRCUMFERENCE - arc.dash}`}
                strokeDashoffset={-arc.offset}
              />
            ))}
          </g>
          <circle cx="100" cy="100" r="58" fill="none" strokeDasharray="1.5 4" stroke="var(--color-bd)" strokeWidth="1" />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
          <span className="mono text-2xl font-semibold">{formatInt(total)}</span>
          <span className="mono text-[11px] tracking-[.06em] text-mu">BARS · {regimes.n_states} STATES</span>
        </div>
      </div>
      <div className="flex flex-col">
        {REGIME_NAMES.map((name) => {
          const perf = performance[name] || {}
          return (
            <div key={name} className="flex flex-col gap-2.5 border-t border-bd py-3.5">
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-2.5 text-[14.5px] font-semibold">
                  <RegimeDot regime={name} />
                  {name}
                </span>
                <span className="mono text-[13px] text-mu">
                  {formatPercent(regimes.time_in_regime_pct?.[name])} · n = {formatInt(regimes.n_bars?.[name])}
                </span>
              </div>
              <div className="flex justify-between gap-3 text-[13px] text-mu">
                <span>
                  Trades <span className="mono text-tx">{formatInt(perf.n_trades)}</span>
                </span>
                <span>
                  Strategy <span className={`mono ${signColor(perf.strategy_return)}`}>{formatSignedPercent(perf.strategy_return)}</span>
                </span>
              </div>
            </div>
          )
        })}
      </div>
      <p className="m-0 text-[12.5px] leading-[1.55] text-mu">
        Fitted on the full history, so it describes the past and does not forecast. Each bar is labeled from filtered probabilities, using only bars up to that day.
      </p>
    </section>
  )
}

function Bar({ value, max, color }) {
  const width = isNumber(value) && max > 0 ? (value / max) * 100 : 0
  return (
    <div className="h-full overflow-hidden rounded-[3px] bg-s2">
      <div className="h-full rounded-[3px]" style={{ width: `${width}%`, background: color }} />
    </div>
  )
}

function ShapCard({ analysis }) {
  const [view, setView] = useState('global')
  const shap = analysis.result.shap
  const output = explainedOutput(analysis)
  const ranked = useMemo(
    () => (shap ? Object.entries(shap.feature_importance || {}).sort((a, b) => b[1] - a[1]) : []),
    [shap],
  )
  const max = ranked.length ? ranked[0][1] : 0
  const byRegime = shap?.feature_importance_by_regime
  const regimeMax = byRegime
    ? Math.max(0, ...REGIME_NAMES.flatMap((name) => Object.values(byRegime[name]?.importance || {})))
    : 0

  return (
    <section className="card flex min-w-0 flex-[999_1_640px] flex-col gap-[18px] p-6" aria-labelledby="shap-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="shap-title" className="m-0 text-[17px] font-semibold">
          Feature importance (SHAP)
        </h2>
        {shap && (
          <Segmented
            label="Importance view"
            value={view}
            onChange={setView}
            options={[
              { value: 'global', label: 'Global' },
              { value: 'regime', label: 'By regime' },
              { value: 'trade', label: 'Per trade' },
            ]}
          />
        )}
      </div>
      {!shap ? (
        <Unavailable title="SHAP unavailable" reason={unavailableReason(analysis, 'shap', 'SHAP values were not computed for this analysis.')} />
      ) : (
        <>
          <p className="m-0 text-[13px] leading-normal text-mu">
            Explained output: <span className="mono text-tx">{output}</span>. Values are the mean absolute contribution to it, on a{' '}
            {shap.sampling === 'stratified_by_regime' ? 'regime-stratified' : 'uniform'} sample of <span className="mono text-tx">{formatInt(shap.sample_size)}</span> bars.
          </p>
          {view === 'global' && (
            <div className="flex flex-col gap-3" role="list" aria-label="Global feature importance">
              {ranked.map(([name, value]) => (
                <div key={name} className="flex items-center gap-3.5" role="listitem">
                  <span className="mono w-[150px] flex-none truncate text-[13px]" title={name}>
                    {name}
                  </span>
                  <div className="h-3.5 flex-1">
                    <Bar value={value} max={max} color="var(--color-ac)" />
                  </div>
                  <span className="mono w-[60px] flex-none text-right text-[13px]">{formatNumber(value, 3)}</span>
                </div>
              ))}
            </div>
          )}
          {view === 'regime' &&
            (!byRegime ? (
              <Unavailable title="No regime breakdown" reason="Regimes were unavailable, so the sample was uniform and not split by regime." />
            ) : (
              <div className="flex flex-wrap gap-5">
                {REGIME_NAMES.map((name) => {
                  const item = byRegime[name] || {}
                  const rows = item.importance ? Object.entries(item.importance).sort((a, b) => b[1] - a[1]).slice(0, 4) : []
                  return (
                    <div key={name} className="flex min-w-0 flex-[1_1_200px] flex-col gap-3 rounded-lg border border-bd p-3.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="inline-flex items-center gap-2 text-[13.5px] font-semibold">
                          <RegimeDot regime={name} />
                          {name}
                        </span>
                        <span className="mono text-xs text-mu">n = {formatInt(item.n_rows)}</span>
                      </div>
                      {rows.length === 0 && <span className="text-[13px] text-mu">No rows in this regime.</span>}
                      {rows.map(([feature, value]) => (
                        <div key={feature} className="flex flex-col gap-1">
                          <div className="flex justify-between gap-2 text-xs">
                            <span className="mono truncate">{feature}</span>
                            <span className="mono text-mu">{formatNumber(value, 3)}</span>
                          </div>
                          <div className="h-2">
                            <Bar value={value} max={regimeMax} color={regimeColorVar(name)} />
                          </div>
                        </div>
                      ))}
                      {item.low_sample && rows.length > 0 && <span className="text-xs text-ac">Small sample, read with care.</span>}
                    </div>
                  )
                })}
              </div>
            ))}
          {view === 'trade' && (
            <div className="flex flex-col items-start gap-3.5 rounded-lg border border-dashed border-bd p-6">
              <span className="text-[15px] font-semibold">Per-trade explanations live in the Trades tab</span>
              <p className="m-0 max-w-[520px] text-[13.5px] leading-[1.55] text-mu">
                Pick a trade to see how each feature moved <span className="mono">{output}</span> from the base value to the model's decision on its signal bar.
                Trade rows are explained separately from the sample above ({formatInt(shap.trade_rows?.length)} trades explained).
              </p>
              <Link className="btn" to={`/analysis/${analysis.id}/trades`}>
                Open trades
              </Link>
            </div>
          )}
        </>
      )}
    </section>
  )
}

function ReportSummaryCard({ analysis, report }) {
  const stored = analysis.report
  const summary = stored?.status === 'ok' ? (stored.sections || []).find((section) => section.id === 'summary') || stored.sections?.[0] : null
  const check = summary ? stored.verification?.sections?.[summary.id] : null
  const failure = stored?.error ? describeFailure(stored.error) : null

  return (
    <section className="card flex min-w-0 flex-[1_1_340px] flex-col gap-4 p-6" aria-labelledby="summary-title">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="summary-title" className="m-0 text-[17px] font-semibold">
          Report summary
        </h2>
        {check && (
          <span className={`mono text-xs ${check.unverified?.length ? 'text-ac' : 'text-pos'}`}>
            {check.total ? `${formatInt(check.verified)}/${formatInt(check.total)} verified` : 'no numbers used'}
          </span>
        )}
      </div>
      {summary ? (
        <>
          <HighlightedText text={summary.text} unverified={check?.unverified} className="text-sm leading-[1.65]" />
          <div className="flex-1" />
          <Link className="btn" to={`/analysis/${analysis.id}/report`}>
            Read the full report
          </Link>
        </>
      ) : (
        <Unavailable title="Report unavailable" reason={failure ? failure.title : 'No report was generated for this analysis.'}>
          <button type="button" className="btn btn-sm" onClick={report.regenerate} disabled={report.busy}>
            {report.busy ? 'Regenerating…' : 'Regenerate report'}
          </button>
          {report.phase === 'error' && <span className="text-xs text-neg">{describeFailure(report.error).title}</span>}
        </Unavailable>
      )}
    </section>
  )
}

function pair(a, b, formatter) {
  return `${formatter(a)} / ${formatter(b)}`
}

function RiskTable({ analysis }) {
  const metrics = analysis.result.backtest.metrics || {}
  const s = metrics.strategy || {}
  const b = metrics.benchmark || {}
  const bars = analysis.result.data?.n_bars
  const rows = [
    ['Annualized volatility', formatPercent(s.annualized_volatility), formatPercent(b.annualized_volatility)],
    ['Sortino ratio', formatRatio(s.sortino), formatRatio(b.sortino)],
    ['Calmar ratio', formatRatio(s.calmar), formatRatio(b.calmar)],
    ['Daily VaR (95%)', formatPercent(s.var_95_daily), formatPercent(b.var_95_daily)],
    ['Best / worst day', pair(s.best_day, s.worst_day, formatSignedPercent), pair(b.best_day, b.worst_day, formatSignedPercent)],
    ['Longest drawdown', isNumber(s.longest_drawdown_days) ? `${formatInt(s.longest_drawdown_days)} days` : NA, isNumber(b.longest_drawdown_days) ? `${formatInt(b.longest_drawdown_days)} days` : NA],
    ['Time in market, long / short', pair(s.time_in_market_long, s.time_in_market_short, formatPercent), pair(b.time_in_market_long, b.time_in_market_short, formatPercent)],
    ['Correlation to Buy & Hold', formatRatio(s.correlation_to_benchmark), formatRatio(b.correlation_to_benchmark)],
    ['Beta to Buy & Hold', formatRatio(s.beta_to_benchmark), formatRatio(b.beta_to_benchmark)],
    ['Round trips per year', formatNumber(s.round_trips_per_year, 1), formatNumber(b.round_trips_per_year, 1)],
    ['Total costs paid', `${formatPercent(s.total_costs_pct_of_initial, 2)} of initial`, `${formatPercent(b.total_costs_pct_of_initial, 2)} of initial`],
    ['Bars ignored (NaN signal)', `${formatInt(s.ignored_bar_count)} of ${formatInt(bars)}`, NA],
  ]
  const head = 'mono py-2.5 text-[11px] font-semibold tracking-[.07em] text-mu uppercase'
  return (
    <section className="card flex min-w-0 flex-[999_1_640px] flex-col pt-6 pb-2" aria-labelledby="risk-title">
      <h2 id="risk-title" className="mx-6 mt-0 mb-3.5 text-[17px] font-semibold">
        Risk and execution detail
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] border-collapse text-[13.5px]">
          <thead>
            <tr className="border-b border-bd">
              <th className={`${head} pr-4 pl-6 text-left`}>Metric</th>
              <th className={`${head} px-4 text-right`}>Strategy</th>
              <th className={`${head} pr-6 pl-4 text-right`}>Buy &amp; Hold</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, strategy, benchmark]) => (
              <tr key={label} className="border-b border-bd">
                <th scope="row" className="py-2.5 pr-4 pl-6 text-left font-normal text-mu">
                  {label}
                </th>
                <td className="mono px-4 py-2.5 text-right whitespace-nowrap">{strategy}</td>
                <td className="mono py-2.5 pr-6 pl-4 text-right whitespace-nowrap text-mu">{benchmark}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function SettingsPanel({ analysis }) {
  const result = analysis.result
  const backtest = result.backtest
  const shap = result.shap
  const regimes = result.regimes
  const passed = shap && isNumber(shap.max_additivity_gap) && isNumber(shap.additivity_epsilon) && shap.max_additivity_gap <= shap.additivity_epsilon
  const items = [
    { label: 'Signal rule', value: result.predictions?.rule || NA },
    { label: 'Fill', value: 'open of bar i+1' },
    { label: 'Fee / slippage', value: `${backtest.fee_bps ?? NA} / ${backtest.slippage_bps ?? NA} bps per side` },
    { label: 'Initial capital', value: formatInt(backtest.initial_capital) },
    { label: 'Sizing', value: '100% equity, no leverage' },
    { label: 'Equity', value: 'marked to market daily' },
    { label: 'Regime model', value: regimes?.regimes_available ? `GaussianHMM, ${regimes.n_states} states, filtered` : 'unavailable' },
  ]
  if (shap) {
    items.push({ label: 'SHAP explainer', value: shap.explainer || NA })
    items.push({
      label: 'SHAP check',
      value: `max gap ${formatSmall(shap.max_additivity_gap)} ≤ ${shap.additivity_epsilon ?? NA}`,
      className: passed ? 'text-pos' : 'text-ac',
    })
  }
  return (
    <section className="card flex min-w-0 flex-[1_1_340px] flex-col gap-4 p-6" aria-labelledby="settings-title">
      <h2 id="settings-title" className="m-0 text-[17px] font-semibold">
        Backtest settings
      </h2>
      <DefinitionList items={items} className="text-[13.5px]" />
    </section>
  )
}

function RecentAnalyses({ currentId }) {
  const history = useHistory()
  const grid = 'grid grid-cols-[minmax(80px,.6fr)_minmax(160px,1.6fr)_minmax(170px,1.4fr)_minmax(90px,.7fr)_minmax(70px,.5fr)_minmax(90px,.7fr)] items-center gap-4'
  return (
    <section className="card flex flex-col py-2" aria-labelledby="recent-title">
      <div className="flex items-baseline justify-between gap-2 px-6 pt-4 pb-2">
        <h2 id="recent-title" className="m-0 text-[17px] font-semibold">
          Recent analyses
        </h2>
        <span className="text-[12.5px] text-mu">Saved in this browser</span>
      </div>
      {history.length === 0 ? (
        <p className="m-0 border-t border-bd px-6 py-4 text-[13px] text-mu">No analyses saved in this browser.</p>
      ) : (
        <div className="overflow-x-auto">
          <div className="min-w-[720px]">
            <div className={`${grid} mono px-6 py-2.5 text-[11px] font-semibold tracking-[.07em] text-mu uppercase`}>
              <span>Ticker</span>
              <span>Model</span>
              <span>Period</span>
              <span className="text-right">Return</span>
              <span className="text-right">Sharpe</span>
              <span className="text-right">When</span>
            </div>
            {history.map((entry) => (
              <Link
                key={entry.id}
                to={`/analysis/${entry.id}`}
                aria-current={entry.id === currentId ? 'page' : undefined}
                className={`${grid} border-t border-bd px-6 py-3.5 text-sm text-tx no-underline hover:bg-s2 ${entry.id === currentId ? 'bg-s2' : ''}`}
              >
                <span className="mono font-semibold">{entry.ticker || 'CSV'}</span>
                <span className="truncate">{entry.model || NA}</span>
                <span className="mono text-[13px] text-mu">
                  {entry.startDate || '?'} → {entry.endDate || '?'}
                </span>
                <span className={`mono text-right ${signColor(entry.totalReturn)}`}>{formatSignedPercent(entry.totalReturn)}</span>
                <span className="mono text-right">{formatRatio(entry.sharpe)}</span>
                <span className="text-right text-[13px] text-mu">{relativeTime(entry.createdAt)}</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

export default function OverviewTab({ analysis, report }) {
  return (
    <>
      <MetricCards metrics={analysis.result.backtest.metrics || {}} />
      <div className="flex flex-wrap items-stretch gap-6">
        <PerformanceCard analysis={analysis} />
        <RegimesCard analysis={analysis} />
      </div>
      <div className="flex flex-wrap items-stretch gap-6">
        <ShapCard analysis={analysis} />
        <ReportSummaryCard analysis={analysis} report={report} />
      </div>
      <div className="flex flex-wrap items-start gap-6">
        <RiskTable analysis={analysis} />
        <SettingsPanel analysis={analysis} />
      </div>
      <RecentAnalyses currentId={analysis.id} />
    </>
  )
}
