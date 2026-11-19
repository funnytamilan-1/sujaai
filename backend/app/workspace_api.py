import json
import io
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.workspace_config import (GOOGLE_CLIENT_ID, WORKSPACE_UPLOAD_MAX_MB, WORKSPACE_MAX_RECORD_BYTES, WORKSPACE_MAX_BACKUP_RECORDS)
from app.database import get_db
from app.models import User, WorkspaceRecord
from app.security import get_current_user, create_access_token
from PIL import Image, UnidentifiedImageError

router = APIRouter()
ALLOWED_TYPES = {"customer", "chit_group", "chit_payment", "receipt", "resume", "id_card"}

def require_admin(user: User = Depends(get_current_user)) -> User:
    if not settings.admin_email or user.email.lower() != settings.admin_email.lower().strip():
        raise HTTPException(403, "This workspace is restricted to the configured administrator.")
    return user

def serialize(record: WorkspaceRecord) -> dict[str, Any]:
    try:
        data = json.loads(record.data_json or "{}")
    except (TypeError, json.JSONDecodeError):
        data = {}
    return {"id": record.id, "type": record.record_type, "title": record.title, "data": data,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None}

@router.get(f"{settings.api_prefix}/workspace/records")
def list_records(record_type: str | None = None, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    query = select(WorkspaceRecord).where(WorkspaceRecord.user_id == user.id)
    if record_type:
        if record_type not in ALLOWED_TYPES:
            raise HTTPException(400, "Unsupported record type")
        query = query.where(WorkspaceRecord.record_type == record_type)
    return [serialize(x) for x in db.scalars(query.order_by(WorkspaceRecord.updated_at.desc()).limit(2000))]

@router.post(f"{settings.api_prefix}/workspace/records")
def create_record(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    kind, data = str(payload.get("type", "")), payload.get("data", {})
    if kind not in ALLOWED_TYPES:
        raise HTTPException(400, "Unsupported record type")
    if not isinstance(data, dict):
        raise HTTPException(422, "Record data must be an object")
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > WORKSPACE_MAX_RECORD_BYTES:
        raise HTTPException(413, "Record data is too large. Store images as files, not embedded base64.")
    record = WorkspaceRecord(user_id=user.id, record_type=kind,
        title=str(payload.get("title", "Untitled")).strip()[:200] or "Untitled", data_json=encoded)
    db.add(record); db.commit(); db.refresh(record)
    return serialize(record)

@router.put(f"{settings.api_prefix}/workspace/records/{{record_id}}")
def update_record(record_id: int, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    record = db.scalar(select(WorkspaceRecord).where(WorkspaceRecord.id == record_id, WorkspaceRecord.user_id == user.id))
    if not record:
        raise HTTPException(404, "Record not found")
    data = payload.get("data", {})
    if not isinstance(data, dict):
        raise HTTPException(422, "Record data must be an object")
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > WORKSPACE_MAX_RECORD_BYTES:
        raise HTTPException(413, "Record data is too large. Store images as files, not embedded base64.")
    record.title = str(payload.get("title", record.title)).strip()[:200] or "Untitled"
    record.data_json = encoded
    record.updated_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(record)
    return serialize(record)

@router.delete(f"{settings.api_prefix}/workspace/records/{{record_id}}")
def delete_record(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    record = db.scalar(select(WorkspaceRecord).where(WorkspaceRecord.id == record_id, WorkspaceRecord.user_id == user.id))
    if not record:
        raise HTTPException(404, "Record not found")
    db.delete(record); db.commit()
    return {"deleted": True, "id": record_id}

@router.get(f"{settings.api_prefix}/workspace/backup")
def create_backup(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    records = db.scalars(select(WorkspaceRecord).where(WorkspaceRecord.user_id == user.id).order_by(WorkspaceRecord.id))
    return {"format": "sujaai-workspace-backup-v1", "created_at": datetime.now(timezone.utc).isoformat(),
            "records": [serialize(x) for x in records]}

@router.post(f"{settings.api_prefix}/workspace/restore")
def restore_backup(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    if payload.get("format") != "sujaai-workspace-backup-v1":
        raise HTTPException(400, "Unsupported backup format")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) > WORKSPACE_MAX_BACKUP_RECORDS:
        raise HTTPException(400, f"Backup must contain at most {WORKSPACE_MAX_BACKUP_RECORDS} records")
    created = []
    for item in records:
        if not isinstance(item, dict) or item.get("type") not in ALLOWED_TYPES or not isinstance(item.get("data", {}), dict):
            raise HTTPException(400, "Backup contains an invalid record")
        encoded = json.dumps(item.get("data", {}), ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > WORKSPACE_MAX_RECORD_BYTES:
            raise HTTPException(413, "A backup record is too large")
        created.append(WorkspaceRecord(user_id=user.id, record_type=item["type"],
            title=str(item.get("title", "Restored record")).strip()[:200] or "Restored record", data_json=encoded))
    db.add_all(created); db.commit()
    return {"restored": len(created), "mode": "append"}

@router.post(f"{settings.api_prefix}/workspace/media")
async def upload_workspace_image(file: UploadFile = File(...), user: User = Depends(require_admin)):
    raw = await file.read()
    if not raw or len(raw) > WORKSPACE_UPLOAD_MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"Choose an image smaller than {WORKSPACE_UPLOAD_MAX_MB} MB")
    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(400, "The uploaded file is not a valid image")
    image = Image.open(io.BytesIO(raw))
    if image.width < 1 or image.height < 1 or image.width > 10000 or image.height > 10000:
        raise HTTPException(400, "Image dimensions are not supported")
    ext = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(image.format)
    if not ext:
        raise HTTPException(400, "Only JPEG, PNG and WEBP images are supported")
    folder = settings.upload_path / "studio"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{ext}"
    target = folder / filename
    target.write_bytes(raw)
    return {"url": f"/uploads/studio/{filename}", "width": image.width, "height": image.height}

@router.post(f"{settings.api_prefix}/auth/google")
def google_admin_login(payload: dict, db: Session = Depends(get_db)):
    client_id = GOOGLE_CLIENT_ID
    credential = payload.get("credential")
    if not client_id:
        raise HTTPException(503, "Google login is not configured. Set GOOGLE_CLIENT_ID on the backend.")
    if not isinstance(credential, str) or not credential:
        raise HTTPException(400, "A Google ID token is required.")
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
        claims = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
    except Exception:
        raise HTTPException(401, "Google sign-in could not be verified.")
    email = str(claims.get("email", "")).lower().strip()
    if not claims.get("email_verified") or not settings.admin_email or email != settings.admin_email.lower().strip():
        raise HTTPException(403, "This Google account is not the configured workspace administrator.")
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(403, "The configured administrator account has not been initialized.")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}
