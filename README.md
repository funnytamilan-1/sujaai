# SUJAAI — Chit Management Suite

SUJAAI's current `main` branch contains a React web workspace and FastAPI backend for chit-group administration. The configured SQL database is the source of truth for financial records.

> **Scope note:** Previous README revisions described WhatsApp Campaign Manager and Insurance AI modules. Their source folders are not present in this current `main` branch, so those features are not included in this build and are not claimed as working.

## Implemented modules

- **Dashboard:** collection totals, group/member counts and payment counts.
- **Chit groups:** create and edit groups, set daily/weekly/monthly frequency and contribution, pause/reactivate or complete groups.
- **Members:** register, search, filter, edit profile details and activate/deactivate members.
- **Payment ledger:** unique payment references, date/time, member/group linkage, notes and controlled corrections. A per-payment Excel record is downloaded automatically after a successful payment entry. Deletion is intentionally unavailable.
- **Audit log:** group/member/payment/user/backup events; payment corrections include before/after values.
- **Reports:** daily, weekly and monthly collection summaries, date filters and group totals.
- **Team access:** owner/admin/staff roles; owner/admin can create admin/staff accounts and deactivate accounts.
- **Backup:** Excel workbook with Summary, Groups, Members, Payments, Group Totals, Member Totals, Daily, Weekly and Monthly sheets; JSON export and owner-only JSON restore into an empty chit database.
- **Resume Designer:** editable profile, photo, summary, skills, languages, education, experience, projects and certifications; modern/classic/minimal layouts; browser Print / Save as PDF.
- **PVC Card Designer:** front/back CR80 (85.6 × 54 mm) layout, editable details, optional photo/logo, generated QR code and Code 128 barcode; browser Print / Save as PDF.

## Technology

- Frontend: React 18, TypeScript, Vite
- Backend: Python 3.12, FastAPI, SQLAlchemy 2
- Database: SQLite local development; PostgreSQL recommended for production
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
uvicorn app.main:app --reload
```

API documentation: `http://127.0.0.1:8000/docs`

Configure these values in `backend/.env` (never commit real credentials):

- `SECRET_KEY`: random secret; at least 32 characters in production
- `ADMIN_EMAIL`: initial owner email
- `ADMIN_PASSWORD`: strong unique owner password
- `DATABASE_URL`: local SQLite default or PostgreSQL connection URL
- `CORS_ORIGINS`: comma-separated frontend origins

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the backend in development. Copy `.env.example` to `.env.local` only if you want to set the API origin explicitly.

## Deployment

### Render backend

- Create a Docker Web Service from this repository.
- Root Directory: `backend`.
- Health check: `/api/health`.
- Configure `DATABASE_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CORS_ORIGINS` and a strong `SECRET_KEY`.
- Use managed PostgreSQL and HTTPS for production.

### Vercel frontend

- Import this repository.
- Root Directory: `frontend`.
- Build command: `npm run build`.
- Output directory: `dist`.
- Set `VITE_API_BASE_URL` to the backend origin, e.g. `https://your-api.onrender.com` (do not append `/api`).
- Add the exact Vercel frontend origin to backend `CORS_ORIGINS`.

## API overview

- `POST /api/auth/login`, `GET /api/auth/me`
- `GET|POST|PATCH /api/chit/groups`
- `GET|POST|PATCH /api/chit/members`
- `GET|POST|PATCH /api/chit/payments`; `GET /api/chit/payments/{id}/excel`
- `GET /api/chit/reports/summary`, `GET /api/chit/reports/periods`
- `GET|POST /api/users`, `PATCH /api/users/{id}`
- `GET /api/backup/json`, `POST /api/backup/json/restore`, `GET /api/backup/excel`
- `GET /api/audit`

## Data safety

- Take a database backup before deploying or changing schemas.
- SQLAlchemy `create_all` creates missing tables; it does not perform general migrations. This change adds the `app_users` table and retains the existing chit table definitions. Use Alembic before future column-changing releases.
- JSON restore is owner-only, transactional, and refuses to overwrite a non-empty chit database. It is not a merge operation.
- Deactivated staff/admin accounts are rejected on subsequent authenticated API requests.
- Payment corrections are audited; no payment delete endpoint is exposed.
- Do not put production credentials in source files, GitHub issues, or chat. Rotate credentials that may have appeared in older Git history.
- Resume/PVC content is kept in browser component state for this session. PDF output and physical card alignment depend on browser/printer settings.

## Tests

```bash
cd backend
pytest
```

The tests force an isolated local SQLite test database named `test_sujaai.db`; they do not use the configured production database.
