# Google-gated passkey signup

Date: 2026-08-25  
Status: approved for implementation

## Problem

Passkeys prove control of an authenticator on this origin. They do not prove mailbox control. Typed-email signup lets whoever finishes WebAuthn own `you@gmail.com`. We will not add a mailer or a sending domain.

## Decision

New accounts are created only after Google OIDC (`email_verified`, PKCE, nonce, RS256) plus a passkey in the same pending session. Identity stored is `google_sub`. Email is a label copied from Google.

Keep FastAPI JWTs. Do not migrate to Supabase Auth.

## Adversarial review (closed)

| Gap | Close how |
|-----|-----------|
| UI-only “prefer Google” | Unauthenticated `register/begin` and signup `register/finish` require a valid `vs_google_pending` cookie. Missing/invalid → 403. |
| Client picks a different email than Google | Signup begin ignores body email. Challenge email = pending token email. |
| Finish without cookie after a leaked challenge id | Signup challenges (`user_id` is null) require pending; email must match. |
| Logged-in “add passkey” | Requires step-up (existing passkey or leftover password hash). Google-only first passkey remains the residual exception. |
| Legacy passkey/password users with no `google_sub` | Leave working. Password **sign-in is closed**. Google login still 409 if email exists without `google_sub` — sign in with passkey/recovery then link. No silent link. |
| Password as default login | Closed at the API. `POST /api/auth/login` always 403. Leftover bcrypt hashes are step-up / delete-account only. |
| Google-only account (skip passkey) | Rejected. Passkey remains required at enrollment. |
| Same `JWT_SECRET` for pending + sessions | Acceptable. Pending `type` is `google_pending`; 15 min TTL. Compromised secret forges everything anyway. |
| XSS 15-min access JWT | Unchanged. Memory-only access token. Not in scope. |
| HF XFF hop | Unchanged. Not this feature. |

## Flows

**Enroll:** Google start → unknown user → pending cookie, no session, no row → `/register?from=google` → passkey begin/finish (cookie required) → user + `google_sub` + recovery codes.

**Login:** Passkey (discoverable, email optional) or Google (`google_sub`). Recovery is secondary. Password sign-in is closed.

**Add passkey:** Authenticated begin/finish, no pending cookie. Step-up required if the account already has a passkey or a password hash.

## Out of scope

Email confirmation mailer, GoTrue, forcing existing users to link Google, JWE, encrypting emails at rest.
