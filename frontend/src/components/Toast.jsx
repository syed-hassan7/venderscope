import { useEffect } from 'react'

export default function Toast({ message, onDismiss, duration = 6000 }) {
  useEffect(() => {
    if (!duration) return
    const t = setTimeout(onDismiss, duration)
    return () => clearTimeout(t)
    // onDismiss intentionally excluded — parents pass a fresh closure each
    // render, and re-arming the timer on every unrelated parent re-render
    // (e.g. typing in a nearby search box) would make the toast never settle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [message, duration])

  if (!message) return null

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="fixed bottom-4 right-4 left-4 sm:left-auto z-[60] flex items-start gap-2.5 rounded-xl px-4 py-3 text-sm sm:max-w-sm"
      style={{
        background: 'var(--elevated)',
        border: '1px solid rgba(240,68,56,0.3)',
        boxShadow: '0 12px 40px rgba(0,0,0,0.7)',
        color: 'var(--hi)',
      }}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0, marginTop: '1px' }} aria-hidden="true">
        <circle cx="12" cy="12" r="9.5" stroke="var(--risk-high)" strokeWidth="1.5"/>
        <path d="M12 7.5v5.5M12 16.5v.01" stroke="var(--risk-high)" strokeWidth="1.8" strokeLinecap="round"/>
      </svg>
      <span className="flex-1">{message}</span>
      <button
        onClick={onDismiss}
        aria-label="Dismiss"
        className="shrink-0 transition-colors duration-150"
        style={{ color: 'var(--lo)' }}
        onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--hi)')}
        onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--lo)')}
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2 2L10 10M10 2L2 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  )
}
