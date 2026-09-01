function formatPct(value) {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(2)}%`
}

function formatNumber(value, decimals = 2) {
  if (value === null || value === undefined) return '—'
  return value.toFixed(decimals)
}

function MetricCard({ label, value, positive }) {
  const colorClass =
    positive === true ? 'text-green-500' : positive === false ? 'text-red-500' : 'text-neutral-200'
  return (
    <div className="border border-neutral-800 rounded px-4 py-3 flex-1 min-w-[120px]">
      <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-lg font-semibold ${colorClass}`}>{value}</p>
    </div>
  )
}

function MetricsBar({ backtest }) {
  if (!backtest) {
    return null
  }

  const totalReturn = backtest.total_return_pct
  const cagr = backtest.cagr

  return (
    <div className="flex flex-wrap gap-3 mb-6">
      <MetricCard
        label="Total Return"
        value={formatPct(totalReturn)}
        positive={totalReturn !== null ? totalReturn >= 0 : null}
      />
      <MetricCard
        label="CAGR"
        value={formatPct(cagr)}
        positive={cagr !== null ? cagr >= 0 : null}
      />
      <MetricCard label="Sharpe" value={formatNumber(backtest.sharpe_ratio)} />
      <MetricCard
        label="Max Drawdown"
        value={formatPct(backtest.max_drawdown)}
        positive={
          backtest.max_drawdown !== null && backtest.max_drawdown !== undefined
            ? backtest.max_drawdown === 0
              ? null
              : false
            : null
        }
      />
      <MetricCard label="Trades" value={backtest.trade_count ?? '—'} />
      <MetricCard label="Win Rate" value={formatPct(backtest.win_rate)} />
    </div>
  )
}

export default MetricsBar