# OneCase

An officer workspace for accountable institution-complaint coordination. The application uses a warm, light-only interface, larger text and sharp controls. Its selected gear emblem connects the officer, student, institution, case record and education symbols, preserving the supplied gold/navy/green/orange palette without an embedded wordmark.

| Component | Implementation / deployment |
| --- | --- |
| Frontend | React + TypeScript + Vite, deployed by you on Vercel |
| API | Flask + SQLAlchemy + psycopg, deployed by you on Render |
| Database | Neon Postgres; Alembic migrations use a direct connection |
| Private evidence | Neon S3-compatible `assets` bucket |
| Rate limits | In-memory local limits; shared Redis required in production |
| Worker | Local semantic matching, deadline alerts and quarantine processing |

Deploy **only `frontend` to Vercel** and **only `backend` to Render**, using those folders as each platform's Root Directory. Deployment configs live in `frontend/vercel.json` and `backend/render.yaml`. No separate AWS account or service is required or provisioned.

## Setup guides

- [Complete setup and deployment](SETUP_GUIDE.md)
- [Frontend / Vercel README](frontend/README.md)
- [Backend / Render / Neon README](backend/README.md)
- [GitHub workflow guide](.github/README.md)
- [Neon setup and actual service verification](docs/NEON_SETUP.md)
- [Database schema and migration notes](docs/DATABASE_SCHEMA.md)
- [Code audit, repairs and release checks](docs/CODE_AUDIT_AND_REPAIRS.md)

## Local commands

Run from the repository root after configuring the private environment files:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
npm ci
npm --prefix frontend ci
npm run build
.venv/Scripts/python.exe backend/migrate.py
npm start
```

The backend API runs at `http://127.0.0.1:5000`; its root returns JSON and `/api/health` checks connectivity. It does not serve frontend pages or assets. Run `npm run dev` in another terminal and open the frontend at `http://127.0.0.1:5173`. Vite proxies `/api` requests to port 5000. Install the optional model dependencies/artifacts before starting `npm run worker`.

Preserve existing `backend/.env` and root `.env.local`; do not overwrite them with example files. Neon/database/storage credentials are backend-only. The frontend uses `/api` and the Vercel server-only proxy; no service secret belongs in a `VITE_*` variable.

## Verification

```powershell
npm run build
.venv/Scripts/python.exe -m pip install -r backend/requirements-test.txt
.venv/Scripts/python.exe -m pytest backend/tests -q
Set-Location frontend
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Resolve-Path '..').Path '.runtime/playwright'
npx playwright install chromium
npm run test:e2e
```

CI runs these checks with a disposable local database and synthetic data. Opt-in real Neon service checks use an isolated branch and private environment file. They have verified actual Postgres persistence, authentication, private-object round trips, quarantine denial and cross-bureau access denial.

## Repository

`frontend/src` contains the UI, case workflow, administration and account-security screens. `backend/app` contains authorization, transactional case APIs, proceeding/compliance services, private storage, security and background jobs. `backend/migrations` contains additive schema changes. The numbered specification files remain the source requirements; the READMEs explain the implemented setup and its verification limits.

The normalized identity/issue schema is additive and preserves legacy cases. Schema availability does not establish a verified person, prove an allegation, or mean every issue-level matching/UI refinement is complete. Existing matching still requires a human relationship decision and never merges complaints.

## Before real-data deployment

Enter platform environment values yourself using the guides. Validate shared Redis, HTTPS/cookies, privileged MFA/recovery, private malware scanning, worker/model availability, approved permissions/policies, encrypted storage and recovery procedures. Production accounts must be provisioned deliberately; do not seed known demonstration passwords into a real-data environment.

No Render/Vercel deployment is published by the setup scripts or the GitHub workflow. Actual cloud-app URLs and GitHub-hosted workflow results require your deployment/configuration.
