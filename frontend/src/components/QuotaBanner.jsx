import { useState } from 'react'

export default function QuotaBanner() {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null

  return (
    <div
      className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs"
      style={{
        background: 'rgba(139,92,246,0.06)',
        border: '1px solid rgba(139,92,246,0.15)',
        overflow: 'hidden',
        width: '100%',
      }}
    >
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ flexShrink: 0, color: 'var(--accent-l)' }}>
        <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.2" />
        <path d="M6 5v3.5M6 3.5v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>

      <span style={{ color: 'var(--mid)' }}>
        Compliance web search uses Tavily —{' '}
        <span style={{ color: 'var(--accent-l)', fontWeight: 500 }}>1,000 credits/month</span>
        <span className="hidden sm:inline" style={{ color: 'var(--lo)' }}>
          {' '}· ~166 full scans · resets 1st of month UTC
        </span>
      </span>

      <button
        onClick={() => setDismissed(true)}
        className="ml-auto shrink-0 transition-colors duration-150"
        style={{ color: 'var(--lo)' }}
        onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--mid)')}
        onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--lo)')}
        aria-label="Dismiss"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2 2L10 10M10 2L2 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  )
}
