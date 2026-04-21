import { useState } from 'react'
import { GoogleLogin } from '@react-oauth/google'
import { api } from './api'
import { useAuth } from './AuthContext'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

interface LoginPageProps {
  onLoginSuccess: () => void
}

export function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const { login } = useAuth()
  const [mode, setMode] = useState<'signin' | 'register'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleGoogleSuccess = async (credentialResponse: { credential?: string }) => {
    const idToken = credentialResponse.credential
    if (!idToken) { setError('No credential received from Google.'); return }
    setLoading(true); setError('')
    try {
      const result = await api.googleAuth(idToken)
      login(result.access_token, result.user)
      onLoginSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Google sign-in failed.')
    } finally { setLoading(false) }
  }

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) { setError('Email and password are required.'); return }
    setLoading(true); setError('')
    try {
      const result = mode === 'signin'
        ? await api.emailLogin(email, password)
        : await api.emailRegister(email, password, fullName || undefined)
      login(result.access_token, result.user)
      onLoginSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed.')
    } finally { setLoading(false) }
  }

  return (
    <div className="min-vh-100 d-flex align-items-center justify-content-center"
      style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
      <div className="card shadow-lg border-0 rounded-4" style={{ width: '100%', maxWidth: 420 }}>
        <div className="card-body p-5">
          <div className="text-center mb-4">
            <span className="fs-1">🎯</span>
            <h1 className="h3 fw-bold mt-2 mb-1">Actypity</h1>
            <p className="text-secondary small">AI-powered career platform</p>
          </div>

          <div className="d-flex mb-4 rounded-3 overflow-hidden border">
            <button
              className={`btn flex-fill rounded-0 py-2 ${mode === 'signin' ? 'btn-primary' : 'btn-light'}`}
              onClick={() => { setMode('signin'); setError('') }}
            >Sign In</button>
            <button
              className={`btn flex-fill rounded-0 py-2 ${mode === 'register' ? 'btn-primary' : 'btn-light'}`}
              onClick={() => { setMode('register'); setError('') }}
            >Create Account</button>
          </div>

          {error && <div className="alert alert-danger py-2 small mb-3">{error}</div>}

          {loading ? (
            <div className="d-flex justify-content-center py-3">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Please wait…</span>
              </div>
            </div>
          ) : (
            <>
              <form onSubmit={handleEmailSubmit} className="mb-3">
                {mode === 'register' && (
                  <div className="mb-3">
                    <input
                      type="text"
                      className="form-control"
                      placeholder="Full name (optional)"
                      value={fullName}
                      onChange={e => setFullName(e.target.value)}
                      autoComplete="name"
                    />
                  </div>
                )}
                <div className="mb-3">
                  <input
                    type="email"
                    className="form-control"
                    placeholder="Email address"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    autoComplete="email"
                    required
                  />
                </div>
                <div className="mb-3">
                  <input
                    type="password"
                    className="form-control"
                    placeholder="Password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                    required
                  />
                </div>
                <button type="submit" className="btn btn-primary w-100 py-2">
                  {mode === 'signin' ? 'Sign In' : 'Create Account'}
                </button>
              </form>

              {GOOGLE_CLIENT_ID && (
                <>
                  <div className="text-center text-secondary small my-3">— or —</div>
                  <div className="d-flex justify-content-center">
                    <GoogleLogin
                      onSuccess={handleGoogleSuccess}
                      onError={() => setError('Google Sign-In failed. Please try again.')}
                      useOneTap={false}
                      text="signin_with"
                      shape="rectangular"
                      size="large"
                      width="280"
                    />
                  </div>
                </>
              )}
            </>
          )}

          <p className="text-secondary small text-center mt-4 mb-0">
            Your data stays private — no resume data leaves this platform.
          </p>
        </div>
      </div>
    </div>
  )
}
