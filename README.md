# OneCase

An officer workspace for institution complaint coordination, built from the six specifications in this folder. React 19 + TypeScript + Vite, Flask + SQLAlchemy/Alembic, a database-backed worker, and local Sentence Transformer / Cross-Encoder matching.

## Run the application on Windows

The local database is already migrated and populated with **synthetic demonstration records**. The production frontend is in `frontend/dist`. From this directory:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

Open **http://127.0.0.1:5000**. In a second terminal, start matching and deadline monitoring:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1 -Worker
```

All synthetic accounts use `OneCaseDemo!2026`, unless a different password was passed during seeding:

| Account | Purpose |
| --- | --- |
| `lead.rb@onecase.demo` | RB lead: register, assign, transfer, handle RB cases |
| `officer.rb@onecase.demo` | RB officer: read RB cases, handle own assignments |
| `lead.pgrc@onecase.demo` | PGRC lead and receiving transfer officer |
| `officer.pgrc@onecase.demo` | PGRC officer |
| `reviewer@onecase.demo` | Explicit access to seeded cases; can record related/unrelated decisions |
| `auditor@onecase.demo` | Explicit read access to seeded cases |
| `admin@onecase.demo` | No automatic complaint access; operational job counts only |

New cases do **not** automatically receive cross-bureau grants. Provision an explicit grant when required:

```powershell
.venv/Scripts/python.exe -m flask --app backend.app grant-case reviewer@onecase.demo 9
```

## Fresh setup

Node 24+ and Python 3.14 were used for this build. The local backend is tested on Python 3.14.3. PostgreSQL is required for shared/multi-worker deployments; the default SQLite database is an isolated, single-worker local experiment.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
.venv/Scripts/python.exe -m pip install -r backend/requirements-models.txt
.venv/Scripts/python.exe -m flask --app backend.app db upgrade -d backend/migrations
.venv/Scripts/python.exe -m flask --app backend.app seed-demo
.venv/Scripts/python.exe backend/download_models.py
Set-Location frontend
npm ci
npm run build
```

`backend/requirements-lock.txt` records the full locally installed Python dependency set; `frontend/package-lock.json` locks frontend dependencies. Model downloads resolve and record exact repository revisions in `.runtime/models/manifest.json`. Inference uses local files only and disables remote model code. If artifacts or inference fail, the case shows failed matching and supports retry; it never silently substitutes TF-IDF.

For frontend development, run `npm run dev` in `frontend` and the API on port 5000. Vite proxies `/api` to Flask. All persistent local data and evidence are in `.runtime/`, excluded from Git.

## Implemented workflows

- Provisioned officer sign-in, Argon2id password hashes, expiring and revocable server sessions, refresh, CSRF protection, same-origin writes, persistent login throttling.
- Bureau-based case reads; only the accountable officer or lead can mutate; transfers require a lead; reviewers and auditors require explicit case grants. An administrator has no implicit complaint access.
- Canonical institution directory, verified/unverified identities, scoped institution history.
- Complaint registration with idempotency, validated owner, permanent reference, initial assignment, event, and queued job committed together.
- Controlled status changes, reasoned disposal/reopening, remarks, ordinary field edits, optimistic concurrency conflicts.
- Atomic transfer with assignment history, recipient notification and separate acknowledgement. Sender access follows the current authorization scope.
- Private evidence uploads with size, extension and signature validation, checksum storage, authorization on every download, and attachment disposition. Validation is not antivirus scanning.
- Versioned illustrative elapsed/business-hour calendars, explicit deadline revisions, approved pause/resume history, deduplicated deadline alerts and bottleneck notifications. No official AICTE deadline is asserted.
- Institution-gated normalization, pinned local embeddings, normalized cosine top-k retrieval, canonical-order Cross-Encoder reranking, normalized hybrid scoring, machine triage, persisted score/run evidence, stale-input detection, reviewer decisions and history. Original cases remain separate.
- Filtered dashboard and case lists, urgency work queue, eight-week chart with accessible table, responsive navigation, light/dark themes, expandable action logs, alerts, scoped CSV exports and lifecycle-episode reports.
- Database migrations, worker retry/lease handling, synthetic seed, CLI account provisioning/grants, OpenAPI inventory, matching evaluation and backup/restore tooling.

The required reference files named by the specifications (`AICTE_ACITS_Algorithms.md`, research PDF, and three design component source files) were not present in this folder. Implementation follows the six supplied specifications. The interface uses an accessible CSS dot-field login background and Radix dialog primitives; it does not depend on missing component imports.

## Verification

```powershell
.venv/Scripts/python.exe -m pytest backend/tests -q
.venv/Scripts/python.exe backend/evaluate.py
.venv/Scripts/python.exe backend/openapi.py
Set-Location frontend
npm run build
npx playwright install chromium
$env:E2E_MATCHING = '1'
npm run test:e2e
```

Browser tests use a disposable database and never change `.runtime/onecase.db`. `E2E_MATCHING=1` enables real local inference and the reviewer journey. Without it, that one model-dependent test is skipped explicitly. Screenshots of 360, 768, and 1440px layouts are written to `frontend/test-results`.

See [verification notes](docs/VERIFICATION.md), [OpenAPI contract](docs/openapi.json), and the [measured synthetic evaluation](docs/evaluation.json). The evaluation separates institutions into train/validation/test, fits TF-IDF only on training text, freezes tuning before held-out testing, and reports undefined metrics explicitly. Its six held-out pairs are a **smoke check, not an operational accuracy estimate**. Runtime weights/triage thresholds remain labelled unvalidated.

## Shared PostgreSQL deployment

Docker is not installed in the current workspace environment, so Compose/PostgreSQL deployment has not been executed here. The supplied configuration is for local shared-demo setup:

1. Copy `.env.example` to `.env`, set a strong `POSTGRES_PASSWORD`, and keep it out of Git.
2. Run `docker compose up --build -d`. The migration service runs before web/worker startup.
3. Seed only an empty demonstration database: `docker compose exec web python -m flask --app backend.app seed-demo`.
4. Download model artifacts into the shared runtime volume: `docker compose exec worker python backend/download_models.py`.
5. For deployment behind an HTTPS reverse proxy, set `COOKIE_SECURE=true`. Keep the database and runtime volumes private.

Provision non-demo accounts with the interactive CLI (password is not printed):

```powershell
.venv/Scripts/python.exe -m flask --app backend.app create-user --email officer@example.test --name "Example Officer" --role officer --bureau 1
```

The protected `GET /api/operations` endpoint exposes job counts and the oldest queued timestamp to administrator accounts, without case contents.

## Backup and restore

Stop web and worker writers before taking the combined local database/document snapshot:

```powershell
.venv/Scripts/python.exe backend/backup.py save --output .runtime/backups/onecase-demo.zip
.venv/Scripts/python.exe backend/backup.py restore .runtime/backups/onecase-demo.zip --target .runtime/restored-demo
```

Restore refuses an existing target, validates archive paths and SHA-256 checksums, and runs SQLite integrity checks. To run the restored copy, point `DATABASE_URL` at its absolute SQLite database path and set `STORAGE_PATH` through an app configuration override. `test_backup.py` exercises a synthetic case, history and protected document across save/restore.

For PostgreSQL, stop writers and use `pg_dump`/`pg_restore` plus an accompanying archive of the private runtime documents volume. Restore into a fresh database/volume, run migrations and verify complaint/event counts and attachment checksums before resuming. PostgreSQL restore and multi-worker/concurrency tests still require a PostgreSQL environment.

## Remaining production release gates

The application is a functional local demonstration. Production acceptance still requires official institution data, approved bureau/role/retention/SLA policies, a representative labelled multilingual corpus, threshold calibration, PostgreSQL concurrency and restore exercises, antivirus/quarantine integration if required, a 10,000-case load test, and a complete accessibility/security assessment. No SSO, official AICTE integration, operational SLA, model accuracy, or WCAG conformance is claimed by this build.
