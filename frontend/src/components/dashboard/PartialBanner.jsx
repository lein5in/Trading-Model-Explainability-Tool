import { collectErrors } from '../../lib/analysis.js'
import { describeFailure } from '../../lib/errors.js'
import { STAGE_LABELS } from '../../lib/stages.js'
import { WarningIcon } from '../Icons.jsx'

export default function PartialBanner({ analysis }) {
  const errors = collectErrors(analysis)
  if (!errors.length && analysis?.status !== 'partial' && analysis?.status !== 'failed') return null
  return (
    <div role="status" className="flex items-start gap-3.5 rounded-[10px] border border-ac bg-s1 px-5 py-4">
      <WarningIcon size={20} stroke="var(--color-ac)" className="mt-px flex-none" />
      <div className="flex min-w-0 flex-col gap-1.5 text-sm leading-[1.6]">
        <strong>
          {analysis?.status === 'failed' ? 'This analysis stopped before the end.' : 'This analysis is partial.'} The panels that depend on a failed step show why
          they are unavailable.
        </strong>
        {errors.map((error, index) => {
          const failure = describeFailure(error)
          return (
            <span key={`${error.stage}-${index}`} className="text-mu">
              <span className="text-tx">{STAGE_LABELS[error.stage] || 'Unknown stage'} failed:</span> {failure.title}
              {failure.message ? ` ${failure.message}` : ''}
            </span>
          )
        })}
      </div>
    </div>
  )
}
