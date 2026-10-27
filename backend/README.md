# OneCase backend — Render + Neon

Flask/SQLAlchemy own authentication, object/field authorization, transactional case workflows, matching jobs, and private evidence access. Vercel serves the frontend; Render hosts this API; Neon supplies Postgres and the private `assets` bucket.

The Render Blueprint follows `dev` with `autoDeployTrigger: checksPass`.
Once the GitHub repository is connected and the Blueprint is applied, pushes
to `dev` deploy after CI checks pass, run `python migrate.py` before deployment,
and start `python serve.py`. Existing services not managed by this Blueprint
need the same branch and Auto-Deploy settings entered once in Render.
See [GitHub deployment instructions](../.github/README.md).

The Blueprint also defines `onecase-worker` (Python background worker) and
`onecase-scanner` (private ClamAV TCP service) on Render. The worker installs
`requirements-models.txt`, downloads the committed model revisions, and receives
server-side configuration from the API service. It runs matching, deadline and
milestone reminders, evidence validation/scanning, and a database heartbeat.
Administration shows queue counts and recent worker liveness. Scanner configuration
alone does not establish that its signatures are ready; evidence stays quarantined
until the scanner returns a complete, valid clean response.

Production requires PostgreSQL, private Neon storage credentials, shared Redis,
secure cookies, a valid Fernet key, and random `SECRET_KEY` and
`FRONTEND_PROXY_SECRET` values of at least 32 characters. Configure the latter
identically on Render and Vercel's server environment. These values never belong
in browser variables. Fresh privileged accounts receive a restricted MFA setup
session; they cannot open case or administrative APIs before enrollment succeeds.
Known-password local seed commands are rejected in production. Opt-in public
demo identities retain their separate synthetic scope and random credentials.

Apply migration `e9c54a830bf1` for worker heartbeat reporting. It follows the
existing stakeholder/closure migration `c7b409d2e106`. The API's Render pre-deploy
command applies this migration before release; no destructive schema changes
are required.

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

This backend is a Flask WSGI application, launched with Waitress. From the
repository root, run `.venv/Scripts/python.exe backend/migrate.py`, then
`npm start`. From `backend`, using the root virtual environment, run
`../.venv/Scripts/python.exe migrate.py`, then `../.venv/Scripts/python.exe serve.py`.
For automatic local reload, use
`../.venv/Scripts/python.exe -m flask --app app run --debug --port 5000`.

To use Uvicorn, install the requirements, activate the workspace virtual
environment and run the ASGI entry point from `backend`:

```powershell
../.venv/Scripts/python.exe -m pip install -r requirements.txt
../.venv/Scripts/Activate.ps1
python migrate.py
uvicorn main:app --reload --port 5000
```

`main.py` wraps the existing Flask application with `asgiref.wsgi.WsgiToAsgi`;
routes, database configuration, cookies and authorization remain in Flask.
Without activation, use
`../.venv/Scripts/python.exe -m uvicorn main:app --reload --port 5000`.

Port 5000 serves only the backend: `/` returns API information as JSON and
`/api/health` checks the database. Frontend routes and built assets return 404
on this port. Start the frontend separately with `npm run dev -- --port 5173
--strictPort` from `frontend`, then open `http://127.0.0.1:5173`.

### Password recovery with Twilio SendGrid

Sign-in includes **Forgot password?**, which opens `/forgot-password`. Fill in
these private fields in `backend/.env.local` and restart the backend:

```dotenv
SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=
SENDGRID_FROM_NAME=OneCase
PUBLIC_APP_URL=http://127.0.0.1:5173
```

Use a SendGrid API key with Mail Send permission and a sender address verified
through SendGrid sender/domain authentication. Use the deployed HTTPS frontend
address for `PUBLIC_APP_URL` in production. Delivery uses the SendGrid v3 Mail
Send HTTPS API; no SMTP username or password is needed. Keep all SendGrid
settings in the backend, never in `VITE_*` fields.

Reset links expire after 20 minutes and work once. Only token hashes are stored.
A successful reset revokes all sessions and outstanding reset links, preserves
MFA, and sends a confirmation email. Missing credentials show an honest setup
error; known and unknown emails otherwise receive the same request response.
Email is delivered outside the HTTP request, and delivery failures are recorded
in the backend log without credentials, reset links or message bodies. A failed
delivery invalidates its token; request a new link after fixing the provider.
Apply migration `d72fa0981c43` before using password recovery.

### Public demo accounts

On a public synthetic demonstration deployment, set
`DEMO_ACCOUNTS_ENABLED=true` in Render and redeploy. `python migrate.py`
then provisions 12 persistent demo identities: student, parent, faculty, staff,
other, officer, lead, reviewer, committee, verifier, executive and auditor.
Alternatively, run `python -m flask --app app create-demo-accounts` after
migrations. Both operations preserve existing accounts and are safe to repeat.

The sign-in page's **Demo accounts** button opens a role chooser. Demo sessions
are issued only for explicitly marked, active demo identities. Demo accounts
cannot become administrators or change shared credentials. Case access and
directory entries are restricted to the synthetic `PUBLIC-DEMO` bureau and
demonstration institution. The existing single administrator uses regular
sign-in. No complaint records are inserted by demo-account provisioning, so
new demo workspaces begin at zero. Disable the flag to turn off demo sign-in.

### Registration behavior

The frontend provides `/register/student-parent` and `/register/other`, linked
from sign-in. Both submit to `POST /api/auth/register` and persist accounts with
Argon2 password hashes. Students, parents, faculty, institution staff and other
community users can sign in immediately. Bureau and administrative roles create
pending access requests; they never grant themselves a staff role or bureau.
An existing administrator reviews these requests in Administration and records
the approved role, required bureau, approval reference and reason.

System administrator is excluded from registration. The application supports
one administrator identity with its own password, using the normal sign-in
page. Additional administrator accounts, promotions and expiring admin-role
assignments are rejected. Migration `61b37e20a4f8` enforces a single primary
administrator in the database. Existing credentials are preserved. On a fresh,
empty system, bootstrap that one account with the interactive `create-user`
CLI command; passwords are never hardcoded into the frontend or backend.

Apply migrations before starting the updated backend; revision `8d42c1e7a905`
adds the requested role and organization fields. Registration never seeds cases,
grants, notifications or other demonstration records. The personal workspace
reads counts from `/api/account/summary`, scoped to the signed-in account.

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
