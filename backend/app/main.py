import re
import hmac
import hashlib
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy import select
from openpyxl import load_workbook
from app.config import settings
from app.database import Base, engine, get_db, SessionLocal
from app.models import User, Contact, Campaign, MessageLog, WorkspaceRecord
from app.workspace_api import router as workspace_router
from app.schemas import RegisterIn, LoginIn, TokenOut, UserOut, ContactOut, CampaignCreate, CampaignOut
from app.security import hash_password, verify_password, create_access_token, get_current_user
from app.whatsapp import send_image_template
from app import ai_models  # register AI tables before metadata.create_all
from app.ai_api import router as ai_router

Base.metadata.create_all(bind=engine)
from sqlalchemy import inspect
def ensure_ai_conversation_columns():
    existing = {column["name"] for column in inspect(engine).get_columns("ai_conversations")}
    statements = [
        ("title", "ALTER TABLE ai_conversations ADD COLUMN title VARCHAR(240) NOT NULL DEFAULT 'New conversation'"),
        ("pinned", "ALTER TABLE ai_conversations ADD COLUMN pinned BOOLEAN NOT NULL DEFAULT FALSE"),
        ("archived", "ALTER TABLE ai_conversations ADD COLUMN archived BOOLEAN NOT NULL DEFAULT FALSE"),
        ("updated_at", "ALTER TABLE ai_conversations ADD COLUMN updated_at TIMESTAMP"),
    ]
    with engine.begin() as connection:
        for column, statement in statements:
            if column not in existing:
                connection.exec_driver_sql(statement)
ensure_ai_conversation_columns()
app = FastAPI(title=settings.app_name, version="1.1.0")
app.include_router(workspace_router)
app.include_router(ai_router)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=str(settings.upload_path)), name="uploads")

@app.on_event("startup")
def ensure_single_admin():
    # Bootstrap exactly one configured admin account. Public registration stays disabled.
    if not settings.admin_email or not settings.admin_password:
        return
    db = SessionLocal()
    try:
        email = settings.admin_email.lower().strip()
        admin = db.scalar(select(User).where(User.email == email))
        if not admin:
            admin = User(email=email, hashed_password=hash_password(settings.admin_password))
            db.add(admin)
            db.commit()
    finally:
        db.close()

def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not settings.admin_email or user.email.lower() != settings.admin_email.lower().strip():
        raise HTTPException(403, "This website is restricted to the configured administrator.")
    return user

def normalize_phone(value) -> str | None:
    raw = str(int(value)) if isinstance(value, float) and value.is_integer() else str(value or "")
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 10 or len(digits) > 15:
        return None
    return digits

@app.get("/")
def root():
    return {"name": settings.app_name, "status": "ok", "docs": "/docs"}

@app.get(f"{settings.api_prefix}/health")
def health():
    return {"status": "ok", "whatsapp_configured": settings.whatsapp_configured}

@app.post(f"{settings.api_prefix}/auth/register", response_model=UserOut)
def register_disabled():
    raise HTTPException(403, "Public registration is disabled. Only the configured administrator can use this website.")

@app.post(f"{settings.api_prefix}/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    if not settings.admin_email or not settings.admin_password or len(settings.secret_key) < 32:
        raise HTTPException(503, "Administrator login is not configured. Set ADMIN_EMAIL, ADMIN_PASSWORD and a SECRET_KEY of at least 32 characters on the server.")
    if payload.email.lower() != settings.admin_email.lower().strip():
        raise HTTPException(403, "This website is restricted to the administrator.")
    user = db.scalar(select(User).where(User.email == settings.admin_email.lower().strip()))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_access_token(user.id)}

@app.get(f"{settings.api_prefix}/auth/me", response_model=UserOut)
def me(user: User = Depends(get_admin_user)):
    return user

@app.post(f"{settings.api_prefix}/contacts/import")
async def import_contacts(
    file: UploadFile = File(...),
    opted_in: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    filename = (file.filename or "").strip()
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        raise HTTPException(400, "Unsupported file type. Please upload an Excel .xlsx or .xlsm file (not .xls or .csv).")

    content = await file.read()
    if not content:
        raise HTTPException(400, "The uploaded file is empty. Choose a valid Excel workbook.")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is too large. Maximum size is {settings.max_upload_mb} MB.")

    workbook = None
    try:
        import io

        workbook = load_workbook(
            filename=io.BytesIO(content),
            read_only=True,
            data_only=True,
        )
        sheet = workbook.active
        if sheet is None or sheet.max_row is None or sheet.max_row < 1:
            raise HTTPException(400, "The Excel workbook has no rows. Add a header row and contact data.")

        def clean_header(value) -> str:
            return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())

        phone_headers = {
            "mobile", "mobileno", "mobilenumber", "phone", "phoneno",
            "phonenumber", "whatsapp", "whatsappno", "whatsappnumber",
            "contact", "contactno", "contactnumber", "cell", "cellphone",
            "cellnumber", "telephone", "telephoneno",
        }
        name_headers = {"name", "customer", "customername", "fullname", "contactname"}

        header_row_index = None
        phone_index = None
        name_index = None
        # Some spreadsheets have a title or blank rows above the actual column headings.
        for row_number, row in enumerate(
            sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 10), values_only=True),
            start=1,
        ):
            normalized = [clean_header(value) for value in row]
            matches = [i for i, value in enumerate(normalized) if value in phone_headers]
            if matches:
                header_row_index = row_number
                phone_index = matches[0]
                name_index = next((i for i, value in enumerate(normalized) if value in name_headers), None)
                break

        if phone_index is None or header_row_index is None:
            raise HTTPException(
                400,
                "Phone column not found. In the first 10 rows, add a heading such as Mobile, Mobile Number, Phone, Phone Number, WhatsApp Number, or Contact Number.",
            )

        added = skipped = invalid = 0
        for row in sheet.iter_rows(min_row=header_row_index + 1, values_only=True):
            value = row[phone_index] if phone_index < len(row) else None
            phone = normalize_phone(value)
            if not phone:
                invalid += 1
                continue

            name_value = row[name_index] if name_index is not None and name_index < len(row) else ""
            name = str(name_value or "").strip()[:160]
            existing = db.scalar(
                select(Contact).where(Contact.phone == phone, Contact.user_id == user.id)
            )
            if existing:
                skipped += 1
                continue

            db.add(Contact(name=name, phone=phone, opted_in=opted_in, user_id=user.id))
            added += 1

        db.commit()
        return {
            "added": added,
            "skipped": skipped,
            "invalid": invalid,
            "note": "Only mark opted_in=true when you have recorded customer permission.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            400,
            "Could not read this Excel workbook. Re-save it as .xlsx in Excel or LibreOffice and try again. "
            f"Details: {type(exc).__name__}",
        )
    finally:
        if workbook is not None:
            workbook.close()

@app.get(f"{settings.api_prefix}/contacts", response_model=list[ContactOut])
def list_contacts(db: Session = Depends(get_db), user: User = Depends(get_admin_user)):
    return list(db.scalars(select(Contact).where(Contact.user_id == user.id).order_by(Contact.created_at.desc()).limit(1000)))

@app.patch(f"{settings.api_prefix}/contacts/{{contact_id}}/consent")
def update_consent(contact_id: int, opted_in: bool, db: Session = Depends(get_db), user: User = Depends(get_admin_user)):
    contact = db.scalar(select(Contact).where(Contact.id == contact_id, Contact.user_id == user.id))
    if not contact: raise HTTPException(404, "Contact not found")
    contact.opted_in = opted_in
    db.commit()
    return {"id": contact.id, "opted_in": contact.opted_in}

@app.post(f"{settings.api_prefix}/media")
async def upload_media(file: UploadFile = File(...), user: User = Depends(get_admin_user)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(400, "Only PNG, JPG and WEBP images are supported")
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "Image is too large")
    if not (settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret):
        raise HTTPException(503, "Configure Cloudinary credentials to upload campaign images, or paste a public HTTPS image URL.")
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(cloud_name=settings.cloudinary_cloud_name, api_key=settings.cloudinary_api_key, api_secret=settings.cloudinary_api_secret, secure=True)
    try:
        result = await run_in_threadpool(cloudinary.uploader.upload, content, folder="sujaai/campaigns", resource_type="image")
    except Exception as exc:
        raise HTTPException(502, f"Image upload failed: {exc}")
    return {"secure_url": result["secure_url"], "public_id": result.get("public_id")}

@app.post(f"{settings.api_prefix}/campaigns", response_model=CampaignOut)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db), user: User = Depends(get_admin_user)):
    if not payload.image_url.startswith("https://"):
        raise HTTPException(400, "Campaign image URL must be a public HTTPS URL accessible by Meta")
    campaign = Campaign(**payload.model_dump(), user_id=user.id)
    db.add(campaign); db.commit(); db.refresh(campaign)
    return campaign

@app.get(f"{settings.api_prefix}/campaigns", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db), user: User = Depends(get_admin_user)):
    return list(db.scalars(select(Campaign).where(Campaign.user_id == user.id).order_by(Campaign.created_at.desc()).limit(100)))

async def run_campaign(campaign_id: int, user_id: int):
    db = SessionLocal()
    try:
        campaign = db.get(Campaign, campaign_id)
        if not campaign or campaign.user_id != user_id: return
        campaign.status = "sending"; db.commit()
        contacts = list(db.scalars(select(Contact).where(Contact.opted_in.is_(True), Contact.user_id == user_id)))
        campaign.total = len(contacts); db.commit()
        for contact in contacts:
            log = MessageLog(campaign_id=campaign.id, phone=contact.phone, status="queued")
            db.add(log); db.commit(); db.refresh(log)
            try:
                message_id = await send_image_template(contact.phone, campaign.template_name, campaign.language, campaign.image_url, campaign.body_text)
                log.status = "sent"; log.provider_message_id = message_id
                campaign.sent += 1
            except Exception as exc:
                log.status = "failed"; log.error = str(exc)[:2000]
                campaign.failed += 1
            db.commit()
        campaign.status = "completed"; db.commit()
    finally:
        db.close()

@app.post(f"{settings.api_prefix}/campaigns/{{campaign_id}}/send")
def start_campaign(campaign_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(get_admin_user)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign or campaign.user_id != user.id: raise HTTPException(404, "Campaign not found")
    if campaign.status in {"sending", "completed"}: raise HTTPException(409, "Campaign has already started")
    if not settings.whatsapp_configured: raise HTTPException(503, "Configure WhatsApp Cloud API credentials first")
    if not db.scalar(select(Contact.id).where(Contact.opted_in.is_(True), Contact.user_id == user.id).limit(1)):
        raise HTTPException(400, "No opted-in contacts available")
    campaign.status = "queued"; db.commit()
    background_tasks.add_task(run_campaign, campaign_id, user.id)
    return {"message": "Campaign queued", "campaign_id": campaign_id}

@app.get(f"{settings.api_prefix}/campaigns/{{campaign_id}}/logs")
def campaign_logs(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_admin_user)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign or campaign.user_id != user.id: raise HTTPException(404, "Campaign not found")
    logs = db.scalars(select(MessageLog).where(MessageLog.campaign_id == campaign_id).order_by(MessageLog.id.desc()).limit(1000))
    return [{"id": x.id, "phone": x.phone, "status": x.status, "error": x.error, "provider_message_id": x.provider_message_id} for x in logs]

@app.get(f"{settings.api_prefix}/webhooks/whatsapp")
def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == settings.whatsapp_verify_token and settings.whatsapp_verify_token:
        return int(params.get("hub.challenge", "0"))
    raise HTTPException(403, "Webhook verification failed")

@app.post(f"{settings.api_prefix}/webhooks/whatsapp")
async def receive_webhook(request: Request):
    raw_body = await request.body()
    if settings.meta_app_secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(settings.meta_app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(401, "Invalid webhook signature")
    import json
    payload = json.loads(raw_body or b"{}")
    # Meta delivery status notifications can be mapped to MessageLog by provider_message_id.
    try:
        statuses = payload["entry"][0]["changes"][0]["value"].get("statuses", [])
        db = SessionLocal()
        for item in statuses:
            log = db.scalar(select(MessageLog).where(MessageLog.provider_message_id == item.get("id")))
            if log:
                log.status = item.get("status", log.status)
        db.commit(); db.close()
    except (KeyError, IndexError, TypeError):
        pass
    return {"status": "received"}
