import { parseReportSections } from '../../lib/parseReportSections'
import ReportSection from '../report/ReportSection'
import Disclaimer from '../report/Disclaimer'

function ReportView({ analysisId, reportText }) {
  const sections = parseReportSections(reportText)

  return (
    <div className="space-y-4 max-w-3xl">
      <h2 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider mb-2">
        Report
      </h2>

      {sections.map((section) => (
        <ReportSection
          key={section.title}
          analysisId={analysisId}
          title={section.title}
          content={section.content}
        />
      ))}

      <Disclaimer />
    </div>
  )
}

export default ReportView