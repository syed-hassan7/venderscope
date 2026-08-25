/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import {
  logout as apiLogout,
  refresh as apiRefresh,
  webauthnAssertBegin,
  webauthnAssertFinish,
  webauthnRegisterBegin,
  webauthnRegisterFinish,
  recoveryConsume,
  getMe,
  ping,
} from '../api/client'
import { setAccessToken, clearAccessToken } from '../api/client'
import { createPasskey, getPasskeyAssertion, isWebAuthnSupported } from './webauthn'

const AuthContext = createContext(null)

const REFRESH_TIMEOUT_MS = 45000

export function AuthProvider({ children }) {
  const [user, setUser]         = useState(null)
  const [factors, setFactors]   = useState(null)
  const [loading, setLoading]   = useState(true)
  const [authError, setAuthError] = useState(null)
  const _refreshSeq = useRef(0)

  const _parseToken = (token) => {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      return { id: payload.sub }
    } catch {
      return null
    }
  }

  const _loadMe = async () => {
    try {
      const { data } = await getMe()
      setUser((prev) => ({ ...(prev || {}), email: data.email }))
      setFactors(data.factors)
    } catch {
      // best-effort
    }
  }

  const _isUnreachable = (err) =>
    !err.response || [502, 503, 504].includes(err.response.status)

  const _wakeBackend = async () => {
    try {
      await ping({ timeout: REFRESH_TIMEOUT_MS })
    } catch {
      // cold start probe — best effort
    }
  }

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
      if (_refreshSeq.current !== seq) return
      setAccessToken(res.data.access_token)
      setUser(_parseToken(res.data.access_token))
      await _loadMe()
    } catch (err) {
      if (_refreshSeq.current !== seq) return
      if (_isUnreachable(err)) setAuthError('unreachable')
      clearAccessToken()
      setUser(null)
      setFactors(null)
    } finally {
      if (_refreshSeq.current === seq) setLoading(false)
    }
  }, [])

  const retryAuth = useCallback(() => {
    setLoading(true)
    silentRefresh()
  }, [silentRefresh])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('oauth') === '1') {
      silentRefresh()
      params.delete('oauth')
      const url = new URL(window.location.href)
      url.search = params.toString()
      window.history.replaceState({}, '', url.pathname + (url.search ? `?${url.search}` : ''))
    } else {
      silentRefresh()
    }
  }, [silentRefresh])

  const _applySession = (accessToken) => {
    setAccessToken(accessToken)
    setUser(_parseToken(accessToken))
    return _loadMe()
  }

  const loginWithPasskey = async (email) => {
    if (!isWebAuthnSupported()) throw new Error('Passkeys are not supported in this browser')
    await _wakeBackend()
    const { data: options } = await webauthnAssertBegin(email ? { email } : {})
    const payload = await getPasskeyAssertion(options)
    const { data } = await webauthnAssertFinish(payload)
    await _applySession(data.access_token)
    return data
  }

  const loginWithRecovery = async (email, code) => {
    const { data } = await recoveryConsume({ email, code })
    await _applySession(data.access_token)
    return data
  }

  const registerWithPasskey = async (email) => {
    if (!isWebAuthnSupported()) throw new Error('Passkeys are not supported in this browser')
    await _wakeBackend()
    const { data: options } = await webauthnRegisterBegin(email ? { email } : {})
    const payload = await createPasskey(options)
    const { data } = await webauthnRegisterFinish(payload)
    await _applySession(data.access_token)
    return data
  }

  const logoutUser = async () => {
    try {
      await apiLogout()
    } finally {
      clearAccessToken()
      setUser(null)
      setFactors(null)
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        factors,
        loading,
        authError,
        retryAuth,
        loginWithPasskey,
        loginWithRecovery,
        registerWithPasskey,
        refreshMe: _loadMe,
        logout: logoutUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
