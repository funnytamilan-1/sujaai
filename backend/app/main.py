from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import json
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from . import models, schemas
from .security import issue_token, verify_admin, current_user, require_roles

Base.metadata.create_all(bind=engine)
app = FastAPI(title="SUJAAI API", version="0.1.0")

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "sujaai-api"}

@app.post("/api/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest):
    if not verify_admin(payload.email, payload.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"access_token": issue_token(payload.email), "token_type": "bearer"}

@app.get("/api/chit/groups", response_model=list[schemas.GroupOut])
def list_groups(db: Session = Depends(get_db), user=Depends(current_user)):
    return db.scalars(select(models.ChitGroup).order_by(models.ChitGroup.created_at.desc())).all()

@app.post("/api/chit/groups", response_model=schemas.GroupOut, status_code=201)
def create_group(payload: schemas.GroupCreate, db: Session = Depends(get_db), user=Depends(require_roles("owner", "admin"))):
    group = models.ChitGroup(**payload.model_dump())
    db.add(group)
    try:
        db.commit()
        db.refresh(group)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Group ID or name already exists")
    db.add(models.AuditLog(actor=user["email"], action="group.create", entity_type="chit_group", entity_id=str(group.id)))
    db.commit()
    return group

@app.get("/api/chit/groups/{group_id}")
def group_detail(group_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    group = db.get(models.ChitGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    member_count = db.scalar(select(func.count()).select_from(models.ChitMember).where(models.ChitMember.group_id == group_id)) or 0
    total = db.scalar(select(func.coalesce(func.sum(models.ChitPayment.amount), 0)).join(models.ChitMember).where(models.ChitMember.group_id == group_id)) or Decimal("0.00")
    today_start = datetime.combine(date.today(), time.min).replace(tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)
    today_total = db.scalar(select(func.coalesce(func.sum(models.ChitPayment.amount), 0)).join(models.ChitMember).where(models.ChitMember.group_id == group_id, models.ChitPayment.paid_at >= today_start, models.ChitPayment.paid_at < today_end)) or Decimal("0.00")
    return {"group": schemas.GroupOut.model_validate(group), "total_members": member_count, "lifetime_collection": total, "today_collection": today_total}

@app.post("/api/chit/members", response_model=schemas.MemberOut, status_code=201)
def create_member(payload: schemas.MemberCreate, db: Session = Depends(get_db), user=Depends(require_roles("owner", "admin", "staff"))):
    if not db.get(models.ChitGroup, payload.group_id):
        raise HTTPException(status_code=404, detail="Chit group not found")
    member = models.ChitMember(**payload.model_dump())
    db.add(member)
    try:
        db.commit()
        db.refresh(member)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Member ID already exists")
    db.add(models.AuditLog(actor=user["email"], action="member.create", entity_type="chit_member", entity_id=str(member.id)))
    db.commit()
    return member

@app.get("/api/chit/members", response_model=list[schemas.MemberOut])
def list_members(group_id: int | None = None, q: str | None = Query(default=None, max_length=160), db: Session = Depends(get_db), user=Depends(current_user)):
    stmt = select(models.ChitMember)
    if group_id is not None:
        stmt = stmt.where(models.ChitMember.group_id == group_id)
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where((models.ChitMember.name.ilike(term)) | (models.ChitMember.mobile.ilike(term)) | (models.ChitMember.member_code.ilike(term)))
    return db.scalars(stmt.order_by(models.ChitMember.id.desc()).limit(200)).all()

@app.post("/api/chit/payments", response_model=schemas.PaymentOut, status_code=201)
def create_payment(payload: schemas.PaymentCreate, db: Session = Depends(get_db), user=Depends(require_roles("owner", "admin", "staff"))):
    member = db.get(models.ChitMember, payload.member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    group = db.get(models.ChitGroup, member.group_id)
    if payload.frequency != group.chit_type:
        raise HTTPException(status_code=422, detail="Payment frequency must match the group's chit type")
    payment = models.ChitPayment(payment_ref=f"PAY-{uuid4().hex[:16].upper()}", member_id=member.id, amount=payload.amount, paid_at=payload.paid_at, frequency=payload.frequency, notes=payload.notes, recorded_by=user["email"])
    db.add(payment)
    try:
        db.flush()
        db.add(models.AuditLog(actor=user["email"], action="payment.create", entity_type="chit_payment", entity_id=str(payment.id), details=json.dumps({"amount": str(payment.amount), "member_id": member.id})))
        db.commit()
        db.refresh(payment)
    except Exception:
        db.rollback()
        raise
    return payment

@app.get("/api/chit/payments", response_model=list[schemas.PaymentOut])
def list_payments(member_id: int | None = None, group_id: int | None = None, start: date | None = None, end: date | None = None, limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db), user=Depends(current_user)):
    stmt = select(models.ChitPayment).join(models.ChitMember)
    if member_id is not None:
        stmt = stmt.where(models.ChitPayment.member_id == member_id)
    if group_id is not None:
        stmt = stmt.where(models.ChitMember.group_id == group_id)
    if start:
        stmt = stmt.where(models.ChitPayment.paid_at >= datetime.combine(start, time.min).replace(tzinfo=timezone.utc))
    if end:
        stmt = stmt.where(models.ChitPayment.paid_at < datetime.combine(end + timedelta(days=1), time.min).replace(tzinfo=timezone.utc))
    return db.scalars(stmt.order_by(models.ChitPayment.paid_at.desc()).offset(offset).limit(limit)).all()

@app.get("/api/chit/reports/summary")
def chit_summary(start: date | None = None, end: date | None = None, db: Session = Depends(get_db), user=Depends(current_user)):
    stmt = select(func.coalesce(func.sum(models.ChitPayment.amount), 0), func.count(models.ChitPayment.id)).select_from(models.ChitPayment)
    if start:
        stmt = stmt.where(models.ChitPayment.paid_at >= datetime.combine(start, time.min).replace(tzinfo=timezone.utc))
    if end:
        stmt = stmt.where(models.ChitPayment.paid_at < datetime.combine(end + timedelta(days=1), time.min).replace(tzinfo=timezone.utc))
    total, count = db.execute(stmt).one()
    groups = db.execute(select(models.ChitGroup.name, func.coalesce(func.sum(models.ChitPayment.amount), 0)).join(models.ChitMember, models.ChitMember.group_id == models.ChitGroup.id).join(models.ChitPayment, models.ChitPayment.member_id == models.ChitMember.id).group_by(models.ChitGroup.id, models.ChitGroup.name)).all()
    return {"total_collection": str(total), "payment_count": count, "group_totals": [{"group_name": name, "collection": str(amount)} for name, amount in groups]}
