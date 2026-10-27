# Project test report — 27 October 2026

The current code passes local validation. The production deployment is not fully working.

## Local validation

| Check | Result |
| --- | --- |
| Backend: `python -m pytest backend/tests -q` | 60 passed |
| Frontend: `npm run build` | Passed |
| API proxy: `npm run test:proxy` | 3 passed |
| Browser: `npm run test:e2e` | 20 passed, 1 skipped |

Browser checks cover registration, password recovery, direct login for all
12 demo roles, sessions, case workflows, outage recovery, and layouts at
320, 390, 768, 820 and 1024 pixels. The optional real-model matching browser
test was skipped because its model dependency flag was not enabled.

Backend and browser tests use disposable databases. Email-provider requests
are captured in tests; actual SendGrid inbox delivery was not verified.

## Live checks

| Endpoint | Observed result |
| --- | --- |
| Render `/` | 200, backend API JSON |
| Render `/api/health` | 200 |
| Production Vercel `/officer/login` | 200, frontend HTML |
| Production Vercel `/api/health` | 200 |
| Production Vercel `/api/auth/me` without a session | 401, expected |
| Production Vercel `/api/auth/demo-accounts` | 500, failing |

Production frontend: `https://sih-solution-kappa.vercel.app`.
Backend: `https://sih-solution.onrender.com`.

The production frontend serves `/assets/index-m8NSC2E_.js`, an older bundle
without the demo-account chooser and password-reset UI. The tested local build
serves `/assets/index-bkb5kV3E.js`.

Read-only inspection of the saved Neon project's production branch, database
`onecase`, confirms Alembic revision `40177bd277c9`. The `user` table lacks
`requested_role`, `organization` and `is_demo`; `password_reset` is absent.
The current committed migration head is `af4e310ce902`.

## Required deployment work

1. Deploy the latest frontend changes to Vercel Production.
2. Apply committed backend migrations using `python migrate.py` on Render.
3. Set `DEMO_ACCOUNTS_ENABLED=true` for the intended public synthetic demo deployment;
   the migration command then provisions the 12 demo identities idempotently.
4. Recheck the live demo-account list and direct demo sign-in after deployment.

No production accounts, credentials or database schema were changed during
this test run. Live account creation, authenticated workflows and email
delivery remain unverified until the deployment issues are resolved.
