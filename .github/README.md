# GitHub checks and production deployment

The current release branch is `dev`. Pushes to `dev`, `main`, and `master`,
pull requests, and manual workflow runs execute `.github/workflows/ci.yml`.
The checks cover backend tests, the production frontend build, the server-side
API proxy, and browser workflows with disposable synthetic services.

## One-time hosting setup

Connect `jitendrachoudhary1401-hue/SIH-Solution` to both hosting services.

| Setting | Vercel frontend | Render API |
| --- | --- | --- |
| Root directory | `frontend` | `backend` |
| Production / linked branch | `dev` (set in Vercel settings) | `dev` |
| Configuration | `frontend/vercel.json` | Blueprint path `backend/render.yaml` |
| Automatic deployments | Enabled by committed Git configuration | After CI Checks Pass |
| Health check | `/api/health` on the frontend hostname | `/api/health` |

For an existing Render service that is not managed by a Blueprint, set its
linked branch to `dev` and **Auto-Deploy → After CI Checks Pass** in the
dashboard. Merely pushing a Blueprint file does not change an unmanaged service.
For an existing Blueprint, confirm automatic Blueprint sync is enabled.

Set private platform variables using [the setup guide](../SETUP_GUIDE.md).
Vercel needs `BACKEND_URL` pointing to the Render API and
`VITE_API_BASE_URL=/api`. Render needs the existing Neon database/storage
credentials, application secrets, and shared Redis configuration. Set
`PUBLIC_APP_URL` on Render to the HTTPS Vercel hostname for password reset links.
Configure SendGrid privately if password reset email is used. Keep
`FRONTEND_PROXY_SECRET` identical on both platforms when enabled.

## Each release

1. Commit the intended changes and push `dev` to GitHub.
2. Check the **OneCase checks** workflow in GitHub Actions.
3. Vercel builds and deploys the frontend from the push. Render deploys the API
   after the commit's checks pass and runs migrations before starting the API.
4. Verify `/api/health` on both hostnames, then sign-in and a case workflow.

Vercel's normal Git deployment does not wait for the GitHub test workflow.
Review changes through pull requests and require the checks before merging
into `dev` if tests must pass before the frontend goes live. The two hosts
deploy independently; API changes must remain compatible during a rollout.

The committed files configure deployment behavior; they do not create hosting
accounts, connect repositories, set private environment variables, or prove a
live release. No deployment token is required in GitHub for native Git hosting.
If changing the release branch later, update the Render `branch`, Vercel's
Production Branch setting, and this guide together.
