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

### Vercel FastAPI backend

Deploy the backend as its own Vercel project (separate from the frontend project):

- Import the existing `funnytamilan-1/sujaai` repository.
- Project name: `sujaai-api` (or another backend-specific name).
- Root Directory: `backend` (important — do not select the repository root).
- Framework Preset: FastAPI / automatic detection.
- Build Command: leave at the Vercel-detected default; do not run Uvicorn or Docker.
- Output Directory: leave blank.
- The Python runtime is pinned to 3.12 by `backend/.python-version`.
- The backend exposes the FastAPI instance through `backend/main.py`, a Vercel-supported root entrypoint. Set the backend project's Root Directory to `backend`; Vercel then routes requests to the FastAPI app so its router handles `/api/*` paths. `backend/vercel.json` excludes tests from the function bundle.
- Health check after deployment: `https://YOUR-API-DOMAIN/api/health/ready`; interactive docs: `https://YOUR-API-DOMAIN/docs`.

Set these Environment Variables in the backend Vercel project (Production and Preview only where appropriate):

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `DEBUG` | `false` |
| `SECRET_KEY` | A unique random secret with at least 32 characters |
| `ADMIN_EMAIL` | Initial owner email |
| `ADMIN_PASSWORD` | Unique password with at least 12 characters |
| `DATABASE_URL` | Persistent PostgreSQL connection URL (use the provider's pooled/serverless URL) |
| `DB_POOL_SIZE` | `1` |
| `DB_MAX_OVERFLOW` | `0` |
| `MAX_REQUEST_BODY_BYTES` | `4194304` (4 MiB; below Vercel's 4.5 MB function request cap) |
| `MAX_DESIGN_PAYLOAD_BYTES` | `3145728` (3 MiB) |
| `FRONTEND_URL` | Exact deployed frontend origin, e.g. `https://sujaai.vercel.app` |
| `CORS_ORIGINS` | Comma-separated exact frontend origins; no `/api` or page paths |

Do not use SQLite for production on Vercel: function filesystems are not durable shared databases. The API requires PostgreSQL in production and the database must be external to the function.

#### First-time database migration

The backend does not run schema migrations automatically on every serverless request or deployment. Before first use:

1. Back up the PostgreSQL database.
2. In GitHub repository Settings → Secrets and variables → Actions, add `SUJAAI_DATABASE_URL` with the PostgreSQL URL.
3. Open Actions → `SUJAAI production database migration` → Run workflow on `main`.
4. Confirm the workflow succeeds before using the API.

This workflow is manual and runs `alembic upgrade head`; it does not drop existing tables. The initial baseline creates missing tables and indexes only. Existing column changes require a separately reviewed migration. Have a trusted adult/maintainer manage production database credentials and backups.

The backend's Vercel Function uses a small per-instance PostgreSQL connection pool because serverless instances can scale independently. Do not depend on local files or in-memory state for durable records.

### Vercel frontend

Deploy the frontend as a separate Vercel project:

- Import the same repository.
- Root Directory: `frontend`.
- Build command: `npm run build`.
- Output directory: `dist`.
- Set `VITE_API_BASE_URL` to the backend Vercel origin only, e.g. `https://sujaai-api.vercel.app` (do not append `/api`).
- Add the exact frontend domain to the backend's `FRONTEND_URL` and `CORS_ORIGINS`, then redeploy the backend.
- The frontend Vite proxy is only for local development; production frontend requests use `VITE_API_BASE_URL`.
- The repository's Dockerfile remains available for non-Vercel container testing; Vercel's native Python runtime does not use it.

### Environment variable reference

| Variable | Where | Purpose |
|---|---|---|
| `APP_ENV` | Backend | `development`, `test`, `staging`, or `production` |
| `SECRET_KEY` | Backend secret | JWT signing key; 32+ characters |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Backend secret | Initial owner login credentials |
| `DATABASE_URL` | Backend Vercel secret | Persistent PostgreSQL connection URL in production |
| `FRONTEND_URL` | Backend | Primary frontend website origin |
| `CORS_ORIGINS` | Backend | Additional/allowed frontend website origins, comma-separated |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Backend | JWT lifetime; default 480 minutes |
| `VITE_API_BASE_URL` | Vercel frontend | Backend Vercel origin; do not include `/api` |

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
