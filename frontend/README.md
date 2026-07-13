# VenderScope Frontend

React 19 + Vite + TailwindCSS frontend for the VenderScope vendor risk intelligence platform.

## Setup

```bash
npm install
```

Create `.env.local`:
```env
VITE_API_URL=http://127.0.0.1:8000/api
```

## Development

```bash
npm run dev       # http://localhost:5173
npm run build     # production build to dist/
npm run lint      # ESLint
npm run preview   # preview production build locally
```

## Deployment

Deployed on Vercel. `vercel.json` configures:
- API reverse proxy: `/api/*` → `https://darkitowo-venderscope-api.hf.space/api/*`
- SPA fallback (non-API routes → `index.html`)
- Security headers: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy

Production env var on Vercel:
```env
VITE_API_URL=/api
```

Use the same-origin `/api` path (not the HF Space URL). Direct browser calls to HF break credentialed auth/CORS.
## Structure

```
src/
├── api/client.js          # Axios client, token injection, silent refresh interceptor
├── context/AuthContext.jsx # JWT access token state, silent refresh on mount
├── pages/
│   ├── Dashboard.jsx       # Vendor list, risk delta, sort controls
│   ├── VendorDetail.jsx    # Per-vendor risk detail, score history, compliance
│   ├── GuestScanPage.jsx   # Unauthenticated CVE scan (v3.5)
│   ├── Login.jsx
│   ├── Register.jsx
│   └── DocPage.jsx         # Renders /privacy, /terms, /security markdown
├── components/
│   ├── VendorCard.jsx
│   ├── ScoreGauge.jsx
│   ├── ScoreChart.jsx
│   ├── EventFeed.jsx
│   ├── CompliancePanel.jsx
│   ├── AddVendorModal.jsx
│   ├── DeleteAccountModal.jsx
│   ├── QuotaBanner.jsx
│   ├── VendorAvatar.jsx
│   └── Footer.jsx
└── docs/
    ├── privacy.md
    ├── terms.md
    └── security.md
```
