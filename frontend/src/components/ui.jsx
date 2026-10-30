import { POINT_IN_TIME_NOTICE } from '../config.js'
import { regimeColorVar } from '../lib/regimes.js'
import { AlertIcon, WarningIcon } from './Icons.jsx'

export function Main({ children, className = '' }) {
  return (
    <main className={`mx-auto flex w-full max-w-[1360px] flex-1 flex-col gap-6 px-4 pt-8 pb-8 sm:px-8 ${className}`}>{children}</main>
  )
}

export function PointInTimeNotice({ compact = false, text }) {
  return (
    <div className={`flex items-start gap-3 rounded-lg border border-ac ${compact ? 'px-3.5 py-3' : 'px-4 py-3.5'}`}>
      <WarningIcon size={18} stroke="var(--color-ac)" className="mt-px flex-none" />
      <p className={`m-0 leading-[1.55] text-tx ${compact ? 'text-[12.5px]' : 'text-[13px]'}`}>
        {text ? (
          text
        ) : (
          <>
            <strong>{POINT_IN_TIME_NOTICE.title}</strong> {POINT_IN_TIME_NOTICE.body}
          </>
        )}
      </p>
    </div>
  )
}

export function Unavailable({ title = 'Unavailable', reason, children }) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-lg border border-dashed border-bd p-6" role="note">
      <span className="text-[15px] font-semibold">{title}</span>
      {reason && <p className="m-0 max-w-[560px] text-[13.5px] leading-[1.55] text-mu">{reason}</p>}
      {children}
    </div>
  )
}

export function Skeleton({ className = '' }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />
}

export function ErrorAlert({ title, message, facts = [], children }) {
  return (
    <div role="alert" className="flex flex-wrap items-start gap-4 rounded-[10px] border border-neg bg-s1 px-6 py-5">
      <AlertIcon size={22} stroke="var(--color-neg)" className="mt-0.5 flex-none" />
      <div className="flex min-w-0 flex-[1_1_420px] flex-col gap-2">
        <strong className="text-base">{title}</strong>
        {message && <span className="text-sm leading-[1.55] text-mu">{message}</span>}
        {facts.length > 0 && (
          <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-[13px]">
            {facts.map((fact) => (
              <div key={fact.label} className="contents">
                <dt className="text-mu">{fact.label}</dt>
                <dd className={`m-0 break-words text-tx ${fact.mono ? 'mono' : ''}`}>{fact.value}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
      {children && <div className="flex flex-wrap gap-3">{children}</div>}
    </div>
  )
}

export function Segmented({ label, options, value, onChange, small = false }) {
  return (
    <div role="group" aria-label={label} className={`seg ${small ? 'seg-sm' : ''}`}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          disabled={option.disabled}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export function RegimeDot({ regime, size = 10 }) {
  const color = regimeColorVar(regime)
  return <span className="inline-block flex-none rounded-full" style={{ width: size, height: size, background: color }} aria-hidden="true" />
}

export function DefinitionList({ items, className = '' }) {
  return (
    <dl className={`m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-3 text-sm ${className}`}>
      {items.map((item) => (
        <div key={item.label} className="contents">
          <dt className="text-mu">{item.label}</dt>
          <dd className={`m-0 break-words text-right ${item.mono === false ? '' : 'mono'} ${item.className || ''}`} title={item.title}>
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  )
}
