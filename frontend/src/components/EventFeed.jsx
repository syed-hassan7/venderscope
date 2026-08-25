import { useState, useRef } from 'react'
import { createPortal } from 'react-dom'
import { formatApiDate, parseApiDate } from '../utils/datetime'

const SEV = {
  CRITICAL: { color: 'var(--risk-crit)',   bg: 'rgba(244,63,94,0.06)',  border: 'rgba(244,63,94,0.14)'  },
  HIGH:     { color: 'var(--risk-high)',   bg: 'rgba(240,68,56,0.05)',  border: 'rgba(240,68,56,0.12)'  },
  MEDIUM:   { color: 'var(--risk-medium)', bg: 'rgba(245,158,11,0.05)', border: 'rgba(245,158,11,0.1)'  },
  LOW:      { color: 'var(--risk-low)',    bg: 'rgba(16,185,129,0.04)', border: 'rgba(16,185,129,0.09)' },
}

const getCVELink = (title) => {
  const id = title?.split(' ')[0]
  return id?.startsWith('CVE-') ? `https://nvd.nist.gov/vuln/detail/${id}` : null
}

const SeverityBadge = ({ severity }) => {
  const cfg = SEV[severity] || SEV.LOW
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-bold tracking-wider shrink-0 whitespace-nowrap"
      style={{
        background: `${cfg.color}18`,
        color: cfg.color,
        border: `1px solid ${cfg.color}30`,
      }}
    >
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: cfg.color }} />
      {severity}
    </span>
  )
}

const AcceptedBadge = ({ acceptance }) => {
  const [hovered, setHovered] = useState(false)
  const [pos, setPos] = useState({ top: 0, right: 0 })
  const badgeRef = useRef(null)
  const expiryDate = formatApiDate(acceptance.expires_at, [], { month: 'short', day: 'numeric', year: 'numeric' })

  const handleMouseEnter = () => {
    if (badgeRef.current) {
      const r = badgeRef.current.getBoundingClientRect()
      setPos({
        top:   r.top,                      // top of badge in viewport
        right: window.innerWidth - r.right, // right-aligned with badge
      })
    }
    setHovered(true)
  }

  /*
   * Portal: mounts the tooltip DOM node directly under <body>, completely
   * outside the Risk Events panel which holds transform: translateY(0) after
   * its fade-up animation completes. Any ancestor CSS transform makes
   * position:fixed children relative to that element rather than the viewport —
   * portalling out is the only reliable escape.
   *
   * Positioning: top = badge's viewport top, then translateY(calc(-100% - 8px))
   * shifts the tooltip fully above the badge with an 8px gap.
   */
  const tooltip = createPortal(
    <div
      id={`accepted-tooltip-${acceptance.id}`}
      role="tooltip"
      style={{
        position:   'fixed',
        top:        pos.top,
        right:      pos.right,
        width:      256,
        background: 'var(--elevated)',
        border:     '1px solid var(--border)',
        borderRadius: 12,
        padding:    '12px 14px',
        color:      'var(--mid)',
        fontSize:   12,
        boxShadow:  '0 8px 40px rgba(0,0,0,0.85)',
        zIndex:     9999,
        pointerEvents: 'none',
        opacity:    hovered ? 1 : 0,
        transform:  hovered
          ? 'translateY(calc(-100% - 8px))'
          : 'translateY(calc(-100% - 4px))',
        transition: 'opacity 140ms ease, transform 140ms ease',
      }}
    >
      <p style={{ color: '#fbbf24', fontWeight: 600, marginBottom: 4 }}>Risk Accepted</p>
      <p style={{ color: 'var(--hi)', fontSize: 11, lineHeight: 1.5, marginBottom: 8 }}>{acceptance.justification}</p>
      <p style={{ fontSize: 10 }}>Reviewer: <span style={{ color: 'var(--hi)' }}>{acceptance.reviewer}</span></p>
      <p style={{ fontSize: 10, marginTop: 2 }}>Expires: <span style={{ color: 'var(--hi)' }}>{expiryDate}</span></p>
    </div>,
    document.body
  )

  return (
    <span className="inline-block shrink-0">
      <button
        type="button"
        ref={badgeRef}
        aria-describedby={`accepted-tooltip-${acceptance.id}`}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-bold tracking-wider whitespace-nowrap cursor-help bg-transparent"
        style={{
          background: 'rgba(251,191,36,0.08)',
          color: '#fbbf24',
          border: '1px solid rgba(251,191,36,0.25)',
        }}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={() => setHovered(false)}
        onFocus={handleMouseEnter}
        onBlur={() => setHovered(false)}
      >
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: '#fbbf24' }} />
        ACCEPTED
      </button>
      {tooltip}
    </span>
  )
}

const DEFAULT_EXPIRY = () => {
  const d = new Date()
  d.setDate(d.getDate() + 90)
  return d.toISOString().split('T')[0]
}

export default function EventFeed({ events, acceptances = [], onAccept, onRevoke, revokingIds }) {
  const [expandedEvent, setExpandedEvent] = useState(null)
  const [formState, setFormState] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [acceptError, setAcceptError] = useState('')

  if (!events.length)
    return (
      <div
        className="rounded-xl p-4 sm:p-5"
        style={{
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.05)',
        }}
      >
        <div className="flex items-start gap-3">
          <div
            className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full shrink-0"
            style={{
              background: 'rgba(16,185,129,0.08)',
              border: '1px solid rgba(16,185,129,0.16)',
              color: 'var(--risk-low)',
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M5 12l4 4L19 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--hi)' }}>
              No public risk events were detected in this scan.
            </p>
            <p className="text-xs mt-1 leading-relaxed" style={{ color: 'var(--lo)' }}>
              This means VenderScope did not find public CVEs, breach references, infrastructure exposure, or other passive signals for this vendor at the time of scanning.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3">
              {[
                ['Passive only', 'Findings come from public sources rather than authenticated checks.'],
                ['Point-in-time', 'A clean result today does not guarantee the vendor will remain clean later.'],
                ['Recommended', 'Scan again periodically to catch newly disclosed issues.'],
              ].map(([title, body]) => (
                <div
                  key={title}
                  className="rounded-lg px-3 py-2.5"
                  style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}
                >
                  <p className="text-[10px] font-bold tracking-[0.12em] uppercase mb-1" style={{ color: 'var(--lo)' }}>
                    {title}
                  </p>
                  <p className="text-[11px] leading-relaxed" style={{ color: 'var(--mid)' }}>
                    {body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    )

  const getAcceptance = (eventId) =>
    acceptances.find((a) => a.event_id === eventId && a.is_active)

  const getForm = (eventId) =>
    formState[eventId] || { justification: '', reviewer: '', expires_at: DEFAULT_EXPIRY(), finding_type: 'CVE' }

  const setForm = (eventId, patch) =>
    setFormState((s) => ({ ...s, [eventId]: { ...getForm(eventId), ...patch } }))

  const handleAccept = async (evt) => {
    const form = getForm(evt.id)
    if (!form.justification.trim() || !form.reviewer.trim()) return
    setSubmitting(true)
    setAcceptError('')
    try {
      await onAccept(evt.id, {
        event_id:      evt.id,
        finding_ref:   evt.title.split(' ')[0] || evt.title,
        finding_type:  form.finding_type,
        justification: form.justification,
        reviewer:      form.reviewer,
        expires_at:    new Date(form.expires_at).toISOString(),
      })
      setExpandedEvent(null)
      setFormState((s) => { const n = { ...s }; delete n[evt.id]; return n })
    } catch (e) {
      setAcceptError(e.response?.data?.detail || 'Failed to save risk acceptance. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-1.5">
      {events.map((evt) => {
        const cfg = SEV[evt.severity] || SEV.LOW
        const cveLink = getCVELink(evt.title)
        const acceptance = getAcceptance(evt.id)
        const isExpanded = expandedEvent === evt.id
        const form = getForm(evt.id)

        return (
          <div
            key={evt.id}
            className="rounded-lg overflow-hidden"
            style={{
              borderTop:    `1px solid ${acceptance ? 'rgba(251,191,36,0.2)' : cfg.border}`,
              borderRight:  `1px solid ${acceptance ? 'rgba(251,191,36,0.2)' : cfg.border}`,
              borderBottom: `1px solid ${acceptance ? 'rgba(251,191,36,0.2)' : cfg.border}`,
              borderLeft:   `3px solid ${acceptance ? '#fbbf24' : cfg.color}`,
              opacity: acceptance ? 0.75 : 1,
              transition: 'opacity 200ms ease',
            }}
          >
            {/* Main event row */}
            <div
              className="p-3.5"
              style={{ background: acceptance ? 'rgba(251,191,36,0.03)' : cfg.bg }}
            >
              {/* Title row */}
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2.5 mb-1.5">
                <span
                  className="text-[13px] font-medium leading-snug flex-1 min-w-0"
                  style={{ color: 'var(--hi)' }}
                >
                  {cveLink ? (
                    <a
                      href={cveLink}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:underline underline-offset-2 transition-opacity hover:opacity-75"
                    >
                      {evt.title}
                      <svg className="inline ml-1 mb-0.5" width="9" height="9" viewBox="0 0 10 10" fill="none" aria-hidden="true">
                        <path d="M2 8L8 2M8 2H4M8 2V6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </a>
                  ) : evt.title}
                </span>

                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  {acceptance ? (
                    <>
                      <AcceptedBadge acceptance={acceptance} />
                      {onRevoke && (
                        <button
                          onClick={() => onRevoke(acceptance.id)}
                          disabled={revokingIds?.has(acceptance.id)}
                          className="text-[9px] px-1.5 py-0.5 rounded transition-colors duration-150 disabled:opacity-40"
                          style={{ color: 'var(--lo)', background: 'transparent' }}
                          onMouseEnter={(e) => e.currentTarget.style.color = 'var(--risk-high)'}
                          onMouseLeave={(e) => e.currentTarget.style.color = 'var(--lo)'}
                          title="Revoke acceptance"
                        >
                          {revokingIds?.has(acceptance.id) ? '…' : '✕'}
                        </button>
                      )}
                    </>
                  ) : (
                    <>
                      <SeverityBadge severity={evt.severity} />
                      {onAccept && (
                        <button
                          onClick={() => { setAcceptError(''); setExpandedEvent(isExpanded ? null : evt.id) }}
                          className="text-[9px] px-2 py-0.5 rounded transition-all duration-150 shrink-0"
                          style={{
                            background: isExpanded ? 'rgba(251,191,36,0.1)' : 'rgba(255,255,255,0.04)',
                            border: isExpanded ? '1px solid rgba(251,191,36,0.3)' : '1px solid rgba(255,255,255,0.07)',
                            color: isExpanded ? '#fbbf24' : 'var(--lo)',
                          }}
                          onMouseEnter={(e) => {
                            if (!isExpanded) {
                              e.currentTarget.style.color = '#fbbf24'
                              e.currentTarget.style.borderColor = 'rgba(251,191,36,0.2)'
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isExpanded) {
                              e.currentTarget.style.color = 'var(--lo)'
                              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)'
                            }
                          }}
                        >
                          Accept Risk
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Description */}
              {evt.description && (
                <p className="text-xs leading-relaxed line-clamp-2 mb-1.5" style={{ color: 'var(--mid)' }}>
                  {evt.description}
                </p>
              )}

              {/* Meta: source · date */}
              <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono" style={{ color: 'var(--lo)' }}>
                <span>{evt.source}</span>
                <span style={{ color: 'var(--border)' }}>·</span>
                <span>
                  {formatApiDate(evt.detected_at, [], {
                    month: 'short', day: 'numeric', year: 'numeric',
                  })}
                </span>
              </div>
            </div>

            {/* Accept form — slides open */}
            {isExpanded && (
              <div
                style={{
                  background: 'var(--bg)',
                  borderTop: '1px solid var(--line)',
                  animation: 'fade-up 200ms cubic-bezier(0.16,1,0.3,1) both',
                }}
                className="p-3.5"
              >
                <p className="text-[10px] font-bold tracking-[0.12em] uppercase mb-3" style={{ color: '#fbbf24' }}>
                  Document Risk Acceptance
                </p>

                <textarea
                  value={form.justification}
                  onChange={(e) => setForm(evt.id, { justification: e.target.value })}
                  placeholder="Justification — why is this risk accepted? (required)"
                  rows={2}
                  maxLength={2000}
                  className="w-full rounded-lg px-3 py-2 text-xs resize-none mb-2"
                  style={{
                    background: 'var(--elevated)',
                    border: '1px solid var(--border)',
                    color: 'var(--hi)',
                    outline: 'none',
                  }}
                />

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-2">
                  <input
                    type="text"
                    value={form.reviewer}
                    onChange={(e) => setForm(evt.id, { reviewer: e.target.value })}
                    placeholder="Reviewer name (required)"
                    maxLength={100}
                    className="rounded-lg px-3 py-2 text-xs"
                    style={{
                      background: 'var(--elevated)',
                      border: '1px solid var(--border)',
                      color: 'var(--hi)',
                      outline: 'none',
                    }}
                  />
                  <div className="flex items-center gap-2">
                    <label className="text-[10px] shrink-0" style={{ color: 'var(--lo)' }}>Expires</label>
                    <input
                      type="date"
                      value={form.expires_at}
                      onChange={(e) => setForm(evt.id, { expires_at: e.target.value })}
                      min={new Date().toISOString().split('T')[0]}
                      className="flex-1 rounded-lg px-2 py-2 text-xs"
                      style={{
                        background: 'var(--elevated)',
                        border: '1px solid var(--border)',
                        color: 'var(--hi)',
                        outline: 'none',
                        colorScheme: 'dark',
                      }}
                    />
                  </div>
                </div>

                {acceptError && (
                  <p className="text-xs mb-2" style={{ color: 'var(--risk-high)' }}>{acceptError}</p>
                )}

                <div className="flex flex-col sm:flex-row gap-2">
                  <button
                    onClick={() => handleAccept(evt)}
                    disabled={submitting || !form.justification.trim() || !form.reviewer.trim()}
                    className="px-3 py-2 rounded-lg text-xs font-semibold transition-all duration-150 disabled:opacity-40"
                    style={{ background: '#fbbf24', color: '#000' }}
                    onMouseEnter={(e) => { if (!submitting) e.currentTarget.style.background = '#f59e0b' }}
                    onMouseLeave={(e) => e.currentTarget.style.background = '#fbbf24'}
                  >
                    {submitting ? 'Saving…' : 'Accept Risk'}
                  </button>
                  <button
                    onClick={() => { setAcceptError(''); setExpandedEvent(null) }}
                    className="px-3 py-2 rounded-lg text-xs transition-all duration-150"
                    style={{ color: 'var(--lo)', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}
                    onMouseEnter={(e) => e.currentTarget.style.color = 'var(--mid)'}
                    onMouseLeave={(e) => e.currentTarget.style.color = 'var(--lo)'}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
