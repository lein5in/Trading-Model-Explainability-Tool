import { useState } from 'react'
import PriceChart from '../charts/PriceChart'
import ShapWaterfall from '../charts/ShapWaterfall'
import { explainSection } from '../../lib/api'

function directionLabel(direction) {
  if (direction === 1) return 'LONG'
  if (direction === -1) return 'SHORT'
  return 'FLAT'
}

function formatDuration(entryTimestamp, exitTimestamp) {
  if (!exitTimestamp) return '—'
  const entry = new Date(entryTimestamp)
  const exit = new Date(exitTimestamp)
  const diffMs = exit - entry
  const diffDays = diffMs / (1000 * 60 * 60 * 24)
  return `${diffDays.toFixed(1)}d`
}

function TradeDetailView({ analysisId, analysisResult, trade, tradeIndex, onBack }) {
  const [interpretation, setInterpretation] = useState(null)
  const [status, setStatus] = useState('idle')

  const { ohlcv, shap } = analysisResult

  const shapRowIndex = trade.shap_row_index
  const hasShapData =
    shapRowIndex !== undefined &&
    shapRowIndex !== null &&
    shapRowIndex >= 0 &&
    shap &&
    Array.isArray(shap.shap_values) &&
    shapRowIndex < shap.shap_values.length

  const entryTime = new Date(trade.entry_timestamp).getTime()
  const exitTime = trade.exit_timestamp ? new Date(trade.exit_timestamp).getTime() : entryTime
  const paddingMs = 1000 * 60 * 60 * 24 * 5
  const zoomedOhlcv = ohlcv.filter((bar) => {
    const barTime = new Date(bar.timestamp).getTime()
    return barTime >= entryTime - paddingMs && barTime <= exitTime + paddingMs
  })

  async function handleLoadInterpretation() {
    setStatus('loading')
    try {
      const result = await explainSection({
        analysisId,
        sectionName: `Trade at ${trade.entry_timestamp}`,
        tradeIndex,
      })
      setInterpretation(result.explanation)
      setStatus('done')
    } catch (err) {
      setStatus('error')
      setInterpretation(err.message)
    }
  }

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={onBack}
        className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
      >
        ← Back to Overview
      </button>

      <h2 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">
        Trade Detail
      </h2>

      <div className="grid grid-cols-2 gap-4">
        <div className="border border-neutral-800 rounded p-4 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-neutral-500">Direction</span>
            <span className={trade.direction === 1 ? 'text-green-500' : 'text-red-500'}>
              {directionLabel(trade.direction)}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-neutral-500">Entry Price</span>
            <span className="text-neutral-200">{trade.entry_price?.toFixed(4)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-neutral-500">Exit Price</span>
            <span className="text-neutral-200">
              {trade.exit_price ? trade.exit_price.toFixed(4) : '—'}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-neutral-500">Duration</span>
            <span className="text-neutral-200">
              {formatDuration(trade.entry_timestamp, trade.exit_timestamp)}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-neutral-500">PnL</span>
            <span className={trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
              {trade.pnl >= 0 ? '+' : ''}
              {trade.pnl.toFixed(4)}
            </span>
          </div>
        </div>

        <div className="border border-neutral-800 rounded p-4">
          <PriceChart ohlcv={zoomedOhlcv} trades={[trade]} />
        </div>
      </div>

      <div className="border border-neutral-800 rounded p-4">
        <p className="text-xs text-neutral-500 mb-3">SHAP Waterfall</p>
        {hasShapData ? (
          <ShapWaterfall
            featureNames={shap.feature_names}
            shapValuesForTrade={shap.shap_values[shapRowIndex]}
            baseValue={shap.base_value}
          />
        ) : (
          <p className="text-sm text-neutral-600">No SHAP data available for this trade.</p>
        )}
      </div>

      {hasShapData && (
        <div className="border border-neutral-800 rounded p-4">
          {status === 'idle' && (
            <button
              type="button"
              onClick={handleLoadInterpretation}
              className="text-xs text-neutral-500 hover:text-neutral-300 border border-neutral-700 rounded px-2 py-1 transition-colors"
            >
              Explain this trade
            </button>
          )}
          {status === 'loading' && (
            <p className="text-xs text-neutral-600">Generating interpretation...</p>
          )}
          {status === 'error' && <p className="text-xs text-red-500">{interpretation}</p>}
          {status === 'done' && (
            <p className="text-xs text-neutral-400 leading-relaxed">{interpretation}</p>
          )}
        </div>
      )}
    </div>
  )
}

export default TradeDetailView