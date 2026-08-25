import { useState, useEffect } from 'react'

export default function AddVendorModal({ onAdd, onClose }) {
  const [form, setForm] = useState({ name: '', domain: '', company_number: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [visible, setVisible] = useState(false)

  // Animate in on mount
  useEffect(() => {
    requestAnimationFrame(() => setVisible(true))
  }, [])

  const close = () => {
    setVisible(false)
    setTimeout(onClose, 200)
  }

  const submit = async () => {
    if (!form.name || !form.domain) return
    setLoading(true)
    setError('')
    try {
      await onAdd({
        name: form.name,
        domain: form.domain,
        company_number: form.company_number || null,
      })
      setLoading(false)
      close()
    } catch (e) {
      setLoading(false)
      if (e.response?.status === 400) {
        setError('This vendor domain already exists.')
      } else {
        setError('Something went wrong. Please try again.')
      }
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter') submit()
    if (e.key === 'Escape') close()
  }

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50 p-4 sm:p-6"
      style={{
        background: visible ? 'rgba(0,0,0,0.75)' : 'rgba(0,0,0,0)',
        backdropFilter: visible ? 'blur(4px)' : 'blur(0px)',
        transition: 'background 200ms ease, backdrop-filter 200ms ease',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) close() }}
    >
      <div
        className="w-full max-w-md rounded-2xl max-h-[calc(100dvh-2rem)] overflow-y-auto"
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          boxShadow: '0 24px 64px rgba(0,0,0,0.8), 0 0 0 1px rgba(139,92,246,0.1)',
          transform: visible ? 'scale(1) translateY(0)' : 'scale(0.96) translateY(8px)',
          opacity: visible ? 1 : 0,
          transition: 'transform 200ms cubic-bezier(0.16,1,0.3,1), opacity 200ms ease',
        }}
        onKeyDown={handleKey}
      >
        <div className="p-4 sm:p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-bold" style={{ color: 'var(--hi)' }}>
              Add Vendor
            </h2>
            <button
              onClick={close}
              className="w-7 h-7 rounded-lg flex items-center justify-center transition-colors duration-150"
              style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--lo)' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--mid)' }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--lo)' }}
              aria-label="Close"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2 2L10 10M10 2L2 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>

          {/* Fields */}
          <div className="space-y-4">
            <Field
              label="Vendor Name"
              required
              placeholder="e.g. Salesforce"
              value={form.name}
              onChange={(v) => setForm({ ...form, name: v })}
            />
            <Field
              label="Domain"
              required
              placeholder="e.g. salesforce.com"
              value={form.domain}
              onChange={(v) => setForm({ ...form, domain: v })}
            />
            <Field
              label="Companies House Number"
              hint="UK only, optional"
              placeholder="e.g. 12345678"
              value={form.company_number}
              onChange={(v) => setForm({ ...form, company_number: v })}
            />
          </div>

          {/* Error */}
          {error && (
            <div
              className="mt-4 rounded-lg px-4 py-2.5 text-sm flex items-start gap-2"
              style={{
                background: 'rgba(239,68,68,0.08)',
                border: '1px solid rgba(239,68,68,0.2)',
                color: '#f87171',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="mt-0.5 shrink-0">
                <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.2"/>
                <path d="M7 4v3.5M7 9.5v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 mt-6">
            <button
              onClick={close}
              className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'var(--mid)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
                e.currentTarget.style.color = 'var(--hi)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.04)'
                e.currentTarget.style.color = 'var(--mid)'
              }}
            >
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={loading || !form.name || !form.domain}
              className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all duration-150 disabled:opacity-40"
              style={{ background: '#8b5cf6', color: '#fff' }}
              onMouseEnter={(e) => {
                if (!loading && form.name && form.domain)
                  e.currentTarget.style.background = '#7c3aed'
              }}
              onMouseLeave={(e) => { e.currentTarget.style.background = '#8b5cf6' }}
            >
              {loading ? (
                <span className="inline-flex items-center justify-center gap-2">
                  <svg className="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4 31.4" strokeLinecap="round"/>
                  </svg>
                  Adding…
                </span>
              ) : 'Add Vendor'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function Field({ label, hint, required, placeholder, value, onChange }) {
  const [focused, setFocused] = useState(false)

  return (
    <div>
      <label className="text-xs font-medium mb-1.5 flex items-center gap-1.5" style={{ color: 'var(--mid)' }}>
        {label}
        {required && <span style={{ color: '#8b5cf6' }}>*</span>}
        {hint && <span style={{ color: 'var(--lo)', fontWeight: 400 }}>({hint})</span>}
      </label>
      <input
        className="w-full rounded-xl px-4 py-2.5 text-sm transition-all duration-150 outline-none"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          background: 'rgba(255,255,255,0.04)',
          border: `1px solid ${focused ? 'rgba(139,92,246,0.5)' : 'var(--line)'}`,
          color: 'var(--hi)',
          boxShadow: focused ? '0 0 0 3px rgba(139,92,246,0.1)' : 'none',
        }}
      />
    </div>
  )
}
