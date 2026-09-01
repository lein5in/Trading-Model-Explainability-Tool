import MetricsBar from './MetricsBar'
import PriceChart from '../charts/PriceChart'
import RegimeBar from '../charts/RegimeBar'

function EquityCurveChart({ equityCurve }) {
  const points = equityCurve.filter((p) => p.timestamp !== null)
  if (points.length === 0) {
    return <p className="text-xs text-neutral-600">No trades executed.</p>
  }

  const values = points.map((p) => p.equity)
  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)
  const range = maxValue - minValue || 1

  const width = 800
  const height = 120
  const pathPoints = points.map((p, i) => {
    const x = (i / (points.length - 1 || 1)) * width
    const y = height - ((p.equity - minValue) / range) * height
    return `${x},${y}`
  })

  const areaPath = `M0,${height} L${pathPoints.join(' L')} L${width},${height} Z`
  const linePath = `M${pathPoints.join(' L')}`

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-28" preserveAspectRatio="none">
      <path d={areaPath} fill="rgba(82, 82, 82, 0.25)" />
      <path d={linePath} fill="none" stroke="#a3a3a3" strokeWidth="1.5" />
    </svg>
  )
}

function OverviewView({ analysisResult, onTradeClick }) {
  const { backtest, regime, ohlcv } = analysisResult

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider mb-2">
        Overview
      </h2>

      <MetricsBar backtest={backtest} />

      <div className="border border-neutral-800 rounded p-4">
        <PriceChart
          ohlcv={ohlcv}
          trades={backtest?.trades}
          onTradeClick={onTradeClick}
        />
      </div>

      <div>
        <p className="text-xs text-neutral-500 mb-1">Market Regime</p>
        <RegimeBar regimePerBar={regime?.regime_per_bar} />
      </div>

      {backtest?.equity_curve && (
        <div className="border border-neutral-800 rounded p-4">
          <p className="text-xs text-neutral-500 mb-2">Equity Curve</p>
          <EquityCurveChart equityCurve={backtest.equity_curve} />
        </div>
      )}
    </div>
  )
}

export default OverviewView