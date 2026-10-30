import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api.js'

export const REPORT_POLL_MS = 5000
export const REPORT_POLL_ATTEMPTS = 36

export function useReportActions(analysis, onRefresh) {
  const [state, setState] = useState({ phase: 'idle', error: null })
  const mounted = useRef(true)
  const timer = useRef(null)
  const analysisId = analysis?.id
  const generatedAt = analysis?.report?.generated_at ?? null

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      if (timer.current) clearTimeout(timer.current)
    }
  }, [])

  const regenerate = useCallback(async () => {
    if (!analysisId) return
    setState({ phase: 'running', error: null })
    try {
      await api.regenerateReport(analysisId)
      if (!mounted.current) return
      setState({ phase: 'idle', error: null })
      onRefresh()
      return
    } catch (error) {
      if (!mounted.current) return
      if (error?.code !== 'request_timeout' && error?.code !== 'network_error') {
        setState({ phase: 'error', error })
        return
      }
    }
    setState({ phase: 'polling', error: null })
    for (let attempt = 0; attempt < REPORT_POLL_ATTEMPTS; attempt += 1) {
      await new Promise((resolve) => {
        timer.current = setTimeout(resolve, REPORT_POLL_MS)
      })
      if (!mounted.current) return
      try {
        const latest = await api.analysis(analysisId)
        if (!mounted.current) return
        if ((latest?.report?.generated_at ?? null) !== generatedAt) {
          setState({ phase: 'idle', error: null })
          onRefresh()
          return
        }
      } catch (error) {
        if (!mounted.current) return
        if (error?.status && error.status < 500) {
          setState({ phase: 'error', error })
          return
        }
      }
    }
    setState({ phase: 'error', error: { code: 'request_timeout', message: 'The new report did not arrive in time.' } })
  }, [analysisId, generatedAt, onRefresh])

  return { ...state, busy: state.phase === 'running' || state.phase === 'polling', regenerate }
}
