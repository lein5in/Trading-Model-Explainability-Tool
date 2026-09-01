import { useEffect, useRef } from 'react'
import {
  createChart,
  CandlestickSeries,
  createSeriesMarkers,
  ColorType,
} from 'lightweight-charts'

function toChartTime(timestamp) {
  return Math.floor(new Date(timestamp).getTime() / 1000)
}

function buildTradeMarkers(trades) {
  const markers = []

  for (const trade of trades) {
    if (trade.entry_timestamp) {
      markers.push({
        time: toChartTime(trade.entry_timestamp),
        position: trade.direction === 1 ? 'belowBar' : 'aboveBar',
        color: trade.direction === 1 ? '#22c55e' : '#ef4444',
        shape: trade.direction === 1 ? 'arrowUp' : 'arrowDown',
        text: trade.direction === 1 ? 'BUY' : 'SELL',
      })
    }
    if (trade.exit_timestamp) {
      markers.push({
        time: toChartTime(trade.exit_timestamp),
        position: 'inBar',
        color: '#a3a3a3',
        shape: 'circle',
        text: 'exit',
      })
    }
  }

  return markers.sort((a, b) => a.time - b.time)
}

function buildEntryTimeIndex(trades) {
  const index = new Map()
  trades.forEach((trade, tradeIndex) => {
    if (trade.entry_timestamp) {
      index.set(toChartTime(trade.entry_timestamp), { trade, tradeIndex })
    }
  })
  return index
}

function PriceChart({ ohlcv, trades, onTradeClick }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) {
      return
    }

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#a3a3a3',
        fontFamily: 'monospace',
      },
      grid: {
        vertLines: { color: '#262626' },
        horzLines: { color: '#262626' },
      },
      width: containerRef.current.clientWidth,
      height: 360,
      timeScale: { borderColor: '#404040' },
      rightPriceScale: { borderColor: '#404040' },
    })
    chartRef.current = chart

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })

    const candleData = ohlcv.map((bar) => ({
      time: toChartTime(bar.timestamp),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }))
    candleSeries.setData(candleData)

    if (trades && trades.length > 0) {
      createSeriesMarkers(candleSeries, buildTradeMarkers(trades))
    }

    let handleClick = null
    if (onTradeClick && trades && trades.length > 0) {
      const entryTimeIndex = buildEntryTimeIndex(trades)
      handleClick = function (param) {
        if (!param.time) {
          return
        }
        const match = entryTimeIndex.get(param.time)
        if (match) {
          onTradeClick(match.trade, match.tradeIndex)
        }
      }
      chart.subscribeClick(handleClick)
    }

    chart.timeScale().fitContent()

    function handleResize() {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      if (handleClick) {
        chart.unsubscribeClick(handleClick)
      }
      chart.remove()
    }
  }, [ohlcv, trades, onTradeClick])

  return <div ref={containerRef} className="w-full" />
}

export default PriceChart