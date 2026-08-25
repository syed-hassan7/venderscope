# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: GRC and Information Security professionals managing a vendor estate day to day — adding vendors, reviewing risk scores and compliance evidence, logging analyst notes, exporting risk registers for audit.

## Product Purpose

Continuous, passive vendor risk intelligence: replaces point-in-time annual vendor audits with 24/7 monitoring across multiple threat-intelligence sources, surfacing risk drift as it happens rather than once a year.

## Positioning

"Your next breach won't wait 12 months." Differentiates from checkbox annual-review vendor risk tools by aggregating live signals (HIBP, NVD, Companies House, Shodan) plus a business-context-weighted Effective Exposure Score — not just a technical severity number, but one adjusted for what a vendor actually touches (PII, financial data, critical infra).

## Operating Context

A GRC/InfoSec analyst adds a vendor by domain; the backend scrapes/searches for compliance certs, security posture, and public risk signals; the analyst reviews the resulting score, compliance evidence, and event feed, sets a data-sensitivity multiplier and review interval, logs analyst notes, and exports a CSV risk register formatted for ISO 27001 risk treatment. Nightly automated re-scans keep data fresh. A guest/unauthenticated scan path exists for quick one-off lookups without an account.

## Capabilities and Constraints

- Free-tier hosting constraints are real and user-facing: HF Spaces backend cold-starts (~30-50s after inactivity), Shodan free-tier key returns zero findings (silently reads as "clean," not "not checked"), outbound email is currently disabled in production (no domain purchased yet for Resend).
- Auth model: Google-then-passkey enrollment, password sign-in closed, recovery codes + session-family invalidation. This is a deliberate, unusual choice (not a generic auth template) and the product's copy already leans into explaining it, but current UI doesn't explain what a passkey *is* to a first-timer.
- Two-stage compliance discovery (site scrape, then web-search fallback) has a known gap: JS-rendered trust centres (Vanta-style) aren't scraped directly, relying on search fallback only.
- Per-user scheduler scoping (alerts scoped to only the vendors a given user owns) is still on the roadmap, not yet built.

## Brand Commitments

Name: VenderScope. Existing visual identity: dark theme, violet/purple accent (`--accent` ~`#8b5cf6`), custom logo component (`VSLogo.jsx`), risk-band color coding (critical/high/medium/low). Auth screens currently carry a distinct "consumer-SaaS" register (animated radar pulses, drifting orbs) vs. the dashboard's soberer tone — per 2026-08-25 critique, this split is being kept deliberately, not converged.

## Evidence on Hand

Live deployed instances exist (frontend + API), README documents exact feature set, known limitations, and version history (CHANGELOG.md). `docs/ARCHITECTURE_REVIEW.md` and `docs/SECURITY.md` carry prior audit findings. No user research, testimonials, or usage analytics on hand — don't fabricate either.

## Product Principles

1. Don't overclaim confidence — surface epistemic limits in the UI itself (e.g. "based on public evidence only," guest-scan disclaimers) rather than presenting scores as verified fact.
2. A silent failure is worse than a visible one, for a risk-monitoring tool specifically — the product's core value is "you can trust what this dashboard says right now."
3. Business-context weighting (data sensitivity × technical severity) over raw technical severity alone — risk is meaningful only relative to what a vendor actually touches.
4. Consequential actions (deleting a vendor's audit trail, changing sign-in factors) get friction and explicit confirmation proportional to what's actually lost, not proportional to which screen got built when.

## Accessibility & Inclusion

Target: WCAG 2.1 AA. Confirmed 2026-08-25 for a GRC/InfoSec professional audience where screen-reader and keyboard-only usage should be assumed, not treated as edge case.
