import { Link } from 'react-router-dom'
import { Main } from '../components/ui.jsx'
import { useDocumentTitle } from '../hooks/useDocumentTitle.js'

export default function NotFoundPage({ title = 'Page not found', message = 'This address does not match any page of TME.' }) {
  useDocumentTitle('not found')
  return (
    <Main className="items-start gap-4 pt-16">
      <span className="lbl">404</span>
      <h1 className="m-0 text-[32px] font-semibold tracking-[-.02em]">{title}</h1>
      <p className="m-0 max-w-[560px] text-[15px] leading-normal text-mu">{message}</p>
      <Link to="/" className="btn btn-pri">
        Back to home
      </Link>
    </Main>
  )
}
