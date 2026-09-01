import { createContext, useContext, useState, useEffect } from 'react'
import { getAccessToken, signIn as apiSignIn, signUp as apiSignUp, signOut as apiSignOut } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [email, setEmail] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = getAccessToken()
    if (token) {
      setIsAuthenticated(true)
    }
    setIsLoading(false)
  }, [])

  async function signIn(credentials) {
    const data = await apiSignIn(credentials)
    setIsAuthenticated(true)
    setEmail(data.email)
    return data
  }

  async function signUp(credentials) {
    const data = await apiSignUp(credentials)
    if (data.session) {
      setIsAuthenticated(true)
      setEmail(data.email)
    }
    return data
  }

  function signOut() {
    apiSignOut()
    setIsAuthenticated(false)
    setEmail(null)
  }

  const value = {
    isAuthenticated,
    email,
    isLoading,
    signIn,
    signUp,
    signOut,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}