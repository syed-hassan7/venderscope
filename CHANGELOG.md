# Changelog

Historical release notes for VenderScope, extracted from `README.md` to keep it concise. The current/newest release lives in the README under "Latest Release" — it moves here once superseded by the next version.

---

## v4.0 — Scan Efficiency, Persistent Quota, and UX Polish

v4.0 is a full product-quality release that improves scan economics, persistence, compliance discovery coverage, and the day-to-day UX of the dashboard and vendor analysis flow.

- **Database-backed search quota enforcement** — Google Custom Search usage no longer lives in a local `quota.json` file. Quota is now persisted in PostgreSQL/SQLite via a dedicated `SearchQuotaUsage` model, so it survives Render restarts and redeploys
- **Incremental quota charging** — full scans no longer burn a worst-case fixed quota cost up front. Search quota is consumed only when an actual external compliance/contact web search is performed, which materially increases practical daily scan capacity on the free tier
- **Quota hardening pass** — quota mutations are now database-backed, concurrency-aware, and failed Google CSE requests refund their reserved unit instead of silently burning the daily budget
- **Broader compliance discovery** — the compliance engine now does a bounded crawl of high-signal same-site trust, legal, privacy, DPA, and security pages instead of relying on just the homepage plus a small set of direct probes. This improves detection of obvious vendor-owned compliance evidence
- **Redirect-safe discovery** — same-site relative redirects are now resolved correctly during compliance and vendor-profile discovery, which closes a subtle quality gap on trust/security/legal pages
- **Safer standard-mode fallback** — when search quota is exhausted, scans still run and fall back cleanly to standard discovery instead of blocking the user-facing scan action
- **Single-owner scheduler lease** — nightly scans, keep-alive pings, and revoked-token cleanup now run behind a database-backed lease so only one app instance owns background jobs at a time
- **Privacy-safe vendor logo discovery** — vendor cards and vendor detail headers now prefer same-site icon metadata discovered from the vendor's own homepage, then fall back to direct favicon paths on the same domain, and finally to the original gradient avatar. No third-party favicon proxy is used, so viewed vendor domains are not leaked to external logo services
- **Vendor detail redesign** — the old drift/gauge-heavy top area was replaced with a denser overview panel covering score, exposure basis, scoring model, sensitivity controls, and review scheduling with significantly cleaner hierarchy
- **Time handling fixes** — API timestamps are now normalized consistently in the frontend so a freshly completed scan no longer appears as if it happened an hour earlier due to naive UTC parsing
- **Risk-events empty state** — vendors with no public findings now show a proper informational panel explaining what "no events detected" means, instead of a bare empty state
- **Consent/settings polish** — cookie settings actions now match the hover behavior of the rest of the UI

Verification after this release:

- `python -m pytest` → `70 passed`
- `npm run build` → passed

---

## v4.5 — Infrastructure Migration & Security Hardening

Render free tier compute hours were exhausted (191.9h/month depleted in ~8 days due to always-on connection pooling). Neon PostgreSQL free tier compute quota was simultaneously exhausted. Both services were migrated to genuinely free alternatives with no compute time quotas.

- **Backend:** Render → Hugging Face Spaces (Docker, 2vCPU/16GB RAM, no compute quota). Deployed via GitHub Actions on push to `backend/`
- **Database:** Neon PostgreSQL → Supabase PostgreSQL (500MB free tier, no compute quota, pauses only after 7 days of zero traffic)
- **Keep-alive:** UptimeRobot pings `https://darkitowo-venderscope-api.hf.space/` every 5 minutes — prevents HF sleep and keeps APScheduler alive
- **`is_production()` generalised:** No longer keys on the `RENDER` env var; now uses `ENV=production` for portability across any host
- **SSL fix for Supabase pooler:** `database.py` disables certificate hostname verification (`ssl.CERT_NONE`) to accommodate Supabase's self-signed certificate in the pooler chain while retaining SSL encryption

---

## Maintenance Pass — Mobile UX, Notes Hardening, Config Safety

This repo has had a full cleanup and stabilization pass across backend safety, frontend logic, and responsive UX.

- **Mobile-first responsive refactor** — Dashboard, Vendor Detail, auth screens, guest scan, cards, charts, modals, footer, and supporting layouts were rebuilt to behave cleanly on modern iPhone and Pixel widths using `100dvh`, safe-area-aware spacing, stacked action rows, and tighter mobile panel spacing
- **Analyst notes redesign + hardening** — the notes section was rebuilt to match the existing product style, note input is now normalized as untrusted plain text on the backend, and regression tests cover control-character stripping plus SQL-looking payloads being treated as inert text
- **Safer backend configuration** — environment loading is centralized, CORS/origin validation now uses shared config instead of drift-prone hardcoded values, and auth origin checks follow the same allowed-origin rules
- **Email/test safeguards** — `EMAIL_ENABLED=0` can disable outbound email, reserved test domains are suppressed, and backend tests are pinned to a dedicated SQLite test database so destructive test setup cannot touch production Neon data
- **Scan and dashboard logic fixes** — `Scan All` now uses the real bulk endpoint, dashboard risk thresholds are aligned with backend logic, and missing-vendor detail pages fail gracefully instead of hanging in a loading state
- **Frontend cleanup** — route-level lazy loading and vendor chunking reduced the entry bundle, unused dependencies were removed, `follow-redirects` was pinned above the vulnerable range, and the audit/build/lint path is clean
- **Cookie consent without auth degradation** — the site now exposes a real cookie-settings flow that lets users decline optional cookies while keeping the strictly necessary auth refresh cookie active so login/session continuity remains intact

Verification after this pass:

- `python -m pytest -q` → `63 passed`
- `npm run lint` → passed
- `npm run build` → passed

---

## v3.7 — UI/UX Overhaul & Brand Identity

v3.7 is a frontend-focused release centred on visual polish and brand identity ahead of a production demo. No backend changes.

### VS Wordmark Logo

A custom `VSLogo` component renders the official VS wordmark as an inline SVG with a sequential stroke-draw animation — the V left leg, V right leg, and S each draw in independently using `pathLength="1"` + `stroke-dashoffset` keyframes. The logo appears in the Dashboard header, VendorDetail navigation bar, and Footer, replacing all previous text-based and icon-based brand marks.

### Login & Register Page Overhaul

Both auth pages were fully redesigned with a layered background system and staggered entrance animations:

- **Looping background traces** — four curved SVG paths stroke-draw in and loop with staggered timing (7–10s cycles), directly mirroring the VS logo draw animation. The background is perpetually alive without being distracting.
- **Radar pulse rings** — on page load, three concentric rings expand outward from the card centre and fade, creating a "system initialising" sonar effect. Plays once.
- **Morphing ambient orbs** — the floating violet gradient orbs now animate `border-radius` alongside position and scale, shifting between organic blob shapes for a living, nebula-like feel.
- **Dot-grid overlay** — a fixed radial-gradient dot grid covers the viewport as a subtle structural layer.
- **Glassmorphism card** — `backdrop-filter: blur(28px)` with a semi-transparent background and violet border accent.
- **Staggered entrance** — every element fades and lifts in sequentially using a double-`requestAnimationFrame` technique to guarantee clean paint timing.
- **Responsive auth shell** — login/register now use a scroll-safe `100dvh` layout instead of a fixed `100vh` shell, so mobile browser chrome and on-screen keyboards do not break the page.

### Text Color Standardization

A consistent four-level text palette is now applied across all pages:

| Token | Hex | Contrast | Use |
|-------|-----|----------|-----|
| `--hi` | `#f0f0ff` | 14:1 | Headings, key values |
| `--mid` | `#b8b8d0` | 6.5:1 | Body text, descriptions |
| `--lo` | `#8080aa` | 4.8:1 | Labels, metadata, hints |
| `--lo2` / `#44445a` | — | decorative | Separator dots and dashes only |

### GRC Polish (v3.6 continuation)

- **VendorCard review status** — cards now show a live "Review overdue by Xd" (amber) or "Review: MMM D" (muted) line when a review schedule is set
- **Dashboard Reviews Due pill** — redesigned as an amber glassmorphism pill with a clock icon and hover tooltip listing overdue vendor names
- **PDF export enrichment** — vendor reports now include a review schedule section and a Risk Acceptances table (finding reference, type, justification, reviewer, expiry, active/expired status)

---

## v3.6 — GRC Workflow Features

v3.6 introduces four features designed specifically for GRC and Information Security professionals — moving VenderScope from a monitoring dashboard into a lightweight risk management tool. Every feature works entirely on existing infrastructure with zero additional cost.

### Analyst Notes — Vendor Evidence Log

A timestamped, append-only note log attached to each vendor record. Designed for the annotations GRC teams make throughout a vendor relationship: risk decisions, conversations, follow-up actions, and review outcomes.

- **Per-vendor log** — add timestamped free-text notes directly on the vendor detail page
- **Immutable by design** — notes can be deleted but not edited, preserving audit integrity
- **Ctrl+Enter shortcut** — quick keyboard submission without leaving context
- **Included in PDF export** — notes appear as an "Analyst Notes" section in the vendor risk report, making them available as evidence in ISO 27001 and SOC 2 reviews
- **Fully scoped** — notes are isolated to the user who created them; no cross-user visibility

### Periodic Review Scheduling — Never Miss a Vendor Review

GRC teams are obligated to review vendors on a defined cycle. This feature brings that obligation into the tool itself rather than a separate spreadsheet or calendar.

- **Set a review interval** — choose from 30 / 60 / 90 / 180 days or annually, per vendor
- **Mark as Reviewed** — one-click button stamps the current timestamp as the last review date
- **Live review status** — VendorDetail shows either "Next review: [date]" (green) or "Overdue by X days" (amber)
- **Dashboard indicator** — a "Reviews Due" count pill appears in the stats row when any vendor is overdue, with vendor names shown on hover
- **No email dependency** — entirely in-app; works without a verified Resend domain

### Risk Acceptance Workflow — Documented, Auditable Risk Decisions

The most significant gap in the tool's GRC capability: surfacing a risk is not enough — teams must formally document when they choose to accept rather than remediate. This is a direct requirement under ISO 27001 (Annex A.5.20) and SOC 2.

- **Per-event acceptance** — each risk event in the feed has an "Accept Risk" button
- **Documented acceptance form** — records justification text, reviewer name, and expiry date (default 90 days; max 1 year)
- **Amber "ACCEPTED" badge** — accepted events show a distinct badge instead of the severity indicator; the badge shows acceptance details on hover
- **Automatic expiry** — acceptances with a past expiry date become inactive; the event resurfaces with its original severity badge, prompting re-review
- **One-click revoke** — revoke an acceptance early if the decision changes
- **Needs Attention logic** — the dashboard only surfaces vendors as needing attention if they have unaccepted rising events
- **Full audit trail** — every acceptance and revocation is recorded in the append-only audit log with user ID, timestamp, and finding reference

### Risk Register Export — CSV for Audit Evidence Packs

GRC teams maintain risk registers that are manually populated from scan results. This feature closes that gap with a single click.

- **"Export Register" button** on the Dashboard header
- **12-column CSV** — Vendor Name, Domain, Data Sensitivity, Technical Score, Effective Exposure Score, Risk Band, Score Delta, Last Scanned, Review Interval, and Export Date
- **Client-side generation** — no server roundtrip; produces a download-ready `.csv` immediately
- **Filename includes date** — `vendorscope_risk_register_YYYY-MM-DD.csv`
- **Maps directly to risk registers** — columns align with standard ISO 27001 risk treatment plans and SOC 2 vendor management evidence

### Business Context Weighting — Effective Exposure Score

_(Shipped in v3.5.x — documented here for completeness)_

Raw CVE scores treat a payment processor the same as a marketing tool. Business context weighting corrects this by applying a data sensitivity multiplier to the technical risk score.

- **Per-vendor sensitivity tier** — set the data type this vendor handles: None (×0.8), Standard (×1.0), PII (×1.4), Financial/Auth (×1.6), Health (×1.8), Critical Infrastructure (×2.0)
- **Effective Exposure Score** — the adjusted score is shown as the primary metric throughout the dashboard, VendorCard, and PDF export
- **Pill-button selector** — styled to match the app's design system; no native browser controls

---

## v3.5

### Guest Mode — Try Before You Register

VenderScope now lets anyone run a quick CVE lookup without creating an account.

- **No account required** — accessible from the login page via "Try as Guest →"
- **CVE-only scan** — queries NIST NVD for known vulnerabilities associated with the vendor name
- **Instant risk score** — same weighted 0–100 scoring engine as full scans, based on CVE signals
- **PDF download** — export a guest report clearly watermarked as a partial scan
- **Zero data persistence** — results are computed and returned; nothing is written to the database
- **Clear limitations banner** — guests are shown exactly what is missing (breach data, Shodan, compliance, profiling) and invited to register for a full scan

### v3.5 Security Hardening

A full security audit was conducted before guest mode launch. Findings resolved:

- **Rate limit IP bypass (HIGH)** — `_real_ip()` was using `XFF[0]` (client-controlled) for rate limiting. Since rate limiting is the *only* gate on unauthenticated endpoints, this was critical. Fixed to `XFF[-1]` (Render-appended, unforgeable) — now consistent with the audit log fix applied in v3.1
- **Missing Content-Security-Policy (MEDIUM)** — CSP added to `vercel.json` as a Vercel response header (`frame-ancestors 'none'`, `connect-src` locked to the API origin, `object-src 'none'`)
- **55/55 security tests passing** — 23 new tests covering SSRF blocks, zero DB write verification, input validation, XML injection handling, invalid severity/score/event limits, and PDF generation

---

## v3.1.5

### Authentication & Multi-User Support
- **JWT authentication** — access token stored in memory (15min expiry), refresh token in `httpOnly` `SameSite=None; Secure` cookie (7 days, single-use rotation)
- **Register / Login / Logout** — full auth flow with bcrypt password hashing (12 rounds)
- **Per-user vendor isolation** — every database query is scoped to the authenticated user; no user can see or scan another user's vendors
- **Silent token refresh** — `AuthContext` silently renews the access token on mount and 401, keeping sessions seamless
- **Password complexity rules** — minimum 12 characters, requires at least one uppercase letter and one digit; enforced on both frontend and backend
- **Confirmation email on registration** — welcome email sent via Resend HTTP API (Gmail SMTP fallback for local dev)

### Security Hardening
- **JTI blacklist** — single-use refresh tokens; each rotation revokes the previous token's JWT ID; logout immediately invalidates the current refresh token
- **Append-only audit log** — every security event (`login.success`, `login.failed`, `logout`, `register.success`, `vendor.added`, `vendor.deleted`, `vendor.scanned`, `export.pdf`, `account.deleted`, `token.refreshed`) is recorded with IP address and timestamp
- **Security headers middleware** — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Strict-Transport-Security` (HSTS in production)
- **FRONTEND_URL startup validation** — server refuses to start if `FRONTEND_URL` is missing or misconfigured in production
- **UUID vendor IDs** — vendor primary keys are UUIDs (not sequential integers), preventing IDOR enumeration
- **bcrypt DoS protection** — max password length enforced at login to prevent billion-hash attacks
- **All 20 audit vulnerabilities resolved** (see `docs/security-architecture.md`)

### Infrastructure
- **PostgreSQL (Supabase)** — migrated from SQLite to cloud PostgreSQL for production; SQLite retained for local dev
- **pg8000 pure-Python driver** — compatible with Python 3.14+, no C dependencies, works on Render without build tools
- **Connection pool** — `pool_pre_ping`, `pool_size=5`, `max_overflow=10` for stable cloud connections
- **Revoked token cleanup** — APScheduler purges expired JTI blacklist entries every 6 hours

### UI & Account Management
- **Delete Account** — 2-step confirmation flow (warning → type "DELETE" → password reconfirmation); cascades to all vendor data
- **Footer** — privacy policy, terms, and security documentation links; subtle delete account trigger
- **Legal & security docs** — `/privacy`, `/terms`, `/security` pages rendered from markdown

---

## v3.1

### Security Hardening (Secondary Audit)
- **Real-IP rate limiting** — uvicorn now runs with `--proxy-headers`, correctly resolving per-client IPs behind Render's load balancer. Previously all users shared one rate-limit bucket.
- **CSRF origin validation** — `logout`, `refresh`, and `delete_account` endpoints now verify the `Origin`/`Referer` header against `FRONTEND_URL` as a defence-in-depth layer on top of CORS
- **Password reconfirmation on deletion** — account deletion now requires the user's current password, protecting against brief access-token compromise
- **Hardened SSRF protection** — `_is_safe_domain()` now blocks URL-encoded IPs (`127%2E0%2E0%2E1`), decimal/octal notation, IPv6-mapped IPv4 addresses, and cloud metadata endpoints (GCP, Azure, Alibaba); redirect chains are followed manually (max 3 hops, each validated)
- **HIBP exact domain matching** — replaced substring match (which produced false positives) with exact match + www-normalisation; added 1hr in-process cache to avoid re-fetching 1MB breach list on every scan
- **Injection prevention** — `xml.sax.saxutils.escape` applied to all external data in PDF export (ReportLab); `html.escape` applied to all external data in email alert templates
- **Quota file thread-safety** — `threading.RLock()` protecting concurrent reads/writes from `ThreadPoolExecutor` scan workers
- **Refresh token lifetime** — reduced from 30 days to 7 days (industry standard for rotation-based tokens)
- **Stale config removed** — SQLite `DATABASE_URL` removed from `render.yaml` (would have silently overridden the PostgreSQL secret if cleared)

### Alerts (Code Complete — Pending Production Domain)
- **Resend HTTP API** — rebuilt alerts dispatcher; uses Resend if a verified sending domain is configured, falls back to Gmail SMTP automatically
- **Per-user alert emails** — scan alerts now go to the vendor owner's registered email, not a hardcoded address
