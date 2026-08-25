import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown } from 'lucide-react'

/*
 * Themed replacement for native <select> — the OS renders a native select's
 * option popup outside CSS's reach (light chrome, system font, no match to
 * the app's dark theme regardless of styling on the <select> itself).
 *
 * Portals the popup to document.body rather than positioning it inline: any
 * ancestor with a non-'none' transform (e.g. this app's `animation: fade-up
 * ... both`, which leaves `transform: translateY(0)` applied after the
 * animation ends) creates a new containing block, so `position: fixed`
 * nested inside one resolves against that ancestor instead of the viewport.
 * Same reason EventFeed's AcceptedBadge tooltip portals to body.
 *
 * Focus never leaves the trigger button — the active option is tracked via
 * aria-activedescendant, not DOM focus, per the WAI-ARIA combobox pattern.
 * Moving focus into the listbox is the detail that breaks screen-reader
 * announcement and is the most common way a hand-rolled select regresses
 * the accessibility a native <select> gave for free.
 */
const optionIdFor = (listboxId, i) => `${listboxId}-opt-${i}`

export default function Select({ value, onChange, options, ariaLabel }) {
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [rect, setRect] = useState(null)
  const triggerRef = useRef(null)
  const listboxId = useId()
  const optionId = (i) => optionIdFor(listboxId, i)

  const selectedIndex = Math.max(0, options.findIndex((o) => o.value === value))
  const selected = options[selectedIndex]

  const openList = () => {
    if (triggerRef.current) setRect(triggerRef.current.getBoundingClientRect())
    setActiveIndex(selectedIndex)
    setOpen(true)
  }
  const closeList = () => setOpen(false)
  const commit = (i) => {
    onChange(options[i].value)
    closeList()
  }

  useEffect(() => {
    if (!open) return
    const onScrollOrResize = () => {
      if (triggerRef.current) setRect(triggerRef.current.getBoundingClientRect())
    }
    const onDocClick = (e) => {
      if (!triggerRef.current?.contains(e.target)) closeList()
    }
    window.addEventListener('scroll', onScrollOrResize, true)
    window.addEventListener('resize', onScrollOrResize)
    document.addEventListener('mousedown', onDocClick)
    return () => {
      window.removeEventListener('scroll', onScrollOrResize, true)
      window.removeEventListener('resize', onScrollOrResize)
      document.removeEventListener('mousedown', onDocClick)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    document.getElementById(optionIdFor(listboxId, activeIndex))?.scrollIntoView({ block: 'nearest' })
  }, [open, activeIndex, listboxId])

  const handleKeyDown = (e) => {
    if (!open) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
        e.preventDefault()
        openList()
      }
      return
    }
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActiveIndex((i) => Math.min(i + 1, options.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActiveIndex((i) => Math.max(i - 1, 0))
        break
      case 'Home':
        e.preventDefault()
        setActiveIndex(0)
        break
      case 'End':
        e.preventDefault()
        setActiveIndex(options.length - 1)
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        commit(activeIndex)
        break
      case 'Escape':
        e.preventDefault()
        closeList()
        break
      case 'Tab':
        closeList()
        break
      default:
        if (e.key.length === 1) {
          const match = options.findIndex((o) => o.label.toLowerCase().startsWith(e.key.toLowerCase()))
          if (match >= 0) setActiveIndex(match)
        }
    }
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={listboxId}
        aria-activedescendant={open ? optionId(activeIndex) : undefined}
        aria-label={ariaLabel}
        onClick={() => (open ? closeList() : openList())}
        onKeyDown={handleKeyDown}
        className="w-full py-2.5 px-3 rounded-lg text-[12px] outline-none flex items-center justify-between gap-2 text-left transition-colors duration-150"
        style={{
          background: 'var(--elevated)',
          border: open ? '1px solid var(--accent)' : '1px solid var(--border)',
          color: 'var(--hi)',
          cursor: 'pointer',
        }}
      >
        <span className="truncate">{selected?.label}</span>
        <ChevronDown
          size={14}
          aria-hidden="true"
          style={{ flexShrink: 0, color: 'var(--lo)', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 150ms ease' }}
        />
      </button>

      {open && rect && createPortal(
        <div
          id={listboxId}
          role="listbox"
          aria-label={ariaLabel}
          className="fixed rounded-xl py-1.5 text-[12px] overflow-y-auto"
          style={{
            top: rect.bottom + 6,
            left: rect.left,
            width: rect.width,
            maxHeight: 280,
            background: 'var(--elevated)',
            border: '1px solid var(--border)',
            boxShadow: '0 12px 40px rgba(0,0,0,0.7)',
            zIndex: 100,
            animation: 'fade-up 150ms cubic-bezier(0.16,1,0.3,1) both',
          }}
        >
          {options.map((o, i) => (
            <div
              key={o.value}
              id={optionId(i)}
              role="option"
              aria-selected={o.value === value}
              onMouseEnter={() => setActiveIndex(i)}
              onMouseDown={(e) => { e.preventDefault(); commit(i) }}
              className="px-3 py-2 truncate cursor-pointer"
              style={{
                background: i === activeIndex ? 'rgba(139,92,246,0.15)' : 'transparent',
                color: o.value === value ? 'var(--accent-l)' : 'var(--hi)',
                fontWeight: o.value === value ? 600 : 400,
              }}
            >
              {o.label}
            </div>
          ))}
        </div>,
        document.body
      )}
    </>
  )
}
