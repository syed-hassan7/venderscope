import { useState, useEffect, useRef } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { googleLoginStart } from '../api/client'
import VSLogo from '../components/VSLogo'

export default function Register() {
  const { user, registerWithPasskey } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [email, setEmail]       = useState(searchParams.get('email') || '')
  const fromGoogle = searchParams.get('from') === 'google'
  const [recoveryCodes, setRecoveryCodes] = useState([])
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [visible, setVisible]   = useState(false)
  const [step, setStep]         = useState('email')
  const emailRef = useRef(null)
  const holdForRecovery = useRef(false)

  useEffect(() => {
    if (user && !holdForRecovery.current && step !== 'recovery') {
      navigate('/', { replace: true })
    }
  }, [user, navigate, step])

  useEffect(() => {
    requestAnimationFrame(() => requestAnimationFrame(() => setVisible(true)))
    if (fromGoogle) emailRef.current?.focus()
  }, [fromGoogle])

  const handleCreatePasskey = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      holdForRecovery.current = true
      const data = await registerWithPasskey()
      if (data.recovery_codes?.length) {
        setRecoveryCodes(data.recovery_codes)
        setStep('recovery')
      } else {
        holdForRecovery.current = false
        navigate('/', { replace: true })
      }
    } catch (err) {
      holdForRecovery.current = false
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : (err.message || 'Registration failed. Please try again.'))
    } finally {
      setLoading(false)
    }
  }

  const copyCodes = () => {
    navigator.clipboard?.writeText(recoveryCodes.join('\n'))
  }

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
      {/* ── Background layers (variant positions for Register) ── */}
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
      <div className="auth-orb auth-orb-a-reg" aria-hidden="true" />
      <div className="auth-orb auth-orb-b-reg" aria-hidden="true" />
      <div className="auth-orb auth-orb-c-reg" aria-hidden="true" />

      {/* ── Content ──────────────────────────────────────────── */}
      <div style={{ width: '100%', maxWidth: 400, position: 'relative', zIndex: 3, margin: 'auto' }}>

        {/* Logo */}
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
          Start your risk intelligence workspace
        </p>

        {/* Glass card */}
        <div style={{
          background: 'var(--elevated)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: '24px 20px 20px',
          boxShadow: '0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04)',
          ...reveal(340),
        }}>

          <p style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: 'var(--lo)',
            marginBottom: 20,
          }}>
            Create your account
          </p>

          {step === 'recovery' ? (
            <div>
              <p style={{ fontSize: 13, color: 'var(--mid)', marginBottom: 12, lineHeight: 1.5 }}>
                Save these recovery codes somewhere safe. Each code works once if you lose your passkey.
                <strong style={{ color: 'var(--hi)' }}> They will not be shown again.</strong>
              </p>
              <div
                style={{
                  background: 'var(--input)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '12px 14px',
                  fontFamily: 'monospace',
                  fontSize: 12,
                  color: 'var(--hi)',
                  lineHeight: 1.8,
                  marginBottom: 12,
                }}
              >
                {recoveryCodes.map((code) => <div key={code}>{code}</div>)}
              </div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <button type="button" onClick={copyCodes} style={secondaryBtnStyle}>Copy codes</button>
                <button
                  type="button"
                  onClick={() => navigate('/', { replace: true })}
                  style={primaryBtnStyle}
                >
                  I saved them — continue
                </button>
              </div>
            </div>
          ) : fromGoogle ? (
          <form onSubmit={handleCreatePasskey} method="post" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

            <div style={reveal(430)}>
              <LoginField
                label="Email"
                type="email"
                value={email}
                onChange={setEmail}
                placeholder="you@company.com"
                autoComplete="email"
                inputRef={emailRef}
                readOnly
              />
            </div>

            <div style={reveal(510)}>
              <p style={{ fontSize: 12, color: 'var(--lo)', lineHeight: 1.5 }}>
                Google already verified this address. Create a passkey to finish — Google stays linked as an extra sign-in method.
              </p>
            </div>

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

            <div style={{ marginTop: 6, ...reveal(700) }}>
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
                {loading ? <SpinnerRow label="Creating passkey…" /> : 'Create passkey'}
              </button>
            </div>

            <div style={{ marginTop: 4, ...reveal(760) }}>
              <button
                type="button"
                onClick={() => googleLoginStart()}
                style={secondaryBtnStyle}
                aria-label="Start over with Google"
              >
                Start over with Google
              </button>
            </div>

          </form>
          ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <p style={{ fontSize: 13, color: 'var(--mid)', lineHeight: 1.5, ...reveal(430) }}>
              New accounts start with Google, then a passkey. Google proves the mailbox; a passkey is required to finish.
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

            <div style={{ marginTop: 6, ...reveal(510) }}>
              <button
                type="button"
                onClick={() => googleLoginStart()}
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
                  cursor: 'pointer',
                  transition: 'all 200ms ease',
                }}
                aria-label="Continue with Google"
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'linear-gradient(135deg, #9b6cf6 0%, #8b4ced 100%)'
                  e.currentTarget.style.boxShadow = '0 0 28px rgba(139,92,246,0.38), 0 8px 24px rgba(0,0,0,0.35)'
                  e.currentTarget.style.transform = 'translateY(-1px)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)'
                  e.currentTarget.style.boxShadow = 'none'
                  e.currentTarget.style.transform = 'translateY(0)'
                }}
                onMouseDown={(e) => { e.currentTarget.style.transform = 'translateY(0) scale(0.98)' }}
                onMouseUp={(e) => { e.currentTarget.style.transform = 'translateY(-1px) scale(1)' }}
              >
                Continue with Google
              </button>
            </div>
          </div>
          )}
        </div>

        {/* Footer link */}
        <div style={{ marginTop: 12, textAlign: 'center', ...reveal(800) }}>
          <p style={{ fontSize: 13, color: 'var(--lo)' }}>
            Already have an account?{' '}
            <Link
              to="/login"
              style={{ color: 'var(--accent-l)', fontWeight: 500, textDecoration: 'none' }}
              onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
              onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
            >
              Sign in
            </Link>
          </p>
        </div>

        <p style={{
          marginTop: 14,
          textAlign: 'center',
          fontSize: 10,
          color: 'var(--lo)',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          ...reveal(880),
        }}>
          VenderScope · Vendor Risk Intelligence
        </p>
        <p style={{
          marginTop: 6,
          textAlign: 'center',
          fontSize: 11,
          color: 'var(--lo)',
          lineHeight: 1.45,
          ...reveal(920),
        }}>
          New accounts: Google, then a passkey. Password sign-in is closed.
        </p>
      </div>
    </div>
  )
}

/* ── Sub-components ──────────────────────────────────────────── */

function LoginField({ label, type, value, onChange, placeholder, autoComplete, inputRef, readOnly }) {
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
        readOnly={readOnly}
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
          opacity: readOnly ? 0.85 : 1,
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

const primaryBtnStyle = {
  flex: 1,
  minHeight: 46,
  padding: '12px 20px',
  borderRadius: 12,
  border: 'none',
  background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
  color: '#fff',
  fontSize: 14,
  fontWeight: 600,
  cursor: 'pointer',
}

const secondaryBtnStyle = {
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
