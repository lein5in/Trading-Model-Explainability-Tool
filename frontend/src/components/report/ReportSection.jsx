import { useState } from 'react'
import { explainSection } from '../../lib/api'

function ReportSection({ analysisId, title, content }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [explanation, setExplanation] = useState(null)
  const [status, setStatus] = useState('idle')

  async function handleExplainClick() {
    if (isExpanded) {
      setIsExpanded(false)
      return
    }

    setIsExpanded(true)

    if (explanation !== null) {
      return
    }

    setStatus('loading')
    try {
      const result = await explainSection({ analysisId, sectionName: title })
      setExplanation(result.explanation)
      setStatus('done')
    } catch (err) {
      setStatus('error')
      setExplanation(err.message)
    }
  }

  return (
    <div className="border border-neutral-800 rounded">
      <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-800">
        <h3 className="text-sm font-semibold text-neutral-200">{title}</h3>
        <button
          type="button"
          onClick={handleExplainClick}
          className="text-xs text-neutral-500 hover:text-neutral-300 border border-neutral-700 rounded px-2 py-1 transition-colors"
        >
          {isExpanded ? 'Hide' : 'Explain this'}
        </button>
      </div>

      <div className="px-4 py-3">
        <p className="text-sm text-neutral-400 whitespace-pre-line leading-relaxed">{content}</p>
      </div>

      {isExpanded && (
        <div className="px-4 py-3 border-t border-neutral-800 bg-neutral-900">
          {status === 'loading' && (
            <p className="text-xs text-neutral-600">Generating explanation...</p>
          )}
          {status === 'error' && (
            <p className="text-xs text-red-500">{explanation}</p>
          )}
          {status === 'done' && (
            <p className="text-xs text-neutral-400 leading-relaxed">{explanation}</p>
          )}
        </div>
      )}
    </div>
  )
}

export default ReportSection