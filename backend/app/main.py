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
from app.models import User, Contact, Campaign, MessageLog
from app.schemas import RegisterIn, LoginIn, TokenOut, UserOut, ContactOut, CampaignCreate, CampaignOut
from app.security import hash_password, verify_password, create_access_token, get_current_user
from app.whatsapp import send_image_template

Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.app_name, version="1.0.0")
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
    if not settings.admin_email or not settings.admin_password:
        raise HTTPException(503, "Administrator login is not configured. Set ADMIN_EMAIL and ADMIN_PASSWORD on the server.")
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
async def import_contacts(file: UploadFile = File(...), opted_in: bool = Query(False), db: Session = Depends(get_db), user: User = Depends(get_admin_user)):
    if not file.filename or Path(file.filename).suffix.lower() not in {".xlsx", ".xlsm"}:
        raise HTTPException(400, "Upload an .xlsx or .xlsm Excel file")
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "File is too large")
    try:
        workbook = load_workbook(filename=__import__("io").BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.active
        headers = [str(c.value or "").strip().lower() for c in next(sheet.iter_rows(min_row=1, max_row=1))]
        candidates = [i for i, h in enumerate(headers) if h in {"mobile", "mobile number", "phone", "phone number", "whatsapp", "whatsapp number"}]
        if not candidates:
            raise HTTPException(400, "No Mobile/Phone column found in the first row")
        phone_index = candidates[0]
        name_index = next((i for i, h in enumerate(headers) if h in {"name", "customer", "customer name"}), None)
        added = skipped = invalid = 0
        for row in sheet.iter_rows(min_row=2, values_only=True):
            phone = normalize_phone(row[phone_index] if phone_index < len(row) else None)
            if not phone:
                invalid += 1; continue
            name = str(row[name_index] or "").strip()[:160] if name_index is not None and name_index < len(row) else ""
            existing = db.scalar(select(Contact).where(Contact.phone == phone, Contact.user_id == user.id))
            if existing:
                skipped += 1
                continue
            db.add(Contact(name=name, phone=phone, opted_in=opted_in, user_id=user.id))
            added += 1
        db.commit()
        return {"added": added, "skipped": skipped, "invalid": invalid, "note": "Only mark opted_in=true when you have recorded customer permission."}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, f"Could not read Excel file: {exc}")
    
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
