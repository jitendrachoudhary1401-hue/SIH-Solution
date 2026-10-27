# OneCase frontend — Vercel

React, TypeScript and Vite provide the public and officer workspaces for **Team MODEST's OneCase**. The interface is **light-only**, uses a warm ivory/terracotta palette and larger text. The square `public/onecase-emblem.png` contains the user-selected gear emblem without its wordmark; its original gold/navy/green/orange palette is retained. Proportional favicon and launcher sizes live under `public/icons/onecase-emblem-*.png`.

[Live website](https://sih-solution-kappa.vercel.app/) · [Feature overview and screenshots](../README.md#screenshots)

## Local setup

From the `frontend` folder (it deploys independently of the repository root):

```powershell
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Start the Flask backend in a second terminal using [the backend guide](../backend/README.md). The development frontend opens at `http://127.0.0.1:5173` and proxies `/api` to the backend at `http://127.0.0.1:5000`. The backend port serves JSON API responses only. Vite fails if its configured port is occupied, so it does not silently move the frontend to another port.

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
| `FRONTEND_PROXY_SECRET` | Required: the same random value of at least 32 characters configured on Render; server-only |

6. Deploy, then verify `/officer/login`, a direct navigation to `/complaints`, and `/api/health` on the **Vercel** hostname.

Set the Vercel **Production Branch to `dev`** for this repository. The committed
`git.deploymentEnabled=true` enables Git deployments and `installCommand=npm ci`
uses the lockfile. After this one-time connection and environment setup, pushes
to `dev` automatically deploy the frontend. Other branches produce previews.
See [GitHub deployment instructions](../.github/README.md) for CI behavior.

`api/proxy.js` runs on Vercel's server. It forwards `/api/*` to Render, forwards the session cookie/CSRF header, and keeps the browser on one origin. This avoids relying on third-party cookies between unrelated Vercel and Render domains. It forwards credentials only to the configured backend and does not expose service keys. It does not fetch arbitrary user-supplied URLs.

The proxy validates write origins before forwarding them. API responses use `no-store`. Original evidence is downloaded through authorized Flask endpoints rather than public S3 links.

On initial load, the app first calls `/api/wake` and waits up to 90 seconds for
temporary cold-start failures to recover, showing “Waking up OneCase”. It does
not attach session credentials to this liveness request. Invalid proxy
configuration fails immediately instead of pretending the server is asleep.
Protected data, logout revocation and writes still use the normal API checks.
This wake flow runs when a user visits; it does not schedule background pings.

Keep individual uploads within the backend's deployed limit (default 3 MiB) and Vercel's function payload limits. Large document archives require a separate approved delivery design; do not make sensitive buckets public as a workaround.

## Install as an app

The production build includes `/manifest.webmanifest`, 192px/512px launcher
icons, and an Apple touch icon. When Chrome/Edge supplies a native installation
offer, **Install OneCase** opens that browser dialog directly from a click.
There is no instructions popup. The button stays hidden when the browser has
not offered installation, after its one-use offer is consumed, or inside an
installed app. The listener does not cancel the browser's own install promotion;
the address-bar icon and browser menu remain controlled by the browser.

After deployment, open the HTTPS hostname in a regular Chrome/Edge browser
(Android or desktop) to install, or use Safari's Share → Add to Home Screen on
iPhone/iPad. The browser decides when its native prompt becomes available;
private windows and embedded browsers may not offer it. Installation requires
no backend change. Case records and authentication still require a connection;
this change adds no service worker or offline cache of private data.

Verify `/manifest.webmanifest` returns JSON and both `/icons/onecase-emblem-192.png` and
`/icons/onecase-emblem-512.png` load from the deployed hostname. In Chrome DevTools,
Application → Manifest shows any installability errors.

## Checks

Privileged production accounts complete a restricted ten-minute authenticator
enrollment flow after password verification. Workspace APIs remain inaccessible
until confirmation. Confirmation rotates the session and CSRF token; the screen
keeps recovery codes visible until the user confirms they have saved them.

The sign-in page includes a **Demo accounts** role chooser. The backend must
have `DEMO_ACCOUNTS_ENABLED=true` and provisioned demo identities. No demo
password is embedded in the frontend. Phone and tablet layouts use a compact
sign-in card, touch-sized controls and drawer navigation through 1100px;
wide tables scroll inside their cards instead of widening the whole page.

```powershell
npm run build
npm run test:proxy
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Resolve-Path '..').Path '.runtime/playwright'
npx playwright install chromium
npm run test:e2e
```

Browser tests require the full workspace checkout and a Python test environment in the root `.venv`; they start a disposable local backend and use synthetic data. Deployment and `npm run build` require only this frontend folder. No Neon credentials are required by browser tests. The test host injects a scanner fixture; it is not a real malware scan or a production scanner configuration. Enable `E2E_MATCHING=1` only after installing local model dependencies/artifacts to also test actual semantic matching.

## Troubleshooting

**Forgot password?** on sign-in opens `/forgot-password`. Reset emails are sent
by the backend through Twilio SendGrid after its private env fields are filled
in. The email opens `/reset-password` with a one-time token in the URL fragment;
the page removes that fragment from the address bar and requires a confirmed
new password. Tokens expire after 20 minutes. Browser tests capture SendGrid
requests only inside the disposable test host; they never send real emails.

Unknown frontend URLs display a custom warm, light 404 page with a return link. Known protected routes still send signed-out visitors to sign-in.

Network errors, request timeouts, browser offline events and API gateway failures (502/503/504) automatically clear the visible session and query cache. A persistent logout marker prevents a reload or another tab from restoring the previous session. When connectivity returns, the frontend revokes the old server session before allowing another sign-in. An unreachable backend cannot revoke its session immediately; the local workspace is hidden immediately and server revocation is retried on reconnect, every 15 seconds while signed out, and before sign-in. Normal authorization/validation errors and missing records do not trigger connection logout.

During an outage, a dedicated warm, light screen displays **“Backend is down. Try again later.”** and confirms automatic logout. The **Try again** button and automatic recovery checks keep the screen visible while the service is unavailable. Once the old session is revoked or confirmed expired, the sign-in screen returns; the previous workspace does not reopen automatically.

- **`Backend connection is not configured`:** set `BACKEND_URL` in Vercel, then redeploy.
- **Login returns to the sign-in page:** keep `VITE_API_BASE_URL=/api`, verify that requests reach the Vercel proxy, and use HTTPS with `COOKIE_SECURE=true` on Render.
- **Frontend route returns 404:** verify the root directory and `vercel.json` SPA fallback.
- **403 after a role/grant change:** affected sessions are revoked intentionally. Sign in again.
- **A control is absent:** actions follow backend capabilities; assigning a designation alone does not grant case access.
- **Evidence remains pending:** the backend worker/scanner must validate it. The frontend cannot mark evidence clean.
