import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { guestScan, downloadGuestReport, ping } from '../api/client'
import VSLogo from '../components/VSLogo'

const riskColor = (s) => s >= 70 ? 'var(--risk-high)' : s >= 35 ? 'var(--risk-medium)' : 'var(--risk-low)'
const riskLabel = (s) => s >= 70 ? 'HIGH RISK' : s >= 35 ? 'MEDIUM RISK' : 'LOW RISK'
const sevColor  = (s) => ({ CRITICAL: 'var(--risk-crit)', HIGH: 'var(--risk-high)', MEDIUM: 'var(--risk-medium)', LOW: 'var(--risk-low)' }[s] || 'var(--lo)')

export default function GuestScanPage() {
  const [domain,      setDomain]      = useState('')
  const [name,        setName]        = useState('')
  const [loading,     setLoading]     = useState(false)
  const [result,      setResult]      = useState(null)
  const [error,       setError]       = useState('')
  const [downloading, setDownloading] = useState(false)
  const [warming,     setWarming]     = useState(true)

  useEffect(() => {
    ping().finally(() => setWarming(false))
  }, [])

  const validate = () => {
    const d = domain.trim().replace(/^https?:\/\//i, '').replace(/\/$/, '')
    const n = name.trim()
    if (!d)             return 'Domain is required.'
    if (d.length > 253) return 'Domain must be under 253 characters.'
    if (!n)             return 'Vendor name is required.'
    if (n.length > 100) return 'Vendor name must be under 100 characters.'
    return null
  }

  const handleScan = async (e) => {
    e.preventDefault()
    setError('')
    setResult(null)
    const err = validate()
    if (err) { setError(err); return }

    const cleanDomain = domain.trim().replace(/^https?:\/\//i, '').replace(/\/$/, '').toLowerCase()
    const cleanName   = name.trim()

    setLoading(true)
    try {
      const res = await guestScan({ domain: cleanDomain, name: cleanName })
      setResult({ ...res.data, name: cleanName, domain: cleanDomain })
    } catch (e) {
      setError(e.response?.data?.detail || 'Scan failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async () => {
    if (!result) return
    setDownloading(true)
    try {
      if (!result.scan_token) {
        setError('Scan session expired. Please run the scan again before downloading.')
        return
      }
      const res = await downloadGuestReport({ scan_token: result.scan_token })
      const url  = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const link = document.createElement('a')
      link.href     = url
      link.download = `venderscope-guest-${result.domain}.pdf`
      link.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('PDF generation failed. Please try again.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div
      className="auth-page-shell page-safe-x page-safe-y"
      style={{ background: 'var(--bg)', position: 'relative' }}
    >
      <div className="auth-grid" aria-hidden="true" />
      <svg className="auth-traces" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <path className="auth-trace auth-trace-1" d="M-80,260 C200,180 550,360 900,280 S1280,240 1540,300" stroke="rgba(139,92,246,0.13)" strokeWidth="1.5" fill="none" pathLength="1" />
        <path className="auth-trace auth-trace-2" d="M-80,680 C160,620 420,730 720,650 S1080,640 1540,700" stroke="rgba(99,102,241,0.10)" strokeWidth="1" fill="none" pathLength="1" />
        <path className="auth-trace auth-trace-3" d="M1180,-30 C1140,180 1220,380 1160,580 S1180,740 1150,940" stroke="rgba(139,92,246,0.09)" strokeWidth="1.2" fill="none" pathLength="1" />
        <path className="auth-trace auth-trace-4" d="M-60,440 C280,370 580,490 880,410 S1250,400 1540,370" stroke="rgba(109,87,200,0.11)" strokeWidth="1" fill="none" pathLength="1" />
      </svg>
      <div className="auth-pulse-ring auth-pulse-ring-1" aria-hidden="true" />
      <div className="auth-pulse-ring auth-pulse-ring-2" aria-hidden="true" />
      <div className="auth-pulse-ring auth-pulse-ring-3" aria-hidden="true" />
      <div className="auth-orb auth-orb-a" aria-hidden="true" />
      <div className="auth-orb auth-orb-b" aria-hidden="true" />
      <div className="auth-orb auth-orb-c" aria-hidden="true" />

      <div style={{ maxWidth: 660, margin: '0 auto', padding: '48px 0 80px', position: 'relative', zIndex: 1 }}>

        {/* Brand header */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
            <VSLogo height={46} />
          </div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--hi)', margin: '0 0 6px' }}>
            Guest Scan
          </h1>
          <p style={{ fontSize: 13, color: 'var(--mid)', margin: 0 }}>
            Quick CVE lookup · No account required · Results not saved
          </p>
          {warming && (
            <p style={{ fontSize: 11, color: 'var(--lo)', marginTop: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
              <svg className="animate-spin" width="10" height="10" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                <circle cx="7" cy="7" r="5" stroke="rgba(255,255,255,0.2)" strokeWidth="2" />
                <path d="M7 2a5 5 0 0 1 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              Connecting to server…
            </p>
          )}
        </div>

        {/* Scan form card */}
        <div style={{
          background: 'var(--elevated)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: '24px 20px 20px',
          marginBottom: 20,
          boxShadow: '0 4px 24px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04)',
        }}>
          <p style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '0.14em',
            textTransform: 'uppercase', color: 'var(--lo)', marginBottom: 18,
          }}>
            Vendor lookup
          </p>

          <form onSubmit={handleScan} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <Field label="Vendor name" value={name} onChange={setName} placeholder="e.g. Stripe" />
            <Field label="Domain"      value={domain} onChange={setDomain} placeholder="e.g. stripe.com" />

            {error && !result && (
              <div style={{
                display: 'flex', alignItems: 'flex-start', gap: 8,
                background: 'rgba(255,68,68,0.06)', border: '1px solid rgba(255,68,68,0.18)',
                borderRadius: 8, padding: '10px 13px', fontSize: 13, color: '#ff6b6b',
              }}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0, marginTop: 1 }}>
                  <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.2"/>
                  <path d="M7 4v3.5M7 9.5v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                </svg>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%', minHeight: 46, padding: '12px 20px', marginTop: 4,
                borderRadius: 8, border: 'none',
                background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
                color: '#fff', fontSize: 14, fontWeight: 600, letterSpacing: '0.02em',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.75 : 1,
                transition: 'all 200ms ease',
              }}
              onMouseEnter={(e) => {
                if (!loading) {
                  e.currentTarget.style.background = 'linear-gradient(135deg, #9b6cf6 0%, #8b4ced 100%)'
                  e.currentTarget.style.boxShadow  = '0 0 28px rgba(139,92,246,0.38), 0 8px 24px rgba(0,0,0,0.35)'
                  e.currentTarget.style.transform  = 'translateY(-1px)'
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)'
                e.currentTarget.style.boxShadow  = 'none'
                e.currentTarget.style.transform  = 'translateY(0)'
              }}
              onMouseDown={(e) => { if (!loading) e.currentTarget.style.transform = 'translateY(0) scale(0.98)' }}
              onMouseUp={(e)   => { if (!loading) e.currentTarget.style.transform = 'translateY(-1px) scale(1)' }}
            >
              {loading
                ? <Spinner label={`Scanning ${domain || ''}…`} />
                : 'Scan (CVEs only)'}
            </button>
          </form>
        </div>

        {/* Results */}
        {result && (
          <div>
            {/* Limitation banner */}
            <div style={{
              display: 'flex', alignItems: 'flex-start', gap: 10,
              background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)',
              borderRadius: 12, padding: '12px 16px', marginBottom: 20,
            }}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0, marginTop: 2 }}>
                <path d="M7 1.5L12.5 11.5H1.5L7 1.5Z" stroke="#fbbf24" strokeWidth="1.3" fill="none" strokeLinejoin="round"/>
                <path d="M7 5.5v2.5M7 9.5v.5" stroke="#fbbf24" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              <p style={{ fontSize: 13, color: '#fbbf24', margin: 0, lineHeight: 1.5 }}>
                <span style={{ fontWeight: 600 }}>Partial scan.</span>{' '}
                Guest mode runs CVE checks only. Breach data, infrastructure exposure,
                compliance posture, and vendor profiling require an account.
                This score may be significantly lower than the actual vendor risk.
              </p>
            </div>

            {/* Score card */}
            <div style={{
              background: 'var(--elevated)', border: '1px solid var(--border)', borderRadius: 12,
              padding: '24px 20px', marginBottom: 16, textAlign: 'center',
              boxShadow: '0 4px 24px rgba(0,0,0,0.35)',
            }}>
              <div style={{ fontSize: 64, fontWeight: 700, color: riskColor(result.score), lineHeight: 1, marginBottom: 6 }}>
                {result.score}
              </div>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.14em', color: riskColor(result.score), opacity: 0.75, marginBottom: 8 }}>
                {riskLabel(result.score)}
              </div>
              <p style={{ fontSize: 12, color: 'var(--lo)', margin: 0 }}>
                CVE-based score only · Full scan requires an account
              </p>
            </div>

            {/* CVE findings card */}
            <div style={{
              background: 'var(--elevated)', border: '1px solid var(--border)', borderRadius: 12,
              padding: '20px', marginBottom: 16,
              boxShadow: '0 4px 24px rgba(0,0,0,0.35)',
            }}>
              <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--hi)', marginBottom: 14 }}>
                CVE Findings ({result.events.length})
              </h2>
              {result.events.length === 0 ? (
                <p style={{ fontSize: 13, color: 'var(--mid)', margin: 0 }}>No CVEs found for this vendor.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {result.events.map((evt, i) => (
                    <div key={i} style={{
                      background: 'var(--surface)', border: '1px solid var(--line)',
                      borderRadius: 8, padding: '12px',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--hi)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {evt.title}
                        </span>
                        <span style={{
                          fontSize: 10, fontWeight: 700, flexShrink: 0,
                          padding: '2px 6px', borderRadius: 4,
                          color: sevColor(evt.severity),
                          background: `${sevColor(evt.severity)}18`,
                        }}>
                          {evt.severity}
                        </span>
                      </div>
                      <p style={{ fontSize: 12, color: 'var(--mid)', margin: 0, lineHeight: 1.5 }}>
                        {evt.description}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Error after scan */}
            {error && (
              <div style={{
                display: 'flex', alignItems: 'flex-start', gap: 8,
                background: 'rgba(255,68,68,0.06)', border: '1px solid rgba(255,68,68,0.18)',
                borderRadius: 8, padding: '10px 13px', fontSize: 13, color: '#ff6b6b', marginBottom: 12,
              }}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0, marginTop: 1 }}>
                  <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.2"/>
                  <path d="M7 4v3.5M7 9.5v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                </svg>
                {error}
              </div>
            )}

            {/* PDF download */}
            <button
              onClick={handleDownload}
              disabled={downloading}
              style={{
                width: '100%', minHeight: 44, padding: '11px 20px', marginBottom: 16,
                borderRadius: 8, border: '1px solid var(--border)',
                background: 'var(--elevated)', color: 'var(--accent-l)',
                fontSize: 14, fontWeight: 600, letterSpacing: '0.02em',
                cursor: downloading ? 'not-allowed' : 'pointer',
                opacity: downloading ? 0.6 : 1,
                transition: 'all 200ms ease',
              }}
              onMouseEnter={(e) => {
                if (!downloading) {
                  e.currentTarget.style.borderColor = 'rgba(139,92,246,0.4)'
                  e.currentTarget.style.background  = 'rgba(139,92,246,0.06)'
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border)'
                e.currentTarget.style.background  = 'var(--elevated)'
              }}
            >
              {downloading ? <Spinner label="Generating PDF…" /> : 'Download PDF Report'}
            </button>

            {/* CTA */}
            <div style={{
              background: 'rgba(139,92,246,0.06)', border: '1px solid rgba(139,92,246,0.18)',
              borderRadius: 12, padding: '20px', textAlign: 'center',
            }}>
              <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--hi)', marginBottom: 6 }}>
                You're seeing a partial picture.
              </p>
              <p style={{ fontSize: 13, color: 'var(--mid)', marginBottom: 16, lineHeight: 1.6 }}>
                Create a free account to run full scans including breach data, Shodan exposure,
                compliance posture, and vendor profiling — and track score changes over time.
              </p>
              <Link
                to="/register"
                style={{
                  display: 'inline-block', padding: '10px 24px', borderRadius: 8,
                  background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
                  color: '#fff', fontSize: 13, fontWeight: 600, textDecoration: 'none',
                  transition: 'all 200ms ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background  = 'linear-gradient(135deg, #9b6cf6 0%, #8b4ced 100%)'
                  e.currentTarget.style.boxShadow   = '0 0 24px rgba(139,92,246,0.35)'
                  e.currentTarget.style.transform   = 'translateY(-1px)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)'
                  e.currentTarget.style.boxShadow  = 'none'
                  e.currentTarget.style.transform  = 'translateY(0)'
                }}
              >
                Create free account →
              </Link>
            </div>
          </div>
        )}

        {/* Footer nav */}
        <div style={{ textAlign: 'center', marginTop: 40 }}>
          <p style={{ fontSize: 13, color: 'var(--lo)', marginBottom: 12 }}>
            <Link
              to="/login"
              style={{ color: 'var(--lo)', textDecoration: 'none' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--mid)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--lo)')}
            >
              ← Back to login
            </Link>
            {' · '}
            <Link
              to="/register"
              style={{ color: 'var(--accent-l)', fontWeight: 500, textDecoration: 'none' }}
              onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
              onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
            >
              Create account
            </Link>
          </p>
          <p style={{ fontSize: 10, color: 'var(--lo)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            VenderScope · Vendor Risk Intelligence
          </p>
        </div>

      </div>
    </div>
  )
}

function Field({ label, value, onChange, placeholder }) {
  const [focused, setFocused] = useState(false)
  return (
    <div>
      <label style={{
        display: 'block', fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
        textTransform: 'uppercase', marginBottom: 7, transition: 'color 180ms ease',
        color: focused ? 'var(--accent-l)' : 'var(--lo)',
      }}>
        {label}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          width: '100%', padding: '11px 14px', borderRadius: 8, outline: 'none',
          background: focused ? 'rgba(139,92,246,0.06)' : 'var(--input)',
          border: focused ? '1px solid rgba(139,92,246,0.55)' : '1px solid var(--line)',
          color: 'var(--hi)', fontSize: 14, transition: 'all 180ms ease',
          boxShadow: focused ? '0 0 0 3px rgba(139,92,246,0.12), inset 0 1px 2px rgba(0,0,0,0.15)' : 'none',
          boxSizing: 'border-box',
        }}
      />
    </div>
  )
}

function Spinner({ label }) {
  return (
    <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
      <svg className="animate-spin" width="14" height="14" viewBox="0 0 14 14" fill="none">
        <circle cx="7" cy="7" r="5" stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
        <path d="M7 2a5 5 0 0 1 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
      {label}
    </span>
  )
}
