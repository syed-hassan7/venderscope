import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import VendorAvatar from './VendorAvatar'
import { riskLevel } from './RiskBadge'
import { formatApiDateTime, parseApiDate } from '../utils/datetime'

const RISK_CONFIG = {
  high: {
    color: 'var(--risk-high)',
    border: 'rgba(240,68,56,0.25)',
    hoverBorder: 'rgba(240,68,56,0.45)',
    hoverGlow: 'rgba(240,68,56,0.08)',
  },
  medium: {
    color: 'var(--risk-medium)',
    border: 'rgba(245,158,11,0.2)',
    hoverBorder: 'rgba(245,158,11,0.4)',
    hoverGlow: 'rgba(245,158,11,0.07)',
  },
  low: {
    color: 'var(--risk-low)',
    border: 'rgba(16,185,129,0.18)',
    hoverBorder: 'rgba(16,185,129,0.38)',
    hoverGlow: 'rgba(16,185,129,0.06)',
  },
}
const riskConfig = (s) => RISK_CONFIG[riskLevel(s)]

const SENSITIVITY_BADGES = {
  none:      { label: 'No Access',  color: 'var(--lo)',          bg: 'rgba(138,140,152,0.1)',   border: 'rgba(138,140,152,0.2)' },
  pii:       { label: 'PII',        color: 'var(--risk-medium)', bg: 'var(--risk-medium-tint)', border: 'rgba(245,158,11,0.25)' },
  financial: { label: 'Financial',  color: 'var(--risk-high)',   bg: 'var(--risk-high-tint)',   border: 'rgba(240,68,56,0.25)'  },
  auth:      { label: 'Auth/SSO',   color: 'var(--risk-high)',   bg: 'var(--risk-high-tint)',   border: 'rgba(240,68,56,0.25)'  },
  health:    { label: 'Health',     color: '#ec4899',            bg: 'rgba(236,72,153,0.1)',    border: 'rgba(236,72,153,0.25)' },
  critical:  { label: 'Critical',   color: 'var(--risk-crit)',   bg: 'rgba(244,63,94,0.12)',    border: 'rgba(244,63,94,0.3)'   },
}

export default function VendorCard({ vendor, onDelete, onScan, scanning }) {
  const nav = useNavigate()
  const [nowTs] = useState(() => Date.now())
  const displayScore = vendor.effective_score ?? vendor.risk_score
  const cfg = riskConfig(displayScore)
  const domain = vendor.domain.split('?')[0].split('/')[0]
  const badge = vendor.data_sensitivity && vendor.data_sensitivity !== 'standard'
    ? SENSITIVITY_BADGES[vendor.data_sensitivity]
    : null
  const reviewStatus = (() => {
    if (!vendor.review_interval_days) return { text: 'Review schedule not set', color: 'var(--lo)' }
    if (!vendor.last_reviewed_at) {
      return { text: 'Never reviewed', color: '#fbbf24' }
    }
    const lastReviewed = parseApiDate(vendor.last_reviewed_at)
    const dueAt = lastReviewed ? lastReviewed.getTime() + vendor.review_interval_days * 86400000 : null
    if (!dueAt) {
      return { text: 'Never reviewed', color: '#fbbf24' }
    }
    const diffDays = Math.round((dueAt - nowTs) / 86400000)
    if (diffDays < 0) {
      return { text: `Review overdue by ${Math.abs(diffDays)}d`, color: '#fbbf24' }
    }
    return {
      text: `Review: ${new Date(dueAt).toLocaleDateString([], { month: 'short', day: 'numeric' })}`,
      color: 'var(--lo)',
    }
  })()

  return (
    <div
      className="rounded-card cursor-pointer h-full"
      style={{
        background: 'var(--surface)',
        border: `1px solid ${cfg.border}`,
        boxShadow: '0 2px 12px rgba(0,0,0,0.35)',
        transition: 'transform 200ms cubic-bezier(0.16,1,0.3,1), box-shadow 200ms ease, border-color 200ms ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = cfg.hoverBorder
        e.currentTarget.style.boxShadow = `0 8px 28px ${cfg.hoverGlow}, 0 2px 12px rgba(0,0,0,0.45)`
        e.currentTarget.style.transform = 'translateY(-2px)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = cfg.border
        e.currentTarget.style.boxShadow = '0 2px 12px rgba(0,0,0,0.35)'
        e.currentTarget.style.transform = 'translateY(0)'
      }}
      onMouseDown={(e) => { e.currentTarget.style.transform = 'translateY(0) scale(0.98)' }}
      onMouseUp={(e) => { e.currentTarget.style.transform = 'translateY(-2px) scale(1)' }}
      onClick={() => nav(`/vendor/${vendor.id}`)}
    >
      <div className="p-4 sm:p-5 h-full flex flex-col">
        {/* Header: avatar + name + score */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <VendorAvatar name={vendor.name} domain={vendor.domain} logoUrl={vendor.logo_url} size={36} />
            <div className="min-w-0">
              <h3 className="font-semibold text-[15px] leading-tight truncate" style={{ color: 'var(--hi)' }}>
                {vendor.name}
              </h3>
              <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--lo)' }}>
                {domain}
              </p>
            </div>
          </div>

          <div className="text-right shrink-0 ml-1 sm:ml-3">
            <div className="text-2xl sm:text-3xl font-bold tabular-nums leading-none" style={{ color: cfg.color }}>
              {displayScore}
            </div>
            {vendor.score_delta != null && vendor.score_delta !== 0 && (
              <div
                className="text-[10px] font-semibold tabular-nums mt-1"
                style={{ color: vendor.score_delta > 0 ? 'var(--risk-high)' : 'var(--risk-low)' }}
              >
                {vendor.score_delta > 0 ? `+${vendor.score_delta} ↑` : `${vendor.score_delta} ↓`}
              </div>
            )}
          </div>
        </div>

        {/* Score progress bar */}
        <div className="h-[3px] rounded-full mb-3" style={{ background: 'var(--line)' }}>
          <div
            className="h-[3px] rounded-full transition-all duration-500"
            style={{ width: `${Math.min(displayScore, 100)}%`, background: cfg.color }}
          />
        </div>

        {/* Timestamp + sensitivity badge */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5 mb-2">
          <p className="text-[11px]" style={{ color: 'var(--lo)' }}>
            {vendor.last_scanned
              ? formatApiDateTime(vendor.last_scanned, [], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
              : 'Never scanned'}
          </p>
          {badge && (
            <span
              className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full shrink-0"
              style={{ color: badge.color, background: badge.bg, border: `1px solid ${badge.border}` }}
            >
              {badge.label}
            </span>
          )}
        </div>

        {/* Review status */}
        <div className="min-h-[20px] mb-3">
          <p className="text-[10px]" style={{ color: reviewStatus.color }}>
            ⏱ {reviewStatus.text}
          </p>
        </div>

        {/* Actions */}
        <div className="flex gap-2 mt-auto" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => onScan(vendor.id)}
            disabled={scanning}
            className="flex-1 min-h-10 py-2 rounded-ctrl text-xs font-medium transition-colors duration-150 disabled:opacity-40"
            style={{ background: 'var(--accent-bg)', color: 'var(--accent-l)', border: '1px solid rgba(139,92,246,0.2)' }}
            onMouseEnter={(e) => { if (!scanning) e.currentTarget.style.background = 'rgba(139,92,246,0.18)' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--accent-bg)' }}
          >
            {scanning ? (
              <span className="inline-flex items-center justify-center gap-1.5">
                <svg className="animate-spin" width="10" height="10" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4 31.4" strokeLinecap="round"/>
                </svg>
                Scanning…
              </span>
            ) : 'Scan Now'}
          </button>

          <button
            onClick={() => onDelete(vendor.id)}
            className="min-h-10 py-2 px-3.5 rounded-ctrl text-xs transition-colors duration-150"
            style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--lo)', border: '1px solid var(--line)' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--risk-high-tint)'
              e.currentTarget.style.color = 'var(--risk-high)'
              e.currentTarget.style.borderColor = 'rgba(240,68,56,0.2)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.04)'
              e.currentTarget.style.color = 'var(--lo)'
              e.currentTarget.style.borderColor = 'var(--line)'
            }}
            aria-label="Remove vendor"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
              <path d="M10 11v6" /><path d="M14 11v6" /><path d="M9 6V4h6v2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
