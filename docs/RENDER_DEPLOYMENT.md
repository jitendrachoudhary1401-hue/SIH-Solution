
# Deploying OneCase Backend on Render

This guide outlines the step-by-step instructions to deploy the OneCase backend API service to [Render](https://render.com).

---

## 1. Prerequisites & Repository Preparation

Ensure your latest changes in `backend/` are committed and pushed to your remote Git repository (GitHub / GitLab).

---

## 2. Deployment Methods on Render

### Option A: Blueprint Deployment (Fastest & Recommended)

This repository includes a pre-configured [`backend/render.yaml`](../backend/render.yaml) specification:

1. Log into your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** → **Blueprint**.
3. Connect your Git repository.
4. Set the **Blueprint Path** to:
   ```text
   backend/render.yaml
   ```
5. Click **Apply**. Render will automatically detect the Python environment, build settings, pre-deploy migrations, and health check.

---

### Option B: Manual Web Service Setup

If setting up the web service manually:

1. Click **New +** → **Web Service**.
2. Connect your repository.
3. Configure the following fields:
   - **Name:** `onecase-api`
   - **Language / Runtime:** `Python 3`
   - **Root Directory:** `backend` *(Important: Must be `backend`)*
   - **Build Command:**
     ```bash
     pip install -r requirements.txt
     ```
   - **Pre-deploy Command:**
     ```bash
     python migrate.py
     ```
   - **Start Command:**
     - Using Waitress: `python serve.py`
     - Or using Uvicorn (ASGI): `uvicorn main:app --host 0.0.0.0 --port $PORT`
     - For a manually configured service without a pre-deploy command: `python migrate.py && python serve.py`.
     - Keep `API_HOST=0.0.0.0`. Waitress now automatically selects this public binding when Render's built-in `RENDER=true` is present, even if an old localhost setting was copied. It uses Render's `PORT` ahead of the local `API_PORT` setting.
   - **Health Check Path:** `/api/health`

---

## 3. Environment Variables Configuration

In the **Environment** tab of your Render Web Service dashboard, set the following environment variables:

### A. Core Runtime Settings

| Variable | Value | Description |
|---|---|---|
| `PYTHON_VERSION` | `3.12.0` (or `3.14.3`) | Python version used by Render build image |
| `API_HOST` | `0.0.0.0` | Bind host for public traffic |
| `APP_ENV` | `production` | Production mode |
| `COOKIE_SECURE` | `true` | Enforces Secure cookies over HTTPS |
| `STORAGE_BACKEND` | `neon` | Neon S3-compatible storage adapter |
| `STORAGE_BUCKET` | `assets` | Target bucket name |
| `MAX_UPLOAD_BYTES` | `3145728` | Per-file size limit (3 MiB) |

---

### B. Security Keys (Generate Cryptographic Secrets)

Generate two random keys using Python locally:

```powershell
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set these on Render:
- `SECRET_KEY`: *First generated string*
- `MFA_ENCRYPTION_KEY`: *Second generated Fernet key*

---

### C. Neon Postgres Database

Retrieve these connection strings from your Neon Console or your local `.env.local`:

- `DATABASE_URL`: Pooled connection string (`postgresql://...pooler...`)
- `DATABASE_URL_UNPOOLED`: Direct connection string (used during `python migrate.py`)

---

### D. Neon Object Storage (Evidence Files)

Map the Neon storage credentials from your local `.env.local` to the corresponding Render variables:

| Neon CLI / Local Key | Render Variable Name |
|---|---|
| `AWS_ACCESS_KEY_ID` | `NEON_STORAGE_ACCESS_KEY_ID` |
| `AWS_SECRET_ACCESS_KEY` | `NEON_STORAGE_SECRET_ACCESS_KEY` |
| `AWS_ENDPOINT_URL_S3` | `NEON_STORAGE_ENDPOINT` |
| `AWS_REGION` | `NEON_STORAGE_REGION` |

---

### E. Rate Limiting & Proxy Protection (Optional / Recommended)

- `RATE_LIMIT_STORAGE_URI`: A shared Redis instance (`rediss://...` or `redis://...`), or `memory://` for a single instance.
- `FRONTEND_PROXY_SECRET`: (Optional) Shared secret between your Vercel frontend proxy and Render.

---

## 4. Deploy & Verify

1. Trigger the deployment in Render.
2. In the deployment logs, verify:
   - Dependencies successfully install via `pip install -r requirements.txt`.
   - `python migrate.py` reports `Database migration completed.`
   - The web server starts listening on the assigned `$PORT`.
3. Check the public health check endpoint in your browser:
   ```text
   https://<your-render-service-name>.onrender.com/api/health
   ```
   Expected response:
   ```json
   {
     "service": "onecase",
     "status": "ok"
   }
   ```

---

## 5. Keeping Your Public URL the Same

To ensure your public URL never changes across deploys:

### 1. Maintain the Same Render Service
- **Do not delete and recreate** the service on Render for updates.
- Render keeps your unique subdomain (`https://<service-name>.onrender.com`) permanently tied to that service.
- For new updates, simply push to your Git branch—Render auto-deploys to the **exact same URL**.

### 2. Using a Custom Domain (Best for Permanent URLs)
If you want an unchanging URL like `api.yourdomain.com`:
1. In Render, go to your service → **Settings** → **Custom Domains**.
2. Click **Add Custom Domain** (e.g., `api.yourdomain.com`).
3. Add the `CNAME` record provided by Render to your DNS provider (Cloudflare, GoDaddy, Namecheap, etc.).
4. Render automatically provisions and renews free TLS/SSL certificates.

### 3. Update Email & Frontend Environment Variables
In Render Environment Variables:
- Set `PUBLIC_APP_URL` to your production frontend URL (e.g., `https://your-frontend.vercel.app` or `https://yourdomain.com`) so email links (verification, password reset) point to your permanent frontend.

---

## 6. Connect Frontend (e.g. Vercel)

In your frontend deployment settings (e.g., Vercel Project Settings → Environment Variables):
- `BACKEND_URL`: `https://<your-render-service-name>.onrender.com` (or your custom domain `https://api.yourdomain.com`)
- `VITE_API_BASE_URL`: `/api`
- `FRONTEND_PROXY_SECRET`: *(Match the value configured in Render, if used)*
