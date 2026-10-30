import { BaselineSeries, LineSeries, LineStyle, createChart } from 'lightweight-charts'
import { memo, useEffect, useRef } from 'react'
import { COLORS, baseChartOptions, observeWidth } from '../../lib/chartTheme.js'
import { formatPercent } from '../../lib/format.js'

const HEIGHT = 340

function DrawdownChart({ data, ariaLabel }) {
  const containerRef = useRef(null)
  const apiRef = useRef(null)

  useEffect(() => {
    const container = containerRef.current
    const chart = createChart(container, baseChartOptions(container.clientWidth, HEIGHT))
    const percentFormat = { type: 'custom', formatter: (value) => formatPercent(value), minMove: 0.0001 }
    const strategy = chart.addSeries(BaselineSeries, {
      baseValue: { type: 'price', price: 0 },
      topLineColor: COLORS.neg,
      topFillColor1: 'rgba(246, 70, 93, 0)',
      topFillColor2: 'rgba(246, 70, 93, 0)',
      bottomLineColor: COLORS.neg,
      bottomFillColor1: 'rgba(246, 70, 93, 0.35)',
      bottomFillColor2: 'rgba(246, 70, 93, 0.35)',
      lineWidth: 2,
      priceFormat: percentFormat,
      priceLineVisible: false,
      title: 'Strategy',
    })
    const benchmark = chart.addSeries(LineSeries, {
      color: COLORS.bh,
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceFormat: percentFormat,
      priceLineVisible: false,
      title: 'B&H',
    })
    apiRef.current = { chart, strategy, benchmark, fitted: false }
    const stop = observeWidth(container, (width) => chart.applyOptions({ width }))
    return () => {
      stop()
      chart.remove()
      apiRef.current = null
    }
  }, [])

  useEffect(() => {
    const api = apiRef.current
    if (!api || !data) return
    api.strategy.setData(data.strategy)
    api.benchmark.setData(data.benchmark)
    if (!api.fitted) {
      api.chart.timeScale().fitContent()
      api.fitted = true
    }
  }, [data])

  return <div ref={containerRef} role="img" aria-label={ariaLabel} className="w-full overflow-hidden rounded-md" />
}

export default memo(DrawdownChart)
