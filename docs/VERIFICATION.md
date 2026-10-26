# Verification record

Updated 27 October 2026. These checks describe the local/synthetic implementation and service setup, not production certification.

| Check | Actual result |
| --- | --- |
| `npm run build` inside `frontend` | Passed: TypeScript + Vite production assets |
| Backend pytest | 24 passed, including isolated backend-folder migrations and health |
| Server-only Vercel proxy tests | 3 passed |
| Browser suite | 3 passed; optional real-model test skipped in the last run |
| Running app | `/api/health` and `/officer/login` returned HTTP 200 |
| Neon migrations | Three migrations passed on validation branch, then on the initially empty intended application branch |
| Real Neon service flow | Pooled connection, authentication, complaint persistence, private-object/checksum round trip, quarantine denial and cross-bureau denial passed |
| Frontend credential scan | No configured server secret values found in three compiled JavaScript bundles |

Backend tests include authorization, sessions, expiry, CSRF, idempotency, stale versions, transfer ownership, lifecycle episodes, protected evidence, backups, matching failure behavior, expiring grants/appointments, case conflicts, independent compliance verification, one-time MFA recovery and missing-scanner quarantine. The rate-limit test confirms that an excess sign-in request returns 429 before any database statement executes.

Deployment configs now live in `frontend/vercel.json` and `backend/render.yaml`. The Vercel proxy is an ES module inside `frontend/api`; its three tests run with `npm run test:proxy` from `frontend`. An isolated subprocess test copies only backend code, with no original environment files or frontend, applies all committed migrations to a disposable database and confirms HTTP 200 from `/api/health`. No AWS resources were added; Neon storage settings on Render use the `NEON_STORAGE_*` aliases.

Browser checks cover the officer registration/action/disposal/reopening/transfer/acknowledgement journey, warm light-only styling, larger body text, responsive navigation, action history and direct API denial. Test files are synthetic. The browser test host uses a scanner double; that is not evidence of a deployed malware scanner.

Earlier local model inference produced a high relevance suggestion for the two seeded fee-refund complaints and low relevance for their comparisons with the unrelated laboratory complaint. The separate tiny synthetic held-out evaluation is recorded in `evaluation.json`; it is not an operational accuracy estimate, a multilingual validation or a 10,000-case load test.

See `NEON_SETUP.md` for provisioning output and a failure/retry account. Render/Vercel publication and GitHub-hosted CI execution remain owner actions. Shared Redis availability, real scanner/parser isolation, production privileged MFA/recovery, HTTPS configuration, encryption/retention policies and real-data operational release gates still require deployment-specific evidence.
