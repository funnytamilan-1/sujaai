# SUJAAI — Chit Management Suite

SUJAAI's current `main` branch contains a React web workspace and FastAPI backend for chit-group administration. It is built around a SQL database and uses the database as the source of truth.

> Scope note: earlier README text described WhatsApp Campaign Manager and Insurance AI modules from a previous project state. Their source folders are not present in this current `main` branch, so those modules are not part of this build and are not represented as working features here.

## Current features

- **Dashboard:** collection totals, group counts, member counts and payment counts.
- **Chit groups:** create groups, set daily/weekly/monthly frequency and contribution, pause/reactivate groups.
- **Members:** register, search, filter, activate/deactivate and retain member history through payment records.
- **Payments:** unique payment references, ledger, date/time, member/group linkage and controlled corrections. Payment deletion is intentionally not provided.
- **Audit history:** records group/member/payment/user/backup actions; payment corrections store before/after values.
- **Reports:** daily, weekly and monthly collection reports with date filters and group totals.
- **Team access:** owner/admin/staff roles; owner/admin can create admin or staff accounts and deactivate accounts.
- **Backup:** Excel workbook with Summary, Groups, Members, Payments, Group Totals, Member Totals, Daily, Weekly and Monthly sheets; JSON export and owner-only JSON restore into an empty chit database.
- **Resume Designer:** editable personal details, summary, skills, education, experience and projects; modern/classic/minimal preview; browser Print / Save as PDF.
- **PVC Card Designer:** front/back card editor at CR80 size (85.6 × 54 mm), generated QR code and Code 128 barcode; browser Print / Save as PDF.

## Technology

- Frontend: React 18, TypeScript, Vite
- Backend: Python 3.12, FastAPI, SQLAlchemy 2
- Database: SQLite for local development; PostgreSQL recommended for production
- Authentication: 8-hour JWT; PBKDF2-SHA256 password hashes for team accounts
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

Set these values in `backend/.env` (never commit real values):

- `SECRET_KEY`: random secret, at least 32 characters for production
- `ADMIN_EMAIL`: initial owner email
- `ADMIN_PASSWORD`: strong unique owner password
- `DATABASE_URL`: defaults to local SQLite; PostgreSQL URL for production
- `CORS_ORIGINS`: comma-separated frontend origins

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://127.0.0.1:8000` in development.

## Deployment

### Render backend

- Create a Web Service from this repository; Docker runtime.
- Set Root Directory to `backend`.
- Health check path: `/api/health`.
- Configure `DATABASE_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CORS_ORIGINS` and a strong `SECRET_KEY`.
- Use managed PostgreSQL and HTTPS for production.

### Vercel frontend

- Import the same repository.
- Set Root Directory to `frontend`.
- Build command: `npm run build`.
- Output directory: `dist`.
- Set `VITE_API_BASE_URL` to the backend origin, for example `https://your-api.onrender.com` (do not append `/api`).
- Add the exact Vercel domain to backend `CORS_ORIGINS`.

## API overview

- `POST /api/auth/login`, `GET /api/auth/me`
- `GET|POST|PATCH /api/chit/groups`
- `GET|POST|PATCH /api/chit/members`
- `GET|POST|PATCH /api/chit/payments`
- `GET /api/chit/reports/summary`, `GET /api/chit/reports/periods`
- `GET|POST /api/users`, `PATCH /api/users/{id}`
- `GET /api/backup/json`, `POST /api/backup/json/restore`, `GET /api/backup/excel`
- `GET /api/audit`

## Data safety and limitations

- Take a database backup before deployment or schema changes.
- SQLAlchemy `create_all` creates missing tables; it does not perform general schema migrations. The current addition introduces the `app_users` table and keeps the existing chit table definitions. Use a formal migration tool before future column-changing releases.
- JSON restore is owner-only, transactional, and refuses to overwrite a non-empty chit database. It is not a merge operation.
- Passwords for team accounts are hashed. The initial owner is configured through environment variables and is not stored as a plaintext database password.
- Do not put production credentials in source files, issues, or chat. Rotate any credential that may have been committed in earlier repository history.
- Browser PDF output and CR80 print alignment depend on the user's printer and print settings.
- A deployment is not considered verified until CI/build checks pass and the deployed health endpoint is tested against the configured database.
