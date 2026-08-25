# Changelog

Historical release notes for VenderScope, extracted from `README.md` to keep it concise. The current/newest release lives in the README under "Latest Release" — it moves here once superseded by the next version.

---

## v5.0 — Google-Gated Passkey Authentication & Re-verification Hardening

Passkeys prove control of an authenticator on this origin, not mailbox control — typed-email signup let anyone finish WebAuthn and own an unverified email address. v5.0 replaces the password-based auth system with Google-then-passkey enrollment, and closes a re-verification gap found in an independent review of that work.

- **Password sign-in closed** — `POST /api/auth/login` and `POST /api/auth/register` always return 403. Leftover bcrypt hashes on legacy accounts remain valid for step-up (add a passkey, link Google, delete account) but not for signing in.
- **Google-gated passkey signup** — new accounts start with Google OIDC (`email_verified`, PKCE, nonce, RS256), which mints a short-lived pending session, then require a passkey to complete enrollment. Identity stored is `google_sub`; email is a label copied from Google. No skip-passkey path.
- **Passkeys (WebAuthn)** — phishing-resistant sign-in; last passkey cannot be removed unless Google remains linked (password hashes and recovery codes don't count as a login method for this check).
- **Recovery codes** — 10 one-time codes issued at enrollment, shown once, stored hashed (HMAC-SHA256 + bcrypt). A backup login path, not a way to drop the last passkey or unlink Google.
- **Session-family kill** — refresh tokens carry a `session_version` claim. Reusing an already-rotated refresh token (JTI already blacklisted) bumps `session_version` and invalidates every outstanding access/refresh token for that user, not just the reused one. Logout does the same, so a leftover 15-minute access token dies immediately instead of surviving until natural expiry.
- **Step-up on factor changes** — linking Google, adding a second-or-later passkey, and permanently deleting the account all require re-proving identity (existing passkey or password) with a live access token, not just a valid cookie.
- **Re-verification hardening (this pass)** — adding a *first* passkey to a Google-only account, and disconnecting Google from any account, now also require step-up: Google-only accounts (which have no existing passkey or password to step up with) go through a fresh Google re-authentication that must resolve to the same account already on file; disconnecting Google now requires the same step-up as linking it. Closes a gap where a compromised short-lived session token could change an account's sign-in factors without proving current control. See `docs/SECURITY.md`'s v5.0 audit entry for the full disclosure.
- **WebAuthn sign-count correctness fix** — the verification library's own clone-detection logic already correctly exempts authenticators that don't track a use counter (common on synced/platform passkeys); an app-side duplicate check lacked that exemption and could have rejected legitimate logins from those authenticators. Removed the duplicate; a genuine clone/replay now returns a clean 401 instead of an unhandled error.

**Follow-up fix, same release — frontend UX/accessibility hardening:** an `impeccable` design critique (dual-assessment: LLM design review + deterministic detector scan) found the app's two most consequential user actions — a scan failing, a vendor being deleted — got the least error handling and confirmation friction in the product, while the auth screens seen once got the most.

- **Silent failures fixed** — `Dashboard.jsx`/`VendorDetail.jsx` scan, delete, note, review-schedule, and risk-acceptance actions used to fail with only a `console.error` (or no error handling at all); a new `Toast` component now surfaces every one visibly. For a risk-monitoring tool, a scan that fails without telling anyone manufactures false assurance.
- **Risk-band threshold bug** — the "medium risk" cutoff was `35` in `VendorCard.jsx`/`GuestScanPage.jsx`/`ScoreGauge.jsx` but `40` in `Dashboard.jsx`/`VendorDetail.jsx`/`ScoreChart.jsx`; the same score could render a different risk level on the same screen. Unified onto `RiskBadge.jsx`'s single-source `riskLevel()`. Also fixed `--risk-crit` being the literal same color as `--risk-high` (visually indistinguishable "Critical" vs "High"); the new value was contrast-checked against the WCAG 2.1 AA target (5.35:1).
- **Vendor deletion hardened** — replaced a bare `confirm('Remove this vendor?')` with a `VendorDeleteModal` itemizing exactly what's lost (scan history, risk events and their audit trail, analyst notes, compliance data), matching the confirmation weight already given to account deletion.
- **VendorDetail restructured** — split into Overview/Compliance/Events/Notes tabs, and converted two oversized button-grid selectors (Data Sensitivity: 7 options, Review Schedule: 6 options) to native `<select>` dropdowns — both a cognitive-load fix and a free accessibility win (native selects are keyboard/screen-reader accessible without hand-rolled ARIA).
- **Keyboard accessibility (WCAG 2.1 AA)** — the scoring-model explainer and the accepted-risk justification tooltip were hover-only with no keyboard equivalent; both now respond to focus, verified by rendering the page and focusing the trigger element (not just reading the code).
- **`prefers-reduced-motion` support** — added app-wide, with in-progress spinners/skeletons explicitly exempted so a multi-minute scan doesn't visually read as a hung app.
- **Detector findings** — fixed 2 overshoot easing curves and a layout-thrashing width transition; documented and suppressed 3 deliberate choices (self-hosted Geist font, decorative auth dot-grid, semantic severity border) with reasons recorded in `.impeccable/config.json`.

Verification after this pass:

- `python -m pytest -q` → `179 passed` (backend untouched by this pass, unaffected)
- `npm run build` (frontend) → passed
- `npm run lint` (frontend) → no new errors (4 pre-existing, unrelated files)
- Playwright screenshots across desktop/mobile viewports, both real dev-server pages (Login/Register/GuestScan) and API-route-stubbed Dashboard/VendorDetail (auth-gated, no backend needed) — including the delete modal, both tooltip-focus states, and `prefers-reduced-motion` — confirmed no visual regressions before commit.

---

## v4.7 — Per-Scan Search Quota Ceiling

Live production testing on v4.6 (real vendor scans through the hosted app, not just Modal) surfaced a fairness gap: nothing capped how many Tavily units a *single* scan could spend. Worst case — 6 certs × up to 4 query templates, plus 7 security-contact prefixes — was ~21 units for one vendor, not the ~6 `ESTIMATED_SCAN_COST` assumed. Combined with no per-user vendor cap, a vendor-heavy account calling `scan-all` at its rate-limit ceiling could exhaust the entire shared monthly Tavily budget in minutes, locking search out for every user until the next reset.

- **`MAX_SEARCH_UNITS_PER_SCAN = 6`** — `services/compliance_discovery.py`'s `_web_search()` now stops issuing further Tavily calls once a single `run_compliance_discovery()` invocation has net-spent 6 units, reusing the existing `quota_state["used"]` counter (no new state). Matches `ESTIMATED_SCAN_COST`, so the "estimated full scans remaining" figure now reflects a real ceiling instead of an average
- **Global exhaustion stays separate** — the per-scan cap only returns `[]` early; it never touches `quota_state["enabled"]`/`["exhausted"]`, so the quota banner still means what it says (true monthly exhaustion, not one scan hitting its own cap)

**Follow-up fix, same release (round 1):** a live scan surfaced false-positive cert evidence — matches were accepted on bare keyword presence rather than page identity, letting a job posting and an unrelated third-party article count as attestations, plus a contaminated doc link from sitemap parsing picking up another company's marketplace profile page. Fixed with junk-path rejection (jobs/careers/marketplace-listing paths excluded from all doc-discovery stages), word-boundary matching for short tokens (`soc`/`iso`/`dpa`), and a two-gate Tavily result filter (vendor relevance + not-junk) with real hostname matching instead of substring checks.

**Follow-up fix, same release (round 2):** a second live scan on the same vendor still surfaced 3 more false positives — two came from `CREDIBLE_DOMAINS` bodies (`ncsc.gov.uk`, `pcisecuritystandards.org`) publishing generic scheme-overview/blog content that never named the vendor; membership in that domain list was being treated as sufficient evidence on its own. Fixed by requiring an actual vendor mention even on a credible domain. The third — a third-party "AI tools" directory page that happened to name-drop the vendor while discussing something else, on a dead/404 URL — passed every deterministic gate cleanly, because it *does* mention the vendor; this is the boundary of what path/keyword heuristics can close (the space of third-party directory/aggregator sites is effectively unenumerable). An LLM-based audit fallback pass, scoped in round 1 but deferred as unnecessary paid-dependency polish, is now the planned fix for this remaining class rather than optional UX — two consecutive rounds of fresh false positives from unenumerated page shapes is the evidence that a third heuristic-gate pass won't close it.

Verification after this pass:

- `python -m pytest -q` → `166 passed`

---

## v4.6 — Tavily Web Search & Modal Cron Scan

Google Custom Search JSON API started 403ing on every request even with the API enabled and a correctly-scoped key — root cause traced to Google's undocumented billing-account requirement, which broke the goal of keeping this build genuinely no-cost. Compliance web search was swapped to Tavily. Separately, the nightly vendor scan gained a second, more reliable scheduling path via Modal's native Cron.

- **Compliance web search: Google CSE → Tavily** — `services/compliance_discovery.py`'s Stage 2 search fallback and the security-contact discovery stage now call the Tavily Search API instead of Google Custom Search. No credit card required at signup; response shape maps near 1:1 onto the old `title`/`link`/`snippet` contract, so no downstream consumer changed
- **Quota model: daily → monthly** — Tavily's free tier is 1,000 credits/month (vs Google's 100/day). `services/quota.py`'s `SearchQuotaUsage` row now keys on `YYYY-MM` instead of `YYYY-MM-DD` — no schema migration needed, since the column was always a plain string primary key. `/api/quota`'s response shape is unchanged, so the frontend needed no changes beyond the banner's copy
- **Reserve/refund race fix** — `consume_search_units`/`refund_search_units` now accept an explicit `period` pinned once at reservation time (`current_quota_period()`), so a request that straddles a month boundary can't reserve against one month and refund into the next
- **Nightly scan: Modal Cron added alongside APScheduler** — `backend/modal_app.py` runs the same per-vendor scan loop as `scheduler.py`'s `scheduled_scan`, on a fixed-wall-clock Modal Cron schedule instead of "24h after the app last started." An `ENABLE_LEGACY_NIGHTLY_SCAN` flag keeps the original APScheduler job as the active path until the Modal cron has held clean for a few nights, at which point the legacy job (and the `SchedulerLease` model it needed for multi-instance safety) will be removed in a follow-up commit
- **Verified live** — a real-vendor Modal run confirmed the quota consumed correctly under the new monthly model, Tavily search located an externally-attested cert, and the quoted-phrase security-contact query still resolves against Tavily's index

Verification after this pass:

- `python -m pytest -q` → `81 passed`
- `npm run build` → passed
- Live Modal run against a real production vendor, end to end

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
