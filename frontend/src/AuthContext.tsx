import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api, getStoredJwt, setStoredJwt } from './api'
import type { User } from './types'

interface AuthContextValue {
  user: User | null
  jwt: string
  loading: boolean
  login: (jwt: string, user: User) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  jwt: '',
  loading: true,
  login: () => {},
  logout: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [jwt, setJwt] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const stored = getStoredJwt()
    if (!stored) {
      setLoading(false)
      return
    }
    api.getAuthMe(stored)
      .then((u) => {
        setUser(u)
        setJwt(stored)
      })
      .catch(() => {
        setStoredJwt('')
      })
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback((token: string, u: User) => {
    setStoredJwt(token)
    setJwt(token)
    setUser(u)
  }, [])

  const logout = useCallback(() => {
    setStoredJwt('')
    setJwt('')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, jwt, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
