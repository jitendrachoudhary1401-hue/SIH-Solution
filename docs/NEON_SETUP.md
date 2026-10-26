# Neon setup and verification

## Preserved and installed configuration

- Neon CLI installed globally: `8.11.4`.
- Nine project agent skills installed in `.agents/skills`. A fresh fetch of the requested overview matched the installed file; no unnecessary replacement was made.
- Existing `.codex/config.toml` entry preserved: OAuth HTTP MCP server `https://mcp.neon.tech/mcp`. MCP OAuth sign-in completed; no project API key was written into that entry.
- Project context: organization `org-young-dew-78896435`, project `sweet-snow-41606635`, branch `production`.
- Region confirmed: `aws-us-east-2`, which supports the requested object storage.
- `neon.ts` keeps existing officer authentication and declares the private `assets` bucket. It does not enable a replacement authentication provider.
- Neon-managed credentials are in ignored root `.env.local`; no credential values appear in this document.

## Provisioning output

```text
Auth complete (profile DEFAULT)
Applying to branch production
Applied changes
  + bucket assets
Utilized services: Postgres, Object Storage
Pulled 7 Neon variables into .env.local
```

The seven keys are `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `NEON_BRANCH`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3`, and `AWS_REGION`. Their values are deliberately omitted.

## Code wiring

Flask retains SQLAlchemy/psycopg, uses pooled application connections and direct Alembic connections, and reads service configuration only on the server. The private evidence adapter uses boto3 with path-style SigV4 requests. New file metadata records the storage backend/bucket/key; downloads still require authorization and a clean scan state. Existing local evidence keeps its recorded local location.

Frontend API settings are separate and contain no service credentials. Render/Vercel deployment templates and their environment instructions are in the platform-specific READMEs.

## Actual isolated-branch service output

Branch: `onecase-validation-20261026`; expiry: 29 October 2026. Production credentials were not replaced by this branch's credentials. Its environment file is ignored under `.runtime/`.

```text
PASS Neon pooled Postgres connection
PASS application migrations on direct Neon connection
PASS synthetic account/case seed
PASS real private Neon object upload/download/checksum/delete
PASS secrets remain server-side; credential values omitted
PASS officer authentication backed by Neon
PASS API complaint write/read persisted in Neon
PASS API upload stored in Neon with PostgreSQL metadata; quarantined bytes denied
PASS unauthorized cross-bureau API access denied
ALL LIVE NEON SERVICE CHECKS PASSED
```

The migration and service lines came from consecutive runs. The first run completed migrations but lost a pooled connection during seeding. A subsequent run checked state, seeded successfully, and passed every live service check. No records were reset. One initial PowerShell command also needed the service list quoted as `'postgres,object-storage'` because an unquoted comma was interpreted as a PowerShell array.

`npm run build` passed from the project root. Local pytest and browser checks are separate from real service verification. A private object round trip does not mean a real malware scanner is installed: uploaded evidence remains quarantined until the configured scanner succeeds.

## Scope of deployment

Neon provisions backend services. It does not publish this React application on Vercel or this Flask application on Render. The owner will supply the platform-specific values and deploy those applications. No GitHub-hosted CI run or public Render/Vercel URL has been verified from this workspace.

## Intended application branch migration

After validation, the same committed migration chain was applied to the initially empty `production` database. Output: `Database migration completed.` Synthetic test accounts were seeded only in the isolated validation branch, not in the intended application branch.
