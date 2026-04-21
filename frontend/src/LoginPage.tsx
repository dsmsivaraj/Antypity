import { useState } from 'react'
import { GoogleLogin } from '@react-oauth/google'
import { api } from './api'
import { useAuth } from './AuthContext'

interface LoginPageProps {
  onLoginSuccess: () => void
}

export function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const { login } = useAuth()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleGoogleSuccess = async (credentialResponse: { credential?: string }) => {
    const idToken = credentialResponse.credential
    if (!idToken) {
      setError('No credential received from Google.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const result = await api.googleAuth(idToken)
      login(result.access_token, result.user)
      onLoginSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-vh-100 d-flex align-items-center justify-content-center" style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
      <div className="card shadow-lg border-0 rounded-4" style={{ width: '100%', maxWidth: 420 }}>
        <div className="card-body p-5 text-center">
          <div className="mb-4">
            <span className="fs-1">🎯</span>
            <h1 className="h3 fw-bold mt-2 mb-1">Actypity</h1>
            <p className="text-secondary small">AI-powered career platform</p>
          </div>

          <div className="mb-4">
            <h2 className="h5 fw-semibold mb-1">Welcome back</h2>
            <p className="text-secondary small">Sign in to access your career dashboard</p>
          </div>

          {error && (
            <div className="alert alert-danger py-2 small mb-3">{error}</div>
          )}

          {loading ? (
            <div className="d-flex justify-content-center py-3">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Signing in...</span>
              </div>
            </div>
          ) : (
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
          )}

          <p className="text-secondary small mt-4 mb-0">
            By signing in you agree to our terms of service.
            <br />
            Your data stays private — no resume data leaves this platform.
          </p>
        </div>
      </div>
    </div>
  )
}
