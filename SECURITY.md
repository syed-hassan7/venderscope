# Security Policy

## Supported versions

Security fixes are applied on the `main` branch of this repository.

## Reporting a vulnerability

Please report security issues **privately** — do not open a public GitHub issue for exploitable flaws.

1. Email the maintainer via the address listed on the [GitHub profile](https://github.com/syed-hassan7) for this project, **or**
2. Use GitHub **Private vulnerability reporting** on this repository (Security → Report a vulnerability), if enabled.

Include:

- Affected component (API / frontend / guest scan / auth)
- Description and impact
- Steps to reproduce (against your own test instance only)
- Any suggested fix

You should receive an acknowledgement when practical. Please allow time for investigation before public disclosure.

## Scope notes

- This product performs outbound intelligence lookups against third-party domains you choose to scan. Do not use it to attack systems you do not own or have permission to assess.
- `VITE_*` frontend environment variables are public by design (embedded in the browser bundle). Never place secrets in `VITE_*` keys.
