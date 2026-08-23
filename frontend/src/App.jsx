import { Suspense, lazy, useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import SiteConsentBanner from './components/SiteConsentBanner'
import AppShell from './components/AppShell'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const VendorDetail = lazy(() => import('./pages/VendorDetail'))
const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const GuestScanPage = lazy(() => import('./pages/GuestScanPage'))
const PrivacyDocPage = lazy(async () => {
  const [{ default: DocPage }, { default: markdown }] = await Promise.all([
    import('./pages/DocPage'),
    import('./docs/privacy.md?raw'),
  ])
  return { default: () => <DocPage markdown={markdown} /> }
})
const TermsDocPage = lazy(async () => {
  const [{ default: DocPage }, { default: markdown }] = await Promise.all([
    import('./pages/DocPage'),
    import('./docs/terms.md?raw'),
  ])
  return { default: () => <DocPage markdown={markdown} /> }
})
const SecurityDocPage = lazy(async () => {
  const [{ default: DocPage }, { default: markdown }] = await Promise.all([
    import('./pages/DocPage'),
    import('./docs/security.md?raw'),
  ])
  return { default: () => <DocPage markdown={markdown} /> }
})

function PageTransition({ children }) {
  const location  = useLocation()

  return (
    <div
      key={location.pathname}
      className="animate-page"
      style={{
        willChange: 'opacity, transform',
      }}
    >
      {children}
    </div>
  )
}

function Spinner({ label }) {
  return (
    <div
      className="animate-spinner-in"
      role="status"
      aria-label={label || 'Loading'}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}
    >
      <svg className="animate-spin" width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="9" stroke="var(--line)" strokeWidth="2" />
        <path d="M12 3a9 9 0 0 1 9 9" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
      {label && <p style={{ fontSize: 12, color: 'var(--lo)', margin: 0 }}>{label}</p>}
    </div>
  )
}

/** Route-chunk loading spinner — fades in only if loading takes >4s. Unrelated to
 *  backend reachability (JS chunk download only), so no retry/error state here. */
function LoadingScreen() {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 4000)
    return () => clearTimeout(t)
  }, [])
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
      <Spinner label={slow ? 'Server is starting up…' : null} />
    </div>
  )
}

function RouteLoadingScreen() {
  return <LoadingScreen />
}

/** Auth check screen — same spinner while the silent refresh is in flight, but
 *  surfaces a real failure state with a manual retry once the backend proves
 *  unreachable (as opposed to a confirmed "not logged in" via a real 401). */
function AuthLoadingScreen() {
  const { authError, retryAuth } = useAuth()
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 4000)
    return () => clearTimeout(t)
  }, [])

  if (authError === 'unreachable') {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, textAlign: 'center', maxWidth: 320 }}>
          <p style={{ fontSize: 13, color: 'var(--mid)', margin: 0 }}>
            Can't reach the server. It may still be waking up from a cold start.
          </p>
          <button
            onClick={retryAuth}
            style={{
              fontSize: 12, padding: '6px 14px', borderRadius: 6,
              border: '1px solid var(--line)', background: 'transparent',
              color: 'var(--hi)', cursor: 'pointer',
            }}
          >
            Try again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
      <Spinner label={slow ? 'Server is starting up…' : null} />
    </div>
  )
}

function ProtectedRoute({ children }) {
  const { user, loading, authError } = useAuth()
  if (loading || authError === 'unreachable') return <AuthLoadingScreen />
  return user ? children : <Navigate to="/login" replace />
}

/** Router must be inside BrowserRouter to use useLocation */
function AppRouter() {
  return (
    <PageTransition>
      <Suspense fallback={<RouteLoadingScreen />}>
        <Routes>
          <Route path="/login"    element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/guest"    element={<GuestScanPage />} />
          <Route path="/" element={
            <ProtectedRoute><AppShell><Dashboard /></AppShell></ProtectedRoute>
          } />
          <Route path="/vendor/:id" element={
            <ProtectedRoute><AppShell><VendorDetail /></AppShell></ProtectedRoute>
          } />
          <Route path="/privacy"  element={<PrivacyDocPage />} />
          <Route path="/terms"    element={<TermsDocPage />} />
          <Route path="/security" element={<SecurityDocPage />} />
        </Routes>
      </Suspense>
    </PageTransition>
  )
}

export default function App() {
  return (
      <AuthProvider>
      <BrowserRouter>
        <AppRouter />
        <SiteConsentBanner />
      </BrowserRouter>
    </AuthProvider>
  )
}
