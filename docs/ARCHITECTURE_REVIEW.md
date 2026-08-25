# VenderScope Architecture Review — Merged Engineering + Design Audit

## 1. Executive Summary

VenderScope's backend has three structural debts that block UI work already planned on top of them: an EPSS scoring service that's fully built but never wired into the scan pipeline (dead code masquerading as a feature), an audit log that's write-only and untethered from account deletion (a live GDPR/copy-accuracy problem), and an auth surface missing basic self-service endpoints (password change, email verification, activity read, data export) that the design plan already assumes will exist. Test coverage on core scoring and auth-rotation logic is effectively zero. The design plan itself is in good shape — dark-mode GRC dashboard language is consistent and well-tokenized — but three of its ten plans didn't fully absorb prior-round findings: the Settings change-password UI doesn't name its missing endpoint as a blocking dependency, the Danger Zone panel doesn't carry forward the audit-log-survives-deletion caveat, and the Activity Panel doesn't flag that failed logins are structurally unattributable to a user without a schema change. None of this is a rewrite — it's five backend endpoints, one schema decision, one retention policy, and tightening three dependency notes before engineers start building against them.

---

## 2. Engineering Gaps

### High Severity

| Area | Finding | Recommendation | Affected Files |
|---|---|---|---|
| **Audit log / GDPR retention** | `AuditLog.user_id` is a bare nullable `String(36)` with no ForeignKey/cascade. `scheduler.py`'s cleanup job only prunes `RevokedToken` rows — `DELETE /api/auth/account` leaves every audit row (IP, user_id, free-text detail) behind forever, contradicting `DeleteAccountModal.jsx`'s "permanently and immediately deleted" copy. Separately, failed-login attempts are audited with `user_id=None` (`auth.py:144`), making them structurally unattributable to a specific account — a fact the design plan's Activity Panel doesn't carry forward. | Decide a retention policy for `AuditLog` (anonymize on deletion, or a documented purge window) and update the modal copy to match. Add the failed-login-attribution caveat explicitly to the Activity Panel's dependency notes, or add a normalized `attempted_user_id`/`attempted_email` column. | `backend/models.py`, `backend/routers/auth.py`, `backend/scheduler.py`, `frontend/src/components/DeleteAccountModal.jsx` |

### Medium Severity

| Area | Finding | Recommendation | Affected Files |
|---|---|---|---|
| **EPSS scoring pipeline** | `epss.get_epss_scores()` has zero call sites anywhere in the repo. `nvd.py` never appends an EPSS score to event descriptions, so `pdf_export.py`'s `parse_epss()` always returns `0.0` — the EPSS tie-break in exported PDFs is permanently inert. | Wire `epss.get_epss_scores()` into `scanner.run_full_scan()` and append `[EPSS: X%]` to event descriptions before save — **or** remove `epss.py` and the dead `parse_epss`/`sort_events` logic. Do not build the EPSS-pill UI until this decision is made and verified landing non-zero. | `backend/services/epss.py`, `backend/services/scanner.py`, `backend/services/nvd.py`, `backend/services/pdf_export.py` |
| **Email verification** | No `email_verified` column; `register()` lets users log in immediately with no confirmation token. The resend-verification action needed by the design plan requires its own rate-limited endpoint, not implied generically by "token endpoints." | Add `email_verified` column + verification-token model/endpoints (`POST /api/auth/verify-email`, `POST /api/auth/resend-verification` with its own SlowAPI limit, mirroring register's 3/hour). Track the resend endpoint as its own backend deliverable. | `backend/models.py`, `backend/routers/auth.py` |
| **Test coverage** | Zero tests for `scanner.run_full_scan`/`_compute_score`, `nvd.py`, `hibp.py`, `shodan_service.py`, `epss.py`, `risk_context.compute_effective_score`, `audit.py`, `pdf_export.py`, `auth_service.py`. Auth's refresh rotation-reuse path, `/logout`, `GET /me`, `DELETE /account` are untested. | Prioritize tests for `scanner._compute_score`, refresh-token rotation/reuse-after-revoke, and `risk_context.compute_effective_score` before building UI on top of untested account-deletion cascade behavior. | `backend/tests/`, `backend/services/scanner.py`, `backend/services/risk_context.py`, `backend/routers/auth.py` |
| **Settings / change-password endpoint** | `auth.py` has exactly six routes (register, login, refresh, logout, `GET /me`, `DELETE /account`) — no endpoint to change a password while authenticated. The design plan's Settings page specifies a change-password UI in detail but its `depends_on_engineering` never names this endpoint as a blocker. | Add `PUT /api/auth/password` (body: `current_password`, `new_password`), reusing the existing validator at `auth.py:36-47`. Decide whether it revokes other sessions' refresh tokens (recommended, for parity with logout/refresh revocation). Track explicitly as a Settings-page blocking dependency. | `backend/routers/auth.py`, `backend/services/auth_service.py`, `frontend/src/pages/Settings.jsx` (not yet built) |

### Low Severity

| Area | Finding | Recommendation | Affected Files |
|---|---|---|---|
| **Dead `getMe()` / AuthContext** | `GET /api/auth/me` works and returns `{email}`, but nothing calls it. `AuthContext`'s `_parseToken` comment claims to decode an email that isn't in the JWT payload. | Fetch once in `AuthContext`'s existing effect, cache as `user.email`, omit the email row entirely on fetch failure rather than a placeholder. No new backend work needed — feasible as specified. | `frontend/src/api/client.js`, `frontend/src/auth/AuthContext.jsx`, `frontend/src/components/DeleteAccountModal.jsx` |
| **Cross-tab logout / access-token revocation** | No cross-tab logout sync; access tokens (`{sub, exp, type}`) carry no `jti` and have no server-side revocation at all — only refresh tokens are revocable. The design plan's fix is correctly scoped as cosmetic but doesn't restate that caveat where a future security reviewer would see it. | No code change needed beyond documentation: add a one-line note to the overlay's implementation notes stating it is UX-only and does not shorten the 15-minute access-token exposure window. | `frontend/src/api/client.js`, `frontend/src/auth/AuthContext.jsx`, `backend/services/auth_service.py` |
| **Account data export** | No "export my data" action exists, despite the pattern already existing for vendor CSV export (`Dashboard.jsx:147-152`). The design plan builds the exact Danger Zone panel this would live in but doesn't mention it. | Add an "Export my data" action (JSON/CSV of vendors + notes + acceptances + audit history) as the non-destructive counterpart to Delete Account on the same panel. | `frontend/src/pages/Settings.jsx` (not yet built), `frontend/src/pages/Dashboard.jsx`, `backend/routers/` |

---

## 3. Design Plan

### 3.1 Addressing: Audit log / GDPR retention (High)

**Profile / Account Settings page** — hosts the Danger Zone panel where the retention decision surfaces to users.
- *Visual direction:* New protected page inside `AppShell`, narrower centered column (`max-w-3xl`). Danger Zone panel clones `DeleteAccountModal`'s step-1 warning-card styling and houses both "Export my data" (secondary/translucent button) and "Delete Account" (solid red, unchanged modal), side-by-side on desktop / stacked on mobile.
- *Implementation notes:* Backend must resolve the AuditLog retention policy **before** this panel ships — it directly contradicts `DeleteAccountModal.jsx:84`'s "permanently and immediately deleted" copy, and that copy must be corrected if the policy doesn't hold. Ship the Footer.jsx "Delete Account" link removal in the **same PR** as this page, not before (no window with zero entry point to deletion). While touching `DeleteAccountModal.jsx`, add the missing Escape-key handler (confirmed: only backdrop-click-close exists today at line 43) — in-scope fix, not a separate ticket.

**Activity / Security History panel** — the read surface for the previously write-only audit log.
- *Visual direction:* Rows modeled on `EventFeed`'s anatomy — neutral `var(--line)` accent (never risk-color, audit isn't severity-scored), lucide action icon, `EventFeed`'s "source · date" meta line. Clean-scan-style empty state.
- *Implementation notes:* **Explicit constraint carried forward from the engineering finding:** do not design a "failed login" row type for v1 — the backend cannot attribute those rows to the viewer's account yet (`user_id=None`). Frame the panel as "account and vendor actions," not "security events," so it doesn't imply completeness it can't deliver. Meta line wraps to a second line on narrow viewports rather than truncating — timestamps are the security-relevant content here; flag this as an intentional deviation from the app's usual `.truncate` convention.

### 3.2 Addressing: EPSS pipeline (Medium)

**EPSS exploit-likelihood indicator** — gated entirely on the wire-vs-remove decision.
- *Visual direction:* If wired, a secondary pill next to CVE-sourced events in `EventFeed`'s title row — neutral violet-informational tint (`rgba(139,92,246,0.08)`, `var(--accent-l)` text), **not** a risk-traffic-light color, since EPSS is a different axis from CVSS severity. Reuses `EventFeed`'s portal-based hover-tooltip, keyboard-focusable.
- *Implementation notes:* **Hard gate:** do not open a design or implementation ticket until engineering documents the wire-vs-remove decision. If wired, only render the pill for events with a real, non-fallback parsed EPSS value — never for a 0%/absent value indistinguishable from the current dead default. If removed, this plan is void with no design deliverable needed.

### 3.3 Addressing: Email verification (Medium)

**Email-verification banner + `/verify-email` page + resend action.**
- *Visual direction:* Banner shares `QuotaBanner`'s structural shell but uses the app's "pending action" amber (`#fbbf24`) — not `--risk-medium` — with an inline "Resend verification email" link. Mounts below TopNav, above QuotaBanner; both stack full-width, never side-by-side. `/verify-email` reuses the glass-card shell without the full ambient auth scene (calmer, transactional): verifying / success / invalid-expired states.
- *Implementation notes:* Depends on `POST /api/auth/resend-verification` — a **new backend deliverable, not previously flagged with this specificity**, requiring its own rate limit (mirroring register's 3/hour SlowAPI limit) to prevent mail-bombing arbitrary addresses. Chained to `email_verified` column + verify-email endpoint. Visibility driven strictly by `user.email_verified` from AuthContext, never by local dismiss state alone — compose as `visible = !dismissed && !email_verified` via the shared dismiss hook (3.7). Banner carries `role="status" aria-live="polite"` — a net-new a11y pattern with no existing precedent, call out explicitly in the PR.

**Branded transactional email templates** (verification, reset, welcome) — needed the moment the above goes live.
- *Visual direction:* Intentionally departs from the dark app shell — light, email-safe chrome, flat `#7C3AED` CTA (non-gradient fallback), static logo mark.
- *Implementation notes:* Hard technical constraint: inline-styled, table-based HTML only — no flexbox/grid/`<style>` blocks/CSS custom properties (Outlook desktop compatibility). End-to-end send testing is blocked until the forgot/reset-password and resend-verification routes actually call Resend — build templates as static files now, flag the send-testing dependency to engineering.

### 3.4 Addressing: Settings change-password endpoint (Medium)

**Profile / Account Settings page — Security panel.**
- *Visual direction:* Verification-status pill on `RiskBadge`'s dot+tint+text shape; change-password form reuses `Register.jsx`'s password-rule microcopy and validation verbatim.
- *Implementation notes:* **Depends on two backend deliverables, now named explicitly:** `PUT /api/auth/password` (reusing the validator at `auth.py:36-47`) plus a documented decision on session revocation on password change (recommended, for parity with logout/refresh revocation). On 200, crossfade the form to a one-line green confirmation that auto-fades after 4 seconds — no manual dismiss.

### 3.5 Addressing: Dead `getMe()` (Low)

**Surface the logged-in user's email.**
- *Visual direction:* TopNav dropdown gets a non-interactive header row (email, `.truncate` + native tooltip) above Settings/Sign out; `DeleteAccountModal` step 1 adds "You are about to delete the account for `<email>`".
- *Implementation notes:* No backend work — pure frontend wiring, confirmed feasible as specified. Extend the *same* effect that runs `_parseToken()` to also call `getMe()` once; don't add a second independent fetch. Remove the misleading comment at `AuthContext.jsx:22-30` claiming the JWT contains an email claim. TopNav row must carry `aria-hidden="true"` and `tabIndex={-1}` so it never becomes a phantom stop in the existing `role=menu` sequence. Omit both slots entirely (no placeholder/skeleton) if the fetch hasn't resolved or fails.

### 3.6 Addressing: Cross-tab logout (Low)

**Cross-tab logout transition.**
- *Visual direction:* Full-viewport scrim reusing `DeleteAccountModal`'s exact overlay convention (`rgba(0,0,0,0.75)` + `blur(4px)`), centered "You've been signed out" + spinner, navigate to `/login` after a fixed 700ms. Escape fast-forwards the redirect.
- *Implementation notes:* Engineering owns the BroadcastChannel/storage-event bridge; this covers the visual transition only. **State plainly in the PR/security review that this does not shorten a leaked access token's 15-minute live window** — it is a rendering fix, not a session-invalidation fix, since access tokens carry no `jti` and have no server-side revocation path.

### 3.7 Addressing: Account data export (Low)

Covered by the Settings Danger Zone panel in 3.1 — "Export my data" ships alongside Delete Account, not as a separate plan.

### 3.8 Supporting / independent design items

**Shared `useDismissibleBanner` hook** — fixes `QuotaBanner`'s dismiss-doesn't-persist bug *before* the verification banner becomes a second consumer of the same broken pattern. New hook persists to `localStorage` (`vs.dismissed.${bannerId}`); must land before or alongside the verification banner so it never ships its own separate dismiss state. Compose visibility as AND (`!dismissed && condition`), never OR — document this in the hook's JSDoc.

**Forgot Password + Reset Password pages** (README gap #1, blocked on email infra) — structural clone of Login's auth-scene, non-committal confirmation copy, 45s resend cooldown persisted in `localStorage`.

**Resolve the dead notification bell** — independent UX finding, not in the engineering audit. TopNav bell has `aria-label="Notifications"` but no handler, which overpromises to assistive tech. Ship now: demote to ~0.4 opacity, `aria-disabled="true"`, append "— coming soon" to the label. Revisit a real dropdown only once Settings/Activity/Verification banner exist to feed it real content.

---

## 4. Combined Prioritized Action List

1. **Decide AuditLog retention policy** (anonymize-on-delete or documented purge window) and fix `DeleteAccountModal.jsx`'s "permanently and immediately deleted" copy — blocks the Settings Danger Zone panel and the Activity Panel's framing; this is the one High-severity item and the copy is actively false today.
2. **Decide EPSS wire-vs-remove** and, if wiring, land real `[EPSS: X%]` values in stored events — blocks the EPSS-pill design ticket, which is hard-gated on this decision.
3. **Stand up working transactional email** (README gap #2, Resend integration) — blocks end-to-end testing of both the password-reset and email-verification flows; templates can be built in isolation now but can't be verified without this.
4. **Add `email_verified` column + verify-email endpoints + `POST /api/auth/resend-verification`** with its own rate limit — blocks the VerificationBanner and `/verify-email` page.
5. **Add `PUT /api/auth/password`** (+ session-revocation decision) — blocks the Settings page's Security panel change-password UI.
6. **Add `GET /api/auth/activity`** scoped to `current_user.id`, and decide the failed-login-attribution schema change (`attempted_user_id`/`attempted_email`) — blocks the Activity Panel; ship the panel with the "no failed logins in v1" constraint if the schema change is deferred.
7. **Backfill tests** for `scanner._compute_score`, refresh-token rotation/reuse-after-revoke, and `risk_context.compute_effective_score` — before building further UI (Settings, Activity) on top of untested scoring/auth/account-deletion logic.
8. **Build the shared `useDismissibleBanner` hook** and refactor `QuotaBanner` onto it — pure frontend, no backend dependency, but must land before the VerificationBanner (item 4's UI) to avoid shipping a second copy of the same dismiss bug.

*Everything else — data-export endpoint, `getMe()` wiring, cross-tab logout overlay, notification-bell demotion, forgot/reset-password pages — has no blocking cross-dependency and can be sequenced opportunistically after the above.*
