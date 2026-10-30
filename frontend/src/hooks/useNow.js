import { useEffect, useState } from 'react'

export function useNow(intervalMs, enabled = true) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!enabled) return undefined
    const handle = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(handle)
  }, [intervalMs, enabled])
  return now
}
