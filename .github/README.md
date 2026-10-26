# GitHub workflow

`workflows/ci.yml` runs on pull requests, pushes to `main`/`master`, and manual dispatch.

It runs backend tests plus the production frontend build and browser checks. Browser tests use a disposable local database, synthetic accounts and an explicitly isolated scanner fixture. The optional real-model test is skipped unless local model setup is enabled separately.

The workflow requires **no Neon, Render, Vercel or other production secrets**. It has read-only repository permissions, cancels superseded runs, limits job duration, and pins third-party actions to immutable commits. Failed browser runs upload traces/screenshots for seven days; fixtures contain no real complainant information.

Frontend build and proxy checks run from `frontend`. Backend tests also verify a copied backend folder can migrate and serve its health endpoint without workspace env files or the frontend. Deploy with Vercel Root Directory `frontend` and Render Root Directory `backend`; configs are inside each folder. Browser tests use both folders for their synthetic test server.

## Team flow

1. Create a feature branch.
2. Run `npm run build` and `.venv/Scripts/python.exe -m pytest backend/tests -q` locally.
3. Open a pull request and review the backend, frontend and migration changes.
4. Require both CI jobs before merging. Enable branch protection in GitHub Settings → Rules; the repository file alone cannot enable that account setting.
5. Use an isolated Neon branch for database changes. Use a direct connection for migrations.
6. Merge after review. Render/Vercel can deploy through their own GitHub integrations if you enable those integrations yourself.

There is no automated production deployment in this workflow. Adding one later requires separately approved deployment credentials and environment protection rules. Do not use `pull_request_target` to execute untrusted pull-request code with secrets.

## First use

Push this repository and workflow to GitHub, open the Actions tab and run **OneCase checks**. A successful local test does not prove a GitHub-hosted run has completed; its actual result appears in GitHub after the push.
