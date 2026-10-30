import { useEffect, useState } from 'react'
import { observeWidth } from '../lib/chartTheme.js'

export function useElementWidth(ref, fallback = 800) {
  const [width, setWidth] = useState(fallback)
  useEffect(() => {
    const element = ref.current
    if (!element) return undefined
    const frame = requestAnimationFrame(() => {
      if (element.clientWidth > 0) setWidth(element.clientWidth)
    })
    const stop = observeWidth(element, setWidth)
    return () => {
      cancelAnimationFrame(frame)
      stop()
    }
  }, [ref])
  return width
}
