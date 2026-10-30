import { useState } from 'react'
import { api } from '../../lib/api.js'
import { describeFailure } from '../../lib/errors.js'
import { formatDate, formatInt } from '../../lib/format.js'
import { WarningIcon } from '../Icons.jsx'
import { ErrorAlert, Unavailable } from '../ui.jsx'
import HighlightedText from './HighlightedText.jsx'

function countLabel(check) {
  if (!check) return { text: 'not checked', className: 'text-mu' }
  if (!check.total) return { text: 'no numbers used', className: 'text-mu' }
  return {
    text: `${formatInt(check.verified)}/${formatInt(check.total)} verified`,
    className: check.unverified?.length ? 'text-ac' : 'text-pos',
  }
}

function FlaggedBanner({ sections, verification }) {
  const flagged = sections.flatMap((section) =>
    (verification.sections?.[section.id]?.unverified || []).map((item, index) => ({ ...item, section, key: `${section.id}-${index}` })),
  )
  if (!flagged.length) return null
  return (
    <div role="status" className="flex items-start gap-3.5 rounded-[10px] border border-ac bg-s1 px-5 py-4">
      <WarningIcon size={20} stroke="var(--color-ac)" className="mt-px flex-none" />
      <div className="flex min-w-0 flex-col gap-2 text-sm leading-[1.6]">
        <strong>
          {flagged.length === 1 ? '1 number could not be matched to the computed data.' : `${flagged.length} numbers could not be matched to the computed data.`}
        </strong>
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
          {flagged.map((item) => (
            <li key={item.key} className="text-mu">
              <span className="flag text-tx">{item.number}</span> in <span className="text-tx">{item.section.title}</span>: “{item.sentence}”
            </li>
          ))}
        </ul>
        <span className="text-mu">Treat those sentences with care, or regenerate the report. Everything else was checked.</span>
      </div>
    </div>
  )
}

function RegenerateCard({ report }) {
  return (
    <div className="card flex flex-col gap-3 p-4">
      <button type="button" className="btn w-full" onClick={report.regenerate} disabled={report.busy}>
        {report.phase === 'running' ? 'Regenerating…' : report.phase === 'polling' ? 'Waiting for the new report…' : 'Regenerate report'}
      </button>
      {report.busy && (
        <p className="m-0 text-[12.5px] text-ac" role="status">
          Writing five sections and verifying every number. This can take a minute or two.
        </p>
      )}
      {report.phase === 'error' && (
        <p className="m-0 text-[12.5px] text-neg" role="alert">
          {describeFailure(report.error).title}
        </p>
      )}
      <p className="m-0 text-[12.5px] leading-normal text-mu">The analysis is stored separately, so the report can be rewritten without re-running anything.</p>
    </div>
  )
}

function ExplainCard({ state, sections }) {
  const section = sections.find((item) => item.id === state.sectionId)
  return (
    <section className="card flex flex-col gap-3 p-6" aria-labelledby="explain-title" aria-live="polite">
      <h2 id="explain-title" className="lbl m-0">
        Explain this section{section ? `: ${section.title}` : ''}
      </h2>
      {state.phase === 'idle' && <p className="m-0 text-sm leading-[1.65] text-mu">Pick “Explain this section” under a section for a plain-language note.</p>}
      {state.phase === 'loading' && <p className="m-0 text-sm text-ac">Writing the explanation…</p>}
      {state.phase === 'error' && <p className="m-0 text-sm text-neg">{describeFailure(state.error).title}</p>}
      {state.phase === 'done' && state.result && (
        <>
          <HighlightedText
            text={state.result.text}
            unverified={state.result.verification?.sections?.[state.sectionId]?.unverified}
            className="text-sm leading-[1.65]"
          />
          <span className={`mono text-xs ${countLabel(state.result.verification?.sections?.[state.sectionId]).className}`}>
            {countLabel(state.result.verification?.sections?.[state.sectionId]).text}
          </span>
        </>
      )}
      <span className="text-xs text-mu">Plain-language note written from the same data slice and checked the same way.</span>
    </section>
  )
}

export default function ReportTab({ analysis, report }) {
  const stored = analysis.report
  const [explain, setExplain] = useState({ phase: 'idle', sectionId: null, result: null, error: null })

  const requestExplain = async (sectionId) => {
    setExplain({ phase: 'loading', sectionId, result: null, error: null })
    try {
      const result = await api.explainSection(analysis.id, sectionId)
      setExplain((previous) => (previous.sectionId === sectionId ? { phase: 'done', sectionId, result, error: null } : previous))
    } catch (error) {
      setExplain((previous) => (previous.sectionId === sectionId ? { phase: 'error', sectionId, result: null, error } : previous))
    }
  }

  if (!stored || stored.status !== 'ok' || !Array.isArray(stored.sections) || !stored.sections.length) {
    const failure = stored?.error ? describeFailure(stored.error) : null
    return (
      <div className="flex flex-wrap items-start gap-6">
        <div className="flex min-w-0 flex-[999_1_520px] flex-col gap-5">
          {failure ? (
            <ErrorAlert title="The report could not be generated" message={failure.title} />
          ) : (
            <Unavailable title="Report unavailable" reason="No report was generated for this analysis." />
          )}
        </div>
        <aside className="flex min-w-[200px] flex-[0_1_260px] flex-col gap-4">
          <RegenerateCard report={report} />
        </aside>
      </div>
    )
  }

  const sections = stored.sections
  const verification = stored.verification || { sections: {} }

  return (
    <>
      <FlaggedBanner sections={sections} verification={verification} />
      <div className="flex flex-wrap items-start gap-6">
        <aside className="flex min-w-[200px] flex-[0_1_220px] flex-col gap-4">
          <nav className="card flex flex-col gap-0.5 p-3" aria-label="Report sections">
            <span className="lbl px-3 pt-1.5 pb-2">Sections</span>
            {sections.map((section, index) => (
              <a key={section.id} href={`#report-${section.id}`} className="block rounded-md px-3 py-2 text-sm text-mu no-underline hover:bg-s2 hover:text-tx">
                {index + 1} · {section.title}
              </a>
            ))}
          </nav>
          <RegenerateCard report={report} />
          <p className="m-0 px-1 text-xs leading-normal text-mu">
            Written by <span className="mono">{stored.model || 'n/a'}</span> on <span className="mono">{formatDate(stored.generated_at)}</span>.
          </p>
        </aside>

        <div className="flex min-w-0 flex-[999_1_520px] flex-col gap-5">
          {sections.map((section, index) => {
            const check = verification.sections?.[section.id]
            const label = countLabel(check)
            return (
              <article key={section.id} id={`report-${section.id}`} className="card flex scroll-mt-4 flex-col gap-4 px-5 py-6 sm:px-8 sm:py-7" aria-labelledby={`report-${section.id}-title`}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h2 id={`report-${section.id}-title`} className="m-0 text-xl font-semibold">
                    <span className="mono mr-2.5 text-[15px] text-ac">{String(index + 1).padStart(2, '0')}</span>
                    {section.title}
                  </h2>
                  <span className={`mono text-[12.5px] ${label.className}`}>{label.text}</span>
                </div>
                <HighlightedText text={section.text} unverified={check?.unverified} className="text-[15.5px] leading-[1.75] text-tx" />
                <div>
                  <button
                    type="button"
                    className="btn btn-sm"
                    aria-pressed={explain.sectionId === section.id}
                    disabled={explain.phase === 'loading'}
                    onClick={() => requestExplain(section.id)}
                  >
                    {explain.phase === 'loading' && explain.sectionId === section.id ? 'Explaining…' : 'Explain this section'}
                  </button>
                </div>
              </article>
            )
          })}
        </div>

        <aside className="flex min-w-0 flex-[1_1_340px] flex-col gap-5">
          <ExplainCard state={explain} sections={sections} />
        </aside>
      </div>
    </>
  )
}
