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
- Neon `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`, `AWS_REGION`.
- `STORAGE_BACKEND=neon`, `STORAGE_BUCKET=assets`.
- Random `SECRET_KEY` and valid Fernet `MFA_ENCRYPTION_KEY`.
- `APP_ENV=production`, `COOKIE_SECURE=true`, `API_HOST=0.0.0.0`.
- A shared `RATE_LIMIT_STORAGE_URI` (Redis); optional configured proxy secret.
- Worker/scanner/model settings for the separate background worker.

### Vercel

- `VITE_API_BASE_URL=/api`.
- `BACKEND_URL=https://YOUR-RENDER-SERVICE.onrender.com`.
- Matching `FRONTEND_PROXY_SECRET` if configured on Render.

Do not put database URLs or service keys in any `VITE_*` variable. Vercel's root serverless API proxy reads `BACKEND_URL`; the browser bundle does not contain Neon credentials.

## Deploy order

1. Test migrations on an isolated Neon branch.
2. Apply reviewed migrations to the intended application branch.
3. Deploy Render with its private environment settings; check `/api/health`.
4. Provision approved officer accounts and complete required privileged MFA/recovery setup.
5. Deploy Vercel from the repository root with its backend URL.
6. Start/configure the worker, private scanner, model artifacts and shared Redis.
7. Check sign-in, registration, authorized case access, a rejected direct cross-bureau request, upload quarantine, post-scan download, and logout.

## Verification status and remaining setup

The Neon CLI/skills/MCP have been configured, the private bucket was provisioned, and actual Postgres/private-object/API checks passed on an isolated synthetic branch. Build/test command evidence is recorded in [Neon setup notes](docs/NEON_SETUP.md).

You will enter Render/Vercel environment values and trigger their deployments yourself. Those public deployment URLs, platform environment values, GitHub branch protection, live Redis/scanner availability, production MFA/recovery readiness and real-data release controls are not proven by local files or a successful Neon test.
