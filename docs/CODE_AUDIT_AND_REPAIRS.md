# OneCase implementation audit and repairs

Review date: 27 October 2026. This review inspected the application source,
migrations, deployment files, worker, models, storage adapter, API proxy and tests.
Findings were reproduced with disposable synthetic SQLite databases. No real
complaint records or private credentials were changed for the reproductions.

## Actual architecture

| Area | Implementation and boundary |
| --- | --- |
| Frontend | React, TypeScript and Vite; hosted on Vercel. UI requests use `/api`. |
| API proxy | Vercel server-side function. Carries the session cookie and CSRF header to Render; validates browser write origins. It contains no database, storage, matching or account business logic. |
| Backend | Flask, SQLAlchemy, Pydantic and Waitress on Render. An ASGI adapter also exists for Uvicorn. Authentication and object/field authorization live here. |
| Database | PostgreSQL through psycopg in production, with Alembic migrations. SQLite remains supported for development/tests. A diagram labeling every local environment PostgreSQL would be inaccurate. |
| Evidence | Backend-only S3-compatible Neon adapter; randomized object keys, size/signature checks, SHA-256 metadata, private objects, parser isolation and configurable malware quarantine (see the explicit opt-out below). The database stores attachment metadata and frozen closure PDFs. |
| Worker | Render Python worker: sentence-transformer retrieval, cross-encoder reranking, reminders and evidence scanning. A private ClamAV service is needed when malware scanning is enabled; the current Blueprint opts out of malware scanning. The worker reads database jobs and storage; it is not a final sequential step after the bucket in a browser request. |
| Supporting services | Existing Neon database/bucket, shared Redis for production limits, SendGrid for configured password recovery. Their credentials remain server-side. No Neon Functions, separate AWS service, or replacement frontend host was introduced. |

## Confirmed defects and changes

| Severity | Reproduced issue | Repair and evidence |
| --- | --- | --- |
| High | A committee appointment with `has_content=false` could obtain original/edited descriptions through `ActionEvent.changes` and free-form history remarks. | Central event serialization redacts payloads, remarks and actor identity for basic readers; basic case summaries redact free-form fields too. Regression exercises detail, history, audit, dashboard and case list. Full authorized history remains available. |
| High | Fresh privileged production accounts were denied login until MFA existed, while MFA setup required login. | Password verification now establishes a ten-minute enrollment-only session. Authorization denies workspace APIs until enrollment succeeds. Confirmation rotates cookie and CSRF, preserves encrypted TOTP storage and returns recovery codes once. UI waits for acknowledgement of saved codes. |
| High | A reviewed pair remained `related` after revised complaint text was rematched, making an old decision appear current. | Material edits invalidate current pair decisions immediately. Rematching also checks evidence revisions and resets outdated decisions to pending. Historical Review/PairScore rows remain intact. Neither complaint is merged or disposed automatically. |
| High | Proxied users shared the backend's remote-address login budget. Naively trusting forwarding headers would enable spoofing. | The Vercel proxy supplies the platform client IP. Flask trusts the dedicated client-IP header only with the correct shared proxy secret. Unauthenticated spoofed headers are ignored. Production requires a strong shared secret. |
| High | HTTPS origins forwarded by Vercel could be rejected when Render terminates TLS and Waitress receives HTTP. | Only the authenticated proxy may bridge that scheme difference, with matching origin/Host and an HTTPS external origin in production. Cross-origin and invalid-secret requests remain denied. A regression models Render's internal HTTP connection. |
| Medium | Aggregate-only executives had valid `monitor.aggregate` grants but dashboard totals used content scope and returned zero. | Counts and reporting honor the aggregate scope; attention lists, case records and recent narratives still require independent read access. A regression proves nonzero totals with empty detail lists and denied direct case URLs. |
| Medium | Missing objects/storage errors escaped the scan loop and could stop every worker task. Old pending files could monopolize the scan batch. | Storage failures retain quarantine, batch selection rotates least-recently-checked files, and worker stages isolate exceptions. Other monitoring/scanning stages continue after one fails. Only a complete valid ClamAV response may mark a file clean; explicit bypass releases parser-validated files as unscanned. |
| Medium | Retrying a completed matching job set the case to queued but left its unique job completed. | Retry explicitly requeues terminal jobs, resets retry metadata and retains the original dedup key. |
| Medium | Unverified institutions could create matching failures with no supported verification action. | An admin-only, recent-authenticated review endpoint and UI preserve the string identifier, source approval and reason. Duplicate identifiers and silent reassignment are rejected; affected jobs are requeued. No registry integration or automatic identity merge is implied. |
| Medium | Proceeding milestones had clocks but were absent from the reminder sweep. | Authorized, active recipients now receive deduplicated milestone reminders. Unconfirmed non-administrative policies do not produce false deadline claims. An unfinished external proceeding clock can continue after internal case closure. |
| Medium | The configured local model directory pointed to a missing path although a real workspace bundle existed. Model setup also resolved latest revisions on each download. | Development can use the existing workspace bundle with a warning; explicit test overrides and production paths are preserved. Model setup uses committed revision SHAs. Actual local encoder and reranker inference completed after the path repair. Scores remain explicitly unvalidated. |
| Medium | Date-only filters were treated as UTC midnight; incoming offset timestamps could lose their offset in SQLite. | All request-model datetimes require a timezone and normalize to UTC. Date-only reporting boundaries use Asia/Kolkata, with inclusive start and exclusive next-day end. |
| Medium | A healthy API did not establish that the worker was alive; the committed Blueprint defined only the API. | The Blueprint defines Render API and worker. The private scanner was removed on 28 October at the user’s request; scanning is explicitly disabled in this Blueprint. Worker heartbeats are persisted and exposed only to administrators. Migration `e9c54a830bf1` follows `c7b409d2e106`. A database ping still does not prove scanner/storage readiness. |
| Hardening | Known-password synthetic seeds could be invoked under a production environment; production could silently use local storage/database defaults. | Known-password seed/access helpers reject production. Startup requires PostgreSQL, complete private storage, shared Redis, HTTPS cookies, valid MFA encryption, and strong application/proxy secrets. The explicitly enabled public demo flow remains confined to synthetic identities. |

Main code: `backend/app/auth.py`, `api.py`, `network.py`, `security.py`,
`matching.py`, `documents.py`, `jobs.py`, `administration.py`, `worker.py`,
`frontend/api/proxy.js`, and the corresponding frontend security/admin screens.
Regressions live in `backend/tests/test_audit_regressions.py`.

## Brand change

The active logo is `frontend/public/onecase-emblem.png`: a square transparent PNG
containing the user's selected gold gear, officer, student, institution, checked
case record and open book. The embedded OneCase wordmark and underline are removed;
the original navy/gold/green/orange palette is retained, with no lamp.
The favicon, Apple icon and PWA launcher icons use proportionally resized copies.
The sign-in page, workspace and account/recovery/error screens use the same mark.

Edited with the built-in image tool. Final edit direction: retain the supplied
emblem and color palette, remove the bottom wordmark and underline only, keep a
1:1 aspect ratio and transparent exterior. Full-resolution selected emblem:
`output/branding/onecase-emblem-no-text.png`. Desktop and phone review images
are under `output/review/`.

## Requirements and existing behavior preserved

The supplied analysis, problem explanation and technical roadmap were used as
requirements references; the two analysis PDF copies are byte-identical. The
roadmap's Express/MongoDB choice and officer-only scope are older proposals.
The accepted application here remains Flask/PostgreSQL with the subsequently
requested public registration, complaint intake, demo roles, proof uploads,
SendGrid recovery and frozen closure reports.

The repairs preserve backend authorization, expiring grants/appointments,
conflict denial, one administrator identity, CSRF, Argon2 password hashing,
opaque hashed sessions, private quarantined evidence, version conflicts,
transactional action history, independent compliance verification, ownership
and deadline preservation on transfer, separate original complaints, and human
review of model suggestions. Connection-loss logout and native browser app
installation remain in place. No public bucket, browser-stored service secret,
MFA bypass, automatic complaint merge or AI adjudication was added.

## Verification and release boundary

The final backend suite passed **88 tests**, including the migration upgrade and
20 audit regressions. The production frontend build and **4 proxy tests** passed.
The browser run passed 26 scenarios; its optional real-model scenario initially
failed on an ambiguous selector, which was corrected to the exact pair. That
scenario then passed with the actual encoder/reranker, verifying all 27 scenarios
across those runs. The final selected emblem also passed a fresh desktop/phone
branding check, and the final build/proxy checks passed after that asset update.
The checks use synthetic data. Browser mail delivery and clean-scanner responses are fixture-controlled;
those checks do not prove a live SendGrid sender or a production malware scanner.
Actual local sentence embeddings and cross-encoder inference are separately
exercised, including the human review workflow. That is not an accuracy,
fairness, multilingual or load benchmark.

The public production frontend and `/api/health` returned HTTP 200 during the
initial read-only audit, before these repairs were deployed. Render credentials,
actual database contents, bucket policies, Redis availability, scanner signatures,
and cloud worker liveness were not inferred from that response.

Before releasing these changes:

The current public Vercel API was subsequently checked after an in-progress
deployment. Both `/api/health` and `/api/auth/me` returned HTTP 503 with
`The application proxy is not configured securely.` That is the new fail-closed
Vercel configuration guard: its `FRONTEND_PROXY_SECRET` is absent or shorter than
32 characters. This response occurs before forwarding a request to Render and
therefore does not establish that the Render backend has stopped. The existing
optional key was made mandatory; private environment files were not populated
with a new value. Complete step 1 below and redeploy both services before testing
the live application again.

1. Set the same random `FRONTEND_PROXY_SECRET` (at least 32 characters) on Render
   and the Vercel server environment. Keep `VITE_API_BASE_URL=/api` and set
   server-only `BACKEND_URL` to the Render API.
2. Verify Render's production PostgreSQL/storage credentials, Redis URI, secret
   key, Fernet key, HTTPS cookies and public frontend URL. Preserve existing data.
3. Apply/sync `backend/render.yaml`, including the worker. The worker uses a paid
   Render plan. Malware scanning is explicitly bypassed in the current Blueprint;
   a scanner is not provisioned. For manually managed services, set
   `MALWARE_SCAN_ENABLED=false` on the API and worker, then redeploy.
4. Let the API pre-deploy migration run, then confirm worker heartbeat and job
   processing. Existing unmanaged services need the same settings entered once.
5. Verify first-time privileged MFA, normal sign-in, approved access, a denied
   direct-object request, pending upload denial, real scan completion, authorized
   download, reset email and logout on the deployed hosts.

The repository changes have not themselves provisioned or published cloud
services. The earlier roadmap's staged CSV importer, comprehensive issue-level
matching, official registry integration, policy certification, and performance
targets are not represented as completed by this repair pass. The normalized
person/issue tables exist, but the current matcher still operates on complaint
descriptions. Administrative database operators remain a trust boundary; the
application timeline is not claimed to be cryptographically tamper-proof.


## Explicit malware-scan bypass — 28 October 2026

At the user's request, `MALWARE_SCAN_ENABLED=false` bypasses malware scanning.
The application defaults to enabled when the variable is absent or unrecognized;
the current Render Blueprint and sanitized environment template explicitly opt out.
New uploads still undergo file signature/extension/size checks and bounded parser
validation before storage, without requiring a scanning worker. They are labelled
`unscanned`, not `clean`. The case timeline records the opt-out; evidence screens
and administrator operations identify skipped/disabled scanning. Scope checks,
private storage, authentication, CSRF and evidence sensitivity remain enforced.
Rejected documents are never released. This setting reduces malware protection.

The worker validates any older pending files. It is still required for matching
and deadline monitoring. Re-enabling scanning immediately blocks unscanned
downloads and evidence use until the worker scans those files. No migration or
private environment file change is required. The repository update does not alter
Render environment values or delete any already-provisioned cloud service.
