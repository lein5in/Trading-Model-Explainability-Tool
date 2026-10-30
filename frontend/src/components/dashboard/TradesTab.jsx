import { useMemo, useState } from 'react'
import { TRADE_WINDOW_AFTER, TRADE_WINDOW_BEFORE } from '../../config.js'
import { explainedOutput, tickerLabel, unavailableReason } from '../../lib/analysis.js'
import { ohlcSlice, tradeWindow, volumeAtPrice } from '../../lib/chartData.js'
import { COLORS } from '../../lib/chartTheme.js'
import { NA, formatDate, formatInt, formatNumber, formatPrice, formatSignedNumber, formatSignedPercent, isNumber, signColor } from '../../lib/format.js'
import { TRADE_FILTERS, filterTrades, paginate } from '../../lib/trades.js'
import { buildWaterfall, domainPercent, waterfallDomain } from '../../lib/waterfall.js'
import TradeChart from '../charts/TradeChart.jsx'
import { RegimeDot, Segmented, Unavailable } from '../ui.jsx'

const ROW_GRID = 'grid grid-cols-[40px_72px_minmax(92px,1fr)_minmax(92px,1fr)_72px_40px_84px_56px] items-center gap-3'

function sideView(side) {
  const long = side === 'long'
  return { arrow: long ? '▲' : '▼', label: long ? 'LONG' : 'SHORT', className: long ? 'text-pos' : 'text-neg' }
}

function outputAt(predictions, index) {
  const value = predictions?.output?.[index]
  return isNumber(value) ? value : null
}

function TradeTable({ trades, filtered, page, onPage, filter, onFilter, selectedId, onSelect, predictions, outputLabel }) {
  const pageData = paginate(filtered, page)
  return (
    <section className="card flex min-w-0 flex-[1_1_680px] flex-col" aria-labelledby="trades-title">
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-5">
        <h2 id="trades-title" className="m-0 text-[17px] font-semibold">
          All trades <span className="mono ml-1.5 text-sm font-normal text-mu">{formatInt(trades.length)}</span>
        </h2>
        <Segmented small label="Filter" value={filter} onChange={onFilter} options={TRADE_FILTERS} />
      </div>
      <div className="overflow-x-auto border-t border-bd">
        <div className="min-w-[630px]">
          <div className={`${ROW_GRID} mono px-6 py-2.5 text-[11px] font-semibold tracking-[.07em] text-mu uppercase`} aria-hidden="true">
            <span>#</span>
            <span>Side</span>
            <span>Entry</span>
            <span>Exit</span>
            <span className="text-right">Return</span>
            <span className="text-right">Bars</span>
            <span>Regime</span>
            <span className="truncate text-right normal-case">{outputLabel}</span>
          </div>
          {pageData.items.length === 0 && <p className="m-0 border-t border-bd px-6 py-4 text-[13px] text-mu">No trade matches this filter.</p>}
          <ul className="m-0 list-none p-0" aria-label="Trades">
            {pageData.items.map((trade) => {
              const side = sideView(trade.side)
              const selected = trade.id === selectedId
              const probability = outputAt(predictions, trade.signal_bar_index)
              return (
                <li key={trade.id}>
                  <button
                    type="button"
                    aria-pressed={selected}
                    aria-label={`Trade ${trade.id}, ${trade.side}, ${formatDate(trade.entry_date)} to ${formatDate(trade.exit_date)}, return ${formatSignedPercent(trade.return, 2)}`}
                    onClick={() => onSelect(trade.id)}
                    className={`${ROW_GRID} w-full border-0 border-t border-solid border-bd px-6 py-3 text-left text-sm text-tx focus-visible:outline-offset-[-2px] ${selected ? 'bg-s2 shadow-[inset_0_0_0_1.5px_var(--color-ac)]' : 'bg-transparent hover:bg-s2'}`}
                  >
                    <span className="mono font-semibold">{trade.id}</span>
                    <span className={`mono text-[12.5px] ${side.className}`}>
                      {side.arrow} {side.label}
                    </span>
                    <span className="mono text-[13px]">{formatDate(trade.entry_date)}</span>
                    <span className="mono text-[13px]">{formatDate(trade.exit_date)}</span>
                    <span className={`mono text-right ${signColor(trade.return)}`}>{formatSignedPercent(trade.return, 2)}</span>
                    <span className="mono text-right">{formatInt(trade.bars_held)}</span>
                    <span className="inline-flex items-center gap-2 text-[13px]">
                      {trade.regime ? <RegimeDot regime={trade.regime} /> : null}
                      {trade.regime || NA}
                    </span>
                    <span className="mono text-right">{formatNumber(probability, 2)}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-bd px-6 py-3.5">
        <span className="mono text-[12.5px] text-mu" aria-live="polite">
          {pageData.total ? `Trades ${formatInt(pageData.from)} to ${formatInt(pageData.to)} of ${formatInt(pageData.total)}` : '0 trades'}
        </span>
        <div className="flex gap-2">
          <button type="button" className="btn btn-sm" disabled={!pageData.hasPrevious} onClick={() => onPage(pageData.page - 1)}>
            Previous
          </button>
          <button type="button" className="btn btn-sm" disabled={!pageData.hasNext} onClick={() => onPage(pageData.page + 1)}>
            Next
          </button>
        </div>
      </div>
    </section>
  )
}

function VolumeProfile({ profile, entryPrice }) {
  if (!profile) return <Unavailable title="No volume data" reason="The bars around this trade have no OHLCV volume." />
  const width = 600
  const height = 200
  const binHeight = height / profile.bins.length
  const columns = profile.cells.length ? Math.max(...profile.cells.map((cell) => cell.offset)) + 1 : 1
  const columnWidth = width / columns
  const yOf = (price) => height - ((price - profile.low) / (profile.high - profile.low || 1)) * height
  const ticks = [0, 1, 2, 3, 4].map((k) => profile.high - (k * (profile.high - profile.low)) / 4)
  return (
    <div className="flex flex-col gap-2">
      <div className="flex border border-bd bg-bg">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`Heatmap of volume traded at each price over ${columns} bars, built from daily OHLCV`}
          className="block h-[200px] min-w-0 flex-1"
        >
          {profile.cells.map((cell, index) => (
            <rect
              key={index}
              x={cell.offset * columnWidth}
              y={height - (cell.bin + 1) * binHeight}
              width={columnWidth + 0.3}
              height={binHeight + 0.3}
              fill={COLORS.ac}
              fillOpacity={0.05 + (profile.maxCell > 0 ? (cell.volume / profile.maxCell) * 0.6 : 0)}
            />
          ))}
          {isNumber(entryPrice) && <line x1="0" x2={width} y1={yOf(entryPrice)} y2={yOf(entryPrice)} stroke={COLORS.ac} strokeDasharray="3 4" vectorEffect="non-scaling-stroke" />}
        </svg>
        <svg viewBox={`0 0 60 ${height}`} preserveAspectRatio="none" role="img" aria-label="Volume profile by price level, up and down bars" className="block h-[200px] w-14 border-l border-bd">
          {profile.bins.map((bin, index) => {
            const up = profile.maxBin > 0 ? (bin.up / profile.maxBin) * 58 : 0
            const down = profile.maxBin > 0 ? (bin.down / profile.maxBin) * 58 : 0
            const y = height - (index + 1) * binHeight + 0.5
            return (
              <g key={index}>
                <rect x="0" y={y} width={up} height={Math.max(0, binHeight - 1)} fill={COLORS.pos} fillOpacity="0.75" />
                <rect x={up} y={y} width={down} height={Math.max(0, binHeight - 1)} fill={COLORS.neg} fillOpacity="0.75" />
              </g>
            )
          })}
        </svg>
        <div className="mono flex h-[200px] w-[62px] flex-col justify-between border-l border-bd py-0.5 pl-1.5 text-[11px] text-mu" aria-hidden="true">
          {ticks.map((tick, index) => (
            <span key={index}>{formatPrice(tick)}</span>
          ))}
        </div>
      </div>
      <span className="text-xs text-mu">
        Volume at price, built from the daily OHLCV of the same bars (each bar's volume spread evenly over its high-low range), never from order-book data. Right: total per
        price level, green for up bars and red for down bars.
      </span>
    </div>
  )
}

function Waterfall({ analysis, trade }) {
  const shap = analysis.result.shap
  const predictions = analysis.result.predictions
  const output = explainedOutput(analysis)
  const row = shap && isNumber(trade.shap_row_index) ? shap.trade_rows?.[trade.shap_row_index] : null
  const waterfall = useMemo(() => buildWaterfall(row, 5), [row])
  const threshold = predictions?.threshold
  const discrete = predictions?.signal_type === 'discrete'
  const domain = useMemo(() => waterfallDomain(waterfall, threshold, discrete), [waterfall, threshold, discrete])

  if (!shap) {
    return <Unavailable title="Not explained" reason={unavailableReason(analysis, 'shap', 'SHAP values were not computed for this analysis.')} />
  }
  if (!waterfall) {
    return (
      <Unavailable
        title="Not explained"
        reason={
          shap.trade_rows_capped
            ? 'This trade is beyond the cap on explained trade rows, so it has no SHAP explanation.'
            : 'The signal bar of this trade had no complete feature row, so it has no SHAP explanation.'
        }
      />
    )
  }

  const bar = (start, end) => {
    const left = domainPercent(Math.min(start, end), domain)
    const right = domainPercent(Math.max(start, end), domain)
    return { left: `${left}%`, width: `${Math.max(0.8, right - left)}%` }
  }
  const solid = (value) => ({ left: 0, width: `${domainPercent(value, domain)}%` })
  const thresholdLeft = isNumber(threshold) ? `${domainPercent(threshold, domain)}%` : null
  const ticks = [0, 1, 2, 3, 4].map((k) => domain[0] + (k * (domain[1] - domain[0])) / 4)
  const finalValue = waterfall.output ?? waterfall.final
  const above = isNumber(threshold) && finalValue >= threshold
  const guide = thresholdLeft ? <div className="absolute top-0 bottom-0 w-px bg-mu" style={{ left: thresholdLeft }} /> : null

  return (
    <div className="flex flex-col gap-3">
      <p className="m-0 text-[13px] leading-[1.55] text-mu">
        Starting from the base value of <span className="mono text-tx">{formatNumber(waterfall.base, 3)}</span>, the features on the signal bar moved {output} to{' '}
        <span className="mono text-tx">{formatNumber(finalValue, 3)}</span>.
        {isNumber(threshold) && (
          <>
            {' '}
            That is {above ? 'at or above' : 'below'} the <span className="mono text-tx">{formatNumber(threshold, 2)}</span> threshold, so the strategy went {trade.side} at the
            next open.
          </>
        )}
      </p>
      <div className="flex flex-col gap-1.5" role="img" aria-label={`SHAP waterfall for trade ${trade.id}: base ${formatNumber(waterfall.base, 3)}, final ${formatNumber(finalValue, 3)}`}>
        <div className="flex items-center gap-3">
          <span className="mono w-44 flex-none text-[12.5px] text-mu">base value</span>
          <div className="relative h-[22px] flex-1">
            {guide}
            <div className="absolute top-[3px] bottom-[3px] rounded-[3px] bg-bh opacity-55" style={solid(waterfall.base)} />
          </div>
          <span className="mono w-[62px] flex-none text-right text-[12.5px]">{formatNumber(waterfall.base, 3)}</span>
        </div>
        {waterfall.items.map((item) => {
          const label = item.kind === 'other' ? `${item.count} other features` : `${item.feature} = ${formatNumber(item.value, 4)}`
          return (
            <div key={item.feature || 'other'} className="flex items-center gap-3">
              <span className="mono w-44 flex-none truncate text-[12.5px]" title={label}>
                {label}
              </span>
              <div className="relative h-[22px] flex-1">
                {guide}
                <div className={`absolute top-[3px] bottom-[3px] rounded-[3px] ${item.delta >= 0 ? 'bg-pos' : 'bg-neg'}`} style={bar(item.start, item.end)} />
              </div>
              <span className={`mono w-[62px] flex-none text-right text-[12.5px] ${item.delta >= 0 ? 'text-pos' : 'text-neg'}`}>{formatSignedNumber(item.delta, 3)}</span>
            </div>
          )
        })}
        <div className="mt-0.5 flex items-center gap-3 border-t border-bd pt-2">
          <span className="mono w-44 flex-none text-[12.5px] font-semibold">{output} at entry</span>
          <div className="relative h-[22px] flex-1">
            {guide}
            <div className="absolute top-[3px] bottom-[3px] rounded-[3px] bg-bh opacity-55" style={solid(finalValue)} />
          </div>
          <span className="mono w-[62px] flex-none text-right text-[12.5px] font-semibold">{formatNumber(finalValue, 3)}</span>
        </div>
        <div className="mono flex gap-3 text-[11.5px] text-mu" aria-hidden="true">
          <span className="w-44 flex-none" />
          <span className="flex flex-1 justify-between">
            {ticks.map((tick, index) => (
              <span key={index}>{formatNumber(tick, 2)}</span>
            ))}
          </span>
          <span className="w-[62px] flex-none" />
        </div>
      </div>
      <div className="flex flex-wrap gap-[18px] text-[12.5px] text-mu">
        <span className="inline-flex items-center gap-2">
          <span className="h-3 w-3 rounded-sm bg-pos" />+ pushes toward buy
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="h-3 w-3 rounded-sm bg-neg" />- pushes toward sell
        </span>
        {isNumber(threshold) && (
          <span className="inline-flex items-center gap-2">
            <span className="h-3.5 w-px bg-mu" />
            <span className="mono">{formatNumber(threshold, 2)}</span> threshold
          </span>
        )}
      </div>
    </div>
  )
}

function TradeDetail({ analysis, trade }) {
  const result = analysis.result
  const bars = result.bars
  const predictions = result.predictions
  const output = explainedOutput(analysis)
  const ticker = tickerLabel(analysis)
  const side = sideView(trade.side)

  const range = useMemo(() => tradeWindow(bars?.date?.length ?? 0, trade, TRADE_WINDOW_BEFORE, TRADE_WINDOW_AFTER), [bars, trade])
  const slice = useMemo(() => ohlcSlice(bars, range), [bars, range])
  const profile = useMemo(() => volumeAtPrice(slice, 20), [slice])
  const chartData = useMemo(() => {
    const long = trade.side === 'long'
    const entryTime = formatDate(trade.entry_date)
    const exitTime = formatDate(trade.exit_date)
    const markers = [
      { time: entryTime, position: long ? 'belowBar' : 'aboveBar', shape: long ? 'arrowUp' : 'arrowDown', color: long ? COLORS.pos : COLORS.neg, text: 'entry' },
      { time: exitTime, position: 'aboveBar', shape: 'circle', color: COLORS.ac, text: 'exit' },
    ].sort((a, b) => a.time.localeCompare(b.time))
    return {
      candles: slice.map((bar) => ({ time: bar.time, open: bar.open, high: bar.high, low: bar.low, close: bar.close })),
      volume: slice.map((bar) => ({
        time: bar.time,
        value: isNumber(bar.volume) ? bar.volume : 0,
        color: bar.close >= bar.open ? 'rgba(46, 189, 133, 0.6)' : 'rgba(246, 70, 93, 0.6)',
      })),
      probability: slice.map((bar) => {
        const value = outputAt(predictions, bar.index)
        return value === null ? { time: bar.time } : { time: bar.time, value }
      }),
      markers,
      entryPrice: trade.entry_price,
      threshold: predictions?.threshold,
      thresholdLabel: 'threshold',
    }
  }, [slice, trade, predictions])

  const entryIndex = trade.entry_bar_index
  const entryBar = bars ? { open: bars.open?.[entryIndex], high: bars.high?.[entryIndex], low: bars.low?.[entryIndex], close: bars.close?.[entryIndex] } : {}
  const signalOutput = outputAt(predictions, trade.signal_bar_index)
  const signalDate = bars?.date?.[trade.signal_bar_index]

  const fields = [
    { label: 'Entry (next open)', value: `${formatDate(trade.entry_date)} @ ${formatPrice(trade.entry_price)}` },
    { label: trade.closed_at_end ? 'Exit (last close)' : 'Exit (next open)', value: `${formatDate(trade.exit_date)} @ ${formatPrice(trade.exit_price)}` },
    { label: 'Bars held', value: formatInt(trade.bars_held) },
    { label: 'Regime at signal', value: trade.regime || NA, regime: trade.regime },
    { label: 'Signal bar', value: `${formatDate(signalDate)}, fill at i+1` },
    { label: 'Costs paid', value: formatPrice(trade.costs) },
    { label: 'MFE (best open P&L)', value: formatSignedPercent(trade.mfe, 2), className: 'text-pos' },
    { label: 'MAE (worst open P&L)', value: formatSignedPercent(trade.mae, 2), className: 'text-neg' },
  ]

  return (
    <section className="card flex min-w-0 flex-[1_1_480px] flex-col gap-[22px] p-6" aria-labelledby="detail-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <span className="lbl">Selected trade</span>
          <h2 id="detail-title" className="m-0 text-[22px] font-semibold">
            <span className="mono">#{trade.id}</span>{' '}
            <span className={`mono text-base ${side.className}`}>
              {side.arrow} {side.label}
            </span>
          </h2>
        </div>
        <span className={`mono text-[30px] font-semibold tracking-[-.02em] ${signColor(trade.return)}`}>{formatSignedPercent(trade.return, 2)}</span>
      </div>

      <dl className="m-0 grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-x-5 gap-y-4 text-sm">
        {fields.map((field) => (
          <div key={field.label}>
            <dt className="lbl mb-1">{field.label}</dt>
            <dd className={`m-0 ${field.regime ? 'inline-flex items-center gap-2' : 'mono'} ${field.className || ''}`}>
              {field.regime && <RegimeDot regime={field.regime} />}
              {field.value}
            </dd>
          </div>
        ))}
      </dl>

      <div className="flex flex-col gap-2.5">
        <span className="lbl">Price around the trade</span>
        <div className="flex flex-col overflow-hidden rounded-md border border-bd bg-bg">
          <div className="mono flex flex-wrap gap-3.5 border-b border-bd px-3 py-2 text-[11.5px] text-mu">
            <span className="text-tx">{ticker || 'CSV'} · 1D</span>
            <span>
              O {formatPrice(entryBar.open)} H {formatPrice(entryBar.high)} L {formatPrice(entryBar.low)} C {formatPrice(entryBar.close)} (entry bar)
            </span>
            <span>
              {output} at signal bar <span className="text-tx">{formatNumber(signalOutput, 2)}</span>
              {isNumber(predictions?.threshold) ? ` · threshold ${formatNumber(predictions.threshold, 2)}` : ''}
            </span>
          </div>
          {slice.length ? (
            <TradeChart
              data={chartData}
              ariaLabel={`Daily candles from ${slice[0].time} to ${slice[slice.length - 1].time} around trade ${trade.id}, with volume, ${output} and entry and exit markers`}
            />
          ) : (
            <div className="p-4">
              <Unavailable title="No price data" reason="The bars around this trade are not stored." />
            </div>
          )}
        </div>
        <div className="mono flex flex-wrap gap-5 text-xs text-mu">
          <span className="inline-flex items-center gap-2">
            <svg width="22" height="10" aria-hidden="true">
              <line x1="0" y1="5" x2="22" y2="5" stroke={COLORS.ac} strokeWidth="2" strokeDasharray="4 3" />
            </svg>
            Entry price {formatPrice(trade.entry_price)}
          </span>
          <span>Panes: candles, volume, {output}</span>
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        <span className="lbl">Volume at price</span>
        <VolumeProfile profile={profile} entryPrice={trade.entry_price} />
      </div>

      <div className="flex flex-col gap-3">
        <span className="lbl">Why the model bought or sold: SHAP on the signal bar</span>
        <Waterfall analysis={analysis} trade={trade} />
      </div>
    </section>
  )
}

export default function TradesTab({ analysis }) {
  const trades = useMemo(() => analysis.result.backtest.trades || [], [analysis])
  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState(null)
  const filtered = useMemo(() => filterTrades(trades, filter), [trades, filter])
  const selected = trades.find((trade) => trade.id === selectedId) || filtered[0] || null
  const outputLabel = explainedOutput(analysis)

  if (!trades.length) {
    return <Unavailable title="No trades" reason="The strategy never entered a position over this period." />
  }

  return (
    <div className="flex flex-wrap items-start gap-6">
      <TradeTable
        trades={trades}
        filtered={filtered}
        page={page}
        onPage={setPage}
        filter={filter}
        onFilter={(value) => {
          setFilter(value)
          setPage(1)
          setSelectedId(null)
        }}
        selectedId={selected?.id}
        onSelect={setSelectedId}
        predictions={analysis.result.predictions}
        outputLabel={outputLabel}
      />
      {selected ? (
        <TradeDetail analysis={analysis} trade={selected} />
      ) : (
        <section className="card flex min-w-0 flex-[1_1_520px] flex-col p-6">
          <Unavailable title="No trade selected" reason="No trade matches this filter." />
        </section>
      )}
    </div>
  )
}
