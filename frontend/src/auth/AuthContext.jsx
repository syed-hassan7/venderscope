/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { login as apiLogin, logout as apiLogout, refresh as apiRefresh } from '../api/client'
import { setAccessToken, clearAccessToken } from '../api/client'

const AuthContext = createContext(null)

// Cold HF Space boot is ~30-50s (see README) — bounded but generous, and only
// applied here, not to every request, so a genuinely dead backend still fails fast
// everywhere else in the app.
const REFRESH_TIMEOUT_MS = 45000

export function AuthProvider({ children }) {
  const [user, setUser]         = useState(null)   // { email } once decoded from token
  const [loading, setLoading]   = useState(true)   // true during initial silent refresh
  const [authError, setAuthError] = useState(null) // 'unreachable' | null
  const _refreshSeq = useRef(0) // guards against overlapping silentRefresh calls
  // (StrictMode double-mount, or a fast retry firing before the prior one settles)
  // clobbering fresher state with a stale result — refresh tokens are single-use,
  // so a superseded call can legitimately 401 even though a newer one already won

  // Decode the user email from a JWT without verifying (verification happens server-side)
  const _parseToken = (token) => {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      return { id: payload.sub }
    } catch {
      return null
    }
  }

  // A reverse-proxy fronting a cold/dead backend (Vercel rewrite -> HF Space)
  // typically answers with a real 502/503/504, not a bare network failure — treat
  // those the same as "no response" so the cold-start retry path actually triggers.
  const _isUnreachable = (err) =>
    !err.response || [502, 503, 504].includes(err.response.status)

  // Called on mount (and on manual retry) — attempts silent login via the httpOnly
  // refresh cookie. Retries once on unreachable-backend errors only (network/timeout/
  // 502/503/504 — consistent with a cold start still booting); a real HTTP response
  // otherwise (e.g. 401, no valid cookie) fails immediately and sends the user to
  // login as before.
  const silentRefresh = useCallback(async () => {
    const seq = ++_refreshSeq.current
    setAuthError(null)
    const attempt = () => apiRefresh({ timeout: REFRESH_TIMEOUT_MS })

    try {
      let res
      try {
        res = await attempt()
      } catch (err) {
        if (!_isUnreachable(err)) throw err
        res = await attempt()
      }
      if (_refreshSeq.current !== seq) return // superseded by a newer call
      setAccessToken(res.data.access_token)
      setUser(_parseToken(res.data.access_token))
    } catch (err) {
      if (_refreshSeq.current !== seq) return
      if (_isUnreachable(err)) setAuthError('unreachable')
      clearAccessToken()
      setUser(null)
    } finally {
      if (_refreshSeq.current === seq) setLoading(false)
    }
  }, [])

  const retryAuth = useCallback(() => {
    setLoading(true)
    silentRefresh()
  }, [silentRefresh])

  useEffect(() => {
    silentRefresh()
  }, [silentRefresh])

  const login = async (email, password) => {
    const { data } = await apiLogin({ email, password })
    setAccessToken(data.access_token)
    setUser(_parseToken(data.access_token))
    return data
  }

  const logoutUser = async () => {
    try {
      await apiLogout()
    } finally {
      clearAccessToken()
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, authError, retryAuth, login, logout: logoutUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
