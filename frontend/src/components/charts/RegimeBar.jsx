const REGIME_COLORS = {
  bullish: '#22c55e',
  bearish: '#ef4444',
  choppy: '#525252',
}

function RegimeBar({ regimePerBar }) {
  if (!regimePerBar || regimePerBar.length === 0) {
    return null
  }

  const segments = []
  let currentRegime = null
  let currentStart = 0

  for (let i = 0; i < regimePerBar.length; i++) {
    const regime = regimePerBar[i]
    if (regime !== currentRegime) {
      if (currentRegime !== null) {
        segments.push({ regime: currentRegime, start: currentStart, end: i })
      }
      currentRegime = regime
      currentStart = i
    }
  }
  if (currentRegime !== null) {
    segments.push({ regime: currentRegime, start: currentStart, end: regimePerBar.length })
  }

  const total = regimePerBar.length

  return (
    <div className="w-full h-3 flex rounded-sm overflow-hidden border border-neutral-800">
      {segments.map((segment, index) => {
        const widthPct = ((segment.end - segment.start) / total) * 100
        return (
          <div
            key={index}
            style={{
              width: `${widthPct}%`,
              backgroundColor: segment.regime ? REGIME_COLORS[segment.regime] : '#171717',
            }}
            title={segment.regime ?? 'unknown'}
          />
        )
      })}
    </div>
  )
}

export default RegimeBar