# Public complaint intake and closure PDFs

Students, parents, faculty, non-teaching staff and other stakeholders register complaints from their personal dashboard. New accounts start with zero complaints. The backend derives the submitter from the authenticated session and issues an `OC-year-UUID` reference. A submission key makes retries return the same receipt. Parents record the affected student and their authority to represent them.

Each complainant can access only their own complaints, history, files and closure reports. An assigned officer can review and act on a public complaint. Bureau leads can supervise their bureau. Explicit case grants and appointed participants retain their existing access controls. The single system administrator can review complaints, actions and evidence and assign the intake queue to an active officer. Public accounts cannot change status, assignment or official action notes.

Set `PUBLIC_INTAKE_OWNER_ID` in the backend environment to an active, non-demo officer or lead ID to assign public intake automatically. The default `0` holds submissions in an inactive intake queue until the administrator assigns an officer through **Complaints > open record > Transfer case**. This queue has no usable login. Demo submissions are confined to the synthetic institution and demo officer.

PDF, JPEG, PNG, MP4 and WebM evidence uses private storage, server-side file signatures, SHA-256 checksums and per-case limits. The default is 3 MiB per file to fit the deployed frontend proxy. Video parsing is bounded to 1080p and 5 minutes. PyAV validates an actual decoded video frame. The worker runs file parsing and ClamAV scans; a missing scanner leaves files quarantined. Configure persistent Neon storage and `CLAMAV_HOST`/`CLAMAV_PORT` in Render, and run `python worker.py`. No production scan bypass is implemented.

Every recorded action is appended to the timeline with the actor account/name, UTC timestamp, reason, changes and applicable proof references. Officers can link approved files when recording an action. The UI shows IST plus the exact UTC timestamp and paginates the complete timeline. Evidence uploads, scan outcomes, transfers, status transitions and proceeding actions use the existing audit events.

Closing requires the existing disposition checks, approved outcome evidence and a communication record. In the same database transaction, the backend creates a watermarked PDF and notifies the complainant and administrator in their Alerts. **Closure reports > Download closure PDF** is available on the complaint record. Each PDF contains intake details, assignment history, every recorded action through that closure, the final decision/communication and the proof manifest with uploader, scan state, timestamp and checksum. Files remain separate authenticated downloads; videos are referenced in the PDF. The watermark appears on every page and is not a digital signature. PDFs are frozen bytes in Postgres, so a later reopening preserves the earlier report; a later closure creates another version.

## Run locally

From the project root:

```powershell
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

From `backend`:

```powershell
..\.venv\Scripts\python.exe migrate.py
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 5000
```

From a separate terminal at the project root:

```powershell
npm --prefix frontend run dev -- --port 5173
```

Apply revision `c7b409d2e106` before serving the updated backend. Render builds from `backend/requirements.txt` and runs `python migrate.py` before starting. Deploy the updated frontend to Vercel as well. Schema changes alone do not publish UI changes. Old officer-entered complaints have no inferred submitter ownership; do not match personal accounts to historical records by name or email automatically.

## Validation and database status - 27 October 2026

- Backend: 68 tests passed, including all five public roles, private ownership, assigned officer access, same-bureau unassigned officer denial, demo isolation, actual MP4 parsing, quarantine, retry-safe uploads and frozen report downloads.
- Browser: 21 tests passed; one optional real-model matching test was skipped. The complaint flow covers registration, proof upload, administrator assignment, officer action, closure, complainant/admin PDF access and 320-1024 px layouts.
- Frontend production build and all three proxy tests passed.
- A fresh SQLite schema and a copy of the configured local database upgraded successfully. The configured local database was backed up and migrated afterward.
- The migration was tested on an isolated Neon branch, then applied to production after explicit user confirmation. Production revision is `c7b409d2e106`; all 12 public demo accounts were preserved. The temporary branch was deleted by the completion tool.
- The synthetic PDF was rendered to page images and visually reviewed. Browser screenshots were reviewed for the complaint form and the closed complaint timeline.
- Render/Vercel application deployments and live storage/scanner configuration still require the deployment operator. The production database update does not deploy these source changes.
