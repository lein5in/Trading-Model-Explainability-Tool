import { Link, Outlet, useLocation } from 'react-router-dom'
import { DISCLAIMER } from '../config.js'
import { useHistory } from '../hooks/useHistory.js'
import { LogoMark } from './Icons.jsx'

const navBase = 'rounded-md px-3 py-2 text-sm font-medium no-underline'
const navIdle = `${navBase} text-mu hover:bg-s2 hover:text-tx`
const navActive = `${navBase} bg-s2 text-tx`

function TopBar() {
  const location = useLocation()
  const history = useHistory()
  const last = history[0]
  const onHome = location.pathname === '/'
  const onHistory = onHome && location.hash === '#history'
  const onDashboard = location.pathname.startsWith('/analysis/')

  return (
    <header className="flex min-h-[60px] flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-bd bg-s1 px-4 py-2 sm:px-8">
      <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
        <Link to="/" className="flex items-center gap-2.5 text-tx no-underline" aria-label="TME home">
          <LogoMark />
          <span className="flex flex-col leading-[1.1]">
            <span className="mono text-[15px] font-semibold tracking-[.04em]">TME</span>
            <span className="text-[11px] text-mu">Trading Model Explainability</span>
          </span>
        </Link>
        <nav className="flex gap-1" aria-label="Main">
          <Link to="/" className={onHome && !onHistory ? navActive : navIdle} aria-current={onHome && !onHistory ? 'page' : undefined}>
            New analysis
          </Link>
          {last ? (
            <Link
              to={`/analysis/${last.id}`}
              className={onDashboard ? navActive : navIdle}
              aria-current={onDashboard ? 'page' : undefined}
            >
              Dashboard
            </Link>
          ) : (
            <span className={`${navBase} cursor-not-allowed text-mu opacity-60`} aria-disabled="true" title="Run an analysis first">
              Dashboard
            </span>
          )}
          <Link to="/#history" className={onHistory ? navActive : navIdle} aria-current={onHistory ? 'page' : undefined}>
            History
          </Link>
        </nav>
      </div>
      {onHome && <span className="mono text-xs text-mu">No account needed</span>}
    </header>
  )
}

function Footer() {
  return (
    <footer className="border-t border-bd bg-s1 px-4 py-5 sm:px-8">
      <p className="mx-auto my-0 max-w-[1296px] text-[12.5px] leading-[1.6] text-mu">{DISCLAIMER}</p>
    </footer>
  )
}

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col bg-bg text-tx">
      <TopBar />
      <Outlet />
      <Footer />
    </div>
  )
}
