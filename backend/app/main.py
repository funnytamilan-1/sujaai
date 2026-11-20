import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape
from .database import Base, engine, get_db
from .config import settings
from . import models, schemas
from .security import issue_token, verify_admin, current_user, require_roles, hash_password, verify_password

Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.api_title, version=settings.api_version, debug=settings.debug)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])

def audit(db, actor, action, entity_type, entity_id, details=None):
    db.add(models.AuditLog(actor=actor, action=action, entity_type=entity_type, entity_id=str(entity_id), details=json.dumps(details or {}, default=str)))

def group_or_404(db, group_id):
    item = db.get(models.ChitGroup, group_id)
    if not item: raise HTTPException(404, "Group not found")
    return item

def member_or_404(db, member_id):
    item = db.get(models.ChitMember, member_id)
    if not item: raise HTTPException(404, "Member not found")
    return item

def payment_or_404(db, payment_id):
    item = db.get(models.ChitPayment, payment_id)
    if not item: raise HTTPException(404, "Payment not found")
    return item

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "sujaai-api", "version": settings.api_version}


@app.get("/api/health/ready")
def readiness():
    from sqlalchemy import text as sql_text
    try:
        with engine.connect() as connection:
            connection.execute(sql_text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception:
        raise HTTPException(503, "Database is unavailable")

