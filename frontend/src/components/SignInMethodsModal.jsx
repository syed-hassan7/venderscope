import { useEffect, useState } from 'react'
import {
  listPasskeys,
  deletePasskey,
  googleUnlink,
  googleLinkStart,
  googleReauthStart,
  getMe,
  webauthnRegisterBegin,
  webauthnRegisterFinish,
  webauthnStepUpBegin,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { createPasskey, getPasskeyAssertion, isWebAuthnSupported } from '../auth/webauthn'

function formatWhen(iso, emptyLabel = 'Unknown') {
  if (!iso) return emptyLabel
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return iso
  return parsed.toLocaleString()
}

function canRemovePasskey(passkeys, factors) {
  if (passkeys.length > 1) return true
  return Boolean(factors?.google)
}

function canUnlinkGoogle(passkeys, factors) {
  if (!factors?.google) return false
  return passkeys.length > 0
}

export default function SignInMethodsModal({ onClose }) {
  const { user, refreshMe } = useAuth()
  const [passkeys, setPasskeys] = useState([])
  const [factors, setFactors] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [googleStepupReady, setGoogleStepupReady] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const stepup = params.get('stepup')
    const stepupError = params.get('stepup_error')
    if (stepup === '1' || stepupError === '1') {
      if (stepup === '1') setGoogleStepupReady(true)
      if (stepupError === '1') setError('Google re-authentication did not match your linked account.')
      params.delete('stepup')
      params.delete('stepup_error')
      const url = new URL(window.location.href)
      url.search = params.toString()
      window.history.replaceState({}, '', url.pathname + (url.search ? `?${url.search}` : ''))
    }
  }, [])

  const load = async () => {
    setError('')
    const [{ data: creds }, { data: me }] = await Promise.all([listPasskeys(), getMe()])
    setPasskeys(Array.isArray(creds) ? creds : [])
    setFactors(me.factors)
  }

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        await load()
      } catch (e) {
        if (!cancelled) setError(e.response?.data?.detail || 'Could not load sign-in methods.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  const afterChange = async () => {
    await load()
    await refreshMe?.()
  }

  const stepUpPayload = async () => {
    if (passkeys.length > 0) {
      const { data: options } = await webauthnStepUpBegin()
      return getPasskeyAssertion(options)
    }
    if (factors?.password) {
      if (!confirmPassword) throw new Error('Confirm with your password to continue.')
      return { password: confirmPassword }
    }
    return {}
  }

  const handleRemovePasskey = async (id) => {
    setBusy(id)
    setError('')
    try {
      await deletePasskey(id)
      await afterChange()
    } catch (e) {
      setError(e.response?.data?.detail || 'Could not remove passkey.')
    } finally {
      setBusy('')
    }
  }

  const handleUnlinkGoogle = async () => {
    setBusy('google')
    setError('')
    try {
      const extra = await stepUpPayload()
      await googleUnlink(extra)
      await afterChange()
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Could not disconnect Google.')
    } finally {
      setBusy('')
    }
  }

  const isGoogleOnly = passkeys.length === 0 && !factors?.password && Boolean(factors?.google)

  const handleAddPasskey = async () => {
    if (!isWebAuthnSupported()) {
      setError('Passkeys are not supported in this browser.')
      return
    }
    // Google-only accounts have no existing passkey/password to step up with —
    // prove current control of the linked Google account via a fresh OAuth round
    // trip instead, then resume here (googleStepupReady) after the redirect back.
    if (isGoogleOnly && !googleStepupReady) {
      setBusy('add')
      setError('')
      try {
        const { data } = await googleReauthStart()
        if (!data?.url) throw new Error('Could not start Google re-authentication.')
        window.location.href = data.url
      } catch (e) {
        setError(e.response?.data?.detail || e.message || 'Could not start Google re-authentication.')
        setBusy('')
      }
      return
    }
    setBusy('add')
    setError('')
    try {
      const email = user?.email
      if (!email) throw new Error('Sign in again to add a passkey.')
      const extra = await stepUpPayload()
      const { data: options } = await webauthnRegisterBegin({ email, ...extra })
      const payload = await createPasskey(options)
      await webauthnRegisterFinish(payload)
      setConfirmPassword('')
      setGoogleStepupReady(false)
      await afterChange()
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Could not add passkey.')
    } finally {
      setBusy('')
    }
  }

  const handleLinkGoogle = async () => {
    setBusy('link')
    setError('')
    try {
      const extra = await stepUpPayload()
      const { data } = await googleLinkStart(extra)
      if (!data?.url) throw new Error('Could not start Google linking.')
      window.location.href = data.url
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Could not link Google.')
      setBusy('')
    }
  }

  const removePasskeyOk = canRemovePasskey(passkeys, factors)
  const unlinkOk = canUnlinkGoogle(passkeys, factors)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="signin-methods-title"
        className="w-full max-w-md rounded-2xl p-4 sm:p-6 max-h-[calc(100dvh-2rem)] overflow-y-auto"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)', boxShadow: '0 24px 64px rgba(0,0,0,0.8)' }}
      >
        <h2 id="signin-methods-title" className="font-bold text-base mb-1" style={{ color: 'var(--hi)' }}>
          Sign-in methods
        </h2>
        <p className="text-sm mb-4" style={{ color: 'var(--mid)' }}>
          Remove a passkey or disconnect Google here. Adding a passkey or linking Google requires a passkey or password confirmation. Recovery codes and leftover password hashes cannot drop your last passkey. You cannot drop the last way to sign in — delete the account instead if you want everything gone.
        </p>

        {loading ? (
          <p className="text-sm mb-4" style={{ color: 'var(--lo)' }}>Loading…</p>
        ) : (
          <>
            <section className="mb-5">
              <div className="flex items-center justify-between gap-3 mb-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--lo)' }}>
                  Passkeys
                </h3>
                <button
                  type="button"
                  onClick={handleAddPasskey}
                  disabled={Boolean(busy)}
                  className="text-xs font-medium"
                  style={{ background: 'none', border: 'none', padding: 0, color: 'var(--accent-l)', cursor: busy ? 'not-allowed' : 'pointer' }}
                >
                  {busy === 'add'
                    ? (isGoogleOnly && !googleStepupReady ? 'Redirecting to Google…' : 'Waiting for device…')
                    : (isGoogleOnly && googleStepupReady ? 'Google verified — finish adding passkey' : 'Add passkey')}
                </button>
              </div>
              {passkeys.length === 0 ? (
                <p className="text-sm" style={{ color: 'var(--lo)' }}>No passkeys on this account.</p>
              ) : (
                <ul className="space-y-2">
                  {passkeys.map((cred) => (
                    <li
                      key={cred.id}
                      className="rounded-xl p-3 flex items-start justify-between gap-3"
                      style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
                    >
                      <div>
                        <p className="text-sm font-medium" style={{ color: 'var(--hi)' }}>
                          {cred.device_label || 'Passkey'}
                        </p>
                        <p className="text-xs mt-1" style={{ color: 'var(--lo)' }}>
                          Added {formatWhen(cred.created_at)}
                          {cred.last_used_at ? ` · Last used ${formatWhen(cred.last_used_at)}` : ' · Never used'}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemovePasskey(cred.id)}
                        disabled={!removePasskeyOk || Boolean(busy)}
                        className="text-xs font-medium shrink-0"
                        title={removePasskeyOk ? 'Remove this passkey' : 'Cannot remove last sign-in method'}
                        style={{
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          color: removePasskeyOk ? 'var(--risk-high)' : 'var(--lo)',
                          cursor: removePasskeyOk && !busy ? 'pointer' : 'not-allowed',
                          opacity: removePasskeyOk ? 1 : 0.5,
                        }}
                      >
                        {busy === cred.id ? 'Removing…' : 'Remove'}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="mb-5">
              <h3 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--lo)' }}>
                Google
              </h3>
              <div
                className="rounded-xl p-3 flex items-start justify-between gap-3"
                style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
              >
                <p className="text-sm" style={{ color: 'var(--hi)' }}>
                  {factors?.google ? 'Connected' : 'Not connected'}
                </p>
                {factors?.google ? (
                  <button
                    type="button"
                    onClick={handleUnlinkGoogle}
                    disabled={!unlinkOk || Boolean(busy)}
                    className="text-xs font-medium shrink-0"
                    title={unlinkOk ? 'Disconnect Google' : 'Cannot remove last sign-in method'}
                    style={{
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      color: unlinkOk ? 'var(--risk-high)' : 'var(--lo)',
                      cursor: unlinkOk && !busy ? 'pointer' : 'not-allowed',
                      opacity: unlinkOk ? 1 : 0.5,
                    }}
                  >
                    {busy === 'google' ? 'Disconnecting…' : 'Disconnect'}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleLinkGoogle}
                    className="text-xs font-medium shrink-0"
                    style={{ background: 'none', border: 'none', padding: 0, color: 'var(--accent-l)', cursor: 'pointer' }}
                  >
                    Link Google
                  </button>
                )}
              </div>
            </section>

            {factors?.password ? (
              <div className="mb-5">
                <label className="text-xs font-semibold uppercase tracking-wider mb-2 block" style={{ color: 'var(--lo)' }}>
                  Confirm password
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="current-password"
                  placeholder="Needed to add a passkey or link Google"
                  className="w-full rounded-xl px-3 py-2 text-sm"
                  style={{ background: 'var(--input)', border: '1px solid var(--border)', color: 'var(--hi)' }}
                />
              </div>
            ) : null}
          </>
        )}

        {error && <p className="text-xs mb-3" style={{ color: '#f87171' }}>{error}</p>}

        <button
          type="button"
          onClick={onClose}
          className="w-full py-2.5 rounded-xl text-sm font-medium"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', color: 'var(--mid)' }}
        >
          Close
        </button>
      </div>
    </div>
  )
}
