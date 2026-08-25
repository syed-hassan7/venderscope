---
name: VenderScope
description: Continuous, passive vendor risk intelligence for GRC and Information Security teams
colors:
  bg: "#0B0B10"
  surface: "#15161C"
  elevated: "#1C1D24"
  input-fill: "#20212A"
  line: "#23242C"
  border: "#2A2B34"
  accent: "#8B5CF6"
  accent-hover: "#7C3AED"
  accent-light: "#A78BFA"
  text-primary: "#F5F6FA"
  text-secondary: "#B4B6C2"
  text-tertiary: "#8A8C98"
  risk-high: "#F04438"
  risk-medium: "#F59E0B"
  risk-low: "#10B981"
  risk-critical: "#F43F5E"
typography:
  body:
    fontFamily: "Geist, system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "22px"
  label:
    fontFamily: "Geist, system-ui, -apple-system, sans-serif"
    fontSize: "10px"
    fontWeight: 700
    lineHeight: "16px"
    letterSpacing: "0.14em"
  mono:
    fontFamily: "'JetBrains Mono', ui-monospace, monospace"
    fontSize: "10px"
    fontWeight: 400
rounded:
  ctrl: "8px"
  card: "12px"
  modal: "16px"
  pill: "9999px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#FFFFFF"
    rounded: "{rounded.ctrl}"
    padding: "10px 16px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-secondary:
    backgroundColor: "rgba(255,255,255,0.05)"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.ctrl}"
    padding: "8px 16px"
  input:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.ctrl}"
    padding: "10px 16px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.card}"
    padding: "16px 24px"
  modal:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.modal}"
    padding: "16px 24px"
---

# Design System: VenderScope

## Overview

**Creative North Star: "The Instrument Panel"**

VenderScope's real identity is the dashboard and vendor-detail screens: dense, sober, quiet, built for a GRC/InfoSec analyst who opens it daily and needs to trust what it says at a glance. Dark, near-black surfaces; a single violet accent used sparingly; small confident type; hairline borders instead of shadows. Nothing decorative competes with the data.

The auth screens (Login, Register, Guest Scan) are a deliberate, confirmed exception — a consumer-SaaS-register first-impression moment (radar pulses, drifting orbs, animated logo draw) that the 2026-08-25 design critique found tonally distinct from the rest of the app, and the product owner chose to keep as-is rather than converge. **This split is intentional, not drift.** Do not "fix" the auth screens toward the instrument-panel register, and do not let the auth register bleed into the dashboard.

**Key Characteristics:**
- Near-black surfaces with a single violet accent (`#8B5CF6`), used on ≤10% of any given screen
- Flat by default — hairline borders (`var(--line)` / `var(--border)`) separate surfaces, not shadows
- Small, confident type (11–14px body/labels); large tabular-nums reserved for risk scores only
- One house motion curve (`cubic-bezier(0.16,1,0.3,1)`) everywhere except the auth screens' own register
- Auth screens are the one confirmed exception to all of the above — see Do's and Don'ts

## Colors

Near-black neutrals carry the interface; violet is the only accent; red/amber/green form a strict semantic risk vocabulary that is never reused for anything else (no green "success" toasts, no amber "warning" unrelated to risk).

### Primary
- **Signal Violet** (`#8B5CF6`, hover `#7C3AED`, light `#A78BFA`): the only brand accent. Primary buttons, active tab state, focus rings, links, "BETA" badge dot. Used sparingly — most of the screen is neutral so the accent still reads as a signal, not decoration.

### Neutral
- **Void** (`#0B0B10`) — page background.
- **Surface** (`#15161C`) — panel/card background, one step up from Void.
- **Elevated** (`#1C1D24`) — anything that sits above a panel: modals, popups, inputs, dropdown menus.
- **Input Fill** (`#20212A`) — occasionally used interchangeably with Elevated for form fields; see Do's and Don'ts, these should consolidate to one.
- **Line** (`#23242C`) — hairline separator, the default border for panels and low-emphasis dividers.
- **Border** (`#2A2B34`) — slightly more visible border, used for modals, popups, and anything that needs to read as "above" its surface without a shadow.
- **Text — Hi** (`#F5F6FA`, ~15:1 on Void) — headings, key values, risk scores.
- **Text — Mid** (`#B4B6C2`, ~6.5:1 on Void) — body copy, descriptions, secondary labels.
- **Text — Lo** (`#8A8C98`, ~4.5:1 on Void) — metadata, timestamps, hints. This is the AA floor for body-sized text; nothing goes lower.

### Risk Semantics
The risk-color vocabulary is a closed, load-bearing set. It is not a general-purpose color palette — do not reach for `risk-high` because you want "a red" for something unrelated to vendor risk.

- **High** (`#F04438`) — an orange-leaning coral red. Risk score ≥70.
- **Medium** (`#F59E0B`) — amber. Risk score 40–69.
- **Low** (`#10B981`) — green. Risk score <40.
- **Critical** (`#F43F5E`) — a rose/magenta-leaning red, deliberately a *different hue family* from High, not just a darker or more saturated version of it. Event severity only (CVE/breach severity), not the vendor risk-score band, which only has High/Medium/Low. The hue separation (coral vs. rose) is intentional — Critical needs to be tellable apart from High at a glance, including for a colorblind user where saturation/lightness differences alone are unreliable. Both independently meet WCAG AA (4.5:1+) as text color against Void.

### Named Rules
**The One Accent Rule.** Violet is the only non-semantic color in the system. If a new element needs emphasis and isn't communicating risk, it's violet or it's neutral — never a new arbitrary color.

**The Risk Vocabulary Is Closed Rule.** Red/amber/green mean vendor/event risk and nothing else. A generic error toast is *not* the same red as `risk-high` in feeling even when the hex happens to be reused (`Toast.jsx` deliberately borrows `--risk-high` for error chrome — that's the one sanctioned exception, because a failed action genuinely is a risk signal in this product).

## Typography

**Body Font:** Geist (self-hosted `@font-face`, variable weight 100–900), falling back to system-ui.
**Mono Font:** JetBrains Mono, for dates/timestamps and a handful of monospace data points (confirmation-code inputs).

**Character:** Plain, technical, unadorned — this is a data tool, not an editorial product. No serif, no display face, no personality font anywhere in the instrument-panel world (the auth screens' logo wordmark is the one custom-drawn exception, via SVG stroke animation, not a font).

### Hierarchy
- **Risk Score display** (700 weight, 32–48px, tabular-nums): the single largest text in the app, reserved exclusively for the headline risk-score number. Nothing else gets this treatment.
- **Heading** (600–700 weight, 16–22px): page titles, panel titles, vendor names.
- **Body** (400 weight, 13–14px, ~22px line-height): descriptions, form copy, general text.
- **Label** (700 weight, 10–11px, `0.12em`–`0.14em` letter-spacing, uppercase): section headers inside panels ("DATA SENSITIVITY", "RISK SCORE") — the app's dominant micro-pattern, used far more than any other text style.
- **Meta/mono** (400 weight, 9–10px, tabular-nums): timestamps, counts, secondary numeric data.

### Named Rules
**The Uppercase Label Rule.** Any section header inside a panel is a small (10–11px), bold, wide-tracked, uppercase label in `text-lo`. This is the single most repeated typographic pattern in the app — new panel sections should default to it rather than inventing a new heading style.

## Layout

Content is capped at `max-w-5xl`/`max-w-7xl` depending on page density (VendorDetail vs. Dashboard) and centered, with responsive horizontal padding (`px-4 sm:px-6`). Panels stack vertically with `mb-4` rhythm. Two-column layouts (VendorDetail's score panel) collapse to one column below `xl`. Grids (vendor cards, stat pills) go 1-column on mobile, 2–3 on tablet/desktop. Nothing exotic — a conventional responsive stack, not a custom grid system.

## Elevation & Depth

**Flat by default.** Panels and cards do not use box-shadow at rest — they're separated from the page and each other purely by a one-step lighter background (`Surface` on `Void`) and a hairline `Line` border. This is a deliberate choice, not an oversight: shadows are reserved for things that are genuinely *above* the page (modals, popups, dropdowns), never for resting content.

### Shadow Vocabulary
- **Overlay shadow** (`0 12px 40px rgba(0,0,0,0.7)` to `0 24px 64px rgba(0,0,0,0.8)`): modals, popups, the custom Select's listbox, tooltips. The one context shadows are allowed in.
- **Focus ring** (`0 0 0 3px rgba(139,92,246,0.1)`): input focus state, paired with an accent border — this is a ring, not a shadow, but occupies the same "depth" role of pulling an element forward.

### Named Rules
**The Flat-At-Rest Rule.** If it's not currently floating above the page (modal, popup, dropdown, tooltip), it does not get a box-shadow. Reach for a border or a background-tint step instead.

## Shapes

Three radius steps, used consistently by role, not by size:
- **`ctrl` (8px)** — every interactive control: buttons, inputs, the Select trigger, tab pills, badges' inner elements.
- **`card` (12px)** — panels, cards, the custom Select's listbox popup.
- **`modal` (16px)** — modal shells only (`rounded-2xl` in Tailwind terms).
- **`pill` (9999px)** — badges, chips, the BETA tag, avatar circles.

Borders are 1px, always `Line` or `Border`, never a color from the accent/risk palette except as a low-opacity tint (`rgba(139,92,246,0.25)`, `rgba(240,68,56,0.25)`) for state (selected, error, hover).

## Components

**Quiet and precise.** Every interactive element has a clear, restrained hover/focus state (a background-opacity shift or a border-color change, rarely both, never a scale/bounce), and default states carry almost no visual weight — hierarchy comes from content, not chrome.

### Buttons
- **Shape:** `ctrl` radius (8px).
- **Primary:** Signal Violet fill, white text, `10px 16px` padding, semibold. Hover darkens to `accent-hover`. Reserved for the one primary action per screen (Scan Now, + Add Vendor, Continue with Google).
- **Secondary:** `rgba(255,255,255,0.05)` fill, `text-secondary` color, `rgba(255,255,255,0.08)` border. Hover lightens fill slightly and brightens text to `text-primary`.
- **Destructive:** `#dc2626` fill, white text — reserved for the single confirm button inside a destructive modal (never a default/idle button state).
- **Icon-only:** transparent fill, `text-lo` icon color, hover adds a subtle `Surface`-tint background.

### Cards / Panels
- **Corner:** `card` radius (12px).
- **Background:** `Surface` on `Void`, or `Elevated` when nested one level deeper (a card inside a panel).
- **Border:** 1px `Line`, no shadow (see Elevation).
- **Padding:** `16px` mobile, `24px` desktop (`p-4 sm:p-6`).

### Modals
- **Shell:** `modal` radius (16px), `Surface` background, `Border` (not `Line`) border, overlay shadow, `rgba(0,0,0,0.75)` backdrop with `blur(4px)`.
- **Entrance:** fade + `translateY`/`scale` in on the house curve, ~200ms.
- **Destructive variant** (`DeleteAccountModal`, `VendorDeleteModal`): a red-tinted (`rgba(239,68,68,0.06)` bg, `rgba(239,68,68,0.15)` border) itemized-consequence panel between the header and the action buttons — the pattern for "explain exactly what's lost" before any destructive confirm.

### Inputs / Fields
- **Style:** `ctrl` radius, `Elevated` background (`AddVendorModal`'s plain-text fields use `rgba(255,255,255,0.04)` instead — an inconsistency to consolidate, see Do's and Don'ts), 1px `Line` border at rest.
- **Focus:** border shifts to a low-opacity accent (`rgba(139,92,246,0.5)`) plus a 3px accent-tinted focus ring (`0 0 0 3px rgba(139,92,246,0.1)`). No glow, no scale.
- **Error:** not yet a distinct pattern in the codebase — inherit the destructive-red treatment used in modals if one is needed.

### Select (custom listbox)
The canonical pattern for any choice list too large for inline buttons/tabs. **Never use a native `<select>`** — see Do's and Don'ts.
- **Trigger:** identical shell to a text Input (`ctrl` radius, `Elevated` background, `Line`/accent border), with a `lucide-react` `ChevronDown` that rotates 180° when open.
- **Popup:** `card` radius, `Elevated` background, `Border`, overlay shadow, portaled to `document.body` (see Do's and Don'ts on the transform trap), entrance on the house curve.
- **Selected/active option:** `rgba(139,92,246,0.15)` background, `accent-light` text.
- **Accessibility is the point of this component, not a bonus:** WAI-ARIA combobox pattern, focus stays on the trigger (`aria-activedescendant`, never move focus into the list), full keyboard support (arrows/Home/End/Enter/Escape/Tab/type-ahead), click-outside close.

### Tabs
- **Trigger row:** a pill-shaped tray (`rgba(255,255,255,0.03)` bg, `Line` border, `p-1`) containing individual pill buttons (`ctrl` radius). Active tab: `rgba(139,92,246,0.15)` bg, `accent-light` text. Inactive: transparent, `text-lo`, hover brightens to `text-mid`.
- **Panels stay mounted, hidden via the `hidden` attribute, never unmounted on tab switch** — switching tabs must never discard in-progress state inside a panel (a draft note, a half-filled accept-risk form). This is a correctness rule, not a styling one.

### Toast
- Fixed bottom-right (bottom-full-width on mobile), `Elevated` background, `rgba(240,68,56,0.3)` border (borrows the risk-high red — an error genuinely is a risk signal here), overlay shadow, auto-dismiss ~6s with a manual close. One at a time; no stacking pattern exists yet.

### Badges / Pills
- **Shape:** `pill` radius.
- **Risk badge:** dot + label, `{risk-color}-tint` background (12% opacity), a lighter tint of the risk color as text (not the raw token — see `RiskBadge.jsx`'s `RISK` map for the exact per-level text colors, which are hand-picked for contrast against the tint, not derived from the base hex).
- **Status/meta pills:** neutral (`rgba(255,255,255,0.04–0.1)` bg, `Line`/`border` border, `text-lo`/`text-mid` text) for anything non-risk (BETA tag, sensitivity badges' "No Access" state).

### Navigation
- **Top nav:** 52px, `Void` background, `Line` bottom border, sticky. Logo/wordmark left, icon-only action buttons right (bell, user menu). User menu is a `framer-motion` popup — this one doesn't need a portal (its ancestor `<nav>` has no lingering transform), see Do's and Don'ts for when a portal *is* required.

## Do's and Don'ts

### Do:
- **Do** use the house motion curve `cubic-bezier(0.16,1,0.3,1)` for every entrance/exit animation outside the auth screens' own register (fade-ups, modal entrances, popup entrances, tab transitions).
- **Do** portal any popup/overlay that's positioned `fixed` and sits inside — or could ever sit inside — an ancestor with `animation: ... both` or any other persistent `transform`. `Panel`'s `fade-up ... both` leaves `transform: translateY(0)` applied forever after the animation completes, and any non-`none` transform creates a new containing block that silently breaks naive `position: fixed` children. Check for this before writing a new inline-positioned overlay; `Select.jsx` and `EventFeed.jsx`'s `AcceptedBadge` are the reference implementations.
- **Do** keep DOM focus on a control's trigger element for any custom listbox/menu/combobox; track the active item via `aria-activedescendant`, not by moving focus into the popup. This is the detail that most commonly breaks screen-reader announcement in a hand-rolled replacement for a native control.
- **Do** wrap `.animate-spin`/`.skeleton` (or any future in-progress indicator) out of the global `prefers-reduced-motion` freeze — a frozen spinner during a multi-minute operation reads as a hung app, not as "motion respectfully reduced."
- **Do** treat the auth screens (Login/Register/GuestScan) as the one confirmed exception to this entire document's "sober instrument panel" register. That split was a deliberate product decision, not drift to be corrected.

### Don't:
- **Don't** use a native `<select>` for anything the user needs to actually read against this theme. A native select's option popup is OS-rendered, not page-rendered — no CSS reaches it (`colorScheme: 'dark'` is not a fix, it's a partial nudge some browsers ignore entirely), and it will render a plain light system dropdown floating over the dark theme regardless of how the trigger is styled. Use `components/Select.jsx`.
- **Don't** unmount a tab panel, accordion section, or any container that might hold in-progress user input (a draft, a partially-filled form) on visibility toggle. Hide it (`hidden` attribute / `display: none`); state must survive a round-trip.
- **Don't** introduce a second red, amber, or green outside the risk-semantic set (`risk-high`/`risk-medium`/`risk-low`/`risk-critical`) for anything unrelated to vendor/event risk. If something needs to feel urgent without being a risk signal, that's a design conversation, not a hex-picking exercise.
- **Don't** add a box-shadow to anything at rest (a card, a panel, a badge). Shadows are reserved for overlays that are genuinely above the page — see Elevation.
- **Don't** reach for an overshoot/back-out easing curve (`cubic-bezier(x,>1,x,x)`) outside the auth screens. It reads as consumer-SaaS bounce, which is precisely the register the dashboard/detail screens are not.
- **Don't** silently swallow an error in a `catch` block with only `console.error` (or omit the `catch` entirely) on any user-triggered action. Every action a user takes that can fail must surface that failure — via `Toast` for background actions, inline error text for actions inside a modal/form. This is the product's own stated principle (`PRODUCT.md`): a silent failure is worse than a visible one, because the value proposition is "you can trust what this dashboard says right now."
