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


## SUJA Insurance AI (initial retrieval-grounded phase)

The existing FastAPI/SQLAlchemy backend is reused; this does not migrate the working app to Express or MongoDB. AI tables are added to the configured SQL database when the app starts.

### API and admin workspace
- Open **Insurance AI** in the signed-in admin workspace.
- Add insurance Q&A knowledge; entries are pending until explicitly approved.
- Upload PDF, DOCX, TXT, CSV, XLSX or XLSM files. Text extraction is performed on the API server; documents remain private and require explicit admin approval.
- Ask questions in the AI Playground. Responses are assembled only from approved knowledge/document chunks, with source identifiers. If no matching approved content is found, the assistant says so.
- Feedback, conversations, document metadata, knowledge versions, training jobs and audit events are stored in SQL tables.

### Persistent AI worker (required for semantic indexing)
Install the optional worker dependencies on a persistent Python host with access to the same database:
```bash
cd backend
pip install -r requirements.txt
pip install -r requirements-ai.txt
python -m app.ai_worker
```
Queue indexing from Insurance AI → Training. The worker generates multilingual sentence embeddings and creates an index version. It is deliberately not run inside Vercel serverless functions. The first embedding-model load may download model files; configure outbound access and persistent cache storage on the worker. Without the optional embedding package, chat uses a transparent lexical fallback and is not semantic neural retrieval.

### Current scope and limitations
- Implemented in this phase: authenticated admin API, knowledge CRUD/approval, supported document extraction, private source storage, chunking, retrieval-grounded chat, feedback, indexing job queue, worker, embedding-index version records, and a small experimental PyTorch transformer encoder definition.
- Not implemented/verified yet: supervised fine-tuning/checkpoint training loop, pause/resume, model rollback/activation controls, robust retrieval evaluation/accuracy metrics, conversation analytics UI, multi-role RBAC, object-storage encryption, production worker supervision, and deployment of the AI worker.
- The experimental encoder is not a conversational language model. The retrieval assistant is extractive and does not generate fluent new answers; it must not be treated as policy advice or an eligibility/claim decision system.
- Use official, current insurer/regulator documents and have an authorized insurance professional review entries before approval. Do not upload unnecessary customer personal data.

AI endpoints are under `/api/ai` and require the existing administrator JWT. Set production database and credentials through deployment environment variables. Do not commit secrets.


### Security action required before production use
Previous repository revisions contained credential defaults in source configuration. The current configuration no longer supplies those defaults: configure DATABASE_URL, SECRET_KEY (at least 32 random characters), ADMIN_EMAIL, ADMIN_PASSWORD and WhatsApp credentials only as deployment environment variables. Rotate the previously committed database password, JWT signing key, administrator password and WhatsApp access token immediately. Removing a value from the latest file does not erase it from Git history; treat every previously committed value as compromised.


## SUJA Insurance AI chat workspace

The signed-in **Insurance AI** workspace is a full-screen conversational UI. It uses the existing administrator JWT and FastAPI/SQLAlchemy backend; this feature does not migrate the project to MongoDB.

### Available now
- Persistent, user-scoped conversations and message records in the configured SQL database.
- New chat, recent history, search within the loaded history, rename, pin, archive/unarchive and delete.
- Responsive collapsible sidebar, light/dark appearance toggle, font-size setting and model selector.
- Retrieval-grounded answers from administrator-approved SUJA knowledge. The Document Assistant filters retrieval to approved documents.
- Server-Sent Events transport for answer delivery, source metadata, copy, feedback, and regenerate.
- PDF, DOCX, TXT, CSV, XLSX and XLSM uploads through the existing private document extraction endpoint. Uploads enter the admin document review queue; they are not automatically approved or inserted into the current chat context.
- The neural model option is explicitly unavailable because no conversational neural checkpoint is deployed.

### Important implementation boundaries
- SSE currently streams the completed retrieval answer in chunks; retrieval/answer assembly is performed before the stream begins. It is not incremental LLM token generation.
- Stopping a stream stops the browser from receiving/displaying further chunks; it does not cancel the already-completed retrieval request on the server.
- The assistant is extractive and source-grounded, not a generative ChatGPT replacement. It does not use conversation history to synthesize new answers.
- Voice input, image understanding, in-chat file-context injection, true message editing/deletion, secure share links, conversation virtualization, and full preference persistence are not implemented in this phase.
- The database startup migration only adds new conversation metadata columns and preserves existing rows. For production, use a formal migration system and backups.
- No MongoDB dependency was introduced because the existing project uses SQLAlchemy and changing databases would be an unnecessary data migration.

Use the **Knowledge, models & training** link in the chat sidebar to return to the existing AI Control Center. Keep the AI worker running on a persistent host for semantic embedding indexing.
