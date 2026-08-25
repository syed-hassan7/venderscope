import { useState } from 'react'
import { recoveryRegenerate, webauthnStepUpBegin } from '../api/client'
import { getPasskeyAssertion } from '../auth/webauthn'

export default function RecoveryCodesModal({ onClose }) {
  const [codes, setCodes] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const generate = async () => {
    setLoading(true)
    setError('')
    try {
      const { data: options } = await webauthnStepUpBegin()
      const assertion = await getPasskeyAssertion(options)
      const { data } = await recoveryRegenerate({
        challenge_id: assertion.challenge_id,
        credential: assertion.credential,
      })
      setCodes(data.recovery_codes || [])
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Could not generate codes.')
    } finally {
      setLoading(false)
    }
  }

  const copyCodes = () => {
    navigator.clipboard?.writeText(codes.join('\n'))
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="w-full max-w-md rounded-2xl p-4 sm:p-6"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)', boxShadow: '0 24px 64px rgba(0,0,0,0.8)' }}
      >
        <h2 className="font-bold text-base mb-2" style={{ color: 'var(--hi)' }}>Recovery codes</h2>
        <p className="text-sm mb-4" style={{ color: 'var(--mid)' }}>
          Generating a new set invalidates unused codes and requires your passkey. Save them — shown once.
        </p>

        {codes.length === 0 ? (
          <button
            type="button"
            onClick={generate}
            disabled={loading}
            className="w-full py-2.5 rounded-xl text-sm font-semibold mb-3"
            style={{ background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)', color: '#fff' }}
          >
            {loading ? 'Verify passkey…' : 'Generate new codes'}
          </button>
        ) : (
          <>
            <div
              className="rounded-xl p-3 mb-3 text-xs"
              style={{ background: 'var(--elevated)', border: '1px solid var(--border)', fontFamily: 'monospace', color: 'var(--hi)', lineHeight: 1.8 }}
            >
              {codes.map((code) => <div key={code}>{code}</div>)}
            </div>
            <button
              type="button"
              onClick={copyCodes}
              className="w-full py-2.5 rounded-xl text-sm font-medium mb-3"
              style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', color: 'var(--mid)' }}
            >
              Copy codes
            </button>
          </>
        )}

        {error && <p className="text-xs mb-3" style={{ color: '#f87171' }}>{error}</p>}

        <button
          type="button"
          onClick={onClose}
          className="w-full py-2.5 rounded-xl text-sm"
          style={{ background: 'none', border: '1px solid var(--border)', color: 'var(--mid)' }}
        >
          Close
        </button>
      </div>
    </div>
  )
}
