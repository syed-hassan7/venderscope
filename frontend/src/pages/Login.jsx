import { useState, useEffect, useRef } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { googleLoginStart } from '../api/client'
import VSLogo from '../components/VSLogo'

export default function Login() {
  const { login, loginWithPasskey, loginWithRecovery, user } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const accountDeleted = searchParams.get('deleted') === '1'
  const googleError = searchParams.get('error') === 'google_conflict'

  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [recoveryCode, setRecoveryCode] = useState('')
  const [mode, setMode]         = useState('password')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [visible, setVisible]   = useState(false)
  const emailRef = useRef(null)

  useEffect(() => {
    if (user) navigate('/', { replace: true })
  }, [user, navigate])

  useEffect(() => {
    requestAnimationFrame(() => requestAnimationFrame(() => setVisible(true)))
    emailRef.current?.focus()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'recovery') {
        await loginWithRecovery(email, recoveryCode)
      } else {
        await login(email, password)
      }
      navigate('/', { replace: true })
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : err.message || 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handlePasskeyLogin = async () => {
    setError('')
    setLoading(true)
    try {
      await loginWithPasskey(email.trim() || undefined)
      navigate('/', { replace: true })
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : err.message || 'Passkey sign-in failed.')
    } finally {
      setLoading(false)
    }
  }

  // Stagger helper — returns transition styles keyed to `visible` state
  const reveal = (delayMs) => ({
    opacity:    visible ? 1 : 0,
    transform:  visible ? 'translateY(0)' : 'translateY(18px)',
    transition: `opacity 600ms cubic-bezier(0.16,1,0.3,1) ${delayMs}ms,
                 transform 600ms cubic-bezier(0.16,1,0.3,1) ${delayMs}ms`,
  })

  return (
    <div
      className="auth-page-shell auth-page-form-shell page-safe-x page-safe-y"
      style={{
        minHeight: '100dvh',
        background: 'var(--bg)',
        position: 'relative',
      }}
    >
      {/* ── Background layers ────────────────────────────────── */}
      <div className="auth-grid" aria-hidden="true" />
      <svg className="auth-traces" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <path className="auth-trace auth-trace-1" d="M-80,260 C200,180 550,360 900,280 S1280,240 1540,300" stroke="rgba(139,92,246,0.13)" strokeWidth="1.5" fill="none" pathLength="1" />
        <path className="auth-trace auth-trace-2" d="M-80,680 C160,620 420,730 720,650 S1080,640 1540,700" stroke="rgba(99,102,241,0.10)" strokeWidth="1"   fill="none" pathLength="1" />
        <path className="auth-trace auth-trace-3" d="M1180,-30 C1140,180 1220,380 1160,580 S1180,740 1150,940" stroke="rgba(139,92,246,0.09)" strokeWidth="1.2" fill="none" pathLength="1" />
        <path className="auth-trace auth-trace-4" d="M-60,440 C280,370 580,490 880,410 S1250,400 1540,370" stroke="rgba(109,87,200,0.11)" strokeWidth="1"   fill="none" pathLength="1" />
      </svg>
      <div className="auth-pulse-ring auth-pulse-ring-1" aria-hidden="true" />
      <div className="auth-pulse-ring auth-pulse-ring-2" aria-hidden="true" />
      <div className="auth-pulse-ring auth-pulse-ring-3" aria-hidden="true" />
      <div className="auth-orb auth-orb-a" aria-hidden="true" />
      <div className="auth-orb auth-orb-b" aria-hidden="true" />
      <div className="auth-orb auth-orb-c" aria-hidden="true" />

      {/* ── Content ──────────────────────────────────────────── */}
      <div style={{ width: '100%', maxWidth: 400, position: 'relative', zIndex: 3, margin: 'auto' }}>

        {/* Logo — draws in on first paint */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16, ...reveal(0) }}>
          <VSLogo height={54} animated />
        </div>

        {/* Tagline */}
        <p style={{
          textAlign: 'center',
          fontSize: 12,
          color: 'var(--lo)',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          marginBottom: 16,
          ...reveal(220),
        }}>
          Continuous vendor risk intelligence
        </p>

        {googleError && (
          <div style={{ marginBottom: 16, ...reveal(280) }}>
            <div style={{
              background: 'rgba(255,68,68,0.06)',
              border: '1px solid rgba(255,68,68,0.18)',
              borderRadius: 12,
              padding: '11px 16px',
              fontSize: 13,
              color: '#ff6b6b',
              textAlign: 'center',
            }}>
              That Google account matches an existing email. Sign in with password or passkey first, then link Google.
            </div>
          </div>
        )}
        {accountDeleted && (
          <div style={{ marginBottom: 16, ...reveal(260) }}>
            <div style={{
              background: 'rgba(34,197,94,0.07)',
              border: '1px solid rgba(34,197,94,0.2)',
              borderRadius: 12,
              padding: '11px 16px',
              fontSize: 13,
              color: '#4ade80',
              textAlign: 'center',
            }}>
              Your account has been permanently deleted.
            </div>
          </div>
        )}

        {/* Glass card */}
        <div style={{
          background: 'var(--elevated)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: '24px 20px 20px',
          boxShadow: '0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04)',
          ...reveal(360),
        }}>

          {/* Section label */}
          <p style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: 'var(--lo)',
            marginBottom: 20,
          }}>
            Sign in to your workspace
          </p>

          <form onSubmit={handleSubmit} method="post" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

            <div style={reveal(460)}>
              <LoginField
                label="Email"
                type="email"
                value={email}
                onChange={setEmail}
                placeholder="you@company.com"
                autoComplete="email"
                inputRef={emailRef}
              />
            </div>

            <div style={reveal(540)}>
              {mode === 'recovery' ? (
                <LoginField
                  label="Recovery code"
                  type="text"
                  value={recoveryCode}
                  onChange={setRecoveryCode}
                  placeholder="XXXX-XXXX-XXXX-XXXX"
                  autoComplete="one-time-code"
                />
              ) : (
                <LoginField
                  label="Password"
                  type="password"
                  value={password}
                  onChange={setPassword}
                  placeholder="••••••••"
                  autoComplete="current-password"
                />
              )}
            </div>

            <p style={{ fontSize: 11, color: 'var(--lo)' }}>
              {mode === 'recovery' ? (
                <button type="button" onClick={() => setMode('password')} style={linkBtnStyle}>Use password instead</button>
              ) : (
                <button type="button" onClick={() => setMode('recovery')} style={linkBtnStyle}>Use a recovery code</button>
              )}
            </p>

            {error && (
              <div style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
                background: 'rgba(255,68,68,0.06)',
                border: '1px solid rgba(255,68,68,0.18)',
                borderRadius: 8,
                padding: '10px 13px',
                fontSize: 13,
                color: '#ff6b6b',
              }}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0, marginTop: 1 }}>
                  <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.2"/>
                  <path d="M7 4v3.5M7 9.5v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                </svg>
                {error}
              </div>
            )}

            <div style={{ marginTop: 6, ...reveal(620) }}>
              <button
                type="submit"
                disabled={loading}
                style={{
                  width: '100%',
                  minHeight: 46,
                  padding: '12px 20px',
                  borderRadius: 12,
                  border: 'none',
                  background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
                  color: '#fff',
                  fontSize: 14,
                  fontWeight: 600,
                  letterSpacing: '0.02em',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.75 : 1,
                  transition: 'all 200ms ease',
                  position: 'relative',
                }}
                onMouseEnter={(e) => {
                  if (!loading) {
                    e.currentTarget.style.background = 'linear-gradient(135deg, #9b6cf6 0%, #8b4ced 100%)'
                    e.currentTarget.style.boxShadow = '0 0 28px rgba(139,92,246,0.38), 0 8px 24px rgba(0,0,0,0.35)'
                    e.currentTarget.style.transform = 'translateY(-1px)'
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)'
                  e.currentTarget.style.boxShadow = 'none'
                  e.currentTarget.style.transform = 'translateY(0)'
                }}
                onMouseDown={(e) => { if (!loading) e.currentTarget.style.transform = 'translateY(0) scale(0.98)' }}
                onMouseUp={(e) => { if (!loading) e.currentTarget.style.transform = 'translateY(-1px) scale(1)' }}
              >
                {loading ? <SpinnerRow label="Signing in…" /> : (mode === 'recovery' ? 'Sign in with code' : 'Sign in')}
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8, ...reveal(680) }}>
              <button
                type="button"
                disabled={loading}
                onClick={handlePasskeyLogin}
                style={altBtnStyle}
                aria-label="Sign in with passkey"
              >
                Sign in with passkey
              </button>
              <button
                type="button"
                onClick={() => googleLoginStart()}
                style={altBtnStyle}
                aria-label="Continue with Google"
              >
                Continue with Google
              </button>
            </div>
          </form>
        </div>

        {/* Footer links */}
        <div style={{ marginTop: 12, textAlign: 'center', ...reveal(720) }}>
          <p style={{ fontSize: 13, color: 'var(--lo)', marginBottom: 8 }}>
            Don't have an account?{' '}
            <Link
              to="/register"
              style={{ color: 'var(--accent-l)', fontWeight: 500, textDecoration: 'none' }}
              onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
              onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
            >
              Create one
            </Link>
          </p>
          <p style={{ fontSize: 13, color: 'var(--lo)' }}>
            Just browsing?{' '}
            <Link
              to="/guest"
              style={{ color: 'var(--lo)', fontWeight: 500, textDecoration: 'none' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--mid)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--lo)')}
            >
              Try as Guest →
            </Link>
          </p>
        </div>

        {/* Micro brand footer */}
        <p style={{
          marginTop: 14,
          textAlign: 'center',
          fontSize: 10,
          color: 'var(--lo)',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          ...reveal(820),
        }}>
          VenderScope · Vendor Risk Intelligence
        </p>
      </div>
    </div>
  )
}

/* ── Sub-components ──────────────────────────────────────────── */

function LoginField({ label, type, value, onChange, placeholder, autoComplete, inputRef }) {
  const [focused, setFocused] = useState(false)
  return (
    <div>
      <label style={{
        display: 'block',
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: focused ? 'var(--accent-l)' : 'var(--lo)',
        marginBottom: 7,
        transition: 'color 180ms ease',
      }}>
        {label}
      </label>
      <input
        ref={inputRef}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          width: '100%',
          padding: '11px 14px',
          borderRadius: 8,
          border: focused
            ? '1px solid rgba(139,92,246,0.55)'
            : '1px solid var(--line)',
          background: focused
            ? 'rgba(139,92,246,0.06)'
            : 'var(--input)',
          color: 'var(--hi)',
          fontSize: 14,
          outline: 'none',
          transition: 'all 180ms ease',
          boxShadow: focused
            ? '0 0 0 3px rgba(139,92,246,0.12), inset 0 1px 2px rgba(0,0,0,0.15)'
            : 'none',
          boxSizing: 'border-box',
        }}
      />
    </div>
  )
}

function SpinnerRow({ label }) {
  return (
    <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
      <svg className="animate-spin" width="14" height="14" viewBox="0 0 14 14" fill="none">
        <circle cx="7" cy="7" r="5" stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
        <path d="M7 2a5 5 0 0 1 5 5" stroke="white" strokeWidth="2" strokeLinecap="round" />
      </svg>
      {label}
    </span>
  )
}

const altBtnStyle = {
  width: '100%',
  minHeight: 44,
  padding: '10px 16px',
  borderRadius: 12,
  border: '1px solid var(--border)',
  background: 'rgba(255,255,255,0.04)',
  color: 'var(--mid)',
  fontSize: 13,
  fontWeight: 500,
  cursor: 'pointer',
}

const linkBtnStyle = {
  background: 'none',
  border: 'none',
  color: 'var(--accent-l)',
  fontSize: 11,
  cursor: 'pointer',
  padding: 0,
  textDecoration: 'underline',
}
