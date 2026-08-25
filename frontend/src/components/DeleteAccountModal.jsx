import { useState, useEffect } from 'react'
import {
  deleteAccount,
  webauthnStepUpBegin,
  getMe,
  clearAccessToken,
} from '../api/client'
import { getPasskeyAssertion } from '../auth/webauthn'

export default function DeleteAccountModal({ onClose }) {
  const [step, setStep] = useState(1)
  const [input, setInput] = useState('')
  const [password, setPassword] = useState('')
  const [recoveryCode, setRecoveryCode] = useState('')
  const [factors, setFactors] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getMe().then(({ data }) => setFactors(data.factors)).catch(() => {})
  }, [])

  const confirmed = input === 'DELETE'
  const usePassword = factors?.password
  const useRecovery = !usePassword && (factors?.recovery_codes_remaining > 0)
  const usePasskey = !usePassword && !useRecovery && (factors?.passkey_count > 0)

  const handleClose = () => {
    setInput('')
    setPassword('')
    setRecoveryCode('')
    setError('')
    onClose()
  }

  const buildDeletePayload = async () => {
    if (usePassword) {
      return { method: 'password', password }
    }
    if (useRecovery) {
      return { method: 'recovery', recovery_code: recoveryCode }
    }
    if (usePasskey) {
      const { data: options } = await webauthnStepUpBegin()
      const payload = await getPasskeyAssertion(options)
      return {
        method: 'webauthn',
        challenge_id: payload.challenge_id,
        credential: payload.credential,
      }
    }
    throw new Error('No verification method available')
  }

  const handleDelete = async () => {
    if (!confirmed) return
    setLoading(true)
    setError('')
    try {
      const body = await buildDeletePayload()
      await deleteAccount(body)
      clearAccessToken()
      window.location.href = '/login?deleted=1'
    } catch (e) {
      if (e.response?.status === 401) {
        setError('Verification failed')
      } else {
        setError(e.response?.data?.detail || e.message || 'Something went wrong. Please try again.')
      }
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
        {step === 1 ? (
          <>
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
                <h2 className="font-bold text-base" style={{ color: 'var(--hi)' }}>Delete Account</h2>
                <p className="text-xs mt-0.5" style={{ color: 'var(--lo)' }}>This action is permanent and cannot be undone.</p>
              </div>
            </div>

            <div
              className="rounded-xl p-4 mb-5 text-sm"
              style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)', color: '#fca5a5' }}
            >
              <p className="font-semibold mb-2">Everything will be permanently deleted:</p>
              <ul className="space-y-1 text-xs" style={{ color: '#f87171' }}>
                <li>· Your account and login credentials</li>
                <li>· All vendors you have added</li>
                <li>· All risk events, scores, and scan history</li>
                <li>· All compliance data associated with your vendors</li>
              </ul>
            </div>

            <p className="text-sm mb-5" style={{ color: 'var(--mid)' }}>
              Your account, vendors, and related records are deleted. Passkeys and a linked Google account go with the user row. To drop one passkey or disconnect Google without closing the account, use Sign-in methods. Security audit rows for this account are removed. Failed-login events with no user id may remain for the audit retention window. See our{' '}
              <a href="/privacy" target="_blank" style={{ color: '#8b5cf6', textDecoration: 'underline' }}>Privacy Policy</a>.
            </p>

            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={handleClose}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-all"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  color: 'var(--mid)',
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => setStep(2)}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all"
                style={{ background: '#dc2626', color: '#fff' }}
              >
                Continue →
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="mb-5">
              <h2 className="font-bold text-base mb-1" style={{ color: 'var(--hi)' }}>Confirm Deletion</h2>
              <p className="text-sm" style={{ color: 'var(--mid)' }}>
                Type <span style={{ color: 'var(--risk-high)', fontWeight: 700, fontFamily: 'monospace' }}>DELETE</span> to confirm.
              </p>
            </div>

            <input
              type="text"
              value={input}
              onChange={(e) => { setInput(e.target.value); setError('') }}
              placeholder="Type DELETE to confirm"
              autoFocus
              className="w-full px-4 py-3 rounded-xl text-sm mb-3 outline-none transition-all"
              style={{
                background: 'var(--elevated)',
                border: `1px solid ${confirmed ? 'rgba(240,68,56,0.5)' : 'var(--border)'}`,
                color: confirmed ? 'var(--risk-high)' : 'var(--hi)',
                fontFamily: 'monospace',
                letterSpacing: '0.05em',
              }}
            />

            {usePassword && (
              <>
                <label className="block text-xs mb-1" style={{ color: 'var(--lo)' }}>Enter your password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError('') }}
                  placeholder="Your account password"
                  className="w-full px-4 py-3 rounded-xl text-sm mb-4 outline-none"
                  style={{ background: 'var(--elevated)', border: '1px solid var(--border)', color: '#e2e8f0' }}
                />
              </>
            )}

            {useRecovery && (
              <>
                <label className="block text-xs mb-1" style={{ color: 'var(--lo)' }}>Enter a recovery code</label>
                <input
                  type="text"
                  value={recoveryCode}
                  onChange={(e) => { setRecoveryCode(e.target.value); setError('') }}
                  placeholder="XXXX-XXXX-XXXX-XXXX"
                  className="w-full px-4 py-3 rounded-xl text-sm mb-4 outline-none"
                  style={{ background: 'var(--elevated)', border: '1px solid var(--border)', color: '#e2e8f0' }}
                />
              </>
            )}

            {usePasskey && (
              <p className="text-xs mb-4" style={{ color: 'var(--lo)' }}>
                Passkey verification runs when you confirm deletion.
              </p>
            )}

            {error && (
              <p className="text-xs mb-3" style={{ color: '#f87171' }}>{error}</p>
            )}

            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => { setStep(1); setInput(''); setPassword(''); setRecoveryCode(''); setError('') }}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--mid)' }}
              >
                ← Back
              </button>
              <button
                onClick={handleDelete}
                disabled={!confirmed || loading}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-30"
                style={{ background: '#dc2626', color: '#fff' }}
              >
                {loading ? 'Deleting…' : 'Delete My Account'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
