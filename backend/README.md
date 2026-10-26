# OneCase backend — Render + Neon

Flask/SQLAlchemy own authentication, object/field authorization, transactional case workflows, matching jobs, and private evidence access. Vercel serves the frontend; Render hosts this API; Neon supplies Postgres and the private `assets` bucket.

## Local setup

Run from the repository root:

```powershell
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
# Only on a fresh setup; preserve any existing .env.
Copy-Item .env.example .env
```

The workspace may already contain `backend/.env`; preserve it instead of overwriting it. Generate new secret values locally when setting up another environment:

```powershell
.venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
.venv/Scripts/python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store the first output as `SECRET_KEY` and the second as `MFA_ENCRYPTION_KEY` in the private environment settings. Do not commit or share the output.

## Environment loading and secrets

Existing process environment wins. Files fill missing keys in this order:

1. `backend/.env.local`.
2. `backend/.env` — application settings and local secrets.
3. Root `.env.local` — optional Neon CLI-managed values during workspace development.
4. Root `.env` — optional local fallback.

All these files are ignored by Git. Render receives values through its environment dashboard; it does not need committed dotenv files. The API normalizes `postgresql://`/`postgres://` to SQLAlchemy's existing `postgresql+psycopg://` driver.

The Render-only deployment reads process environment variables and its own `.env` files. Workspace-root env files are optional. Production runtime/model defaults are under `backend/.runtime`; existing local workspace data remains supported for development. Flask does not require the frontend build on Render.

Neon is the file-storage provider; no AWS account or AWS resources are added. For Render, map Neon's CLI-generated `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`, and `AWS_REGION` to `NEON_STORAGE_ACCESS_KEY_ID`, `NEON_STORAGE_SECRET_ACCESS_KEY`, `NEON_STORAGE_ENDPOINT`, and `NEON_STORAGE_REGION` respectively. The adapter still accepts the original CLI names as a local compatibility fallback. All values stay private.

| Setting | Purpose |
| --- | --- |
| `DATABASE_URL` | Pooled Neon application connection |
| `DATABASE_URL_UNPOOLED` | Direct connection for Alembic migrations |
| `NEON_STORAGE_ACCESS_KEY_ID`, `NEON_STORAGE_SECRET_ACCESS_KEY` | Private Neon bucket credentials |
| `NEON_STORAGE_ENDPOINT`, `NEON_STORAGE_REGION` | Neon object-storage endpoint and region |
| `STORAGE_BACKEND=neon`, `STORAGE_BUCKET=assets` | Store new evidence in the private Neon bucket |
| `SECRET_KEY`, `MFA_ENCRYPTION_KEY` | Backend identity protection; never frontend variables |
| `RATE_LIMIT_STORAGE_URI` | `memory://` for one local process; shared `rediss://…`/`redis://…` for production |
| `COOKIE_SECURE` | `false` only for local HTTP, `true` for deployed HTTPS |
| `SESSION_IDLE_MINUTES`, `STEP_UP_MINUTES` | Idle session expiry and recent-authentication window |
| `CLAMAV_HOST`, `CLAMAV_PORT` | Approved private malware-scanner service |
| `MODEL_PATH` | Pinned local model bundle directory |
| `API_HOST`, `API_PORT` | Local listener; Render's `PORT` takes precedence |
| `MAX_UPLOAD_BYTES` | Deployed per-file size limit; default 3 MiB |

Never include these keys in frontend source, logs, screenshots, or public CI variables. Only examples with placeholders belong in Git.

## Neon setup

The CLI, nine Neon skills, and OAuth MCP entry have already been configured for this project. Preserve `neon.ts` and `.codex/config.toml`. The MCP entry stores the server URL, not a project API key.

For a fresh workstation:

```powershell
npm i -g neon@latest
neon login
neon init -y --org-id org-young-dew-78896435 --project-id sweet-snow-41606635 --branch production --services 'postgres,object-storage' --agent codex --mcp-auth oauth --mcp-config-location project
neon deploy
```

Finish browser OAuth when prompted. `neon deploy` provisions the private bucket in `neon.ts` and writes service values into root `.env.local`. It does not host the React frontend or deploy the Flask API to Render.

## Migrate and run

Run these commands from `backend` after the local setup above:

```powershell
.venv/Scripts/python.exe migrate.py
.venv/Scripts/python.exe serve.py
```

Open `http://127.0.0.1:5000/api/health` to check the database connection. A pooled URL serves normal requests; migrations use the direct URL. Existing local evidence retains its recorded local backend while new Neon evidence stores object keys and metadata in Postgres.

For an **empty synthetic demonstration environment only**:

```powershell
.venv/Scripts/python.exe -m flask --app app seed-demo
```

Do not seed known demo passwords into a real-data deployment. Provision approved users with the interactive `create-user` command instead. Privileged production users must complete MFA enrollment before production sign-in will be allowed. Enrollment/recovery need to be completed through the approved operating process; do not disable the production check to bypass setup.

## Deploy to Render

1. Connect the GitHub repository to a Render Python web service. For Blueprint setup, set the Blueprint file path to `backend/render.yaml` (it declares `rootDir: backend`). If deploying this folder as its own repository, change that field to `.`.
2. Set **Root Directory to `backend`**. Deployment needs no frontend or repository-root files.
3. Build command: `pip install -r requirements.txt`.
4. Pre-deploy command: `python migrate.py`. If your Render plan has no pre-deploy hook, apply migrations manually before starting the new release.
5. Start command: `python serve.py`.
6. Health path: `/api/health`.
7. Copy the Neon-managed values from private `.env.local` into Render's environment dashboard yourself.
8. Add the application secrets and set `APP_ENV=production`, `COOKIE_SECURE=true`, `API_HOST=0.0.0.0`, `STORAGE_BACKEND=neon`, `STORAGE_BUCKET=assets`.
9. Supply a shared Redis URI for rate limiting. Production startup fails closed without Redis configuration.
10. Add the Render URL as `BACKEND_URL` on Vercel, keep `VITE_API_BASE_URL=/api`, and redeploy Vercel.

Do not copy `API_PORT=5000` over Render's assigned `PORT`; the server reads `PORT` first. SQLite is only a local experiment and is not the deployed database.

## Worker, evidence scanning and models

Use a separate Render background worker or another approved worker host:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-models.txt
.venv/Scripts/python.exe download_models.py
.venv/Scripts/python.exe worker.py
```

The worker needs the same Neon/database/storage and model-path configuration as the API. Persist and protect the downloaded model bundle; a web-instance filesystem is not durable model storage. Models load locally with pinned revisions and remote model code disabled.

The worker processes matching, deadline scans, and quarantined uploads. Configure a reachable private ClamAV scanner. If scanning is unavailable, files remain pending and downloads return 423. No upload is silently marked clean. Parser execution has a timeout, page/pixel limits and a reduced environment; hardened production parser/network isolation and host-level controls still require deployment verification.

## Checks and live service proof

From `backend` (browser journeys additionally require the frontend checkout):

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-test.txt
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe tests/live_neon_services.py --env-file /PRIVATE/PATH/validation.env --migrate --seed-demo
```

The live command is opt-in and should run on an isolated Neon branch, not against real complaints. It checks actual Postgres authentication/persistence, actual private S3 round trips/checksums, API evidence metadata, quarantine denial, and cross-bureau denial. It never prints credential values. The validation branch used during setup expires automatically.

## Schema and operational boundaries

Committed Alembic migrations preserve the original complaints and add proceeding/permission/security/storage records plus normalized people, locations, campuses, contacts, identity claims/checks, participants, sources, issues and issue relationships. Legacy complaints receive a marked default issue and preserved source record. Names are not used to backfill people. Creating the schema does not itself verify a person or complete every issue-level matching/UI refinement.

Database backups, private-object backups, recovery testing, storage encryption, HTTPS/proxy trust, MFA recovery ownership, grant reviews, policy sources and incident response must be validated for the actual deployment. See [the security requirements](../09_Security.md) and the [root setup guide](../SETUP_GUIDE.md).
