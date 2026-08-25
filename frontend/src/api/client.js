import axios from 'axios'

// Prefer same-origin `/api` (Vercel rewrite → HF). Absolute HF URL is fallback only.
const BASE_URL = import.meta.env.VITE_API_URL || '/api'
const _HF_ORIGIN = 'https://darkitowo-venderscope-api.hf.space'
const _BACKEND_ORIGIN = BASE_URL.startsWith('http')
  ? BASE_URL.replace(/\/api$/, '')
  : _HF_ORIGIN

// Access token stored in memory — never in localStorage or cookies
// This prevents XSS-based token theft
let _accessToken = null

export function setAccessToken(token) {
  _accessToken = token
}

export function clearAccessToken() {
  _accessToken = null
}

const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // needed to send/receive the httpOnly refresh cookie
})

// Attach Authorization header to every request if we have a token
api.interceptors.request.use((config) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`
  }
  return config
})

// 401 interceptor — tries silent token refresh then retries the original request
let _isRefreshing = false
let _failedQueue = []

const _processQueue = (error, token = null) => {
  _failedQueue.forEach((p) => (error ? p.reject(error) : p.resolve(token)))
  _failedQueue = []
}

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config
    const status = err.response?.status

    // Don't retry auth endpoints — prevents infinite loops
    if (status === 401 && !original._retry && !original.url?.includes('/auth/')) {
      if (_isRefreshing) {
        // Queue requests that arrive while a refresh is in progress
        return new Promise((resolve, reject) => {
          _failedQueue.push({ resolve, reject })
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return api(original)
        })
      }

      original._retry = true
      _isRefreshing = true

      try {
        const { data } = await api.post('/auth/refresh')
        const newToken = data.access_token
        setAccessToken(newToken)
        _processQueue(null, newToken)
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      } catch (refreshErr) {
        _processQueue(refreshErr, null)
        clearAccessToken()
        window.location.href = '/login'
        return Promise.reject(refreshErr)
      } finally {
        _isRefreshing = false
      }
    }

    return Promise.reject(err)
  }
)

// --- API methods ---

export const getVendors       = ()                    => api.get('/vendors')
export const addVendor        = (data)                => api.post('/vendors', data)
export const deleteVendor     = (id)                  => api.delete(`/vendors/${id}`)
export const setVendorContext = (id, data_sensitivity) => api.patch(`/vendors/${id}/context`, { data_sensitivity })
export const getVendorEvents  = (id)                  => api.get(`/vendors/${id}/events`)
export const getScoreHistory  = (id)                  => api.get(`/vendors/${id}/history`)

// force=true — always fetches fresh data, 150s timeout covers cold start (~50s) + scan (~60s)
export const scanVendor = (id) => api.post(`/intelligence/scan/${id}?force=true`, {}, { timeout: 150000 })

// force=false — uses 24hr cache, makes Scan All fast for recently scanned vendors
export const scanAll    = ()   => api.post('/intelligence/scan-all?force=false')

export const exportPDF         = (id) => api.get(`/export/${id}/pdf`, { responseType: 'blob' })
export const getDashboardSummary = ()  => api.get('/dashboard/summary')

export const login          = (data) => api.post('/auth/login', data)
export const register       = (data) => api.post('/auth/register', data)
export const logout         = ()     => api.post('/auth/logout')
export const webauthnRegisterBegin = (data) => api.post('/auth/webauthn/register/begin', data)
export const webauthnRegisterFinish = (data) => api.post('/auth/webauthn/register/finish', data)
export const webauthnAssertBegin = (data) => api.post('/auth/webauthn/assert/begin', data ?? {})
export const webauthnAssertFinish = (data) => api.post('/auth/webauthn/assert/finish', data)
export const webauthnStepUpBegin = () => api.post('/auth/webauthn/step-up/begin')
export const recoveryConsume = (data) => api.post('/auth/recovery/consume', data)
export const recoveryRegenerate = (data) => api.post('/auth/recovery/regenerate', data)
export const googleLoginStart = () => { window.location.href = `${BASE_URL}/auth/google/start` }
export const googleLinkStart = (body = {}) => api.post('/auth/google/link/start', body)
export const googleUnlink = () => api.post('/auth/google/unlink')
export const listPasskeys = () => api.get('/auth/webauthn/credentials')
export const deletePasskey = (id) => api.delete(`/auth/webauthn/credentials/${id}`)
// config override used by the initial silent refresh — needs a longer bound to
// survive an HF cold start instead of hanging on the instance's unbounded default
export const refresh        = (config) => api.post('/auth/refresh', {}, config)
export const getMe          = ()     => api.get('/auth/me')
export const deleteAccount  = (body) => api.delete('/auth/account', { data: body })
// Axios DELETE with a body uses the `data` key, not `body`

export const ping                = ()     => axios.get(`${_BACKEND_ORIGIN}/`)
export const guestScan           = (data) => api.post('/guest/scan', data)
export const downloadGuestReport = (data) => api.post('/guest/report', data, { responseType: 'blob' })

// Notes
export const getNotes    = (id)           => api.get(`/vendors/${id}/notes`)
export const addNote     = (id, content)  => api.post(`/vendors/${id}/notes`, { content })
export const deleteNote  = (id, noteId)   => api.delete(`/vendors/${id}/notes/${noteId}`)

// Review scheduling
export const updateReview = (id, data) => api.patch(`/vendors/${id}/review`, data)

// Risk acceptances
export const getAcceptances   = (id)       => api.get(`/vendors/${id}/acceptances`)
export const createAcceptance = (id, data) => api.post(`/vendors/${id}/acceptances`, data)
export const revokeAcceptance = (id, accId) => api.delete(`/vendors/${id}/acceptances/${accId}`)

export default api
