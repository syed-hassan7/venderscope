import { useNavigate } from 'react-router-dom'

// --- Inline markdown formatter (bold, code, links) ---
function Inline({ text }) {
  if (!text) return null
  const regex = /(\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\))/g
  const parts = []
  let last = 0, match, key = 0

  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index))
    const raw = match[1]
    if (raw.startsWith('**')) {
      parts.push(<strong key={key++} style={{ color: '#e2e8f0', fontWeight: 600 }}>{match[2]}</strong>)
    } else if (raw.startsWith('`')) {
      parts.push(
        <code key={key++} style={{
          background: 'rgba(139,92,246,0.15)', borderRadius: '4px',
          padding: '1px 5px', fontSize: '0.85em', color: '#a78bfa', fontFamily: 'monospace',
        }}>{match[3]}</code>
      )
    } else {
      parts.push(
        <a key={key++} href={match[5]} target="_blank" rel="noreferrer"
           style={{ color: '#8b5cf6', textDecoration: 'underline' }}>{match[4]}</a>
      )
    }
    last = match.index + raw.length
  }
  if (last < text.length) parts.push(text.slice(last))
  return <>{parts}</>
}

// --- Table parser ---
function MdTable({ rows }) {
  if (rows.length < 2) return null
  const parseCells = (line) => line.split('|').slice(1, -1).map(c => c.trim())
  const isSeparator = (line) => /^\|[-| :]+\|$/.test(line.trim())

  const headerLine = rows[0]
  const dataLines = rows.filter((r, i) => i > 0 && !isSeparator(r))
  const headers = parseCells(headerLine)

  return (
    <div style={{ overflowX: 'auto', margin: '16px 0' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
        <thead>
          <tr style={{ background: '#111827' }}>
            {headers.map((h, i) => (
              <th key={i} style={{
                padding: '10px 12px', textAlign: 'left',
                color: '#8080aa', borderBottom: '1px solid #2a2a4a',
              }}><Inline text={h} /></th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dataLines.map((row, ri) => (
            <tr key={ri} style={{ background: ri % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
              {parseCells(row).map((cell, ci) => (
                <td key={ci} style={{
                  padding: '8px 12px', color: '#b8b8d0',
                  borderBottom: '1px solid #1a1a2e',
                }}><Inline text={cell} /></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// --- Main markdown parser ---
function parseMarkdown(md) {
  const lines = md.split('\n')
  const elements = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Headings
    if (line.startsWith('### ')) {
      elements.push(
        <h3 key={i} style={{ color: '#c4b5fd', fontSize: '14px', fontWeight: 600, marginTop: '20px', marginBottom: '6px', letterSpacing: '0.02em' }}>
          <Inline text={line.slice(4)} />
        </h3>
      )
    } else if (line.startsWith('## ')) {
      elements.push(
        <h2 key={i} style={{ color: '#e2e8f0', fontSize: '17px', fontWeight: 700, marginTop: '32px', marginBottom: '8px', paddingBottom: '6px', borderBottom: '1px solid #1a1a2e' }}>
          <Inline text={line.slice(3)} />
        </h2>
      )
    } else if (line.startsWith('# ')) {
      elements.push(
        <h1 key={i} style={{ color: '#f0f0ff', fontSize: '26px', fontWeight: 800, marginTop: 0, marginBottom: '8px' }}>
          <Inline text={line.slice(2)} />
        </h1>
      )

    // Horizontal rule
    } else if (line.trim() === '---') {
      elements.push(<hr key={i} style={{ border: 'none', borderTop: '1px solid #1a1a2e', margin: '24px 0' }} />)

    // Bullet list — collect consecutive items
    } else if (line.startsWith('- ') || line.startsWith('* ')) {
      const items = []
      while (i < lines.length && (lines[i].startsWith('- ') || lines[i].startsWith('* '))) {
        items.push(lines[i].slice(2))
        i++
      }
      elements.push(
        <ul key={`ul-${i}`} style={{ color: '#b8b8d0', paddingLeft: '20px', margin: '8px 0', lineHeight: '1.7' }}>
          {items.map((item, idx) => (
            <li key={idx}><Inline text={item} /></li>
          ))}
        </ul>
      )
      continue

    // Table — collect consecutive rows
    } else if (line.startsWith('| ')) {
      const rows = []
      while (i < lines.length && lines[i].startsWith('|')) {
        rows.push(lines[i])
        i++
      }
      elements.push(<MdTable key={`tbl-${i}`} rows={rows} />)
      continue

    // Empty line
    } else if (line.trim() === '') {
      // skip — spacing handled by element margins

    // Regular paragraph
    } else {
      elements.push(
        <p key={i} style={{ color: '#b8b8d0', lineHeight: '1.75', margin: '10px 0' }}>
          <Inline text={line} />
        </p>
      )
    }

    i++
  }

  return elements
}

export default function DocPage({ markdown }) {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen" style={{ background: '#090911' }}>
      <div className="max-w-3xl mx-auto px-6 py-12">

        {/* Back button */}
        <button
          onClick={() => navigate(-1)}
          className="mb-8 flex items-center gap-2 text-sm transition-colors"
          style={{ color: '#8080aa', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          onMouseEnter={(e) => e.currentTarget.style.color = '#b8b8d0'}
          onMouseLeave={(e) => e.currentTarget.style.color = '#8080aa'}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M19 12H5M5 12l7 7M5 12l7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back
        </button>

        {/* Doc content */}
        <div
          className="rounded-2xl p-8"
          style={{
            background: '#0f1117',
            border: '1px solid #1a1a2e',
          }}
        >
          {parseMarkdown(markdown)}
        </div>

        <p className="text-center text-xs mt-8" style={{ color: '#8080aa' }}>
          VenderScope · Continuous Passive Vendor Risk Intelligence
        </p>
        <p className="text-center text-xs mt-2" style={{ color: '#8080aa' }}>
          New accounts: Google, then a passkey. Password sign-in is closed.
        </p>
      </div>
    </div>
  )
}
