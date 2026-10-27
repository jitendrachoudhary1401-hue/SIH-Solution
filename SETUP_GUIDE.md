# OneCase setup and deployment guide

The supported deployment layout is:

```text
Browser → Vercel frontend + same-origin /api proxy → Render Flask API
                                                    ├─ Neon Postgres
                                                    ├─ Neon private object storage
                                                    └─ Shared Redis rate limiter
                  Separate worker → matching, alerts and quarantined evidence scanning
```

Start with [frontend setup](frontend/README.md), [backend setup](backend/README.md), and [GitHub workflow](.github/README.md).

Set Vercel Root Directory to **`frontend`**: install `npm ci`, build `npm run build`, output `dist`. Its proxy and deployment config are inside that folder.

Set Render Root Directory to **`backend`**: build `pip install -r requirements.txt`, pre-deploy `python migrate.py`, start `python serve.py`, health path `/api/health`. For Blueprint import, choose `backend/render.yaml` as the Blueprint file path. If the plan has no pre-deploy hook, run migrations manually before releasing the new API. The backend needs no frontend build or repository-root files.

No AWS account or AWS service is added. Private files remain on Neon object storage. The Neon CLI emits S3-compatible names; when entering Render settings, map these private values:

| Neon CLI key in private root `.env.local` | Render key |
| --- | --- |
| `AWS_ACCESS_KEY_ID` | `NEON_STORAGE_ACCESS_KEY_ID` |
| `AWS_SECRET_ACCESS_KEY` | `NEON_STORAGE_SECRET_ACCESS_KEY` |
| `AWS_ENDPOINT_URL_S3` | `NEON_STORAGE_ENDPOINT` |
| `AWS_REGION` | `NEON_STORAGE_REGION` |

These are Neon credentials, not a request to create AWS resources. Legacy CLI variable names remain supported for local development. Never place either version in Vercel browser variables. Set `DATABASE_URL` and `DATABASE_URL_UNPOOLED` unchanged on Render.

## Local quick start

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
npm ci
npm --prefix frontend ci
npm run build
.venv/Scripts/python.exe backend/migrate.py
npm start
```

Preserve existing private environment files. A fresh workstation needs `backend/.env` application settings and root `.env.local` Neon-managed service values. Never commit either file. Use `frontend/.env.local` only for public API-path and local dev-proxy settings.

## Values you supply to the deployment platforms

### Render

- Neon `DATABASE_URL` and `DATABASE_URL_UNPOOLED`.
- Neon `NEON_STORAGE_ACCESS_KEY_ID`, `NEON_STORAGE_SECRET_ACCESS_KEY`, `NEON_STORAGE_ENDPOINT`, `NEON_STORAGE_REGION` (mapping below).
- `STORAGE_BACKEND=neon`, `STORAGE_BUCKET=assets`.
- Random `SECRET_KEY` and valid Fernet `MFA_ENCRYPTION_KEY`.
- `APP_ENV=production`, `COOKIE_SECURE=true`, `API_HOST=0.0.0.0`.
- Required shared `FRONTEND_PROXY_SECRET` of at least 32 random characters,
  identical to the Vercel server-side value. Production startup rejects an absent
  or short value, local SQLite, and incomplete private-storage configuration.
- A shared `RATE_LIMIT_STORAGE_URI` (Redis); optional configured proxy secret.
- Worker/scanner/model settings for the separate background worker.

### Vercel

- `VITE_API_BASE_URL=/api`.
- `BACKEND_URL=https://YOUR-RENDER-SERVICE.onrender.com`.
- Required matching `FRONTEND_PROXY_SECRET` (server-only, at least 32 characters).

Do not put database URLs or service keys in any `VITE_*` variable. The serverless API proxy inside `frontend/api` reads `BACKEND_URL`; the browser bundle does not contain Neon credentials.

## Deploy order

1. Test migrations on an isolated Neon branch.
2. Apply reviewed migrations to the intended application branch.
3. Deploy Render with its private environment settings; check `/api/health`.
4. Provision approved officer accounts and complete required privileged MFA/recovery setup.
5. Deploy Vercel with Root Directory `frontend` and its backend URL; set Render Root Directory to `backend`.
6. Apply/sync the Blueprint's Render worker and private scanner services. The worker
   installs model dependencies and the pinned `backend/model-bundle.json` artifacts
   at build time. Its private environment values reference the API. Review the
   selected Render plans before applying: ClamAV needs 3-4 GiB for signature reloads.
   Supply a working shared Redis URI to the API; the worker inherits it.
7. Check sign-in, registration, authorized case access, a rejected direct cross-bureau request, upload quarantine, post-scan download, and logout.

Fresh privileged accounts first see authenticator enrollment. The short setup
session cannot read workspace records. After a valid TOTP code, save the recovery
codes and continue; the server rotates the cookie and CSRF token. Never disable
the production MFA requirement to get around account setup.

Use Administration's institution review tab to confirm an unverified institution
from an authorized source. Preserve its exact identifier and record approval and
reason. Existing records are never automatically merged; verification requeues
matching failures for that institution. Inspect `/api/operations` as an administrator
for worker heartbeats and backlog. `/api/health` alone checks database connectivity.

## Verification status and remaining setup

The Neon CLI/skills/MCP have been configured, the private bucket was provisioned, and actual Postgres/private-object/API checks passed on an isolated synthetic branch. Build/test command evidence is recorded in [Neon setup notes](docs/NEON_SETUP.md).

Enter Render/Vercel environment values and connect the GitHub repository once.
Use `dev` as Vercel's Production Branch and apply `backend/render.yaml` as the
Render Blueprint (or set an existing service's linked branch to `dev` and
Auto-Deploy to After CI Checks Pass). Subsequent pushes to `dev` deploy the
frontend automatically; the API deploys after CI checks pass. Set Render's
`PUBLIC_APP_URL` to the HTTPS frontend URL and configure SendGrid privately
for password reset email. See [the release guide](.github/README.md).

Live deployment URLs, platform environment values, GitHub branch protection,
Redis/scanner availability, and production MFA/recovery readiness still require
verification on the deployed services.
