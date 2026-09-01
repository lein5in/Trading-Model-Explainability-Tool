const REGIME_COLORS = {
  bullish: '#22c55e',
  bearish: '#ef4444',
  choppy: '#a3a3a3',
}

const REGIME_LABELS = {
  bullish: 'Bull',
  bearish: 'Bear',
  choppy: 'Range',
}

const REGIME_ORDER = ['bullish', 'choppy', 'bearish']

function FeatureImportanceByRegime({ regimeSegmentedImportance, featureNames }) {
  if (!regimeSegmentedImportance || featureNames.length === 0) {
    return <p className="text-sm text-neutral-600">No feature importance data available.</p>
  }

  const maxValue = Math.max(
    0.0001,
    ...featureNames.flatMap((name) =>
      REGIME_ORDER.map((regime) => regimeSegmentedImportance[regime]?.[name] ?? 0)
    )
  )

  return (
    <div className="space-y-4">
      <div className="flex gap-4 text-xs text-neutral-500 pl-32">
        {REGIME_ORDER.map((regime) => (
          <div key={regime} className="flex items-center gap-1.5 flex-1">
            <span
              className="w-2 h-2 rounded-full inline-block"
              style={{ backgroundColor: REGIME_COLORS[regime] }}
            />
            {REGIME_LABELS[regime]}
          </div>
        ))}
      </div>

      {featureNames.map((name) => (
        <div key={name} className="flex items-center gap-4">
          <span className="w-28 shrink-0 text-xs text-neutral-400 truncate">{name}</span>
          <div className="flex gap-4 flex-1">
            {REGIME_ORDER.map((regime) => {
              const value = regimeSegmentedImportance[regime]?.[name] ?? 0
              const widthPct = (value / maxValue) * 100
              return (
                <div key={regime} className="flex-1 flex items-center gap-2">
                  <div className="flex-1 h-4 bg-neutral-900 rounded-sm overflow-hidden">
                    <div
                      className="h-full rounded-sm"
                      style={{
                        width: `${widthPct}%`,
                        backgroundColor: REGIME_COLORS[regime],
                        opacity: 0.85,
                      }}
                    />
                  </div>
                  <span className="text-xs text-neutral-500 w-12 text-right shrink-0">
                    {value.toFixed(3)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

export default FeatureImportanceByRegime