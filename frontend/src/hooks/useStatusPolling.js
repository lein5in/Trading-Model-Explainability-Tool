import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api.js'
import { createPoller } from '../lib/polling.js'

export function useStatusPolling(analysisId, enabled, onTerminal) {
  const [state, setState] = useState(null)
  const [attempt, setAttempt] = useState(0)
  const terminalRef = useRef(onTerminal)

  useEffect(() => {
    terminalRef.current = onTerminal
  }, [onTerminal])

  useEffect(() => {
    if (!enabled) return undefined
    const poller = createPoller({
      fetchStatus: () => api.status(analysisId),
      isHidden: () => typeof document !== 'undefined' && document.visibilityState === 'hidden',
      onUpdate: (next) => {
        setState(next)
        if (next.phase === 'done' && terminalRef.current) terminalRef.current(next.status)
      },
    })
    const onVisibility = () => {
      if (document.visibilityState === 'visible') poller.resume()
    }
    document.addEventListener('visibilitychange', onVisibility)
    poller.start()
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      poller.stop()
    }
  }, [analysisId, enabled, attempt])

  return { state, retry: () => setAttempt((value) => value + 1) }
}
