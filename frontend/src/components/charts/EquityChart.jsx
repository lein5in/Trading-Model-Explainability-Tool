import { HistogramSeries, LineSeries, LineStyle, createChart } from 'lightweight-charts'
import { memo, useEffect, useRef } from 'react'
import { COLORS, baseChartOptions, fixedRange, observeWidth } from '../../lib/chartTheme.js'
import { formatInt, formatPercent } from '../../lib/format.js'

const MAIN_HEIGHT = 300
const PNL_HEIGHT = 90
const HEAT_HEIGHT = 54

function EquityChart({ data, showRegimes, ariaLabel }) {
  const containerRef = useRef(null)
  const apiRef = useRef(null)

  useEffect(() => {
    const container = containerRef.current
    const height = MAIN_HEIGHT + PNL_HEIGHT + (showRegimes ? HEAT_HEIGHT : 0)
    const chart = createChart(container, baseChartOptions(container.clientWidth, height))
    const shading = showRegimes
      ? chart.addSeries(HistogramSeries, {
          priceScaleId: 'regime-shading',
          priceLineVisible: false,
          lastValueVisible: false,
          base: 0,
          autoscaleInfoProvider: fixedRange(0, 1),
          crosshairMarkerVisible: false,
        })
      : null
    if (shading) chart.priceScale('regime-shading').applyOptions({ visible: false, scaleMargins: { top: 0, bottom: 0 } })
    const equityFormat = { type: 'custom', formatter: (value) => formatInt(value), minMove: 1 }
    const benchmark = chart.addSeries(LineSeries, {
      color: COLORS.bh,
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceFormat: equityFormat,
      priceLineStyle: LineStyle.Dashed,
      priceLineColor: COLORS.bh,
      title: 'B&H',
    })
    const strategy = chart.addSeries(LineSeries, {
      color: COLORS.ac,
      lineWidth: 2,
      priceFormat: equityFormat,
      priceLineStyle: LineStyle.Dashed,
      priceLineColor: COLORS.ac,
      title: 'Strategy',
    })
    const monthly = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: 'custom', formatter: (value) => formatPercent(value), minMove: 0.0001 }, priceLineVisible: false, lastValueVisible: false, base: 0 },
      1,
    )
    const heat = showRegimes
      ? [0, 1, 2].map((row) =>
          chart.addSeries(
            HistogramSeries,
            {
              priceScaleId: 'regime-heat',
              base: row,
              priceLineVisible: false,
              lastValueVisible: false,
              autoscaleInfoProvider: fixedRange(0, 3),
              priceFormat: { type: 'custom', formatter: () => '' },
              crosshairMarkerVisible: false,
            },
            2,
          ),
        )
      : []
    const panes = chart.panes()
    panes[0]?.setStretchFactor(MAIN_HEIGHT)
    panes[1]?.setStretchFactor(PNL_HEIGHT)
    if (showRegimes) {
      panes[2]?.setStretchFactor(HEAT_HEIGHT)
      chart.priceScale('regime-heat', 2).applyOptions({ visible: false, scaleMargins: { top: 0, bottom: 0 } })
    }
    apiRef.current = { chart, strategy, benchmark, shading, monthly, heat, fitted: false }
    const stop = observeWidth(container, (width) => chart.applyOptions({ width }))
    return () => {
      stop()
      chart.remove()
      apiRef.current = null
    }
  }, [showRegimes])

  useEffect(() => {
    const api = apiRef.current
    if (!api || !data) return
    api.strategy.setData(data.strategy)
    api.benchmark.setData(data.benchmark)
    if (api.shading) api.shading.setData(data.shading)
    api.monthly.setData(data.monthly.map((point) => ({ ...point, color: point.value >= 0 ? 'rgba(46, 189, 133, 0.85)' : 'rgba(246, 70, 93, 0.85)' })))
    api.heat.forEach((series, row) => series.setData(data.heatRows[row] || []))
    if (!api.fitted) {
      api.chart.timeScale().fitContent()
      api.fitted = true
    }
  }, [data])

  return <div ref={containerRef} role="img" aria-label={ariaLabel} className="w-full overflow-hidden rounded-md" />
}

export default memo(EquityChart)
