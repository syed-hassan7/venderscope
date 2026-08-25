# Google-gated signup Implementation Plan

> **For agentic workers:** Execute inline in this session. TDD. Do not commit unless the user asks.

**Goal:** New accounts cannot be created without a valid Google pending cookie; login UX leads with passkey and Google.

**Architecture:** Gate unauthenticated WebAuthn register begin/finish on `vs_google_pending`. Ignore client email on signup. Logged-in add-passkey unchanged. Register page is Google-first; Login leads with passkey + Google.

**Tech Stack:** FastAPI, py_webauthn, React, existing JWT cookies.

## Global Constraints

- No new mailer, domain, or Supabase Auth.
- Password register stays closed.
- 403 detail for missing pending: `Start with Google to create an account`
- Tests: `cd backend && python -m pytest tests/ -q`

## Files

- Modify: `backend/routers/auth.py`
- Modify: `backend/tests/test_webauthn_auth.py`
- Modify: `backend/tests/test_google_auth.py`
- Modify: `frontend/src/pages/Register.jsx`
- Modify: `frontend/src/pages/Login.jsx`
- Modify: `frontend/src/auth/AuthContext.jsx` (begin may omit email)
- Modify: `docs/SECURITY.md`, `frontend/src/docs/security.md`, `frontend/src/docs/privacy.md`

### Task 1: API gate

- [x] Failing tests: unauthenticated begin without cookie → 403; signup finish without cookie → 403; begin ignores body email; logged-in begin without cookie → 200
- [x] `_require_google_pending(request)`; signup begin uses pending email; signup finish requires pending + matching challenge email
- [x] Pytest auth tests green

### Task 2: UI + docs

- [x] Register: Google-only until `from=google`; 403 copy sends user back to Google
- [x] Login: passkey + Google primary; password/recovery in a disclosure
- [x] Docs: new accounts require Google then passkey
