# VenderScope

> **Still running annual vendor audits? Your next breach won't wait 12 months.**

[![Live Beta - v4.7](https://img.shields.io/badge/Live%20Demo-venderscope.vercel.app-6366f1?style=for-the-badge)](https://venderscope.vercel.app)
[![API](https://img.shields.io/badge/API-darkitowo--venderscope--api.hf.space-10b981?style=for-the-badge)](https://darkitowo-venderscope-api.hf.space/docs)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Zarak%20Hassan-0A66C2?style=for-the-badge&logo=linkedin)](https://www.linkedin.com/in/zarak-hassan7/)
[![Version](https://img.shields.io/badge/version-v4.7-violet?style=for-the-badge)](https://github.com/darkyzowo/venderscope/releases)

> **Performance note:** VenderScope backend runs on Hugging Face Spaces (Docker, 2vCPU/16GB RAM). Free-tier Spaces still idle-sleep on inactivity — UptimeRobot pings every 5 minutes to minimize that, but a cold boot (~30–50s) can still happen after a gap in traffic or an HF-side restart. Actual scan time once warm is 8–15s using concurrent API calls to HIBP, NVD, Companies House, Shodan, and the compliance engine simultaneously.

VenderScope is a continuous, passive vendor risk intelligence platform built for GRC and Information Security professionals. Instead of point-in-time annual reviews, VenderScope monitors your vendor estate 24/7 across multiple threat intelligence sources and surfaces risk drift in real time — with full user authentication, production-grade security hardening, and a cloud PostgreSQL backend.

---

## Latest Release — v4.7: Per-Scan Search Quota Ceiling

Live production testing on v4.6 (real vendor scans through the hosted app, not just Modal) surfaced a fairness gap: nothing capped how many Tavily units a *single* scan could spend. Worst case — 6 certs × up to 4 query templates, plus 7 security-contact prefixes — was ~21 units for one vendor, not the ~6 `ESTIMATED_SCAN_COST` assumed. Combined with no per-user vendor cap, a vendor-heavy account calling `scan-all` at its rate-limit ceiling could exhaust the entire shared monthly Tavily budget in minutes, locking search out for every user until the next reset.

- **`MAX_SEARCH_UNITS_PER_SCAN = 6`** — `services/compliance_discovery.py`'s `_web_search()` now stops issuing further Tavily calls once a single `run_compliance_discovery()` invocation has net-spent 6 units, reusing the existing `quota_state["used"]` counter (no new state). Matches `ESTIMATED_SCAN_COST`, so the "estimated full scans remaining" figure now reflects a real ceiling instead of an average
- **Global exhaustion stays separate** — the per-scan cap only returns `[]` early; it never touches `quota_state["enabled"]`/`["exhausted"]`, so the quota banner still means what it says (true monthly exhaustion, not one scan hitting its own cap)

Verification after this pass:

- `python -m pytest -q` → `82 passed`

Full version history: [`CHANGELOG.md`](CHANGELOG.md)

---

## Known Limitations & Deferred Work

### Shodan (Exposed Infrastructure)
- **Search API requires a paid Shodan membership.** On a free-tier `SHODAN_API_KEY`, `check_shodan_exposure()`'s `api.search()` call gets a 403 on every scan and the source silently returns zero events. A vendor scanned on a free key will always show "no Shodan findings" regardless of real exposure — that reads as "clean," not "not checked." Upgrading the key or swapping to a free-tier-compatible endpoint (e.g. per-IP `host()` lookups) would restore this signal.

### Email (Transactional)
- **HF Spaces blocks outbound SMTP** — ports 587 and 465 return `[Errno 101] Network is unreachable`. Gmail SMTP will never work on HF.
- **Resend requires a verified custom domain** — `venderscope.app` is a placeholder; no domain is currently owned. Resend code is complete (`alerts.py`); it just needs a real domain pointed at it.
- **Current state:** welcome emails and alert emails are silently skipped on HF. No broken logs, no user-facing errors. Set `EMAIL_ENABLED=0` to hard-disable outbound email for local/test runs; reserved test domains (`example.com`, `.test`, `.invalid`, `localhost`) are always suppressed regardless.
- **To fix:** buy a domain (e.g. `venderscope.app` ~$14/yr), add Resend DNS records (DKIM TXT + SPF MX/TXT), set `RESEND_API_KEY` + `RESEND_FROM_EMAIL=noreply@<domain>` in HF env vars. All send logic already exists.

### Password Reset / Profile Page
- No password reset flow exists. Custom auth (bcrypt + JWT) — Supabase Auth is not used.
- Plan: `PasswordResetToken` model + `POST /api/auth/forgot-password` + `POST /api/auth/reset-password` + `/reset-password` frontend page. Blocked on email working first.

### Scheduler & Hosting
- Nightly scan currently has two paths: the original APScheduler job (behind a DB-backed `SchedulerLease`, still authoritative) and, as of v4.6, an alternate Modal Cron path — gated by `ENABLE_LEGACY_NIGHTLY_SCAN` so only one runs. Per-user scheduler scoping (so users only get alerts for their own vendors) is still on the roadmap.
- HF Spaces sleep after 48 hours of zero traffic. UptimeRobot pings every 5 minutes keep it warm in practice; a cold boot (~30-50s) can still happen after a gap in traffic or an HF-side restart.

### JS-Rendered Trust Centres
- Vendors using Vanta or similar platforms load certifications dynamically. VenderScope's scraper fetches raw HTML and relies on the Tavily search fallback for these.

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
- **Two-Stage Compliance Discovery** — Scrapes vendor pages for ISO 27001, SOC 2, GDPR, Cyber Essentials, PCI DSS evidence; Tavily search fallback when direct scraping is insufficient
- **Verified Security Contacts** — Finds security/privacy contacts via RFC 9116 `security.txt`, page scraping, and web search
- **Scan Quota Tracker** — Live banner showing remaining Tavily search quota with automatic monthly reset
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
| Compliance    | Tavily Search API, BeautifulSoup4, security.txt                             |
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
| **Tavily**          | External certification evidence for ISO 27001, SOC 2, DPA, and more         |
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
│       ├── quota.py              # DB-backed global Tavily quota tracker
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
- API keys for: NVD, Companies House, Shodan, Tavily

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
TAVILY_API_KEY=your_key

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

**Stage 2 — Web search fallback (costs Tavily quota):** For certifications or security contacts not confirmed on the vendor's own pages, fires targeted Tavily search queries to find external evidence. Quota is consumed incrementally per actual query rather than per scan, capped at 6 units per single scan (`MAX_SEARCH_UNITS_PER_SCAN`) so no one scan — or a burst of them — can exhaust the shared monthly budget.

### Third-Party Attribution Detection

VenderScope detects a common false positive — vendors referencing their *infrastructure providers'* certifications rather than their own. Matches are analysed at sentence/element granularity. If every occurrence of a cert keyword appears in a third-party attribution context, the result is flagged **"Via infra partners"** instead of **"Verified"**.

| Badge | Meaning |
|-------|---------|
| **Verified** | Evidence found on vendor's own website claiming direct ownership |
| **External source** | Evidence found via web search |
| **Via infra partners** | Cert belongs to infrastructure providers, not the vendor |
| **No evidence** | Nothing found |

### Scan Quota

Tavily's free tier allows 1,000 credits/month, no card required. VenderScope tracks this quota in the database, consumes units only when an external web search actually happens, and refunds units when a request fails before a successful result is returned. In practice, that means many scans cost far less than the old worst-case model. When quota is exhausted, scans automatically fall back to Standard Scan (vendor-site discovery only). Quota resets on the 1st of the month, UTC.

---

## Vendor Profile Discovery

During every scan, VenderScope passively discovers three data points at no quota cost:

**Description** — Scraped from `og:description` or `<meta name="description">`.

**Authentication Method** — Detected from public pages across 11 categories (SSO/SAML, OpenID Connect, OAuth 2.0, Passwordless, Social Login, Okta/Auth0, Password-based).

**2FA Support** — "Yes" if MFA/2FA/TOTP/authenticator keywords are found. Returns "Not detected" rather than "No" — absence of evidence is not evidence of absence.

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
- [x] Two-stage certification detection (scrape + Tavily search)
- [x] Third-party certification attribution detection
- [x] Verified security contact discovery
- [x] Monthly scan quota tracker
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
TAVILY_API_KEY
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
