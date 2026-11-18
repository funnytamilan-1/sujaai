# SUJAAI — WhatsApp Campaign Manager

A full-stack dashboard for importing opted-in contacts from Excel, preparing image + text campaigns, and sending approved WhatsApp message templates through the official WhatsApp Cloud API.

## Stack
- Frontend: React, TypeScript, Vite
- Backend: FastAPI, SQLAlchemy, SQLite (local default; PostgreSQL supported through DATABASE_URL)
- Authentication: JWT
- Excel: openpyxl
- Media: local uploads (use persistent storage or object storage in production)

## Run locally

### Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env  # Windows; use cp on macOS/Linux
uvicorn app.main:app --reload
```
API docs: http://127.0.0.1:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open the Vite URL (normally http://localhost:5173). The frontend proxies `/api` to the backend. For Vercel, set the project Root Directory to `frontend`, Build Command to `npm run build`, Output Directory to `dist`, and `VITE_API_BASE_URL` to `https://YOUR_API_HOST/api` (no trailing slash). Add the Vercel domain to backend `CORS_ORIGINS`.

## Administrator-only access\n\nPublic registration is disabled. Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in the backend environment (Render environment variables in production). On first startup, the backend creates the administrator account if it does not already exist. Only that email can sign in; all protected dashboard APIs reject other accounts. Keep the administrator password private and use a long unique password.\n\nThe WhatsApp Cloud API credentials are configured once on the backend and shared by this single administrator workspace. They are never entered into or exposed by the frontend. This integration uses a WhatsApp Business Platform number, not a personal WhatsApp app account.\n\n## Configuration
All backend settings are centralized in `backend/app/config.py` and loaded from environment variables. Never commit real tokens or passwords. See `backend/.env.example`.

For dashboard image uploads, configure `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET`. You can alternatively paste an existing public HTTPS image URL into the campaign form.

## WhatsApp setup
1. Create a Meta app and add the WhatsApp product.
2. Configure a WhatsApp Business phone number and obtain a Phone Number ID and permanent access token.
3. Set `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, and `WHATSAPP_GRAPH_API_VERSION`.
4. Create and get approval for a WhatsApp message template that includes an IMAGE header and BODY text parameters.
5. In the dashboard, import contacts with consent, create a campaign using the exact approved template name/language, provide an HTTPS image URL, and start it.
6. Configure the Meta webhook URL as `https://YOUR_API_HOST/api/webhooks/whatsapp`; set `WHATSAPP_VERIFY_TOKEN` and subscribe to `messages`.

The sender only targets contacts whose WhatsApp consent is recorded as true. Campaign sends use approved templates; it does not automate a personal WhatsApp account or bypass WhatsApp policies. Messaging limits, template approval, quality rules, and pricing are controlled by Meta.

## Production notes
- Set `ADMIN_EMAIL` and `ADMIN_PASSWORD`, a strong `SECRET_KEY`, `APP_ENV=production`, `CORS_ORIGINS`, and a managed `DATABASE_URL` (PostgreSQL recommended).
- Set `UPLOAD_DIR` to persistent storage or replace local media storage with private object storage.
- Run behind HTTPS. Configure the WhatsApp webhook in Meta.
- Add backups, monitoring, rate limits, and a production-grade secret manager before handling real customer data.
- SQLite is intended for local development, not multi-instance production.

## Tests
```bash
cd backend
pytest
```

This starter is designed to be runnable and extensible. Live WhatsApp delivery requires valid Meta credentials, an approved template, and an eligible recipient who has opted in.
