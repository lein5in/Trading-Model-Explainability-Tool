import { useState, useEffect } from 'react'
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useAnalysis } from '../lib/AnalysisContext'
import { useAuth } from '../lib/AuthContext'
import { getAnalysis } from '../lib/api'
import Sidebar from '../components/dashboard/Sidebar'
import OverviewView from '../components/dashboard/OverviewView'
import FeaturesView from '../components/dashboard/FeaturesView'
import TradeDetailView from '../components/dashboard/TradeDetailView'
import ReportView from '../components/dashboard/ReportView'

const VALID_SECTIONS = ['overview', 'features', 'trades', 'report']

function DashboardPage() {
  const { analysisId } = useParams()
  const { analysisResult, setAnalysisResult } = useAnalysis()
  const { signOut } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [loadStatus, setLoadStatus] = useState(
    analysisResult && analysisResult.analysis_id === analysisId ? 'done' : 'loading'
  )

  useEffect(() => {
    if (analysisResult && analysisResult.analysis_id === analysisId) {
      setLoadStatus('done')
      return
    }

    let cancelled = false
    setLoadStatus('loading')

    getAnalysis({ analysisId })
      .then((result) => {
        if (cancelled) return
        setAnalysisResult(result)
        setLoadStatus('done')
      })
      .catch(() => {
        if (cancelled) return
        setLoadStatus('error')
      })

    return () => {
      cancelled = true
    }
  }, [analysisId])

  if (loadStatus === 'error') {
    return <Navigate to="/" replace />
  }

  if (loadStatus === 'loading') {
    return (
      <div className="min-h-screen bg-neutral-950 flex items-center justify-center">
        <p className="text-neutral-500 text-sm font-mono">Loading analysis...</p>
      </div>
    )
  }

  if (!analysisResult) {
    return <Navigate to="/" replace />
  }

  const sectionParam = searchParams.get('section')
  const activeSection = VALID_SECTIONS.includes(sectionParam) ? sectionParam : 'overview'

  const tradeParam = searchParams.get('trade')
  const selectedTradeIndex = tradeParam !== null ? Number(tradeParam) : null
  const allTrades = analysisResult.backtest?.trades ?? []
  const selectedTrade =
    selectedTradeIndex !== null &&
    Number.isInteger(selectedTradeIndex) &&
    selectedTradeIndex >= 0 &&
    selectedTradeIndex < allTrades.length
      ? allTrades[selectedTradeIndex]
      : null

  function handleSectionChange(sectionId) {
    if (sectionId === 'new-analysis') {
      navigate('/')
      return
    }
    setSearchParams(sectionId === 'overview' ? {} : { section: sectionId })
  }

  function handleTradeClick(trade, tradeIndex) {
    setSearchParams({ section: 'trades', trade: String(tradeIndex) })
  }

  function handleBackFromTrade() {
    setSearchParams({})
  }

  function handleSignOut() {
    signOut()
    navigate('/auth')
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 font-mono flex">
      <Sidebar
        activeSection={activeSection}
        onSectionChange={handleSectionChange}
        onSignOut={handleSignOut}
      />

      <main className="flex-1 px-8 py-6 overflow-y-auto">
        <p className="text-xs text-neutral-600 mb-4">{analysisResult.model_name}</p>

        {activeSection === 'overview' && (
          <OverviewView analysisResult={analysisResult} onTradeClick={handleTradeClick} />
        )}

        {activeSection === 'features' && <FeaturesView analysisResult={analysisResult} />}

        {activeSection === 'trades' && selectedTrade && (
          <TradeDetailView
            analysisId={analysisResult.analysis_id}
            analysisResult={analysisResult}
            trade={selectedTrade}
            tradeIndex={selectedTradeIndex}
            onBack={handleBackFromTrade}
          />
        )}

        {activeSection === 'trades' && !selectedTrade && (
          <div className="space-y-4">
            <h2 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider mb-2">
              Trades
            </h2>
            <p className="text-sm text-neutral-600">
              Click on a BUY/SELL marker in the Overview price chart to inspect a trade.
            </p>
          </div>
        )}

        {activeSection === 'report' && (
          <ReportView
            analysisId={analysisResult.analysis_id}
            reportText={analysisResult.report_text}
          />
        )}
      </main>
    </div>
  )
}

export default DashboardPage