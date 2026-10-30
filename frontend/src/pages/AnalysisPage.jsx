import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react'
import ProgressScreen from '../components/progress/ProgressScreen.jsx'
import { ErrorAlert, Main, Skeleton } from '../components/ui.jsx'
import { useDocumentTitle } from '../hooks/useDocumentTitle.js'
import { useStatusPolling } from '../hooks/useStatusPolling.js'
import { api } from '../lib/api.js'
import { describeFailure } from '../lib/errors.js'
import { historyStore } from '../lib/history.js'
import { hasResult, statusFromAnalysis } from '../lib/stages.js'
import { formFromAnalysis } from '../lib/validation.js'
import NotFoundPage from './NotFoundPage.jsx'

const DashboardView = lazy(() => import('../components/dashboard/DashboardView.jsx'))

const LIVE = ['queued', 'running']

function DashboardFallback() {
  return (
    <Main>
      <Skeleton className="h-16" />
      <Skeleton className="h-10" />
      <div className="flex flex-wrap gap-4">
        {[0, 1, 2, 3, 4, 5].map((key) => (
          <Skeleton key={key} className="h-28 flex-[1_1_200px]" />
        ))}
      </div>
      <Skeleton className="h-[420px]" />
    </Main>
  )
}

function LoadError({ error, onRetry }) {
  useDocumentTitle('analysis unavailable')
  const failure = describeFailure(error)
  return (
    <Main className="pt-10">
      <ErrorAlert title="The analysis could not be loaded" message={failure.title}>
        <button type="button" className="btn btn-pri" onClick={onRetry}>
          Retry
        </button>
      </ErrorAlert>
    </Main>
  )
}

export default function AnalysisPage({ id, tab }) {
  const [record, setRecord] = useState({ loading: true, analysis: null, error: null, wasLive: false })
  const [reload, setReload] = useState(0)
  const [openResult, setOpenResult] = useState(false)

  useEffect(() => {
    let active = true
    api
      .analysis(id)
      .then((analysis) => {
        if (active) setRecord((previous) => ({ loading: false, analysis, error: null, wasLive: previous.wasLive || LIVE.includes(analysis?.status) }))
      })
      .catch((error) => {
        if (active) setRecord((previous) => ({ ...previous, loading: false, error }))
      })
    return () => {
      active = false
    }
  }, [id, reload])

  const analysis = record.analysis
  const live = Boolean(analysis && LIVE.includes(analysis.status))
  const onTerminal = useCallback(() => setReload((value) => value + 1), [])
  const polling = useStatusPolling(id, live, onTerminal)

  useEffect(() => {
    const metrics = analysis?.result?.backtest?.metrics?.strategy
    if (metrics && !LIVE.includes(analysis.status)) {
      historyStore.update(analysis.id, { totalReturn: metrics.total_return, sharpe: metrics.sharpe })
    }
  }, [analysis])

  const refresh = useCallback(() => setReload((value) => value + 1), [])
  const tryAgainState = useMemo(() => ({ form: formFromAnalysis(analysis) }), [analysis])

  if (record.loading) return <DashboardFallback />
  if (record.error?.status === 404) {
    return <NotFoundPage title="Analysis not found" message="This analysis does not exist or has expired. Analysis links stay valid while the result is stored." />
  }
  if (record.error && !analysis) return <LoadError error={record.error} onRetry={refresh} />

  const liveStatus = live && polling.state?.status ? polling.state.status : statusFromAnalysis(analysis)
  const resultExists = hasResult(analysis)
  const showDashboard =
    !live &&
    (analysis.status === 'completed' || (resultExists && (!record.wasLive || openResult)))

  if (!showDashboard) {
    return (
      <ProgressScreen
        analysis={analysis}
        status={liveStatus}
        poll={live ? polling.state : null}
        onRetryPolling={polling.retry}
        canOpenResult={!live && (analysis.status === 'partial' || resultExists)}
        onOpenResult={() => setOpenResult(true)}
        tryAgainState={tryAgainState}
      />
    )
  }

  return (
    <Suspense fallback={<DashboardFallback />}>
      <DashboardView analysis={analysis} tab={tab} onRefresh={refresh} />
    </Suspense>
  )
}
