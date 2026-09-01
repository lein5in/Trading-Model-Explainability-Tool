import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'

function AuthPage() {
  const navigate = useNavigate()
  const { isAuthenticated, signIn, signUp } = useAuth()

  const [mode, setMode] = useState('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState('idle')
  const [errorMessage, setErrorMessage] = useState(null)

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setErrorMessage(null)
    setStatus('submitting')

    try {
      if (mode === 'signin') {
        await signIn({ email, password })
      } else {
        await signUp({ email, password })
      }
      navigate('/')
    } catch (err) {
      setStatus('error')
      setErrorMessage(err.message)
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 font-mono flex items-center justify-center">
      <div className="w-full max-w-sm px-6">
        <h1 className="text-lg font-bold tracking-tight mb-1">Trading Explainability Tool</h1>
        <p className="text-sm text-neutral-500 mb-8">
          {mode === 'signin' ? 'Sign in to continue.' : 'Create an account.'}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-neutral-400 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-neutral-500"
            />
          </div>

          <div>
            <label className="block text-xs text-neutral-400 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-neutral-500"
            />
          </div>

          {errorMessage && (
            <div className="border border-red-900 bg-red-950 text-red-400 text-sm rounded px-3 py-2">
              {errorMessage}
            </div>
          )}

          <button
            type="submit"
            disabled={status === 'submitting'}
            className="w-full bg-neutral-100 text-neutral-950 font-semibold text-sm rounded px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white transition-colors"
          >
            {status === 'submitting'
              ? 'Please wait...'
              : mode === 'signin'
                ? 'Sign In'
                : 'Sign Up'}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode(mode === 'signin' ? 'signup' : 'signin')
            setErrorMessage(null)
          }}
          className="w-full text-xs text-neutral-500 hover:text-neutral-300 mt-4 transition-colors"
        >
          {mode === 'signin' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
        </button>
      </div>
    </div>
  )
}

export default AuthPage