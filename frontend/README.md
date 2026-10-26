# OneCase frontend — Vercel

React, TypeScript and Vite provide the officer workspace. The interface is **light-only**, uses a warm ivory/terracotta palette and larger text, and uses the supplied `public/logo.png` as its logo and favicon.

## Local setup

From the `frontend` folder (it deploys independently of the repository root):

```powershell
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Start the Flask backend in a second terminal using [the backend guide](../backend/README.md). The development frontend opens at `http://127.0.0.1:5173` and proxies `/api` to the backend.

| Variable | Where it is used | Example |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Browser API path | `/api` |
| `API_PROXY_TARGET` | Vite dev server only | `http://127.0.0.1:5000` |
| `FRONTEND_HOST` | Vite dev server | `127.0.0.1` |
| `FRONTEND_PORT` | Vite dev server | `5173` |

Only `VITE_*` variables are intentionally exposed to browser code. **Never put database URLs, Neon storage keys, Redis credentials, or MFA secrets in a `VITE_*` variable.**

## Deploy to Vercel

1. Import the GitHub repository in Vercel.
2. Set **Root Directory to `frontend`**. Both `api/proxy.js` and `vercel.json` are inside this folder; deployment requires no files outside it.
3. Select the Other framework preset if Vercel asks. The committed config supplies build/output settings.
4. Use Node.js 24. Install command: `npm ci`. Build command: `npm run build`. Output directory: `dist`.
5. Add the following project environment values yourself:

| Vercel variable | Value |
| --- | --- |
| `VITE_API_BASE_URL` | `/api` |
| `BACKEND_URL` | Your Render web-service URL, such as `https://your-api.onrender.com`, without `/api` |
| `FRONTEND_PROXY_SECRET` | The same long random value configured on Render, if proxy protection is enabled |

6. Deploy, then verify `/officer/login`, a direct navigation to `/complaints`, and `/api/health` on the **Vercel** hostname.

`api/proxy.js` runs on Vercel's server. It forwards `/api/*` to Render, forwards the session cookie/CSRF header, and keeps the browser on one origin. This avoids relying on third-party cookies between unrelated Vercel and Render domains. It forwards credentials only to the configured backend and does not expose service keys. It does not fetch arbitrary user-supplied URLs.

The proxy validates write origins before forwarding them. API responses use `no-store`. Original evidence is downloaded through authorized Flask endpoints rather than public S3 links.

Keep individual uploads within the backend's deployed limit (default 3 MiB) and Vercel's function payload limits. Large document archives require a separate approved delivery design; do not make sensitive buckets public as a workaround.

## Checks

```powershell
npm run build
npm run test:proxy
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Resolve-Path '..').Path '.runtime/playwright'
npx playwright install chromium
npm run test:e2e
```

Browser tests require the full workspace checkout and a Python test environment in the root `.venv`; they start a disposable local backend and use synthetic data. Deployment and `npm run build` require only this frontend folder. No Neon credentials are required by browser tests. The test host injects a scanner fixture; it is not a real malware scan or a production scanner configuration. Enable `E2E_MATCHING=1` only after installing local model dependencies/artifacts to also test actual semantic matching.

## Troubleshooting

- **`Backend connection is not configured`:** set `BACKEND_URL` in Vercel, then redeploy.
- **Login returns to the sign-in page:** keep `VITE_API_BASE_URL=/api`, verify that requests reach the Vercel proxy, and use HTTPS with `COOKIE_SECURE=true` on Render.
- **Frontend route returns 404:** verify the root directory and `vercel.json` SPA fallback.
- **403 after a role/grant change:** affected sessions are revoked intentionally. Sign in again.
- **A control is absent:** actions follow backend capabilities; assigning a designation alone does not grant case access.
- **Evidence remains pending:** the backend worker/scanner must validate it. The frontend cannot mark evidence clean.
