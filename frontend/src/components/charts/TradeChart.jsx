import { CandlestickSeries, HistogramSeries, LineSeries, LineStyle, createChart, createSeriesMarkers } from 'lightweight-charts'
import { memo, useEffect, useRef } from 'react'
import { COLORS, baseChartOptions, observeWidth } from '../../lib/chartTheme.js'
import { formatNumber } from '../../lib/format.js'

const PRICE_HEIGHT = 240
const VOLUME_HEIGHT = 60
const PROB_HEIGHT = 80

function TradeChart({ data, ariaLabel }) {
  const containerRef = useRef(null)
  const apiRef = useRef(null)

  useEffect(() => {
    const container = containerRef.current
    const chart = createChart(container, baseChartOptions(container.clientWidth, PRICE_HEIGHT + VOLUME_HEIGHT + PROB_HEIGHT))
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: COLORS.pos,
      downColor: COLORS.neg,
      wickUpColor: COLORS.pos,
      wickDownColor: COLORS.neg,
      borderVisible: false,
      priceLineVisible: false,
    })
    const entryLine = candles.createPriceLine({ price: 0, color: COLORS.ac, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: 'entry' })
    const markers = createSeriesMarkers(candles, [])
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false }, 1)
    const probability = chart.addSeries(
      LineSeries,
      { color: '#4C8DF6', lineWidth: 2, priceLineVisible: false, priceFormat: { type: 'custom', formatter: (value) => formatNumber(value, 2), minMove: 0.01 } },
      2,
    )
    const thresholdLine = probability.createPriceLine({ price: 0.5, color: COLORS.mu, lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: '' })
    const panes = chart.panes()
    panes[0]?.setStretchFactor(PRICE_HEIGHT)
    panes[1]?.setStretchFactor(VOLUME_HEIGHT)
    panes[2]?.setStretchFactor(PROB_HEIGHT)
    apiRef.current = { chart, candles, entryLine, markers, volume, probability, thresholdLine }
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
    api.candles.setData(data.candles)
    api.volume.setData(data.volume)
    api.probability.setData(data.probability)
    api.markers.setMarkers(data.markers)
    api.entryLine.applyOptions({ price: data.entryPrice ?? 0, axisLabelVisible: data.entryPrice != null, lineVisible: data.entryPrice != null })
    api.thresholdLine.applyOptions({ price: data.threshold ?? 0.5, title: data.thresholdLabel || '' })
    api.chart.timeScale().fitContent()
  }, [data])

  return <div ref={containerRef} role="img" aria-label={ariaLabel} className="w-full overflow-hidden" />
}

export default memo(TradeChart)
