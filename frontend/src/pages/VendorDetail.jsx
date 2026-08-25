import { useCallback, useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getVendors, getVendorEvents, getScoreHistory, scanVendor, exportPDF, setVendorContext, getNotes, addNote, deleteNote, updateReview, getAcceptances, createAcceptance, revokeAcceptance } from '../api/client'
import api from '../api/client'
import EventFeed from '../components/EventFeed'
import CompliancePanel from '../components/CompliancePanel'
import QuotaBanner from '../components/QuotaBanner'
import VendorAvatar from '../components/VendorAvatar'
import PageBackground from '../components/PageBackground'
import RiskBadge, { riskLevel } from '../components/RiskBadge'
import Toast from '../components/Toast'
import Tabs, { TabPanel } from '../components/Tabs'
import Select from '../components/Select'
import { formatApiDateTime, parseApiDate } from '../utils/datetime'

const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
const EVENTS_SHOWN = 10

const SENSITIVITY_OPTIONS = [
  { value: 'none',      label: 'No Data Access',          hint: '0.8×' },
  { value: 'standard',  label: 'Standard / Unknown',      hint: '1.0×' },
  { value: 'pii',       label: 'PII / Personal Data',     hint: '1.4×' },
  { value: 'financial', label: 'Financial / Payment',     hint: '1.6×' },
  { value: 'auth',      label: 'Authentication / SSO',    hint: '1.6×' },
  { value: 'health',    label: 'Health / Medical',        hint: '1.8×' },
  { value: 'critical',  label: 'Critical Infrastructure', hint: '2.0×' },
]

const parseEPSS = (desc) => {
  const m = desc?.match(/\[EPSS: ([\d.]+)%/)
  return m ? parseFloat(m[1]) : 0
}

const sortEvents = (evts) =>
  [...evts].sort((a, b) => {
    const d = (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4)
    return d !== 0 ? d : parseEPSS(b.description) - parseEPSS(a.description)
  })

const relativeTime = (iso) => {
  const parsed = parseApiDate(iso)
  if (!parsed) return '—'
  const diff = Date.now() - parsed.getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'Just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}

const formatScheduleStatus = (vendor) => {
  if (!vendor.review_interval_days) {
    return { text: 'No recurring review schedule configured yet.', tone: 'var(--lo)' }
  }

  const lastReviewed = parseApiDate(vendor.last_reviewed_at)
  const dueAt = lastReviewed
    ? new Date(lastReviewed.getTime() + vendor.review_interval_days * 86400000)
    : null
  const now = new Date()
  const daysOverdue = dueAt ? Math.floor((now - dueAt) / 86400000) : null

  if (!lastReviewed) {
    return { text: 'Schedule active, but this vendor has never been marked reviewed.', tone: '#fbbf24' }
  }
  if (daysOverdue > 0) {
    return { text: `Overdue by ${daysOverdue} day${daysOverdue !== 1 ? 's' : ''}.`, tone: '#fbbf24' }
  }
  return {
    text: `Next review due ${dueAt.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}.`,
    tone: 'var(--risk-low)',
  }
}

// Reusable panel wrapper
const Panel = ({ children, className = '', style: extraStyle }) => (
  <div
    className={`rounded-card p-4 sm:p-6 ${className}`}
    style={{
      background: 'var(--surface)',
      border: '1px solid var(--line)',
      ...extraStyle,
    }}
  >
    {children}
  </div>
)

const PanelTitle = ({ children, meta }) => (
  <h3 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--hi)' }}>
    {children}
    {meta && (
      <span className="text-xs font-normal" style={{ color: 'var(--lo)' }}>{meta}</span>
    )}
  </h3>
)

export default function VendorDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [vendor, setVendor] = useState(null)
  const [events, setEvents] = useState([])
  const [history, setHistory] = useState([])
  const [scanning, setScan] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [quotaExhausted, setQuotaEx] = useState(false)
  const [updatingContext, setUpdatingContext] = useState(false)
  const [notes, setNotes] = useState([])
  const [noteInput, setNoteInput] = useState('')
  const [addingNote, setAddingNote] = useState(false)
  const [updatingReview, setUpdatingReview] = useState(false)
  const [acceptances, setAcceptances] = useState([])
  const [loadError, setLoadError] = useState('')
  const [toastMessage, setToastMessage] = useState('')
  const [revokingIds, setRevokingIds] = useState(() => new Set())
  const [activeTab, setActiveTab] = useState('overview')

  const fetchData = useCallback(async () => {
    setLoadError('')
    const [vRes, eRes, hRes, nRes, aRes] = await Promise.all([
      getVendors(),
      getVendorEvents(id),
      getScoreHistory(id),
      getNotes(id),
      getAcceptances(id),
    ])
    const currentVendor = vRes.data.find((v) => v.id === id)
    if (!currentVendor) {
      throw new Error('Vendor not found')
    }
    setVendor(currentVendor)
    setEvents(sortEvents(eRes.data))
    setHistory(hRes.data)
    setNotes(nRes.data)
    setAcceptances(aRes.data)
  }, [id])

  useEffect(() => {
    setVendor(null)
    fetchData().catch((e) => {
      console.error('Vendor load failed:', e)
      setLoadError('Vendor not found or failed to load.')
    })
    api.get('/quota').then((r) => setQuotaEx(r.data.exhausted)).catch(() => {})
  }, [id, fetchData])

  const handleScan = async () => {
    setScan(true)
    try {
      await scanVendor(id)
    } catch (e) {
      setToastMessage(e.response?.data?.detail || "Scan failed — this vendor's risk data may be stale.")
    }
    finally {
      await fetchData()
      api.get('/quota').then((r) => setQuotaEx(r.data.exhausted)).catch(() => {})
      setScan(false)
    }
  }

  const handleContextChange = async (sensitivity) => {
    setUpdatingContext(true)
    try {
      await setVendorContext(id, sensitivity)
      await fetchData()
    } catch (e) {
      setToastMessage(e.response?.data?.detail || 'Failed to update data sensitivity. Please try again.')
    }
    finally { setUpdatingContext(false) }
  }

  const handleExportPDF = async () => {
    setExporting(true)
    try {
      const res = await exportPDF(vendor.id)
      const blob = new Blob([res.data], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `vendorscope_${vendor.name.replace(/\s+/g, '_').toLowerCase()}_report.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setToastMessage(e.response?.data?.detail || 'PDF export failed. Please try again.')
    }
    finally { setExporting(false) }
  }

  const handleAddNote = async () => {
    if (!noteInput.trim()) return
    setAddingNote(true)
    try {
      await addNote(id, noteInput.trim())
      setNoteInput('')
      const res = await getNotes(id)
      setNotes(res.data)
    } catch (e) {
      setToastMessage(e.response?.data?.detail || 'Failed to add note. Please try again.')
    }
    finally { setAddingNote(false) }
  }

  const handleDeleteNote = async (noteId) => {
    try {
      await deleteNote(id, noteId)
      setNotes((n) => n.filter((x) => x.id !== noteId))
    } catch (e) {
      setToastMessage(e.response?.data?.detail || 'Failed to delete note. Please try again.')
    }
  }

  const handleReviewUpdate = async (patch) => {
    setUpdatingReview(true)
    try {
      await updateReview(id, patch)
      await fetchData()
    } catch (e) {
      setToastMessage(e.response?.data?.detail || 'Failed to update review schedule. Please try again.')
    }
    finally { setUpdatingReview(false) }
  }

  const handleAccept = async (eventId, data) => {
    await createAcceptance(id, data)
    const res = await getAcceptances(id)
    setAcceptances(res.data)
  }

  const handleRevoke = async (accId) => {
    setRevokingIds((s) => new Set(s).add(accId))
    try {
      await revokeAcceptance(id, accId)
      setAcceptances((a) => a.filter((x) => x.id !== accId))
    } catch (e) {
      setToastMessage(e.response?.data?.detail || 'Failed to revoke risk acceptance. Please try again.')
    } finally {
      setRevokingIds((s) => { const n = new Set(s); n.delete(accId); return n })
    }
  }

  if (loadError)
    return (
      <div className="app-page-shell min-h-screen" style={{ background: 'var(--bg)' }}>
        <PageBackground />
        <div className="max-w-5xl mx-auto page-safe-x page-safe-y px-4 sm:px-6 py-8 sm:py-10" style={{ position: 'relative', zIndex: 1 }}>
          <button
            onClick={() => nav('/')}
            className="inline-flex items-center gap-1.5 text-sm mb-6 transition-colors duration-150"
            style={{ color: 'var(--lo)' }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M9 2L4 7L9 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Dashboard
          </button>

          <Panel className="animate-page">
            <PanelTitle>Vendor Unavailable</PanelTitle>
            <p className="text-sm" style={{ color: 'var(--mid)' }}>{loadError}</p>
          </Panel>
        </div>
      </div>
    )

  // Skeleton loading state — matches actual page layout
  if (!vendor)
    return (
      <div className="app-page-shell min-h-screen" style={{ background: 'var(--bg)' }}>
        <div className="max-w-5xl mx-auto page-safe-x page-safe-y px-4 sm:px-6 py-6 sm:py-8">
          {/* Back placeholder */}
          <div className="skeleton h-4 w-20 mb-6 rounded" />
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-8">
            <div className="flex items-center gap-4">
              <div className="skeleton w-12 h-12 rounded-xl" />
              <div>
                <div className="skeleton h-7 w-40 mb-2 rounded" />
                <div className="skeleton h-4 w-24 rounded" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:flex">
              <div className="skeleton h-9 w-24 rounded-xl" />
              <div className="skeleton h-9 w-24 rounded-xl" />
            </div>
          </div>
          {/* Hero panels */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4">
            <div className="skeleton md:col-span-2 h-64 rounded-xl" />
            <div className="skeleton md:col-span-3 h-64 rounded-xl" />
          </div>
          {/* Lower panels */}
          <div className="skeleton h-32 rounded-xl mb-4" />
          <div className="skeleton h-48 rounded-xl" />
        </div>
      </div>
    )

  const displayedEvents = events.slice(0, EVENTS_SHOWN)
  const hiddenCount = events.length - EVENTS_SHOWN

  return (
    <div className="flex-1 flex flex-col" style={{ background: 'var(--bg)', width: '100%', minWidth: 0, overflowX: 'clip' }}>
      <PageBackground />
      <div className="max-w-5xl mx-auto page-safe-x page-safe-y px-4 sm:px-6 py-4 sm:py-6" style={{ position: 'relative', zIndex: 1, width: '100%', minWidth: 0 }}>

        {/* Back nav */}
        <div className="mb-6">
          <button
            onClick={() => nav('/')}
            className="inline-flex items-center gap-1.5 text-sm transition-colors duration-150"
            style={{ color: 'var(--lo)' }}
            onMouseEnter={(e) => e.currentTarget.style.color = 'var(--mid)'}
            onMouseLeave={(e) => e.currentTarget.style.color = 'var(--lo)'}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M9 2L4 7L9 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Dashboard
          </button>
        </div>

        {/* Quota */}
        <div className="mb-6"><QuotaBanner /></div>

        {/* Page header */}
        <div className="flex flex-col gap-4 sm:gap-5 lg:flex-row lg:items-start lg:justify-between mb-8">
          <div className="flex items-start gap-3 sm:gap-4 min-w-0">
            <VendorAvatar name={vendor.name} domain={vendor.domain} logoUrl={vendor.logo_url} size={48} />
            <div className="min-w-0">
              <h1 className="text-xl sm:text-2xl font-bold leading-tight break-words" style={{ color: 'var(--hi)' }}>{vendor.name}</h1>
              <p className="text-sm mt-0.5 break-all" style={{ color: 'var(--lo)' }}>{vendor.domain}</p>
              <p className="text-xs mt-0.5 min-h-[1rem]" style={{ color: 'var(--lo)' }}>
                {vendor.company_number ? `CH: ${vendor.company_number}` : 'CH: not available'}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full lg:w-auto shrink-0 min-w-0">
            <button
              onClick={handleScan}
              disabled={scanning}
              title={quotaExhausted ? 'Search quota exhausted — this scan will still run, but compliance web search will be limited until reset.' : ''}
              className="w-full px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-150 disabled:opacity-40"
              style={{ background: '#8b5cf6', color: '#fff' }}
              onMouseEnter={(e) => {
                if (!scanning) e.currentTarget.style.background = '#7c3aed'
              }}
              onMouseLeave={(e) => { e.currentTarget.style.background = '#8b5cf6' }}
            >
              {scanning ? (
                <span className="inline-flex items-center gap-1.5">
                  <svg className="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4 31.4" strokeLinecap="round"/>
                  </svg>
                  Scanning…
                </span>
              ) : quotaExhausted ? 'Scan Now (Standard)' : 'Scan Now'}
            </button>

            <button
              onClick={handleExportPDF}
              disabled={exporting}
              className="w-full px-4 py-2.5 rounded-xl text-sm transition-all duration-150"
              style={{
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'var(--mid)',
                cursor: exporting ? 'not-allowed' : 'pointer',
                opacity: exporting ? 0.5 : 1,
              }}
              onMouseEnter={(e) => {
                if (!exporting) {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
                  e.currentTarget.style.color = 'var(--hi)'
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
                e.currentTarget.style.color = 'var(--mid)'
              }}
            >
              {exporting ? 'Exporting…' : 'Export PDF'}
            </button>
          </div>
        </div>

        <Tabs
          active={activeTab}
          onChange={setActiveTab}
          tabs={[
            { key: 'overview', label: 'Overview' },
            { key: 'compliance', label: 'Compliance' },
            { key: 'events', label: events.length ? `Events (${events.length})` : 'Events' },
            { key: 'notes', label: notes.length ? `Notes (${notes.length})` : 'Notes' },
          ]}
        />

        {/* Risk overview */}
        <TabPanel id="overview" active={activeTab}>
        {(() => {
          const displayScore = vendor.effective_score ?? vendor.risk_score
          const level = riskLevel(displayScore)
          const scoreColor = { high: 'var(--risk-high)', medium: 'var(--risk-medium)', low: 'var(--risk-low)' }[level]
          const scheduleStatus = formatScheduleStatus(vendor)
          const hasTrend = history.length >= 2
          const scoreDelta = vendor.score_delta ?? 0
          const riskBand = { high: 'High Risk', medium: 'Medium Risk', low: 'Low Risk' }[level]
          const monitorState = vendor.last_scanned ? 'Actively tracked' : 'Awaiting first scan'
          return (
            <Panel className="mb-4" style={{ animation: 'fade-up 260ms cubic-bezier(0.16,1,0.3,1) both' }}>
              <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] gap-6">
                <div
                  className="rounded-2xl p-4 sm:p-5 self-start h-full flex flex-col"
                  style={{
                    background: 'linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01))',
                    border: '1px solid rgba(255,255,255,0.05)',
                    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)',
                  }}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-[10px] font-bold tracking-[0.14em] uppercase mb-2" style={{ color: 'var(--lo)' }}>
                        Risk Score
                      </p>
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span className="text-5xl sm:text-6xl font-bold tabular-nums leading-none" style={{ color: scoreColor }}>
                          {displayScore}
                        </span>
                        <div className="pt-1">
                          <RiskBadge score={displayScore} size="md" />
                        </div>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <p className="text-[10px] font-bold tracking-[0.12em] uppercase mb-2" style={{ color: 'var(--lo)' }}>
                        Score Delta
                      </p>
                      <p className="text-[10px] mb-2" style={{ color: 'var(--lo)' }}>
                        vs previous scan
                      </p>
                      {hasTrend && scoreDelta !== 0 ? (
                        <div>
                          <div
                            className="text-2xl font-bold tabular-nums leading-none"
                            style={{ color: scoreDelta > 0 ? 'var(--risk-high)' : 'var(--risk-low)' }}
                          >
                            {scoreDelta > 0 ? `+${scoreDelta}` : scoreDelta}
                          </div>
                          <div className="text-[11px] mt-1" style={{ color: scoreDelta > 0 ? 'var(--risk-high)' : 'var(--risk-low)' }}>
                            {scoreDelta > 0 ? 'Rising' : 'Falling'}
                          </div>
                        </div>
                      ) : hasTrend ? (
                        <div>
                          <div className="text-2xl font-bold leading-none tabular-nums" style={{ color: 'var(--lo)' }}>0</div>
                          <div className="text-[11px] mt-1" style={{ color: 'var(--lo)' }}>Stable</div>
                        </div>
                      ) : (
                        <div>
                          <div className="text-2xl font-bold leading-none" style={{ color: 'var(--lo)' }}>—</div>
                          <div className="text-[11px] mt-1" style={{ color: 'var(--lo)' }}>Need 2 scans</div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-5">
                    <div
                      className="rounded-xl px-3.5 py-3 min-h-[84px]"
                      style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.05)' }}
                    >
                      <p className="text-[10px] font-bold tracking-[0.12em] uppercase mb-1.5" style={{ color: 'var(--lo)' }}>
                        Last Scan
                      </p>
                      <p className="text-sm font-semibold leading-tight" style={{ color: 'var(--hi)' }}>
                        {vendor.last_scanned ? relativeTime(vendor.last_scanned) : '—'}
                      </p>
                      <p className="text-[10px] mt-1 min-h-[1rem]" style={{ color: 'var(--lo)' }}>
                        {vendor.last_scanned
                          ? formatApiDateTime(vendor.last_scanned, [], {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : 'No completed scan yet'}
                      </p>
                    </div>

                    <div
                      className="rounded-xl px-3.5 py-3 min-h-[84px]"
                      style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.05)' }}
                    >
                      <p className="text-[10px] font-bold tracking-[0.12em] uppercase mb-1.5" style={{ color: 'var(--lo)' }}>
                        Exposure Basis
                      </p>
                      <p className="text-sm font-semibold leading-tight" style={{ color: 'var(--hi)' }}>
                        {vendor.effective_score != null && vendor.effective_score !== vendor.risk_score ? 'Context adjusted' : 'Technical only'}
                      </p>
                      <p className="text-[10px] mt-1 tabular-nums" style={{ color: 'var(--lo)' }}>
                        Technical {vendor.risk_score}
                        {vendor.effective_score != null && vendor.effective_score !== vendor.risk_score ? ` -> Effective ${vendor.effective_score}` : ''}
                      </p>
                    </div>
                  </div>

                  <div
                    className="mt-5 pt-4"
                    style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
                  >
                    <div
                      className="rounded-xl px-3.5 py-3 mb-4"
                      style={{
                        background: 'rgba(255,255,255,0.02)',
                        border: '1px solid rgba(255,255,255,0.045)',
                      }}
                    >
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                          <p className="text-[9px] font-bold tracking-[0.14em] uppercase mb-1" style={{ color: 'var(--lo)' }}>
                            Current Posture
                          </p>
                          <p className="text-[12px] font-semibold" style={{ color: scoreColor }}>
                            {riskBand}
                          </p>
                        </div>
                        <div>
                          <p className="text-[9px] font-bold tracking-[0.14em] uppercase mb-1" style={{ color: 'var(--lo)' }}>
                            Monitoring
                          </p>
                          <p className="text-[12px] font-semibold" style={{ color: 'var(--mid)' }}>
                            {monitorState}
                          </p>
                        </div>
                        <div>
                          <p className="text-[9px] font-bold tracking-[0.14em] uppercase mb-1" style={{ color: 'var(--lo)' }}>
                            Scan History
                          </p>
                          <p className="text-[12px] font-semibold" style={{ color: 'var(--mid)' }}>
                            {history.length} recorded{history.length === 1 ? '' : ' scans'}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center justify-between gap-3 mb-2">
                      <p className="text-[10px] font-bold tracking-[0.14em] uppercase" style={{ color: 'var(--lo)' }}>
                        Scoring Model
                      </p>
                      <div className="group relative inline-block">
                        <button
                          type="button"
                          aria-describedby="scoring-model-explainer"
                          className="text-[11px] cursor-help bg-transparent p-0"
                          style={{ color: 'var(--lo)', borderBottom: '1px dotted #44445a', borderTop: 'none', borderLeft: 'none', borderRight: 'none' }}
                        >
                          How is this calculated?
                        </button>
                        <div
                          id="scoring-model-explainer"
                          role="tooltip"
                          className="absolute right-0 bottom-full mb-3 w-[min(22rem,calc(100vw-2rem))] rounded-xl p-4 text-xs hidden group-hover:block group-focus-within:block z-50"
                          style={{
                            background: 'var(--elevated)',
                            border: '1px solid var(--border)',
                            color: 'var(--mid)',
                            boxShadow: '0 12px 40px rgba(0,0,0,0.8)',
                          }}
                        >
                          <p className="font-semibold mb-1.5" style={{ color: 'var(--hi)' }}>Technical Score</p>
                          <p className="mb-3">
                            Top CVEs are weighted by severity, then combined with breach data, Companies House signals, and Shodan exposure. Final score is capped at 100.
                          </p>
                          <p className="font-semibold mb-1.5" style={{ color: 'var(--hi)' }}>Effective Exposure</p>
                          <p className="mb-2">
                            Business context multiplies the technical score based on the type of access this vendor has to your environment or data.
                          </p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-1 pt-2" style={{ borderTop: '1px solid var(--border)' }}>
                            {[
                              ['No Data Access', '×0.8'],
                              ['PII / Personal', '×1.4'],
                              ['Financial', '×1.6'],
                              ['Auth / SSO', '×1.6'],
                              ['Health / Medical', '×1.8'],
                              ['Critical Infra', '×2.0'],
                            ].map(([lbl, mult]) => (
                              <div key={lbl} className="flex justify-between">
                                <span>{lbl}</span>
                                <span style={{ color: 'var(--accent-l)' }}>{mult}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    <p className="text-[11px] leading-relaxed" style={{ color: 'var(--lo)' }}>
                      Technical findings set the baseline. Business context then adjusts exposure based on the type of access this vendor has.
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3">
                      {[
                        { label: 'Signals', value: 'CVEs, breaches, infra' },
                        { label: 'Context', value: 'Sensitivity multiplier' },
                        { label: 'Output', value: '0-100 capped score' },
                      ].map(({ label, value }) => (
                        <div
                          key={label}
                          className="rounded-xl px-3 py-2.5"
                          style={{
                            background: 'rgba(255,255,255,0.02)',
                            border: '1px solid rgba(255,255,255,0.05)',
                          }}
                        >
                          <p className="text-[9px] font-bold tracking-[0.14em] uppercase mb-1" style={{ color: 'var(--lo)' }}>
                            {label}
                          </p>
                          <p className="text-[11px] leading-snug" style={{ color: 'var(--mid)' }}>
                            {value}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="grid gap-5 content-start">
                  <div style={{ opacity: updatingContext ? 0.5 : 1, transition: 'opacity 200ms ease', pointerEvents: updatingContext ? 'none' : 'auto' }}>
                    <div className="flex items-center justify-between mb-2.5">
                      <div>
                        <p className="text-[10px] font-bold tracking-[0.14em] uppercase" style={{ color: 'var(--lo)' }}>
                          Data Sensitivity
                        </p>
                        <p className="text-[11px] mt-1" style={{ color: 'var(--lo)' }}>
                          Adjust the score based on what this vendor can actually touch.
                        </p>
                      </div>
                      {updatingContext && (
                        <span className="text-[10px]" style={{ color: 'var(--lo)' }}>saving…</span>
                      )}
                    </div>

                    {(() => {
                      const current = vendor.data_sensitivity || 'standard'
                      return (
                        <Select
                          value={current}
                          onChange={handleContextChange}
                          ariaLabel="Data sensitivity"
                          options={SENSITIVITY_OPTIONS.map(({ value, label, hint }) => ({
                            value,
                            label: `${label} — ${hint}${value === 'standard' ? ' (default)' : ''}`,
                          }))}
                        />
                      )
                    })()}
                  </div>

                  <div
                    style={{
                      opacity: updatingReview ? 0.5 : 1,
                      transition: 'opacity 200ms ease',
                      pointerEvents: updatingReview ? 'none' : 'auto',
                    }}
                  >
                    <div className="flex items-center justify-between mb-2.5">
                      <div>
                        <p className="text-[10px] font-bold tracking-[0.14em] uppercase" style={{ color: 'var(--lo)' }}>
                          Review Schedule
                        </p>
                        <p className="text-[11px] mt-1" style={{ color: scheduleStatus.tone }}>
                          {scheduleStatus.text}
                        </p>
                      </div>
                      {updatingReview && (
                        <span className="text-[10px]" style={{ color: 'var(--lo)' }}>saving…</span>
                      )}
                    </div>

                    {(() => {
                      const current = vendor.review_interval_days ?? null
                      const REVIEW_OPTIONS = [
                        { value: 'none', label: 'No schedule (default)' },
                        { value: '30',   label: '30 days' },
                        { value: '60',   label: '60 days' },
                        { value: '90',   label: '90 days' },
                        { value: '180',  label: '180 days' },
                        { value: '365',  label: 'Annually' },
                      ]
                      return (
                        <div className="mb-2">
                          <Select
                            value={current === null ? 'none' : String(current)}
                            onChange={(v) => handleReviewUpdate({ interval_days: v === 'none' ? null : Number(v) })}
                            ariaLabel="Review schedule"
                            options={REVIEW_OPTIONS}
                          />
                        </div>
                      )
                    })()}

                    {vendor.review_interval_days && (
                      <div className="flex justify-end">
                        <button
                          onClick={() => handleReviewUpdate({ mark_reviewed: true })}
                          className="text-[10px] px-2.5 py-1 rounded-lg transition-all duration-150"
                          style={{
                            background: 'rgba(34,197,94,0.08)',
                            border: '1px solid rgba(34,197,94,0.2)',
                            color: 'var(--risk-low)',
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(34,197,94,0.15)'}
                          onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(34,197,94,0.08)'}
                        >
                          Mark Reviewed
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </Panel>
          )
        })()}

        {/* Vendor Profile */}
        {/* Vendor Profile — always rendered for stable layout */}
        <Panel className="mb-4" style={{ animation: 'fade-up 260ms cubic-bezier(0.16,1,0.3,1) 50ms both' }}>
          <PanelTitle meta="(auto-discovered)">Vendor Profile</PanelTitle>

          <div className="mb-5 min-h-[3.5rem]">
            <p className="text-sm leading-relaxed" style={{ color: vendor.description ? 'var(--mid)' : 'var(--lo)' }}>
              {vendor.description || 'No vendor profile description detected from public sources.'}
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <p className="text-[10px] font-bold tracking-[0.14em] uppercase mb-1.5" style={{ color: 'var(--lo)' }}>
                Auth Method
              </p>
              <p className="text-sm" style={{ color: 'var(--mid)' }}>
                {vendor.auth_method || (
                  <span style={{ color: 'var(--lo)' }}>Not detected</span>
                )}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-bold tracking-[0.14em] uppercase mb-1.5" style={{ color: 'var(--lo)' }}>
                2FA Support
              </p>
              {vendor.two_factor === 'Yes' ? (
                <span
                  className="inline-flex items-center text-xs px-2.5 py-0.5 rounded-full"
                  style={{
                    background: 'rgba(34,197,94,0.08)',
                    border: '1px solid rgba(34,197,94,0.2)',
                    color: 'var(--risk-low)',
                  }}
                >
                  Yes
                </span>
              ) : (
                <span className="text-sm" style={{ color: 'var(--lo)' }}>Not detected</span>
              )}
            </div>
          </div>
        </Panel>
        </TabPanel>

        {/* Compliance */}
        <TabPanel id="compliance" active={activeTab}>
        <Panel className="mb-4" style={{ animation: 'fade-up 260ms cubic-bezier(0.16,1,0.3,1) both' }}>
          <PanelTitle meta="(auto-discovered from public sources)">Compliance Posture</PanelTitle>
          <CompliancePanel compliance={vendor.compliance} />
        </Panel>
        </TabPanel>

        {/* Risk Events */}
        <TabPanel id="events" active={activeTab}>
        <Panel style={{ animation: 'fade-up 260ms cubic-bezier(0.16,1,0.3,1) both' }}>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--hi)' }}>
              Risk Events{' '}
              <span className="font-normal" style={{ color: 'var(--lo)' }}>
                (top {displayedEvents.length} of {events.length})
              </span>
            </h3>
            {hiddenCount > 0 && (
              <button
                onClick={handleExportPDF}
                disabled={exporting}
                className="text-xs rounded-full px-3 py-1 transition-colors duration-150"
                style={{
                  background: 'rgba(139,92,246,0.1)',
                  border: '1px solid rgba(139,92,246,0.2)',
                  color: 'var(--accent-l)',
                  cursor: exporting ? 'not-allowed' : 'pointer',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(139,92,246,0.18)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(139,92,246,0.1)'}
              >
                +{hiddenCount} more in PDF
              </button>
            )}
          </div>
          <EventFeed events={displayedEvents} acceptances={acceptances} onAccept={handleAccept} onRevoke={handleRevoke} revokingIds={revokingIds} />
        </Panel>
        </TabPanel>

        {/* Analyst Notes */}
        <TabPanel id="notes" active={activeTab}>
        <Panel style={{ animation: 'fade-up 260ms cubic-bezier(0.16,1,0.3,1) both' }}>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--hi)' }}>
              Analyst Notes{' '}
              {notes.length > 0 && (
                <span className="font-normal text-xs" style={{ color: 'var(--lo)' }}>({notes.length})</span>
              )}
            </h3>
            <p className="text-[10px]" style={{ color: 'var(--lo)' }}>Included in PDF export</p>
          </div>

          {/* Composer */}
          <div
            className="mb-5 rounded-xl p-3 sm:p-4"
            style={{
              background: 'rgba(255,255,255,0.025)',
              border: '1px solid rgba(255,255,255,0.05)',
              boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.02)',
            }}
          >
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
              <div>
                <p className="text-[10px] font-bold tracking-[0.14em] uppercase" style={{ color: 'var(--lo)' }}>
                  Add Evidence Note
                </p>
                <p className="text-[11px] mt-1" style={{ color: 'var(--lo)' }}>
                  Capture rationale, follow-up actions, or review context for the vendor file.
                </p>
              </div>
              <div
                className="shrink-0 rounded-full px-2.5 py-1 text-[10px] font-medium tabular-nums"
                style={{
                  background: 'rgba(139,92,246,0.08)',
                  border: '1px solid rgba(139,92,246,0.18)',
                  color: 'var(--accent-l)',
                }}
              >
                {noteInput.trim().length}/1000
              </div>
            </div>

            <textarea
              value={noteInput}
              onChange={(e) => setNoteInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleAddNote()
              }}
              placeholder="Example: Accepted medium-risk exposure pending vendor remediation evidence by month-end."
              rows={4}
              maxLength={1000}
              disabled={addingNote}
              className="w-full rounded-xl px-3.5 py-3 text-sm resize-y min-h-[120px]"
              style={{
                background: 'var(--elevated)',
                border: '1px solid var(--border)',
                color: 'var(--hi)',
                outline: 'none',
                opacity: addingNote ? 0.5 : 1,
                transition: 'opacity 200ms ease, border-color 200ms ease, box-shadow 200ms ease',
                boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.02)',
              }}
            />

            <div className="mt-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <p className="text-[11px]" style={{ color: 'var(--lo)' }}>
                Submit with <span style={{ color: 'var(--mid)' }}>Ctrl+Enter</span> or use the action button.
              </p>

              <button
                onClick={handleAddNote}
                disabled={addingNote || !noteInput.trim()}
                className="inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-xs font-semibold transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
                style={{
                  background: noteInput.trim() ? '#8b5cf6' : 'rgba(139,92,246,0.35)',
                  color: '#fff',
                  minWidth: '132px',
                  boxShadow: noteInput.trim() ? '0 10px 24px rgba(139,92,246,0.22)' : 'none',
                }}
                onMouseEnter={(e) => {
                  if (!addingNote && noteInput.trim()) e.currentTarget.style.background = '#7c3aed'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = noteInput.trim() ? '#8b5cf6' : 'rgba(139,92,246,0.35)'
                }}
              >
                {addingNote ? (
                  <>
                    <svg className="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4 31.4" strokeLinecap="round" />
                    </svg>
                    Saving…
                  </>
                ) : (
                  <>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                    Add Note
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Notes list */}
          {notes.length === 0 ? (
            <div
              className="rounded-xl py-10 px-4 text-center"
              style={{
                background: 'rgba(255,255,255,0.02)',
                border: '1px dashed rgba(255,255,255,0.07)',
              }}
            >
              <div className="flex justify-center mb-3 opacity-60">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M8 7h8M8 11h8M8 15h5" stroke="#8080aa" strokeWidth="1.6" strokeLinecap="round" />
                  <rect x="4.75" y="4.75" width="14.5" height="14.5" rx="2.5" stroke="#2a2a4a" strokeWidth="1.5" />
                </svg>
              </div>
              <p className="text-sm font-medium" style={{ color: 'var(--mid)' }}>No analyst notes yet</p>
              <p className="text-xs mt-1" style={{ color: 'var(--lo)' }}>
                Notes you add here are saved with the vendor record and included in PDF exports.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {notes.map((note, i) => (
                <div
                  key={note.id}
                  className="group flex items-start gap-3 p-3 rounded-lg"
                  style={{
                    background: 'rgba(255,255,255,0.02)',
                    border: '1px solid rgba(255,255,255,0.04)',
                    animation: `fade-up 200ms cubic-bezier(0.16,1,0.3,1) ${i * 30}ms both`,
                  }}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-xs leading-relaxed" style={{ color: 'var(--hi)' }}>{note.content}</p>
                    <p className="text-[10px] mt-1 font-mono" style={{ color: 'var(--lo)' }}>
                      {formatApiDateTime(note.created_at, [], {
                        month: 'short', day: 'numeric', year: 'numeric',
                        hour: '2-digit', minute: '2-digit',
                      })}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDeleteNote(note.id)}
                    className="opacity-100 sm:opacity-0 sm:group-hover:opacity-100 text-xs px-2 py-1 rounded transition-all duration-150 shrink-0"
                    style={{ color: 'var(--lo)', background: 'rgba(255,255,255,0.03)' }}
                    onMouseEnter={(e) => e.currentTarget.style.color = 'var(--risk-high)'}
                    onMouseLeave={(e) => e.currentTarget.style.color = 'var(--lo)'}
                    title="Delete note"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </Panel>
        </TabPanel>

      </div>

      <Toast message={toastMessage} onDismiss={() => setToastMessage('')} />
      </div>
    )
}
