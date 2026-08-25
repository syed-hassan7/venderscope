export default function Tabs({ tabs, active, onChange }) {
  const activeIndex = Math.max(0, tabs.findIndex((t) => t.key === active))

  const handleKeyDown = (e) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return
    e.preventDefault()
    let nextIndex = activeIndex
    if (e.key === 'ArrowLeft') nextIndex = (activeIndex - 1 + tabs.length) % tabs.length
    if (e.key === 'ArrowRight') nextIndex = (activeIndex + 1) % tabs.length
    if (e.key === 'Home') nextIndex = 0
    if (e.key === 'End') nextIndex = tabs.length - 1
    const nextKey = tabs[nextIndex].key
    onChange(nextKey)
    document.getElementById(`tab-${nextKey}`)?.focus()
  }

  return (
    <div
      role="tablist"
      onKeyDown={handleKeyDown}
      className="flex flex-wrap items-center gap-1.5 mb-4 p-1 rounded-xl w-fit max-w-full"
      style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}
    >
      {tabs.map(({ key, label }) => {
        const isActive = active === key
        return (
          <button
            key={key}
            role="tab"
            id={`tab-${key}`}
            tabIndex={isActive ? 0 : -1}
            aria-selected={isActive}
            aria-controls={`tabpanel-${key}`}
            onClick={() => onChange(key)}
            className="px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 whitespace-nowrap"
            style={{
              background: isActive ? 'rgba(139,92,246,0.15)' : 'transparent',
              color: isActive ? 'var(--accent-l)' : 'var(--lo)',
            }}
            onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.color = 'var(--mid)' }}
            onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.color = 'var(--lo)' }}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}

export function TabPanel({ id, active, children }) {
  // Stays mounted (hidden via the `hidden` attribute) rather than
  // unmounting on tab switch — an unmounted panel would silently drop any
  // in-progress draft inside it (an accept-risk justification being typed,
  // a note being composed) the moment the user switched tabs and back.
  return (
    <div role="tabpanel" id={`tabpanel-${id}`} aria-labelledby={`tab-${id}`} hidden={active !== id}>
      {children}
    </div>
  )
}
