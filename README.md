# VenderScope

> **Still running annual vendor audits? Your next breach won't wait 12 months.**

[![Live Beta - v4.5](https://img.shields.io/badge/Live%20Demo-venderscope.vercel.app-6366f1?style=for-the-badge)](https://venderscope.vercel.app)
[![API](https://img.shields.io/badge/API-darkitowo--venderscope--api.hf.space-10b981?style=for-the-badge)](https://darkitowo-venderscope-api.hf.space/docs)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Zarak%20Hassan-0A66C2?style=for-the-badge&logo=linkedin)](https://www.linkedin.com/in/zarak-hassan7/)
[![Version](https://img.shields.io/badge/version-v4.5-violet?style=for-the-badge)](https://github.com/darkyzowo/venderscope/releases)

> **Performance note:** VenderScope backend runs on Hugging Face Spaces (Docker, 2vCPU/16GB RAM). Free-tier Spaces still idle-sleep on inactivity — UptimeRobot pings every 5 minutes to minimize that, but a cold boot (~30–50s) can still happen after a gap in traffic or an HF-side restart. Actual scan time once warm is 8–15s using concurrent API calls to HIBP, NVD, Companies House, Shodan, and the compliance engine simultaneously.

VenderScope is a continuous, passive vendor risk intelligence platform built for GRC and Information Security professionals. Instead of point-in-time annual reviews, VenderScope monitors your vendor estate 24/7 across multiple threat intelligence sources and surfaces risk drift in real time — with full user authentication, production-grade security hardening, and a cloud PostgreSQL backend.

---

## What's New in v4.0 — Scan Efficiency, Persistent Quota, and UX Polish

v4.0 is a full product-quality release that improves scan economics, persistence, compliance discovery coverage, and the day-to-day UX of the dashboard and vendor analysis flow.

- **Database-backed search quota enforcement** — Google Custom Search usage no longer lives in a local `quota.json` file. Quota is now persisted in PostgreSQL/SQLite via a dedicated `SearchQuotaUsage` model, so it survives Render restarts and redeploys
- **Incremental quota charging** — full scans no longer burn a worst-case fixed quota cost up front. Search quota is consumed only when an actual external compliance/contact web search is performed, which materially increases practical daily scan capacity on the free tier
- **Quota hardening pass** — quota mutations are now database-backed, concurrency-aware, and failed Google CSE requests refund their reserved unit instead of silently burning the daily budget
- **Broader compliance discovery** — the compliance engine now does a bounded crawl of high-signal same-site trust, legal, privacy, DPA, and security pages instead of relying on just the homepage plus a small set of direct probes. This improves detection of obvious vendor-owned compliance evidence
- **Redirect-safe discovery** — same-site relative redirects are now resolved correctly during compliance and vendor-profile discovery, which closes a subtle quality gap on trust/security/legal pages
- **Safer standard-mode fallback** — when search quota is exhausted, scans still run and fall back cleanly to standard discovery instead of blocking the user-facing scan action
- **Single-owner scheduler lease** — nightly scans, keep-alive pings, and revoked-token cleanup now run behind a database-backed lease so only one app instance owns background jobs at a time
- **Privacy-safe vendor logo discovery** — vendor cards and vendor detail headers now prefer same-site icon metadata discovered from the vendor’s own homepage, then fall back to direct favicon paths on the same domain, and finally to the original gradient avatar. No third-party favicon proxy is used, so viewed vendor domains are not leaked to external logo services
- **Vendor detail redesign** — the old drift/gauge-heavy top area was replaced with a denser overview panel covering score, exposure basis, scoring model, sensitivity controls, and review scheduling with significantly cleaner hierarchy
- **Time handling fixes** — API timestamps are now normalized consistently in the frontend so a freshly completed scan no longer appears as if it happened an hour earlier due to naive UTC parsing
- **Risk-events empty state** — vendors with no public findings now show a proper informational panel explaining what "no events detected" means, instead of a bare empty state
- **Consent/settings polish** — cookie settings actions now match the hover behavior of the rest of the UI

Verification after this release:

- `python -m pytest` → `70 passed`
- `npm run build` → passed

---

## What's New in v4.5 — Infrastructure Migration & Security Hardening

Render free tier compute hours were exhausted (191.9h/month depleted in ~8 days due to always-on connection pooling). Neon PostgreSQL free tier compute quota was simultaneously exhausted. Both services were migrated to genuinely free alternatives with no compute time quotas.

- **Backend:** Render → Hugging Face Spaces (Docker, 2vCPU/16GB RAM, no compute quota). Deployed via GitHub Actions on push to `backend/`
- **Database:** Neon PostgreSQL → Supabase PostgreSQL (500MB free tier, no compute quota, pauses only after 7 days of zero traffic)
- **Keep-alive:** UptimeRobot pings `https://darkitowo-venderscope-api.hf.space/` every 5 minutes — prevents HF sleep and keeps APScheduler alive
- **`is_production()` generalised:** No longer keys on the `RENDER` env var; now uses `ENV=production` for portability across any host
- **SSL fix for Supabase pooler:** `database.py` disables certificate hostname verification (`ssl.CERT_NONE`) to accommodate Supabase's self-signed certificate in the pooler chain while retaining SSL encryption

---

## Known Limitations & Deferred Work

### Shodan (Exposed Infrastructure)
- **Search API requires a paid Shodan membership.** On a free-tier `SHODAN_API_KEY`, `check_shodan_exposure()`'s `api.search()` call gets a 403 on every scan and the source silently returns zero events. A vendor scanned on a free key will always show "no Shodan findings" regardless of real exposure — that reads as "clean," not "not checked." Upgrading the key or swapping to a free-tier-compatible endpoint (e.g. per-IP `host()` lookups) would restore this signal.

### Email (Transactional)
- **HF Spaces blocks outbound SMTP** — ports 587 and 465 return `[Errno 101] Network is unreachable`. Gmail SMTP will never work on HF.
- **Resend requires a verified custom domain** — `venderscope.app` is a placeholder; no domain is currently owned. Resend code is complete (`alerts.py`); it just needs a real domain pointed at it.
- **Current state:** welcome emails and alert emails are silently skipped on HF. No broken logs, no user-facing errors.
- **To fix:** buy a domain (e.g. `venderscope.app` ~$14/yr), add Resend DNS records (DKIM TXT + SPF MX/TXT), set `RESEND_API_KEY` + `RESEND_FROM_EMAIL=noreply@<domain>` in HF env vars. All send logic already exists.

### Password Reset / Profile Page
- No password reset flow exists. Custom auth (bcrypt + JWT) — Supabase Auth is not used.
- Plan: `PasswordResetToken` model + `POST /api/auth/forgot-password` + `POST /api/auth/reset-password` + `/reset-password` frontend page. Blocked on email working first.

---

## Latest Maintenance Update

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

## What's New in v3.7 — UI/UX Overhaul & Brand Identity

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

## What's New in v3.6 — GRC Workflow Features

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

## What's New in v3.5

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

## What's New in v3.1.5

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

## What's New in v3.1

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

---

## Features

### Monitoring & Intelligence
- **Continuous Passive Monitoring** — Automatically scans vendors every 24 hours with zero manual effort
- **Multi-Source Intelligence** — Aggregates risk signals from HIBP, NVD (NIST), Companies House, and Shodan simultaneously
- **Live Risk Scoring** — Weighted severity scoring engine (0–100) with CRITICAL/HIGH/MEDIUM/LOW classification
- **Business Context Weighting** — Per-vendor data sensitivity multiplier produces an Effective Exposure Score that reflects business risk, not just technical signals
- **Risk Score Drift Timeline** — Area chart showing how a vendor's risk posture changes over time
- **Vendor Profile Auto-Discovery** — Passively detects description, authentication method, and 2FA support from public pages
- **Third-Party Certification Attribution** — Distinguishes vendors who hold certs directly vs those referencing their infrastructure providers' certs
- **UK-Native Governance** — Companies House integration flags financial distress, overdue filings, and director changes
- **Exposed Infrastructure Detection** — Shodan flags dangerous open ports (RDP, SMB, MongoDB, etc.)
- **24hr Intelligent Caching** — Repeat scans return instantly; nightly scheduler forces fresh data overnight
- **Two-Stage Compliance Discovery** — Scrapes vendor pages for ISO 27001, SOC 2, GDPR, Cyber Essentials, PCI DSS evidence; Google CSE fallback when direct scraping is insufficient
- **Verified Security Contacts** — Finds security/privacy contacts via RFC 9116 `security.txt`, page scraping, and web search
- **Scan Quota Tracker** — Live banner showing remaining Google CSE quota with automatic daily reset
- **Client-side Vendor Logos** — Vendor avatars attempt to load the vendor site's favicon/logo before falling back to the deterministic gradient monogram

### GRC Workflow (v3.6)
- **Analyst Notes** — Timestamped evidence log per vendor; included in PDF export; append-only for audit integrity
- **Periodic Review Scheduling** — Set review intervals per vendor; track overdue reviews on the dashboard
- **Risk Acceptance Workflow** — Formally document accepted risks with justification, reviewer, and expiry; full audit trail
- **Risk Register Export** — One-click CSV export of the full vendor estate, formatted for ISO 27001 risk treatment plans

---

## Tech Stack

| Layer         | Technology                                                                   |
|---------------|------------------------------------------------------------------------------|
| Backend       | Python 3.11+, FastAPI, SQLAlchemy 2.0, APScheduler, Uvicorn                 |
| Database      | PostgreSQL (Supabase, production) / SQLite (local dev)                       |
| DB Driver     | pg8000 (pure Python, Python 3.14+ compatible)                                |
| Authentication| JWT (python-jose), bcrypt, httpOnly cookies                                  |
| Frontend      | React 19, Vite 8, React Router 7, TailwindCSS 3, Axios                      |
| Intelligence  | HIBP API, NVD/NIST API, Companies House API, Shodan API                      |
| Compliance    | Google Custom Search API, BeautifulSoup4, security.txt                       |
| Email         | Resend HTTP API (production) / Gmail SMTP (local dev)                        |
| PDF Export    | ReportLab                                                                    |
| Rate Limiting | SlowAPI                                                                      |

---

## Intelligence Sources

| Source              | What it detects                                                              |
|---------------------|------------------------------------------------------------------------------|
| **HaveIBeenPwned**  | Domain breach exposure across all known data breaches                        |
| **NVD (NIST)**      | CVEs associated with vendor products and services                            |
| **Companies House** | UK company status, overdue filings, director resignations                    |
| **Shodan**          | Exposed ports and services on vendor infrastructure                          |
| **Google CSE**      | External certification evidence for ISO 27001, SOC 2, DPA, and more         |
| **Vendor Profile**  | Homepage meta description, auth method, and 2FA support (passive scrape)    |

---

## Architecture

```
VenderScope/
├── backend/
│   ├── main.py                   # FastAPI app, CORS, security headers, lifespan
│   ├── models.py                 # Vendor, RiskEvent, RiskScoreHistory, User,
│   │                             #   RevokedToken, AuditLog, VendorNote,
│   │                             #   RiskAcceptance (SQLAlchemy)
│   ├── database.py               # PostgreSQL + SQLite connection (pg8000, ssl_context)
│   ├── scheduler.py              # 24hr scan + 6hr JTI cleanup + 10min keep-alive
│   ├── routers/
│   │   ├── auth.py               # Register, login, refresh, logout, /me, delete account
│   │   ├── vendors.py            # Vendor CRUD, notes, review scheduling (all user-scoped)
│   │   ├── acceptances.py        # Risk acceptance lifecycle (create, list, revoke)
│   │   ├── intelligence.py       # Scan trigger endpoints
│   │   ├── dashboard.py          # Aggregate stats, needs attention, overdue reviews
│   │   ├── export.py             # PDF export (Content-Disposition sanitised)
│   │   └── quota.py              # Global search quota status
│   └── services/
│       ├── scanner.py            # Concurrent scan orchestrator + caching
│       ├── auth_service.py       # JWT encode/decode, password hash, get_current_user
│       ├── audit.py              # Append-only security event recorder
│       ├── alerts.py             # Resend HTTP API + Gmail SMTP dispatcher
│       ├── compliance_discovery.py  # Two-stage compliance + cert discovery
│       ├── vendor_profile.py     # Passive vendor description, auth & 2FA discovery
│       ├── quota.py              # DB-backed global Google CSE quota tracker
│       ├── hibp.py               # HIBP breach intelligence
│       ├── nvd.py                # NVD CVE intelligence
│       ├── companies_house.py    # UK governance checks
│       ├── shodan_service.py     # Exposed infrastructure checks
│       └── pdf_export.py         # ReportLab PDF generator
└── frontend/
    └── src/
        ├── pages/
        │   ├── Login.jsx             # Auth: login form + deleted account banner
        │   ├── Register.jsx          # Auth: register with client-side complexity rules
        │   ├── Dashboard.jsx         # Main vendor overview
        │   ├── VendorDetail.jsx      # Per-vendor risk detail + profile panel
        │   └── DocPage.jsx           # Lightweight markdown renderer for /privacy, /terms, /security
        ├── components/
        │   ├── VendorCard.jsx        # Risk score card
        │   ├── ScoreChart.jsx        # Lightweight SVG drift timeline chart
        │   ├── EventFeed.jsx         # Risk events list
        │   ├── AddVendorModal.jsx    # Add vendor form
        │   ├── CompliancePanel.jsx   # Compliance posture with badge system
        │   ├── QuotaBanner.jsx       # Daily scan quota tracker
        │   ├── Footer.jsx            # Links to docs + delete account trigger
        │   └── DeleteAccountModal.jsx # 2-step account deletion (type "DELETE" to confirm)
        ├── contexts/AuthContext.jsx  # JWT access token in memory, silent refresh
        ├── docs/
        │   ├── privacy.md
        │   ├── terms.md
        │   └── security.md
        └── api/client.js            # Axios client, auth headers, token refresh
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- API keys for: NVD, Companies House, Shodan, Google Custom Search

### Backend

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env`:

```env
# Intelligence APIs
NVD_API_KEY=your_key
COMPANIES_HOUSE_API_KEY=your_key
SHODAN_API_KEY=your_key
GOOGLE_CSE_API_KEY=your_key
GOOGLE_CSE_ID=your_cse_id

# Email (local: Gmail SMTP; production: Resend with verified domain)
GMAIL_ADDRESS=your@gmail.com
GMAIL_APP_PASSWORD=your_app_password
EMAIL_ENABLED=1
# Set EMAIL_ENABLED=0 for local test runs or anytime you want to hard-disable outbound email
# RESEND_API_KEY=re_...           # Uncomment when you have a verified sending domain
# RESEND_FROM_EMAIL=VenderScope <alerts@yourdomain.com>
ALERT_THRESHOLD=70

# Auth
JWT_SECRET=your_64_char_hex_secret

# Frontend (must match your deployed frontend URL in production)
FRONTEND_URL=http://localhost:5173

# Database (PostgreSQL for production, SQLite for local)
DATABASE_URL=sqlite:///./vendorscope.db
# DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
```

```bash
uvicorn main:app --reload
# API: http://127.0.0.1:8000
# Docs: http://127.0.0.1:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

Create `frontend/.env.local`:

```env
VITE_API_URL=http://127.0.0.1:8000/api
```

---

## Authentication

VenderScope uses a **dual-token JWT scheme**:

| Token | Storage | Expiry | Purpose |
|-------|---------|--------|---------|
| Access token | JS memory (never localStorage) | 15 minutes | Bearer auth on every API request |
| Refresh token | `httpOnly` `SameSite=None; Secure` cookie | 7 days | Silently issues new access tokens (single-use) |

**Token rotation:** Every refresh issues a new refresh token and immediately revokes the previous token's JWT ID (JTI) in the database. Replayed refresh tokens are rejected.

**Logout:** Instantly blacklists the current refresh token's JTI. The token is useless even if intercepted.

**Session persistence:** On page load, `AuthContext` calls `/api/auth/refresh` to silently restore the session from the cookie — no re-login needed after browser restart.

---

## Security Architecture

VenderScope has undergone a full security audit. Key controls:

| Control | Implementation |
|---------|---------------|
| Authentication | JWT with httpOnly cookie refresh tokens |
| Authorization | Every DB query scoped to `current_user.id` |
| IDOR protection | All resource endpoints return 404 (not 403) for unauthorised access |
| Brute force protection | Rate limiting on all auth endpoints (SlowAPI) |
| Password storage | bcrypt 12 rounds |
| Password policy | Min 12 chars, uppercase, digit |
| DoS protection | Max password length at login (prevents billion-hash attack) |
| XSS | Access token in memory only; httpOnly cookie for refresh |
| SSRF | RFC1918 blocklist, cloud metadata endpoints, URL-decode bypass prevention, decimal/IPv6-mapped IP detection, 3-hop redirect chain validation with per-hop domain check |
| SQL injection | SQLAlchemy ORM (parameterised queries throughout) |
| Header injection | PDF Content-Disposition filename sanitised with regex |
| Security headers | X-Content-Type-Options, X-Frame-Options, HSTS, Referrer-Policy |
| Audit trail | Append-only AuditLog table; X-Forwarded-For aware |
| Secrets | All credentials in environment variables; `.env` gitignored |
| Token replay | JTI blacklist on logout + single-use refresh tokens |
| CSRF | Origin/Referer header validation on all cookie-consuming endpoints |
| Content injection | XML escape on all external data in PDF; HTML escape in email templates |
| Session tokens | UUIDs (not sequential integers) for vendor IDs |
| Input validation | Pydantic validators on all inputs; domain normalised on ingest |
| Startup checks | FRONTEND_URL validated at startup; server refuses to start if misconfigured |

Full audit findings and remediation notes: `docs/security-architecture.md`

---

## Risk Scoring

Scores use a weighted average of the top 5 detected events with a count multiplier — preventing low-severity CVE lists from inflating scores artificially.

| Severity | Score Value |
|----------|-------------|
| CRITICAL | 100 |
| HIGH     | 70 |
| MEDIUM   | 40 |
| LOW      | 15 |

Top 5 events by severity are averaged, multiplied by a count factor (up to 1.4× for vendors with many signals), capped at 100. Vendors scoring ≥ `ALERT_THRESHOLD` (default 70) trigger email alerts to the vendor owner's registered email address.

---

## Compliance Discovery

**Stage 1 — Page discovery + scrape (free):** Fetches the vendor homepage, probes known legal/security paths, inspects sitemap URLs, follows relevant same-site trust/legal/privacy/DPA links, and searches the collected vendor-owned pages for ISO 27001, SOC 2, GDPR, Cyber Essentials, PCI DSS, and Data Processing Agreement evidence.

**Stage 2 — Web search fallback (costs Google CSE quota):** For certifications or security contacts not confirmed on the vendor's own pages, fires targeted Google Custom Search queries to find external evidence. Quota is consumed incrementally per actual query rather than per scan.

### Third-Party Attribution Detection

VenderScope detects a common false positive — vendors referencing their *infrastructure providers'* certifications rather than their own. Matches are analysed at sentence/element granularity. If every occurrence of a cert keyword appears in a third-party attribution context, the result is flagged **"Via infra partners"** instead of **"Verified"**.

| Badge | Meaning |
|-------|---------|
| **Verified** | Evidence found on vendor's own website claiming direct ownership |
| **External source** | Evidence found via web search |
| **Via infra partners** | Cert belongs to infrastructure providers, not the vendor |
| **No evidence** | Nothing found |

### Scan Quota

Google Custom Search allows 100 free queries/day. VenderScope now tracks this quota in the database, consumes units only when an external web search actually happens, and refunds units when a Google request fails before a successful result is returned. In practice, that means many scans cost far less than the old worst-case model. When quota is exhausted, scans automatically fall back to Standard Scan (vendor-site discovery only). Quota resets at midnight UTC.

---

## Vendor Profile Discovery

During every scan, VenderScope passively discovers three data points at no quota cost:

**Description** — Scraped from `og:description` or `<meta name="description">`.

**Authentication Method** — Detected from public pages across 11 categories (SSO/SAML, OpenID Connect, OAuth 2.0, Passwordless, Social Login, Okta/Auth0, Password-based).

**2FA Support** — "Yes" if MFA/2FA/TOTP/authenticator keywords are found. Returns "Not detected" rather than "No" — absence of evidence is not evidence of absence.

---

## Known Limitations

**HF Space sleep:** Hugging Face Spaces sleep after 48 hours of zero traffic. UptimeRobot pings every 5 minutes keep the space warm in practice. If the space does sleep, first request triggers a ~30s cold start.

**JS-rendered trust centres:** Vendors using Vanta or similar platforms load certifications dynamically. VenderScope's scraper fetches raw HTML and relies on the Google CSE fallback for these.

**Email alerts in production:** Render's free tier blocks outbound SMTP. Resend HTTP API is wired up and ready — it activates automatically once a verified sending domain is configured in `RESEND_FROM_EMAIL`. Until then, alerts are skipped in production and delivered locally via Gmail SMTP.

**Safe local/test runs:** Set `EMAIL_ENABLED=0` to hard-disable all outbound email. VenderScope also suppresses deliveries to reserved test domains such as `example.com`, `.test`, `.invalid`, and `localhost`, so automated tests and fake registrations do not generate bounce spam.

**Scheduler scope:** The 24hr background scheduler now uses a database-backed lease so only one app instance runs background jobs at a time. Per-user scheduler scoping (so users only get alerts for their own vendors) is still on the roadmap.

---

## Roadmap

- [x] Multi-source passive intelligence engine
- [x] Risk score drift timeline
- [x] Companies House UK integration
- [x] PDF audit export (ISO 27001 ready)
- [x] Shodan exposed infrastructure detection
- [x] 24hr intelligent caching + nightly scheduler
- [x] Concurrent API fetching
- [x] Compliance posture auto-discovery
- [x] Two-stage certification detection (scrape + Google CSE)
- [x] Third-party certification attribution detection
- [x] Verified security contact discovery
- [x] Daily scan quota tracker
- [x] Vendor profile auto-discovery
- [x] Full JWT authentication (v3)
- [x] Per-user vendor isolation (v3)
- [x] bcrypt password hashing + complexity rules (v3)
- [x] JTI blacklist / single-use refresh tokens (v3)
- [x] Append-only audit log (v3)
- [x] Security headers middleware (v3)
- [x] UUID vendor IDs (v3)
- [x] PostgreSQL (Supabase) + pg8000 migration (v3 → migrated from Neon)
- [x] Resend HTTP API email dispatcher (v3, pending sending domain)
- [x] Account deletion with cascade + password reconfirmation (v3)
- [x] Legal and security documentation pages (v3)
- [x] Real-IP rate limiting behind Render proxy (v3.1)
- [x] CSRF origin validation on cookie endpoints (v3.1)
- [x] SSRF redirect-chain validation + cloud metadata blocklist (v3.1)
- [x] HIBP exact domain matching + breach list cache (v3.1)
- [x] PDF and email content injection prevention (v3.1)
- [x] Risk Delta Dashboard — score drift, "needs attention" view, VendorCard delta badges (v3.1)
- [x] Compliance discovery improvements — expanded path probing, sitemap fallback, broader cert keywords (v3.1)
- [x] Guest Mode — unauthenticated CVE-only scan with PDF download, zero data persistence (v3.5)
- [x] Content-Security-Policy on Vercel frontend (v3.5)
- [x] Business context weighting — data sensitivity multiplier produces Effective Exposure Score (v3.5.x)
- [x] Analyst Notes — timestamped per-vendor evidence log, included in PDF export (v3.6)
- [x] Periodic Review Scheduling — per-vendor review intervals, overdue indicator on dashboard (v3.6)
- [x] Risk Acceptance Workflow — documented risk decisions with justification, reviewer, expiry, audit trail (v3.6)
- [x] Risk Register CSV Export — one-click 12-column export from dashboard (v3.6)
- [x] VS wordmark logo with animated stroke-draw — placed in dashboard, footer, vendor detail (v3.7)
- [x] Login/Register overhaul — looping traces, pulse rings, morphing orbs, glassmorphism card (v3.7)
- [x] Site-wide text color standardization — four-level contrast palette (v3.7)
- [x] VendorCard review status line + Dashboard Reviews Due amber pill (v3.7)
- [x] PDF export enriched with review schedule and risk acceptance table (v3.7)
- [x] Backend migration: Render → Hugging Face Spaces Docker (2vCPU/16GB, no compute quota) (v4.5)
- [x] Database migration: Neon → Supabase (no compute quota, 500MB free tier) (v4.5)
- [x] GitHub Actions CI/CD deploy pipeline to HF Spaces (v4.5)
- [x] `is_production()` generalised — ENV-based, not host-specific (v4.5)
- [ ] Vendor Comparison View — side-by-side risk posture for two vendors
- [ ] Shareable Risk Report — time-limited public read-only vendor snapshot link
- [ ] Bulk CSV Import — add multiple vendors at once
- [ ] In-app score change alerts (no email dependency)
- [ ] Per-user alert configuration (threshold, channel, webhook)
- [ ] Email alerts in production (requires verified Resend domain)
- [ ] Per-user scheduler scoping
- [ ] Async task queue (Celery + Redis)

---

## Deployment

### Backend (Hugging Face Spaces)

Deploy via GitHub Actions (`.github/workflows/deploy-hf.yml`) — triggers on push to `backend/`. Set `HF_TOKEN` as a GitHub secret.

Required secrets on HF Space (Settings → Variables and secrets):

```
DATABASE_URL        postgresql://postgres.[ref]:PASSWORD@aws-X-eu-west-2.pooler.supabase.com:5432/postgres
JWT_SECRET          64-char hex string
FRONTEND_URL        https://venderscope.vercel.app
ENV                 production
NVD_API_KEY
COMPANIES_HOUSE_API_KEY
SHODAN_API_KEY
GOOGLE_CSE_API_KEY
GOOGLE_CSE_ID
GMAIL_ADDRESS       (optional — local email fallback)
GMAIL_APP_PASSWORD  (optional)
EMAIL_ENABLED       1 (set to 0 to disable all outbound email)
ALERT_THRESHOLD     70
```

**Keep-alive:** Set up UptimeRobot (free) to ping `https://darkitowo-venderscope-api.hf.space/` every 5 minutes using HTTP GET. This prevents HF sleep and keeps APScheduler alive.

### Frontend (Vercel)

Same-origin API via rewrite in `frontend/vercel.json` (`/api/*` → HF Space). Set:

```
VITE_API_URL        /api
```

Do **not** point `VITE_API_URL` at the HF Space origin in the browser — credentialed auth XHR fails CORS there. Local dev still uses `http://127.0.0.1:8000/api` via `.env.local` / Vite proxy.
---

## Motivation

Built from direct experience managing 50+ vendor audits annually at Thrive Learning. Traditional GRC tooling (Vanta, SecurityScorecard, BitSight) costs thousands per year and is reactive. VenderScope is open-source, UK-aware via Companies House, and continuously passive — it watches your vendors so you don't have to.

---

## Author

**Syed Zarak Hassan**
Compliance Analyst & MSc Cyber Security Student
[LinkedIn](https://linkedin.com/in/zarak-hassan7) · [GitHub](https://github.com/darkyzowo)

---

_VenderScope is an independent open-source project. Data is sourced from public APIs and should be reviewed by a qualified security professional._
