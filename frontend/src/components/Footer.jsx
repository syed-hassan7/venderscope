import { useState } from 'react'
import { Link } from 'react-router-dom'
import DeleteAccountModal from './DeleteAccountModal'
import RecoveryCodesModal from './RecoveryCodesModal'
import SignInMethodsModal from './SignInMethodsModal'
import VSLogo from './VSLogo'
import { CONSENT_SETTINGS_EVENT } from '../consent/siteConsent'

const FooterLink = ({ to, children, external }) =>
  external ? (
    <a
      href={to}
      target="_blank"
      rel="noreferrer"
      className="transition-colors duration-150"
      style={{ color: 'var(--lo)' }}
      onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent-l)'}
      onMouseLeave={(e) => e.currentTarget.style.color = 'var(--lo)'}
    >{children}</a>
  ) : (
    <Link
      to={to}
      className="transition-colors duration-150"
      style={{ color: 'var(--lo)' }}
      onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent-l)'}
      onMouseLeave={(e) => e.currentTarget.style.color = 'var(--lo)'}
    >{children}</Link>
  )

export default function Footer() {
  const [showDelete, setShowDelete] = useState(false)
  const [showRecovery, setShowRecovery] = useState(false)
  const [showSignIn, setShowSignIn] = useState(false)
  const openCookieSettings = () => {
    window.dispatchEvent(new Event(CONSENT_SETTINGS_EVENT))
  }

  return (
    <>
      <footer style={{ borderTop: '1px solid var(--line)' }} className="w-full">
        <div className="max-w-7xl mx-auto page-safe-x px-4 sm:px-6 py-6 sm:py-8">

          {/* Main row */}
          <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center sm:justify-between gap-4">
            {/* Brand */}
            <div className="flex justify-center sm:justify-start">
              <VSLogo height={22} />
            </div>

            {/* Navigation links */}
            <nav className="flex flex-wrap items-center justify-center sm:justify-start gap-4 sm:gap-5 text-xs">
              <FooterLink to="/privacy">Privacy Policy</FooterLink>
              <FooterLink to="/terms">Terms of Service</FooterLink>
              <FooterLink to="/security">Security</FooterLink>
              <FooterLink to="https://github.com/darkyzowo/venderscope" external>GitHub</FooterLink>
              <button
                onClick={openCookieSettings}
                className="transition-colors duration-150"
                style={{ background: 'none', border: 'none', padding: 0, color: 'var(--lo)', cursor: 'pointer' }}
                onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent-l)'}
                onMouseLeave={(e) => e.currentTarget.style.color = 'var(--lo)'}
              >
                Cookie Settings
              </button>
            </nav>
          </div>

          {/* Bottom row */}
          <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center sm:justify-between gap-3 mt-4 text-center sm:text-left">
            <p className="text-xs leading-relaxed" style={{ color: 'var(--lo)' }}>
              © {new Date().getFullYear()} VenderScope · Continuous Passive Vendor Risk Intelligence · MIT Licence
              <span className="block sm:inline sm:before:content-['·'] sm:before:mx-2">
                New accounts: Google, then a passkey. Password sign-in is closed.
              </span>
            </p>

            <div className="flex flex-col sm:flex-row items-center gap-3 sm:gap-5">
              <button
                onClick={() => setShowSignIn(true)}
                className="text-xs transition-colors duration-150"
                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--lo)' }}
                onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent-l)'}
                onMouseLeave={(e) => e.currentTarget.style.color = 'var(--lo)'}
              >
                Sign-in methods
              </button>
              <button
                onClick={() => setShowRecovery(true)}
                className="text-xs transition-colors duration-150"
                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--lo)' }}
                onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent-l)'}
                onMouseLeave={(e) => e.currentTarget.style.color = 'var(--lo)'}
              >
                Recovery codes
              </button>
              <button
                onClick={() => setShowDelete(true)}
                className="text-xs transition-colors duration-150"
                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--lo)' }}
                onMouseEnter={(e) => e.currentTarget.style.color = 'var(--risk-high)'}
                onMouseLeave={(e) => e.currentTarget.style.color = 'var(--lo)'}
              >
                Delete Account
              </button>
            </div>
          </div>
        </div>
      </footer>

      {showDelete && <DeleteAccountModal onClose={() => setShowDelete(false)} />}
      {showRecovery && <RecoveryCodesModal onClose={() => setShowRecovery(false)} />}
      {showSignIn && <SignInMethodsModal onClose={() => setShowSignIn(false)} />}
    </>
  )
}
