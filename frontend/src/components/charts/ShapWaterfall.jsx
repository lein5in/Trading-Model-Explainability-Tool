function ShapWaterfall({ featureNames, shapValuesForTrade, baseValue }) {
  if (!featureNames || !shapValuesForTrade) {
    return <p className="text-sm text-neutral-600">No SHAP data available for this trade.</p>
  }

  const contributions = featureNames.map((name, i) => ({
    name,
    value: shapValuesForTrade[i],
  }))

  let cumulative = baseValue
  const steps = [{ label: 'Base value', start: baseValue, end: baseValue, isBase: true }]

  for (const contribution of contributions) {
    const start = cumulative
    cumulative += contribution.value
    steps.push({
      label: contribution.name,
      start,
      end: cumulative,
      value: contribution.value,
      isBase: false,
    })
  }

  steps.push({ label: 'Final value', start: cumulative, end: cumulative, isFinal: true })

  const allValues = steps.flatMap((s) => [s.start, s.end])
  const minValue = Math.min(...allValues)
  const maxValue = Math.max(...allValues)
  const range = maxValue - minValue || 1

  function toPct(value) {
    return ((value - minValue) / range) * 100
  }

  return (
    <div className="space-y-2">
      {steps.map((step, index) => {
        if (step.isBase || step.isFinal) {
          const pos = toPct(step.start)
          return (
            <div key={index} className="flex items-center gap-3">
              <span className="w-28 shrink-0 text-xs text-neutral-500">{step.label}</span>
              <div className="flex-1 h-4 relative bg-neutral-900 rounded-sm">
                <div
                  className="absolute top-0 h-full w-0.5 bg-neutral-400"
                  style={{ left: `${pos}%` }}
                />
              </div>
              <span className="text-xs text-neutral-500 w-16 text-right shrink-0">
                {step.start.toFixed(3)}
              </span>
            </div>
          )
        }

        const left = toPct(Math.min(step.start, step.end))
        const width = Math.abs(toPct(step.end) - toPct(step.start))
        const isPositive = step.value >= 0

        return (
          <div key={index} className="flex items-center gap-3">
            <span className="w-28 shrink-0 text-xs text-neutral-400 truncate">{step.label}</span>
            <div className="flex-1 h-4 relative bg-neutral-900 rounded-sm overflow-hidden">
              <div
                className="absolute top-0 h-full rounded-sm"
                style={{
                  left: `${left}%`,
                  width: `${width}%`,
                  backgroundColor: isPositive ? '#22c55e' : '#ef4444',
                  opacity: 0.85,
                }}
              />
            </div>
            <span
              className={`text-xs w-16 text-right shrink-0 ${
                isPositive ? 'text-green-500' : 'text-red-500'
              }`}
            >
              {isPositive ? '+' : ''}
              {step.value.toFixed(3)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default ShapWaterfall