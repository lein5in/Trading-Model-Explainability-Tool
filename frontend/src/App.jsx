import { BrowserRouter, Route, Routes, useParams } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import { DASHBOARD_TABS } from './config.js'
import AnalysisPage from './pages/AnalysisPage.jsx'
import HomePage from './pages/HomePage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'

function AnalysisRoute() {
  const { id, tab } = useParams()
  if (tab !== undefined && !DASHBOARD_TABS.includes(tab)) return <NotFoundPage />
  return <AnalysisPage key={id} id={id} tab={tab || 'overview'} />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="analysis/:id/:tab?" element={<AnalysisRoute />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
