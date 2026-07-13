import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { getVendors, addVendor, deleteVendor, scanVendor, scanAll, getDashboardSummary } from '../api/client'
import VendorCard from '../components/VendorCard'
import AddVendorModal from '../components/AddVendorModal'
import QuotaBanner from '../components/QuotaBanner'
import Footer from '../components/Footer'
import { useAuth } from '../auth/AuthContext'
import PageBackground from '../components/PageBackground'
import { parseApiDate } from '../utils/datetime'

const StatPill = ({ value, label, color }) => (
  <div
    className="flex items-center gap-2.5 rounded-xl px-3.5 py-2.5 sm:px-4"
    style={{
      background: 'var(--surface)',
      border: '1px solid var(--line)',
    }}
  >
    <span className="text-lg sm:text-xl font-bold tabular-nums" style={{ color }}>{value}</span>
    <span className="text-xs sm:text-sm" style={{ color: 'var(--lo)' }}>{label}</span>
  </div>
)

const EmptyState = ({ onAdd }) => (
  <div className="text-center py-20 sm:py-32">
    <div className="flex justify-center mb-4 opacity-15">
      <svg width="48" height="48" viewBox="0 0 32 32" fill="none">
        <path d="M16 2.5L27.5 9.25V22.75L16 29.5L4.5 22.75V9.25L16 2.5Z" stroke="#8b5cf6" strokeWidth="1.5" fill="none"/>
        <circle cx="16" cy="16" r="5.5" stroke="#8b5cf6" strokeWidth="1.2"/>
        <circle cx="16" cy="16" r="1.8" fill="#8b5cf6"/>
      </svg>
    </div>
    <p className="font-medium" style={{ color: 'var(--lo)' }}>No vendors monitored yet</p>
    <p className="text-sm mt-1" style={{ color: 'var(--lo)' }}>
      Add your first vendor to start continuous monitoring.
    </p>
    <button
      onClick={onAdd}
      className="mt-6 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-150"
      style={{ background: '#8b5cf6', color: '#fff' }}
      onMouseEnter={(e) => e.currentTarget.style.background = '#7c3aed'}
      onMouseLeave={(e) => e.currentTarget.style.background = '#8b5cf6'}
    >
      + Add Vendor
    </button>
  </div>
)

const SORT_OPTIONS = [
  { key: 'risk',    label: 'Risk Score' },
  { key: 'delta',   label: 'Biggest Movers' },
  { key: 'scanned', label: 'Recently Scanned' },
]

export default function Dashboard() {
  useAuth()
  const nav = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [vendors, setVendors] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [scanning, setScanning] = useState({})
  const [scanningAll, setScanAll] = useState(false)
  const [cardsVisible, setCardsVisible] = useState(false)
  const [sortBy, setSortBy] = useState('risk')
  const [summary, setSummary] = useState(null)
  const [searchValue, setSearchValue] = useState(searchParams.get('q') || '')

  const handleSearch = (val) => {
    setSearchValue(val)
    setSearchParams(val ? { q: val } : {}, { replace: true })
  }
  const clearSearch = () => {
    setSearchValue('')
    setSearchParams({}, { replace: true })
  }

  const refreshDashboard = async () => {
    const [vendorsRes, summaryRes] = await Promise.all([
      getVendors(),
      getDashboardSummary().catch(() => null),
    ])
    const list = vendorsRes?.data
    setVendors(Array.isArray(list) ? list : [])
    if (summaryRes) {
      setSummary(summaryRes.data)
    }
  }

  useEffect(() => {
    refreshDashboard().catch(() => {})
    const t = setTimeout(() => setCardsVisible(true), 80)
    return () => clearTimeout(t)
  }, [])

  const handleAdd = async (data) => { await addVendor(data); await refreshDashboard() }

  const handleDelete = async (id) => {
    if (!confirm('Remove this vendor?')) return
    await deleteVendor(id)
    await refreshDashboard()
  }

  const handleScan = async (id) => {
    setScanning((s) => ({ ...s, [id]: true }))
    try { await scanVendor(id); await refreshDashboard() }
    catch (e) { console.error('Scan failed:', e) }
    finally { setScanning((s) => ({ ...s, [id]: false })) }
  }

  const handleScanAll = async () => {
    setScanAll(true)
    try {
      await scanAll()
      await refreshDashboard()
    } catch (e) { console.error('Scan all failed:', e) }
    finally { setScanAll(false) }
  }

  const handleExportRegister = () => {
    if (!vendors.length) return
    const headers = [
      'Vendor Name', 'Domain', 'Data Sensitivity', 'Technical Score',
      'Effective Exposure Score', 'Risk Band', 'Score Delta', 'Last Scanned',
      'Review Interval (days)', 'CVE Count', 'Breach Detected', 'Export Date',
    ]
    const riskBand = (s) => s >= 70 ? 'HIGH' : s >= 40 ? 'MEDIUM' : 'LOW'
    const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
    const rows = vendors.map((v) => {
      const score = v.effective_score ?? v.risk_score
      return [
        esc(v.name),
        esc(v.domain),
        esc(v.data_sensitivity || 'standard'),
        esc(v.risk_score),
        esc(score),
        esc(riskBand(score)),
        esc(v.score_delta != null ? (v.score_delta > 0 ? `+${v.score_delta}` : v.score_delta) : 'N/A'),
        esc(v.last_scanned ? parseApiDate(v.last_scanned)?.toLocaleDateString() ?? 'Never' : 'Never'),
        esc(v.review_interval_days ?? 'None'),
        esc('See vendor report'),
        esc('See vendor report'),
        esc(new Date().toLocaleDateString()),
      ].join(',')
    })
    const csv = [headers.map(esc).join(','), ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `vendorscope_risk_register_${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const effScore = (v) => v.effective_score ?? v.risk_score
  const high    = vendors.filter((v) => effScore(v) >= 70).length
  const medium  = vendors.filter((v) => effScore(v) >= 40 && effScore(v) < 70).length
  const low     = vendors.filter((v) => effScore(v) < 40).length
  const rising  = vendors.filter((v) => v.score_delta > 0).sort((a, b) => b.score_delta - a.score_delta)

  const sortedVendors = [...vendors].sort((a, b) => {
    if (sortBy === 'risk')    return effScore(b) - effScore(a)
    if (sortBy === 'delta')   return (b.score_delta ?? -Infinity) - (a.score_delta ?? -Infinity)
    if (sortBy === 'scanned') {
      const ta = a.last_scanned ? (parseApiDate(a.last_scanned)?.getTime() ?? 0) : 0
      const tb = b.last_scanned ? (parseApiDate(b.last_scanned)?.getTime() ?? 0) : 0
      return tb - ta
    }
    return 0
  })

  const q = searchValue.toLowerCase().trim()
  const filteredVendors = q
    ? sortedVendors.filter((v) =>
        v.name.toLowerCase().includes(q) || v.domain.toLowerCase().includes(q)
      )
    : sortedVendors

  return (
    <div className="flex-1 flex flex-col" style={{ background: 'var(--bg)' }}>
      <PageBackground />
      <main className="flex-1 w-full">
      <div className="max-w-7xl mx-auto page-safe-x page-safe-y px-4 sm:px-6 py-4 sm:py-6" style={{ position: 'relative', zIndex: 1 }}>

        {/* Quota */}
        <div className="mb-4"><QuotaBanner /></div>

        {/* Unified toolbar: context left · actions right */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-5">

          {/* Left: brand context */}
          <div className="flex items-center gap-2.5 text-xs flex-wrap">
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-semibold tracking-wide shrink-0"
              style={{
                background: 'rgba(139,92,246,0.07)',
                border: '1px solid rgba(139,92,246,0.15)',
                color: 'var(--accent-l)',
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: '#8b5cf6' }} />
              BETA
            </span>
            <span className="hidden sm:inline" style={{ color: 'var(--lo)' }}>
              Vendors are private to your account.
            </span>
          </div>

          {/* Right: search + actions */}
          <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">

            {/* Search */}
            <div className="relative">
              <Search
                size={12}
                aria-hidden="true"
                style={{
                  position: 'absolute',
                  left: '9px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--lo)',
                  pointerEvents: 'none',
                  flexShrink: 0,
                }}
              />
              <input
                type="search"
                placeholder="Filter vendors…"
                value={searchValue}
                onChange={(e) => handleSearch(e.target.value)}
                aria-label="Filter vendors"
                style={{
                  height: '34px',
                  width: '180px',
                  paddingLeft: '28px',
                  paddingRight: searchValue ? '28px' : '10px',
                  background: 'var(--surface)',
                  border: '1px solid var(--line)',
                  borderRadius: '8px',
                  color: 'var(--hi)',
                  fontSize: '12px',
                  outline: 'none',
                  transition: 'border-color 150ms, width 200ms',
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = 'var(--accent)'
                  e.target.style.width = '220px'
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = 'var(--line)'
                  e.target.style.width = '180px'
                }}
              />
              {searchValue && (
                <button
                  type="button"
                  onClick={clearSearch}
                  aria-label="Clear filter"
                  style={{
                    position: 'absolute',
                    right: '8px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--lo)',
                    padding: 0,
                  }}
                >
                  <X size={11} />
                </button>
              )}
            </div>

            {/* Scan All */}
            <div className="relative group">
              <button
                onClick={handleScanAll}
                disabled={scanningAll || vendors.length === 0}
                className="px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 disabled:opacity-40 whitespace-nowrap"
                style={{
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  color: 'var(--mid)',
                }}
                onMouseEnter={(e) => {
                  if (!scanningAll && vendors.length > 0) {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
                    e.currentTarget.style.color = 'var(--hi)'
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
                  e.currentTarget.style.color = 'var(--mid)'
                }}
              >
                {scanningAll ? (
                  <span className="inline-flex items-center gap-1.5">
                    <svg className="animate-spin" width="11" height="11" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="31.4 31.4" strokeLinecap="round"/>
                    </svg>
                    Scanning…
                  </span>
                ) : 'Scan All'}
              </button>
              <div
                className="absolute right-0 top-11 w-72 rounded-xl p-3.5 text-xs hidden group-hover:block z-50"
                style={{
                  background: 'var(--elevated)',
                  border: '1px solid var(--border)',
                  color: 'var(--mid)',
                  boxShadow: '0 12px 40px rgba(0,0,0,0.7)',
                }}
              >
                <span style={{ color: '#fbbf24', fontWeight: 600 }}>Heads up:</span>{' '}
                Works best with 1–2 vendors on the free tier. Scanning 3+ can take 3–5 min or time out.{' '}
                <span style={{ color: 'var(--accent-l)' }}>Use Scan Now on individual cards for reliable results.</span>
              </div>
            </div>

            <button
              onClick={handleExportRegister}
              disabled={vendors.length === 0}
              className="px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 disabled:opacity-40 whitespace-nowrap"
              style={{
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'var(--mid)',
              }}
              onMouseEnter={(e) => {
                if (vendors.length > 0) {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
                  e.currentTarget.style.color = 'var(--hi)'
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
                e.currentTarget.style.color = 'var(--mid)'
              }}
              title="Download risk register as CSV"
            >
              Export
            </button>

            <button
              onClick={() => setShowModal(true)}
              className="px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-150 whitespace-nowrap"
              style={{ background: '#8b5cf6', color: '#fff' }}
              onMouseEnter={(e) => e.currentTarget.style.background = '#7c3aed'}
              onMouseLeave={(e) => e.currentTarget.style.background = '#8b5cf6'}
            >
              + Add Vendor
            </button>

          </div>
        </div>

        {/* Stats row */}
        {vendors.length > 0 && (
          <div className="grid grid-cols-2 xl:flex xl:flex-wrap items-stretch gap-3 mb-8">
            <StatPill value={vendors.length} label="Total" color="var(--hi)" />
            <StatPill value={high}           label="High Risk" color="var(--risk-high)" />
            <StatPill value={medium}         label="Medium" color="var(--risk-medium)" />
            <StatPill value={low}            label="Low Risk" color="var(--risk-low)" />
            {rising.length > 0 && (
              <StatPill value={rising.length} label="Rising ↑" color="var(--risk-high)" />
            )}
            {summary?.overdue_review_count > 0 && (
              <div
                className="flex items-center gap-2.5 rounded-xl px-3.5 py-2.5 sm:px-4 col-span-2 xl:col-span-1"
                title={`Overdue: ${summary.overdue_reviews?.map((v) => v.name).join(', ')}`}
                style={{
                  background: 'rgba(251,191,36,0.06)',
                  border: '1px solid rgba(251,191,36,0.2)',
                  cursor: 'default',
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true" style={{ flexShrink: 0 }}>
                  <circle cx="12" cy="12" r="9.5" stroke="#fbbf24" strokeWidth="1.5"/>
                  <path d="M12 7v5l3 3" stroke="#fbbf24" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <span className="text-xl font-bold tabular-nums" style={{ color: '#fbbf24' }}>
                  {summary.overdue_review_count}
                </span>
                <span className="text-sm" style={{ color: '#c4a060' }}>Reviews Due</span>
              </div>
            )}
          </div>
        )}

        {/* Needs Attention */}
        {rising.length > 0 && (
          <div className="mb-8 rounded-xl p-4" style={{
            background: 'rgba(239,68,68,0.04)',
            border: '1px solid rgba(239,68,68,0.15)',
          }}>
            <div className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-2 mb-3">
              <span className="text-xs font-bold tracking-widest" style={{ color: 'var(--risk-high)' }}>
                NEEDS ATTENTION
              </span>
              <span className="text-xs" style={{ color: 'var(--lo)' }}>
                — scores rose since last scan
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {rising.map((v) => (
                <div
                  key={v.id}
                  className="flex items-center justify-between sm:justify-start gap-2 w-full sm:w-auto px-3 py-2 rounded-lg text-xs cursor-pointer transition-colors duration-150"
                  style={{
                    background: 'rgba(239,68,68,0.08)',
                    border: '1px solid rgba(239,68,68,0.2)',
                    color: 'var(--hi)',
                  }}
                  onClick={() => nav(`/vendor/${v.id}`)}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(239,68,68,0.14)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(239,68,68,0.08)'}
                >
                  <span className="font-medium truncate">{v.name}</span>
                  <span className="font-bold shrink-0" style={{ color: 'var(--risk-high)' }}>
                    +{v.score_delta} ↑
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Vendor grid */}
        {vendors.length === 0 ? (
          <EmptyState onAdd={() => setShowModal(true)} />
        ) : (
          <>
            {/* Sort controls */}
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <span className="text-xs" style={{ color: 'var(--lo)' }}>Sort:</span>
              {SORT_OPTIONS.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setSortBy(key)}
                  className="px-3 py-1 rounded-lg text-xs font-medium transition-all duration-150"
                  style={{
                    background: sortBy === key ? 'rgba(139,92,246,0.15)' : 'rgba(255,255,255,0.04)',
                    border: sortBy === key ? '1px solid rgba(139,92,246,0.35)' : '1px solid rgba(255,255,255,0.06)',
                    color: sortBy === key ? 'var(--accent-l)' : 'var(--lo)',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            {filteredVendors.length === 0 && searchValue ? (
              <div className="py-12 text-center">
                <p className="text-sm" style={{ color: 'var(--lo)' }}>No vendors match "{searchValue}"</p>
                <button
                  onClick={clearSearch}
                  className="mt-3 text-xs transition-colors duration-150"
                  style={{ color: 'var(--accent-l)', background: 'none', border: 'none', cursor: 'pointer' }}
                >
                  Clear filter
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredVendors.map((v, i) => (
                  <div
                    key={v.id}
                    style={{
                      opacity: cardsVisible ? 1 : 0,
                      transform: cardsVisible ? 'translateY(0)' : 'translateY(14px)',
                      transition: `opacity 260ms cubic-bezier(0.16,1,0.3,1) ${i * 18}ms, transform 260ms cubic-bezier(0.16,1,0.3,1) ${i * 18}ms`,
                    }}
                  >
                    <VendorCard
                      vendor={v}
                      onDelete={handleDelete}
                      onScan={handleScan}
                      scanning={!!scanning[v.id]}
                    />
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
      </main>

      {showModal && (
        <AddVendorModal onAdd={handleAdd} onClose={() => setShowModal(false)} />
      )}

      <Footer />
    </div>
  )
}
