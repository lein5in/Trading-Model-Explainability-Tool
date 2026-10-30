import { useMemo, useRef, useState } from 'react'
import { CATALOG_POINT_IN_TIME_NOTICE } from '../../config.js'
import { useElementWidth } from '../../hooks/useElementWidth.js'
import { explainedOutput, unavailableReason } from '../../lib/analysis.js'
import { effectsBySample, featureColumn } from '../../lib/effect.js'
import { NA, formatInt, formatNumber, formatSmall, isNumber } from '../../lib/format.js'
import { REGIME_NAMES, regimeColorVar } from '../../lib/regimes.js'
import { DefinitionList, PointInTimeNotice, RegimeDot, Unavailable } from '../ui.jsx'

const HEIGHT = 320

function adaptiveDigits(low, high) {
  const span = Math.abs(high - low)
  if (!isNumber(span) || span === 0) return 3
  if (span >= 100) return 0
  if (span >= 10) return 1
  if (span >= 1) return 2
  if (span >= 0.1) return 3
  return 4
}

function heatStyle(value, max) {
  if (!isNumber(value) || max <= 0) return undefined
  return { background: `color-mix(in srgb, var(--color-ac) ${Math.round((value / max) * 55)}%, transparent)` }
}

function ImportanceTable({ shap, output }) {
  const effects = useMemo(() => effectsBySample(shap), [shap])
  const ranked = useMemo(() => Object.entries(shap.feature_importance || {}).sort((a, b) => b[1] - a[1]), [shap])
  const byRegime = shap.feature_importance_by_regime
  const globalMax = ranked.length ? ranked[0][1] : 0
  const regimeMax = byRegime ? Math.max(0, ...REGIME_NAMES.flatMap((name) => Object.values(byRegime[name]?.importance || {}))) : 0
  const grid = byRegime
    ? 'grid grid-cols-[minmax(170px,1.5fr)_minmax(200px,2fr)_repeat(3,minmax(88px,.7fr))_minmax(190px,1.6fr)] items-center gap-4'
    : 'grid grid-cols-[minmax(170px,1.5fr)_minmax(200px,2fr)_minmax(190px,1.6fr)] items-center gap-4'

  return (
    <section className="card flex flex-col gap-[18px] p-6" aria-labelledby="drivers-title">
      <div className="flex flex-col gap-2">
        <h2 id="drivers-title" className="m-0 text-[17px] font-semibold">
          What drives the model
        </h2>
        <p className="m-0 max-w-[780px] text-[13.5px] leading-[1.55] text-mu">
          Mean absolute contribution of each feature to <span className="mono text-tx">{output}</span>.{' '}
          {byRegime ? (
            <>
              The regime columns use the stratified sample:{' '}
              <span className="mono text-tx">{REGIME_NAMES.map((name) => formatInt(byRegime[name]?.n_rows)).join(' / ')}</span> rows for low, mid and high
              volatility. Darker cells mean a larger contribution in that regime.
            </>
          ) : (
            'Regimes were unavailable, so there is no regime breakdown.'
          )}
        </p>
      </div>
      <div className="overflow-x-auto">
        <div className={`${byRegime ? 'min-w-[760px]' : 'min-w-[560px]'} flex flex-col`} role="table" aria-label="Feature importance">
          <div role="row" className={`${grid} mono items-end px-3 py-2.5 text-[11px] font-semibold tracking-[.07em] text-mu uppercase`}>
            <span role="columnheader">Feature</span>
            <span role="columnheader">Mean |SHAP|</span>
            {byRegime &&
              REGIME_NAMES.map((name) => (
                <span key={name} role="columnheader" className="inline-flex items-center gap-1.5">
                  <RegimeDot regime={name} size={8} />
                  {name}
                </span>
              ))}
            <span role="columnheader">Effect of a higher value</span>
          </div>
          {ranked.map(([name, value]) => {
            const effect = effects[name] || {}
            return (
              <div key={name} role="row" className={`${grid} border-t border-bd p-3`}>
                <span role="cell" className="mono text-[13.5px] font-medium break-all">
                  {name}
                </span>
                <span role="cell" className="flex items-center gap-3">
                  <span className="h-3 flex-1 overflow-hidden rounded-[3px] bg-s2">
                    <span className="block h-full rounded-[3px] bg-ac" style={{ width: `${globalMax > 0 ? (value / globalMax) * 100 : 0}%` }} />
                  </span>
                  <span className="mono w-12 text-right text-[13px]">{formatNumber(value, 3)}</span>
                </span>
                {byRegime &&
                  REGIME_NAMES.map((regime) => {
                    const item = byRegime[regime] || {}
                    const cell = item.importance ? item.importance[name] : null
                    return (
                      <span
                        key={regime}
                        role="cell"
                        className="mono rounded px-2 py-1.5 text-center text-[13px] text-tx"
                        style={heatStyle(cell, regimeMax)}
                        title={item.importance ? (item.low_sample ? 'Small sample, read with care' : undefined) : 'No rows in this regime'}
                      >
                        {item.importance ? formatNumber(cell, 3) : 'no rows'}
                        {item.importance && item.low_sample ? '*' : ''}
                      </span>
                    )
                  })}
                <span
                  role="cell"
                  className={`inline-flex items-center gap-2 text-[13px] ${effect.direction === 'raises' ? 'text-pos' : effect.direction === 'lowers' ? 'text-neg' : 'text-mu'}`}
                >
                  <span className="mono" aria-hidden="true">
                    {effect.direction === 'raises' ? '▲' : effect.direction === 'lowers' ? '▼' : '–'}
                  </span>
                  {effect.direction === 'raises' ? `raises ${output}` : effect.direction === 'lowers' ? `lowers ${output}` : 'no clear direction'}
                </span>
              </div>
            )
          })}
        </div>
      </div>
      <p className="m-0 text-[12.5px] leading-[1.55] text-mu">
        The effect is the sign of the correlation between the feature value and its contribution in the stored sample. It describes this model on this sample and is
        not a statement about the market.
        {byRegime && REGIME_NAMES.some((name) => byRegime[name]?.low_sample) ? ' * Small sample: fewer rows than the low-sample threshold, read with care.' : ''}
      </p>
    </section>
  )
}

function DependenceScatter({ shap, output }) {
  const names = useMemo(() => shap.feature_names || [], [shap])
  const ranked = useMemo(() => [...names].sort((a, b) => (shap.feature_importance?.[b] ?? 0) - (shap.feature_importance?.[a] ?? 0)), [names, shap])
  const [picked, setPicked] = useState(null)
  const feature = picked && names.includes(picked) ? picked : ranked[0]
  const boxRef = useRef(null)
  const width = useElementWidth(boxRef)

  const points = useMemo(() => {
    const index = names.indexOf(feature)
    if (index < 0) return null
    const xs = featureColumn(shap.sample, index, 'feature_values')
    const ys = featureColumn(shap.sample, index, 'contributions')
    const regimes = shap.sample?.regime || []
    const list = xs.map((x, row) => ({ x, y: ys[row], regime: regimes[row] })).filter((point) => isNumber(point.x) && isNumber(point.y))
    if (!list.length) return { list, xMin: 0, xMax: 0, yMax: 0 }
    return {
      list,
      xMin: Math.min(...list.map((point) => point.x)),
      xMax: Math.max(...list.map((point) => point.x)),
      yMax: Math.max(...list.map((point) => Math.abs(point.y))) || 1,
    }
  }, [names, feature, shap])

  const padX = 12
  const plotWidth = Math.max(100, width - 68)
  const toX = (value) => (points.xMax === points.xMin ? plotWidth / 2 : padX + ((value - points.xMin) / (points.xMax - points.xMin)) * (plotWidth - padX * 2))
  const toY = (value) => HEIGHT / 2 - (value / points.yMax) * (HEIGHT / 2 - 8)
  const digits = points ? adaptiveDigits(points.xMin, points.xMax) : 3
  const yTicks = points ? [points.yMax, points.yMax / 2, 0, -points.yMax / 2, -points.yMax] : []

  return (
    <section className="card flex min-w-0 flex-[999_1_640px] flex-col gap-[18px] p-6" aria-labelledby="dependence-title">
      <div className="flex flex-col gap-2">
        <h2 id="dependence-title" className="m-0 text-[17px] font-semibold">
          Feature dependence
        </h2>
        <p className="m-0 text-[13.5px] leading-[1.55] text-mu">
          Each dot is one bar of the sample. Position shows the feature value and how far it pushed <span className="mono text-tx">{output}</span> up or down. Color is the
          regime.
        </p>
      </div>
      <div role="group" aria-label="Feature" className="flex flex-wrap gap-2">
        {ranked.map((name) => (
          <button key={name} type="button" className="pill" aria-pressed={name === feature} onClick={() => setPicked(name)}>
            {name}
          </button>
        ))}
      </div>
      <div ref={boxRef} className="w-full min-w-0">
      {!points || points.list.length === 0 ? (
        <Unavailable title="No points" reason="The stored sample has no finite values for this feature." />
      ) : (
        <div className="flex gap-3">
          <div className="mono flex h-[320px] w-14 flex-none flex-col justify-between text-right text-[11.5px] text-mu" aria-hidden="true">
            {yTicks.map((tick, index) => (
              <span key={index}>{formatNumber(tick, 3)}</span>
            ))}
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <div className="w-full">
              <svg
                width={plotWidth}
                height={HEIGHT}
                viewBox={`0 0 ${plotWidth} ${HEIGHT}`}
                role="img"
                aria-label={`Scatter of ${feature} against its SHAP contribution, ${points.list.length} bars, contribution between ${formatNumber(-points.yMax, 3)} and ${formatNumber(points.yMax, 3)}`}
                className="block rounded-md bg-bg"
              >
                {[0, 1, 2, 3, 4].map((k) => (
                  <line key={k} x1="0" x2={plotWidth} y1={(k * HEIGHT) / 4} y2={(k * HEIGHT) / 4} stroke={k === 2 ? 'var(--color-mu)' : 'var(--color-grid)'} strokeWidth="1" />
                ))}
                {points.list.map((point, index) => (
                  <circle key={index} cx={toX(point.x)} cy={toY(point.y)} r="3.2" fill={regimeColorVar(point.regime)} fillOpacity="0.78" />
                ))}
              </svg>
            </div>
            <div className="mono flex justify-between text-[11.5px] text-mu">
              <span>{formatNumber(points.xMin, digits)}</span>
              <span className="text-tx">{feature}</span>
              <span>{formatNumber(points.xMax, digits)}</span>
            </div>
          </div>
        </div>
      )}
      </div>
      <div className="flex flex-wrap gap-5 text-[13px] text-mu">
        {REGIME_NAMES.map((name) => (
          <span key={name} className="inline-flex items-center gap-2">
            <RegimeDot regime={name} />
            {name}
          </span>
        ))}
        {shap.sampling !== 'stratified_by_regime' && <span>Regimes unavailable: dots are shown in grey.</span>}
      </div>
    </section>
  )
}

function ComputedCard({ shap, output }) {
  const passed = isNumber(shap.max_additivity_gap) && isNumber(shap.additivity_epsilon) && shap.max_additivity_gap <= shap.additivity_epsilon
  return (
    <section className="card flex flex-col gap-3.5 p-6" aria-labelledby="computed-title">
      <h2 id="computed-title" className="lbl m-0">
        How these were computed
      </h2>
      <DefinitionList
        items={[
          { label: 'Explained output', value: output },
          { label: 'Explainer', value: shap.explainer || NA },
          { label: 'Sample', value: `${formatInt(shap.sample_size)} bars` },
          { label: 'Sampling', value: shap.sampling === 'stratified_by_regime' ? 'stratified by regime' : 'uniform' },
          { label: 'Trade rows', value: `${formatInt(shap.trade_rows?.length)}, kept separate${shap.trade_rows_capped ? ' (capped)' : ''}` },
          {
            label: 'Additivity check',
            value: `${passed ? 'passed' : 'check'}, max gap ${formatSmall(shap.max_additivity_gap)}`,
            className: passed ? 'text-pos' : 'text-ac',
          },
        ]}
      />
      <p className="m-0 text-[12.5px] leading-[1.55] text-mu">
        Contributions must add up to the model output within <span className="mono">{shap.additivity_epsilon ?? NA}</span>, otherwise the step fails and nothing is shown.
      </p>
    </section>
  )
}

function FeaturesUsedCard({ analysis }) {
  const features = analysis.model_meta?.feature_columns || analysis.result?.data?.feature_columns || []
  const csv = analysis.params?.data_source_kind === 'csv'
  return (
    <section className="card flex flex-col gap-3.5 p-6" aria-labelledby="used-title">
      <h2 id="used-title" className="lbl m-0">
        Features used
      </h2>
      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
        {features.map((name) => (
          <li key={name} className="chip mono text-tx">
            {name}
          </li>
        ))}
      </ul>
      <span className="text-[12.5px] text-mu">Source: {csv ? 'uploaded CSV columns' : 'server-side indicator catalog'}</span>
      {analysis.model_meta?.columns_reordered && <span className="text-[12.5px] text-mu">Columns were reordered to match the model's training order.</span>}
      <PointInTimeNotice compact text={CATALOG_POINT_IN_TIME_NOTICE} />
    </section>
  )
}

export default function FeaturesTab({ analysis }) {
  const shap = analysis.result.shap
  const output = explainedOutput(analysis)
  if (!shap) {
    return (
      <div className="flex flex-wrap items-start gap-6">
        <section className="card flex min-w-0 flex-[999_1_640px] flex-col gap-4 p-6">
          <h2 className="m-0 text-[17px] font-semibold">What drives the model</h2>
          <Unavailable title="SHAP unavailable" reason={unavailableReason(analysis, 'shap', 'SHAP values were not computed for this analysis.')} />
        </section>
        <aside className="flex min-w-0 flex-[1_1_340px] flex-col gap-6">
          <FeaturesUsedCard analysis={analysis} />
        </aside>
      </div>
    )
  }
  return (
    <>
      <ImportanceTable shap={shap} output={output} />
      <div className="flex flex-wrap items-stretch gap-6">
        <DependenceScatter shap={shap} output={output} />
        <aside className="flex min-w-0 flex-[1_1_340px] flex-col gap-6">
          <ComputedCard shap={shap} output={output} />
          <FeaturesUsedCard analysis={analysis} />
        </aside>
      </div>
    </>
  )
}
