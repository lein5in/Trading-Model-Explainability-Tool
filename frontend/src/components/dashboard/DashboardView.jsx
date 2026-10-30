import { Link } from 'react-router-dom'
import { useDocumentTitle } from '../../hooks/useDocumentTitle.js'
import { useReportActions } from '../../hooks/useReportActions.js'
import { tickerLabel } from '../../lib/analysis.js'
import { Main } from '../ui.jsx'
import DashboardHeader from './DashboardHeader.jsx'
import FeaturesTab from './FeaturesTab.jsx'
import OverviewTab from './OverviewTab.jsx'
import PartialBanner from './PartialBanner.jsx'
import ReportTab from './ReportTab.jsx'
import TradesTab from './TradesTab.jsx'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'features', label: 'Features' },
  { id: 'trades', label: 'Trades' },
  { id: 'report', label: 'Report' },
]

export default function DashboardView({ analysis, tab, onRefresh }) {
  const ticker = tickerLabel(analysis)
  const current = TABS.find((item) => item.id === tab) || TABS[0]
  useDocumentTitle(`${ticker || 'analysis'} ${current.label.toLowerCase()}`)
  const report = useReportActions(analysis, onRefresh)

  return (
    <Main>
      <DashboardHeader analysis={analysis} />
      <PartialBanner analysis={analysis} />
      <nav className="flex gap-1 overflow-x-auto border-b border-bd" aria-label="Dashboard sections">
        {TABS.map((item) => {
          const active = item.id === current.id
          return (
            <Link
              key={item.id}
              to={`/analysis/${analysis.id}/${item.id}`}
              aria-current={active ? 'page' : undefined}
              className={`-mb-px border-b-2 px-4 py-3 text-sm whitespace-nowrap no-underline ${active ? 'border-ac font-semibold text-tx' : 'border-transparent font-medium text-mu hover:text-tx'}`}
            >
              {item.label}
            </Link>
          )
        })}
      </nav>
      {current.id === 'overview' && <OverviewTab analysis={analysis} report={report} />}
      {current.id === 'features' && <FeaturesTab analysis={analysis} />}
      {current.id === 'trades' && <TradesTab analysis={analysis} />}
      {current.id === 'report' && <ReportTab analysis={analysis} report={report} />}
    </Main>
  )
}
