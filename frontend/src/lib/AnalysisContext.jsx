import { createContext, useContext, useState } from 'react'

const AnalysisContext = createContext(null)

export function AnalysisProvider({ children }) {
  const [analysisResult, setAnalysisResult] = useState(null)
  const [registeredModel, setRegisteredModel] = useState(null)

  const value = {
    analysisResult,
    setAnalysisResult,
    registeredModel,
    setRegisteredModel,
  }

  return (
    <AnalysisContext.Provider value={value}>
      {children}
    </AnalysisContext.Provider>
  )
}

export function useAnalysis() {
  const context = useContext(AnalysisContext)
  if (context === null) {
    throw new Error('useAnalysis must be used within an AnalysisProvider')
  }
  return context
}