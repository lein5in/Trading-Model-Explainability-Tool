import { ColorType, CrosshairMode, LineStyle } from 'lightweight-charts'

export const COLORS = {
  bg: '#06080C',
  s1: '#0B0F15',
  s2: '#111721',
  bd: '#1C2431',
  tx: '#D3DAE4',
  mu: '#8A96A8',
  ac: '#F2B544',
  acf: '#1A1300',
  pos: '#2EBD85',
  neg: '#F6465D',
  grid: '#151C27',
  bh: '#7B879A',
}

export function baseChartOptions(width, height) {
  return {
    width,
    height,
    layout: {
      background: { type: ColorType.Solid, color: COLORS.bg },
      textColor: COLORS.mu,
      fontFamily: "'JetBrains Mono', ui-monospace, monospace",
      fontSize: 11,
      attributionLogo: false,
      panes: { separatorColor: COLORS.bd, separatorHoverColor: COLORS.s2, enableResize: false },
    },
    grid: {
      vertLines: { color: COLORS.grid, style: LineStyle.Dashed },
      horzLines: { color: COLORS.grid },
    },
    rightPriceScale: { borderColor: COLORS.bd },
    timeScale: { borderColor: COLORS.bd, timeVisible: false },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: { color: COLORS.mu, labelBackgroundColor: COLORS.s2 },
      horzLine: { color: COLORS.mu, labelBackgroundColor: COLORS.s2 },
    },
    handleScale: { axisPressedMouseMove: false },
  }
}

export function fixedRange(minValue, maxValue) {
  return () => ({ priceRange: { minValue, maxValue } })
}

export function debounce(callback, wait) {
  let handle = null
  const debounced = (...args) => {
    if (handle !== null) clearTimeout(handle)
    handle = setTimeout(() => {
      handle = null
      callback(...args)
    }, wait)
  }
  debounced.cancel = () => {
    if (handle !== null) clearTimeout(handle)
    handle = null
  }
  return debounced
}

export const RESIZE_DEBOUNCE_MS = 120

export function observeWidth(element, onWidth) {
  if (typeof ResizeObserver === 'undefined') return () => {}
  let last = element.clientWidth
  const update = debounce((width) => onWidth(width), RESIZE_DEBOUNCE_MS)
  const observer = new ResizeObserver((entries) => {
    const width = Math.floor(entries[0]?.contentRect?.width ?? element.clientWidth)
    if (width > 0 && width !== last) {
      last = width
      update(width)
    }
  })
  observer.observe(element)
  return () => {
    update.cancel()
    observer.disconnect()
  }
}
