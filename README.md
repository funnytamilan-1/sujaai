# SUJAAI — Chit Management Suite

SUJAAI's current `main` branch contains a React web workspace and FastAPI backend for chit-group administration. The configured SQL database is the source of truth for financial records.

> **Scope note:** Previous README revisions described WhatsApp Campaign Manager and Insurance AI modules. Their source folders are not present in this current `main` branch, so those features are not included in this build and are not claimed as working.

## Implemented modules

- **Dashboard:** collection totals, group/member counts and payment counts.
- **Chit groups:** create and edit groups, set daily/weekly/monthly frequency and contribution, pause/reactivate or complete groups.
- **Members:** register, search, filter, edit profile details and activate/deactivate members.
- **Payment ledger:** unique payment references, date/time, member/group linkage, notes and controlled corrections. A per-payment Excel record is downloaded automatically after a successful payment entry; PDF receipts and member-wise Excel statements are also available. Deletion is intentionally unavailable.
- **Audit log:** group/member/payment/user/backup events; payment corrections include before/after values.
- **Reports:** daily, weekly and monthly collection summaries, date filters and group totals.
- **Team access:** owner/admin/staff roles; owner/admin can create admin/staff accounts and deactivate accounts.
- **Backup:** Excel workbook with Summary, Groups, Members, Payments, Group Totals, Member Totals, Daily, Weekly and Monthly sheets; JSON export and owner-only JSON restore into an empty chit database.
- **Saved designs:** Resume and PVC designs can be saved, listed, loaded, updated and deleted from the authenticated account. Each account can access only its own designs.
- **Resume Designer:** editable profile, photo, summary, skills, languages, education, experience, projects and certifications; modern/classic/minimal layouts; browser Print / Save as PDF.
- **PVC Card Designer:** front/back CR80 (85.6 × 54 mm) layout, editable details, optional photo/logo, generated QR code and Code 128 barcode; browser Print / Save as PDF.

## Technology

- Frontend: React 18, TypeScript, Vite
- Backend: Python 3.12, FastAPI, SQLAlchemy 2
- Database: SQLite local development; PostgreSQL required for Vercel production
- Authentication: 8-hour JWT; PBKDF2-SHA256 hashes for team-account passwords
- Excel: openpyxl

## Local development

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

API documentation: `http://127.0.0.1:8000/docs`

Configure these values in `backend/.env` (never commit real credentials):

- `SECRET_KEY`: random secret; at least 32 characters in production
- `ADMIN_EMAIL`: initial owner email
- `ADMIN_PASSWORD`: strong unique owner password
- `DATABASE_URL`: local SQLite default or PostgreSQL connection URL (PostgreSQL required on Vercel)
- `CORS_ORIGINS`: comma-separated frontend origins

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the backend in development. Copy `.env.example` to `.env.local` only if you want to set the API origin explicitly.

## Deployment

### Current deployment: Render backend + Vercel frontend

This repository includes a Render Docker service definition in `render.yaml`. The frontend is deployed separately on Vercel.

**Render backend**

- Connect this repository to Render and create the web service from `render.yaml`, or create a Docker web service manually.
- Root directory: `backend`.
- Dockerfile: `backend/Dockerfile`.
- Health check path: `/api/health/ready`.
- The Docker startup command applies Alembic migrations before starting Uvicorn. Keep a persistent PostgreSQL database attached; do not use SQLite for production.
- The current backend origin supplied for this deployment is `https://suja-bxf5.onrender.com`. If Render assigns a different service domain, use that new origin everywhere below.

Set these backend Environment Variables in Render (Production):

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `DEBUG` | `false` |
| `SECRET_KEY` | Generate a unique secret with at least 32 characters |
| `ADMIN_EMAIL` | Owner login email |
| `ADMIN_PASSWORD` | Unique owner password with at least 12 characters |
| `DATABASE_URL` | Persistent PostgreSQL connection URL |
| `FRONTEND_URL` | `https://suja-in.vercel.app` |
| `CORS_ORIGINS` | `https://suja-in.vercel.app` |
| `DB_POOL_SIZE` | `1` |
| `DB_MAX_OVERFLOW` | `0` |

Do not commit secrets or paste them into chat. Back up the PostgreSQL database before deployments that change the schema. Render free web services may spin down after inactivity; the first request after a sleep period can take longer while the service starts. This is different from a browser reporting `ERR_INTERNET_DISCONNECTED`, which can also indicate a local network interruption.

**Vercel frontend**

- Import the same repository as a separate Vercel project.
- Root Directory: `frontend`.
- Build Command: `npm run build`.
- Output Directory: `dist`.
- Set the frontend project's Environment Variable:

```env
VITE_API_BASE_URL=https://suja-bxf5.onrender.com
```

Use only the backend origin; do not append `/api` or a trailing path. Redeploy the frontend after changing this variable. The backend must allow the exact frontend origin in `FRONTEND_URL` and `CORS_ORIGINS`.

### Optional: deploy the backend on Vercel instead

The repository also contains Vercel FastAPI entrypoints and configuration. If choosing Vercel for the backend instead of Render, create a separate Vercel project with Root Directory `backend`, use a persistent PostgreSQL database, configure the backend environment variables above, and change `VITE_API_BASE_URL` to that Vercel backend origin. Do not point the frontend to both providers at once.

### Environment variable reference

| Variable | Where | Purpose |
|---|---|---|
| `APP_ENV` | Backend | `development`, `test`, `staging`, or `production` |
| `SECRET_KEY` | Backend secret | JWT signing key; 32+ characters |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Backend secret | Initial owner login credentials |
| `DATABASE_URL` | Backend secret | Persistent PostgreSQL connection URL in production |
| `FRONTEND_URL` | Backend | Primary frontend website origin |
| `CORS_ORIGINS` | Backend | Exact allowed frontend website origins, comma-separated |
| `VITE_API_BASE_URL` | Vercel frontend | Backend origin only; do not include `/api` |

## API overview

- `POST /api/auth/login`, `GET /api/auth/me`
- `GET|POST|PATCH /api/chit/groups`
- `GET|POST|PATCH /api/chit/members`
- `GET|POST|PATCH /api/chit/payments`; `GET /api/chit/payments/{id}/excel`, `GET /api/chit/payments/{id}/pdf`
- `GET /api/chit/members/{id}/statement/excel`
- `GET /api/chit/reports/summary`, `GET /api/chit/reports/periods`
- `GET|POST /api/users`, `PATCH /api/users/{id}`
- `GET /api/backup/json`, `POST /api/backup/json/restore`, `GET /api/backup/excel`
- `GET /api/audit`
- `GET|POST /api/designs`, `GET|PUT|DELETE /api/designs/{id}`

## Data safety

- Take a database backup before deploying or changing schemas.
- Alembic manages database schema versions. The initial baseline creates missing SUJAAI tables without dropping existing tables or records; it does not rewrite existing columns. Add explicit Alembic revisions for every future schema change and take a backup before applying them.
- JSON restore is owner-only, transactional, and refuses to overwrite a non-empty chit database. It is not a merge operation.
- Deactivated staff/admin accounts are rejected on subsequent authenticated API requests.
- Payment corrections are audited; no payment delete endpoint is exposed.
- Do not put production credentials in source files, GitHub issues, or chat. Rotate credentials that may have appeared in older Git history.
- Resume/PVC designs are stored in the configured database and scoped to the signed-in account. PDF output and physical card alignment depend on browser/printer settings.

## Continuous integration

GitHub Actions runs the backend pytest suite and the frontend TypeScript/Vite production build on pushes and pull requests targeting `main`.

## Tests

```bash
cd backend
pytest
```

The tests force an isolated local SQLite test database named `test_sujaai.db`; they do not use the configured production database. Coverage includes authentication/roles, chit records, payment corrections, Excel/PDF exports, backups/restores and saved-design ownership.
