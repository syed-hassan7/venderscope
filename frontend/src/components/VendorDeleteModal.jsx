import { useState } from 'react'

export default function VendorDeleteModal({ vendor, onConfirm, onClose }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleClose = () => { if (!loading) onClose() }

  const handleConfirm = async () => {
    setLoading(true)
    setError('')
    try {
      await onConfirm()
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Failed to remove vendor. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) handleClose() }}
    >
      <div
        className="w-full max-w-md rounded-2xl p-4 sm:p-6 max-h-[calc(100dvh-2rem)] overflow-y-auto"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)', boxShadow: '0 24px 64px rgba(0,0,0,0.8)' }}
      >
        <div className="flex items-center gap-3 mb-5">
          <div
            className="flex items-center justify-center rounded-xl w-10 h-10 shrink-0"
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)' }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
                stroke="var(--risk-high)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <line x1="12" y1="9" x2="12" y2="13" stroke="var(--risk-high)" strokeWidth="2" strokeLinecap="round"/>
              <line x1="12" y1="17" x2="12.01" y2="17" stroke="var(--risk-high)" strokeWidth="2.5" strokeLinecap="round"/>
            </svg>
          </div>
          <div>
            <h2 className="font-bold text-base" style={{ color: 'var(--hi)' }}>Remove Vendor</h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--lo)' }}>This action is permanent and cannot be undone.</p>
          </div>
        </div>

        <div
          className="rounded-xl p-4 mb-5 text-sm"
          style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)', color: '#fca5a5' }}
        >
          <p className="font-semibold mb-2">
            Removing <span style={{ color: 'var(--hi)' }}>{vendor?.name}</span> permanently deletes:
          </p>
          <ul className="space-y-1 text-xs" style={{ color: '#f87171' }}>
            <li>· Full scan history and risk score timeline</li>
            <li>· All risk events, including accepted-risk records and their audit trail</li>
            <li>· Analyst notes and evidence log for this vendor</li>
            <li>· Discovered compliance data (certs, security contacts, trust centre)</li>
          </ul>
        </div>

        {error && (
          <p className="text-xs mb-4" style={{ color: '#f87171' }}>{error}</p>
        )}

        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={handleClose}
            disabled={loading}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-all disabled:opacity-40"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              color: 'var(--mid)',
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={loading}
            className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-60"
            style={{ background: '#dc2626', color: '#fff' }}
          >
            {loading ? 'Removing…' : 'Remove Vendor'}
          </button>
        </div>
      </div>
    </div>
  )
}
