import json
import os
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
from .database import Base, engine, get_db
from . import models, schemas
from .security import issue_token, verify_admin, current_user, require_roles, hash_password, verify_password

Base.metadata.create_all(bind=engine)
app = FastAPI(title="SUJAAI API", version="0.2.0")
origins = [v.strip() for v in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if v.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET","POST","PUT","PATCH","DELETE"], allow_headers=["Authorization","Content-Type"])

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
    return {"status":"ok","service":"sujaai-api","version":"0.2.0"}

@app.post("/api/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session=Depends(get_db)):
    if verify_admin(payload.email, payload.password):
        canonical_email = os.getenv("ADMIN_EMAIL", payload.email).strip().lower()
        return {"access_token":issue_token(canonical_email,"owner")}
    user = db.scalar(select(models.AppUser).where(func.lower(models.AppUser.email)==payload.email.lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401,"Invalid email or password")
    return {"access_token":issue_token(user.email,user.role)}

@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user

@app.get("/api/users", response_model=list[schemas.UserOut])
def list_users(db:Session=Depends(get_db), user=Depends(require_roles("owner","admin"))):
    return db.scalars(select(models.AppUser).order_by(models.AppUser.id)).all()

@app.post("/api/users", response_model=schemas.UserOut, status_code=201)
def create_user(payload:schemas.UserCreate, db:Session=Depends(get_db), user=Depends(require_roles("owner","admin"))):
    item=models.AppUser(email=payload.email.lower().strip(),password_hash=hash_password(payload.password),role=payload.role)
    db.add(item)
    try: db.commit(); db.refresh(item)
    except IntegrityError: db.rollback(); raise HTTPException(409,"Email already registered")
    audit(db,user["email"],"user.create","user",item.id,{"role":item.role}); db.commit()
    return item

@app.patch("/api/users/{user_id}", response_model=schemas.UserOut)
def set_user_status(user_id:int,payload:schemas.UserStatusUpdate,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin"))):
    item=db.get(models.AppUser,user_id)
    if not item: raise HTTPException(404,"User not found")
    if item.email==user["email"] and not payload.is_active: raise HTTPException(422,"You cannot deactivate your own account")
    item.is_active=payload.is_active
    audit(db,user["email"],"user.status","user",item.id,{"is_active":item.is_active}); db.commit(); db.refresh(item)
    return item

@app.get("/api/chit/groups",response_model=list[schemas.GroupOut])
def list_groups(db:Session=Depends(get_db),user=Depends(current_user)):
    return db.scalars(select(models.ChitGroup).order_by(models.ChitGroup.created_at.desc())).all()

@app.post("/api/chit/groups",response_model=schemas.GroupOut,status_code=201)
def create_group(payload:schemas.GroupCreate,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin"))):
    item=models.ChitGroup(**payload.model_dump()); db.add(item)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409,"Group ID or name already exists")
    audit(db,user["email"],"group.create","chit_group",item.id); db.commit(); db.refresh(item)
    return item

@app.patch("/api/chit/groups/{group_id}",response_model=schemas.GroupOut)
def update_group(group_id:int,payload:schemas.GroupUpdate,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin"))):
    item=group_or_404(db,group_id); changes=payload.model_dump(exclude_unset=True)
    for key,value in changes.items(): setattr(item,key,value)
    audit(db,user["email"],"group.update","chit_group",item.id,changes)
    try: db.commit(); db.refresh(item)
    except IntegrityError: db.rollback(); raise HTTPException(409,"Group name conflicts with another group")
    return item

@app.get("/api/chit/groups/{group_id}")
def group_detail(group_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
    group=group_or_404(db,group_id)
    count=db.scalar(select(func.count()).select_from(models.ChitMember).where(models.ChitMember.group_id==group_id)) or 0
    total=db.scalar(select(func.coalesce(func.sum(models.ChitPayment.amount),0)).join(models.ChitMember).where(models.ChitMember.group_id==group_id)) or Decimal("0")
    return {"group":schemas.GroupOut.model_validate(group),"total_members":count,"lifetime_collection":str(total)}

@app.post("/api/chit/members",response_model=schemas.MemberOut,status_code=201)
def create_member(payload:schemas.MemberCreate,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","staff"))):
    group=group_or_404(db,payload.group_id)
    if group.status!="active": raise HTTPException(422,"Cannot add members to an inactive group")
    item=models.ChitMember(**payload.model_dump()); db.add(item)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409,"Member ID already exists")
    audit(db,user["email"],"member.create","chit_member",item.id); db.commit(); db.refresh(item)
    return item

@app.get("/api/chit/members",response_model=list[schemas.MemberOut])
def list_members(group_id:int|None=None,q:str|None=Query(default=None,max_length=160),status:str|None=None,limit:int=Query(200,ge=1,le=500),offset:int=Query(0,ge=0),db:Session=Depends(get_db),user=Depends(current_user)):
    stmt=select(models.ChitMember)
    if group_id is not None: stmt=stmt.where(models.ChitMember.group_id==group_id)
    if status in {"active","inactive"}: stmt=stmt.where(models.ChitMember.status==status)
    if q:
        term=f"%{q.strip()}%"
        stmt=stmt.where((models.ChitMember.name.ilike(term))|(models.ChitMember.mobile.ilike(term))|(models.ChitMember.member_code.ilike(term)))
    return db.scalars(stmt.order_by(models.ChitMember.id.desc()).offset(offset).limit(limit)).all()

@app.patch("/api/chit/members/{member_id}",response_model=schemas.MemberOut)
def update_member(member_id:int,payload:schemas.MemberUpdate,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","staff"))):
    item=member_or_404(db,member_id); changes=payload.model_dump(exclude_unset=True)
    for key,value in changes.items(): setattr(item,key,value)
    audit(db,user["email"],"member.update","chit_member",item.id,changes)
    try: db.commit(); db.refresh(item)
    except IntegrityError: db.rollback(); raise HTTPException(409,"Member update conflicts with existing data")
    return item

@app.post("/api/chit/payments",response_model=schemas.PaymentOut,status_code=201)
def create_payment(payload:schemas.PaymentCreate,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin","staff"))):
    member=member_or_404(db,payload.member_id); group=group_or_404(db,member.group_id)
    if member.status!="active": raise HTTPException(422,"Cannot record a payment for an inactive member")
    if group.status!="active": raise HTTPException(422,"Cannot record a payment for an inactive group")
    if payload.frequency!=group.chit_type: raise HTTPException(422,"Payment frequency must match the group's chit type")
    item=models.ChitPayment(payment_ref="PAY-"+uuid4().hex[:16].upper(),member_id=member.id,amount=payload.amount,paid_at=payload.paid_at,frequency=payload.frequency,notes=payload.notes,recorded_by=user["email"])
    db.add(item); db.flush()
    audit(db,user["email"],"payment.create","chit_payment",item.id,{"amount":str(item.amount),"member_id":member.id})
    db.commit(); db.refresh(item)
    return item

@app.get("/api/chit/payments",response_model=list[schemas.PaymentOut])
def list_payments(member_id:int|None=None,group_id:int|None=None,start:date|None=None,end:date|None=None,limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),db:Session=Depends(get_db),user=Depends(current_user)):
    stmt=select(models.ChitPayment).join(models.ChitMember)
    if member_id is not None: stmt=stmt.where(models.ChitPayment.member_id==member_id)
    if group_id is not None: stmt=stmt.where(models.ChitMember.group_id==group_id)
    if start: stmt=stmt.where(models.ChitPayment.paid_at>=datetime.combine(start,time.min).replace(tzinfo=timezone.utc))
    if end: stmt=stmt.where(models.ChitPayment.paid_at<datetime.combine(end+timedelta(days=1),time.min).replace(tzinfo=timezone.utc))
    return db.scalars(stmt.order_by(models.ChitPayment.paid_at.desc()).offset(offset).limit(limit)).all()

@app.get("/api/chit/payments/{payment_id}/excel")
def export_payment_excel(payment_id:int,db:Session=Depends(get_db),user=Depends(current_user)):
    payment=payment_or_404(db,payment_id)
    member=member_or_404(db,payment.member_id)
    group=group_or_404(db,member.group_id)
    wb=Workbook()
    sheet=wb.active
    sheet.title="Payment"
    sheet.append(["SUJAAI PAYMENT RECORD",""])
    sheet.append(["Payment reference",payment.payment_ref])
    sheet.append(["Member ID",member.member_code])
    sheet.append(["Member name",member.name])
    sheet.append(["Group",group.name])
    sheet.append(["Amount (INR)",float(payment.amount)])
    sheet.append(["Paid at",payment.paid_at.isoformat()])
    sheet.append(["Frequency",payment.frequency])
    sheet.append(["Recorded by",payment.recorded_by])
    sheet.append(["Notes",payment.notes or ""])
    for cell in sheet[1]:
        cell.font=Font(bold=True,color="FFFFFF")
        cell.fill=PatternFill("solid",fgColor="176B4A")
    sheet.column_dimensions["A"].width=24
    sheet.column_dimensions["B"].width=42
    stream=BytesIO()
    wb.save(stream)
    stream.seek(0)
    safe_ref="".join(ch for ch in payment.payment_ref if ch.isalnum() or ch in "-_")
    return StreamingResponse(stream,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f"attachment; filename={safe_ref}.xlsx"})

@app.patch("/api/chit/payments/{payment_id}",response_model=schemas.PaymentOut)
def correct_payment(payment_id:int,payload:schemas.PaymentUpdate,db:Session=Depends(get_db),user=Depends(require_roles("owner","admin"))):
    item=payment_or_404(db,payment_id)
    before={"amount":str(item.amount),"paid_at":item.paid_at.isoformat(),"notes":item.notes}
    changes=payload.model_dump(exclude_unset=True)
    for key,value in changes.items(): setattr(item,key,value)
    audit(db,user["email"],"payment.correct","chit_payment",item.id,{"before":before,"after":{k:str(v) for k,v in changes.items()}})
    db.commit(); db.refresh(item)
    return item

@app.get("/api/chit/reports/summary")
def summary(start:date|None=None,end:date|None=None,db:Session=Depends(get_db),user=Depends(current_user)):
    if start and end and start>end: raise HTTPException(422,"Start date must be on or before end date")
    stmt=select(func.coalesce(func.sum(models.ChitPayment.amount),0),func.count(models.ChitPayment.id)).select_from(models.ChitPayment)
    if start: stmt=stmt.where(models.ChitPayment.paid_at>=datetime.combine(start,time.min).replace(tzinfo=timezone.utc))
    if end: stmt=stmt.where(models.ChitPayment.paid_at<datetime.combine(end+timedelta(days=1),time.min).replace(tzinfo=timezone.utc))
    total,count=db.execute(stmt).one()
    group_stmt=select(models.ChitGroup.name,func.coalesce(func.sum(models.ChitPayment.amount),0)).join(models.ChitMember,models.ChitMember.group_id==models.ChitGroup.id).join(models.ChitPayment,models.ChitPayment.member_id==models.ChitMember.id).group_by(models.ChitGroup.id,models.ChitGroup.name)
    if start: group_stmt=group_stmt.where(models.ChitPayment.paid_at>=datetime.combine(start,time.min).replace(tzinfo=timezone.utc))
    if end: group_stmt=group_stmt.where(models.ChitPayment.paid_at<datetime.combine(end+timedelta(days=1),time.min).replace(tzinfo=timezone.utc))
    groups=db.execute(group_stmt).all()
    return {"total_collection":str(total),"payment_count":count,"group_totals":[{"group_name":n,"collection":str(v)} for n,v in groups]}

@app.get("/api/chit/reports/periods")
def period_report(period:str=Query("monthly",pattern="^(daily|weekly|monthly)$"),start:date|None=None,end:date|None=None,db:Session=Depends(get_db),user=Depends(current_user)):
    if start and end and start>end: raise HTTPException(422,"Start date must be on or before end date")
    bucket=func.date(models.ChitPayment.paid_at) if period=="daily" else func.strftime("%Y-%W",models.ChitPayment.paid_at) if period=="weekly" and engine.dialect.name=="sqlite" else func.strftime("%Y-%m",models.ChitPayment.paid_at) if period=="monthly" and engine.dialect.name=="sqlite" else func.date_trunc({"daily":"day","weekly":"week","monthly":"month"}[period],models.ChitPayment.paid_at)
    stmt=select(bucket.label("period"),func.sum(models.ChitPayment.amount).label("total"),func.count(models.ChitPayment.id).label("entries")).group_by(bucket).order_by(bucket)
    if start: stmt=stmt.where(models.ChitPayment.paid_at>=datetime.combine(start,time.min).replace(tzinfo=timezone.utc))
    if end: stmt=stmt.where(models.ChitPayment.paid_at<datetime.combine(end+timedelta(days=1),time.min).replace(tzinfo=timezone.utc))
    return [{"period":str(r.period),"total":str(r.total),"entries":r.entries} for r in db.execute(stmt)]

def backup_payload(db):
    groups=db.scalars(select(models.ChitGroup).order_by(models.ChitGroup.id)).all()
    members=db.scalars(select(models.ChitMember).order_by(models.ChitMember.id)).all()
    payments=db.scalars(select(models.ChitPayment).order_by(models.ChitPayment.id)).all()
    def row(obj,fields):
        return {field:(getattr(obj,field).isoformat() if isinstance(getattr(obj,field),(date,datetime)) else str(getattr(obj,field)) if isinstance(getattr(obj,field),Decimal) else getattr(obj,field)) for field in fields}
    return {"schema_version":1,"exported_at":datetime.now(timezone.utc).isoformat(),"groups":[row(x,["id","group_code","name","chit_type","default_amount","description","start_date","status"]) for x in groups],"members":[row(x,["id","member_code","group_id","name","mobile","address","joining_date","status","notes"]) for x in members],"payments":[row(x,["id","payment_ref","member_id","amount","paid_at","frequency","notes","recorded_by"]) for x in payments]}

@app.get("/api/backup/json")
def export_json(db:Session=Depends(get_db),user=Depends(require_roles("owner","admin"))):
    payload=backup_payload(db)
    return StreamingResponse(iter([json.dumps(payload,ensure_ascii=False,indent=2)]),media_type="application/json",headers={"Content-Disposition":"attachment; filename=sujaai-backup.json"})

@app.post("/api/backup/json/restore")
def restore_json(payload:schemas.BackupImport,db:Session=Depends(get_db),user=Depends(require_roles("owner"))):
    existing=(db.scalar(select(func.count()).select_from(models.ChitGroup)) or 0)+(db.scalar(select(func.count()).select_from(models.ChitMember)) or 0)+(db.scalar(select(func.count()).select_from(models.ChitPayment)) or 0)
    if existing: raise HTTPException(409,"Restore is allowed only into an empty chit database. Export a backup first.")
    try:
        group_map={}
        for data in payload.groups:
            data=dict(data); old_id=data.pop("id",None); data["default_amount"]=Decimal(str(data["default_amount"])); data["start_date"]=date.fromisoformat(data["start_date"])
            item=models.ChitGroup(**data); db.add(item); db.flush(); group_map[old_id]=item.id
        member_map={}
        for data in payload.members:
            data=dict(data); old_id=data.pop("id",None); data["group_id"]=group_map[data["group_id"]]; data["joining_date"]=date.fromisoformat(data["joining_date"])
            item=models.ChitMember(**data); db.add(item); db.flush(); member_map[old_id]=item.id
        for data in payload.payments:
            data=dict(data); data.pop("id",None); data["member_id"]=member_map[data["member_id"]]; data["amount"]=Decimal(str(data["amount"])); data["paid_at"]=datetime.fromisoformat(data["paid_at"])
            db.add(models.ChitPayment(**data))
        audit(db,user["email"],"backup.restore","database","chit",{"groups":len(payload.groups),"members":len(payload.members),"payments":len(payload.payments)})
        db.commit()
    except Exception as exc:
        db.rollback()
        if isinstance(exc,HTTPException): raise
        raise HTTPException(422,"Backup validation failed; no records were restored")
    return {"restored":True,"groups":len(payload.groups),"members":len(payload.members),"payments":len(payload.payments)}

@app.get("/api/backup/excel")
def export_excel(db:Session=Depends(get_db),user=Depends(require_roles("owner","admin"))):
    groups=db.scalars(select(models.ChitGroup).order_by(models.ChitGroup.id)).all()
    members=db.scalars(select(models.ChitMember).order_by(models.ChitMember.id)).all()
    payments=db.scalars(select(models.ChitPayment).order_by(models.ChitPayment.paid_at)).all()
    group_by_id={g.id:g for g in groups}
    member_by_id={m.id:m for m in members}
    wb=Workbook()
    summary_sheet=wb.active
    summary_sheet.title="Summary"
    total=sum((p.amount for p in payments),Decimal("0.00"))
    summary_sheet.append(["SUJAAI CHIT MANAGEMENT REPORT"])
    summary_sheet.append(["Exported at",datetime.now(timezone.utc).isoformat()])
    summary_sheet.append(["Total collection",float(total)])
    summary_sheet.append(["Payment entries",len(payments)])
    summary_sheet.append(["Groups",len(groups)])
    summary_sheet.append(["Members",len(members)])
    summary_sheet.append(["Active members",sum(1 for m in members if m.status=="active")])

    def add_sheet(title,headers,rows):
        sheet=wb.create_sheet(title)
        sheet.append(headers)
        for row in rows: sheet.append(row)
        sheet.freeze_panes="A2"
        if sheet.max_row>1: sheet.auto_filter.ref=sheet.dimensions
        for cell in sheet[1]:
            cell.font=Font(bold=True,color="FFFFFF")
            cell.fill=PatternFill("solid",fgColor="176B4A")
            cell.alignment=Alignment(vertical="center")
        for col in sheet.columns:
            letter=col[0].column_letter
            sheet.column_dimensions[letter].width=min(38,max(12,max(len(str(c.value or "")) for c in col)+2))
        return sheet

    add_sheet("Groups",["ID","Group ID","Group Name","Frequency","Contribution","Start Date","Status"],[
        [g.id,g.group_code,g.name,g.chit_type,float(g.default_amount),g.start_date.isoformat(),g.status] for g in groups
    ])
    add_sheet("Members",["ID","Member ID","Group ID","Name","Mobile","Address","Joining Date","Status","Notes"],[
        [m.id,m.member_code,group_by_id[m.group_id].group_code if m.group_id in group_by_id else "",m.name,m.mobile,m.address,m.joining_date.isoformat(),m.status,m.notes or ""] for m in members
    ])
    add_sheet("Payments",["ID","Payment Ref","Member ID","Member Name","Group","Amount","Paid At","Frequency","Recorded By","Notes"],[
        [p.id,p.payment_ref,p.member_id,member_by_id[p.member_id].name if p.member_id in member_by_id else "",group_by_id[member_by_id[p.member_id].group_id].name if p.member_id in member_by_id and member_by_id[p.member_id].group_id in group_by_id else "",float(p.amount),p.paid_at.isoformat(),p.frequency,p.recorded_by,p.notes or ""] for p in payments
    ])
    member_totals={}
    group_totals={}
    daily={}
    weekly={}
    monthly={}
    for p in payments:
        member=member_by_id.get(p.member_id)
        if not member: continue
        group=group_by_id.get(member.group_id)
        key=(member.id,member.member_code,member.name,group.name if group else "")
        old=member_totals.get(key,[Decimal("0.00"),0])
        member_totals[key]=[old[0]+p.amount,old[1]+1]
        gkey=(group.id,group.group_code,group.name) if group else (0,"","Unknown")
        gold=group_totals.get(gkey,[Decimal("0.00"),0])
        group_totals[gkey]=[gold[0]+p.amount,gold[1]+1]
        day=p.paid_at.date()
        iso=day.isocalendar()
        dkey=day.isoformat()
        wkey=f"{iso.year}-W{iso.week:02d}"
        mkey=day.strftime("%Y-%m")
        for bucket,bkey in ((daily,dkey),(weekly,wkey),(monthly,mkey)):
            bucket[bkey]=bucket.get(bkey,Decimal("0.00"))+p.amount
    add_sheet("Group Totals",["Group ID","Group Code","Group Name","Payment Count","Total Collection"],[
        [k[0],k[1],k[2],v[1],float(v[0])] for k,v in sorted(group_totals.items(),key=lambda x:x[0][0])
    ])
    add_sheet("Member Totals",["Member ID","Member Code","Member Name","Group","Payment Count","Total Paid"],[
        [k[0],k[1],k[2],k[3],v[1],float(v[0])] for k,v in sorted(member_totals.items(),key=lambda x:x[0][0])
    ])
    for title,bucket in (("Daily",daily),("Weekly",weekly),("Monthly",monthly)):
        add_sheet(title,["Period","Payment Collection"],[[k,float(v)] for k,v in sorted(bucket.items())])
    for cell in summary_sheet[1]:
        cell.font=Font(bold=True,color="FFFFFF",size=14)
        cell.fill=PatternFill("solid",fgColor="176B4A")
    summary_sheet.column_dimensions["A"].width=24
    summary_sheet.column_dimensions["B"].width=36
    stream=BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(stream,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":"attachment; filename=sujaai-chit-backup.xlsx"})

@app.get("/api/audit")
def audit_history(limit:int=Query(100,ge=1,le=500),db:Session=Depends(get_db),user=Depends(require_roles("owner","admin"))):
    rows=db.scalars(select(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(limit)).all()
    return [{"id":x.id,"actor":x.actor,"action":x.action,"entity_type":x.entity_type,"entity_id":x.entity_id,"details":x.details,"created_at":x.created_at} for x in rows]


def saved_design_out(item):
    return {"id": item.id, "design_type": item.design_type, "title": item.title,
            "data": json.loads(item.data), "created_at": item.created_at,
            "updated_at": item.updated_at}

def serialize_design_data(data):
    serialized = json.dumps(data, ensure_ascii=False)
    if len(serialized.encode("utf-8")) > 6 * 1024 * 1024:
        raise HTTPException(413, "Design data is too large. Reduce image sizes and try again.")
    return serialized

@app.get("/api/designs")
def list_saved_designs(design_type: str | None = Query(default=None, pattern="^(resume|pvc)$"),
                       db: Session = Depends(get_db), user=Depends(current_user)):
    stmt = select(models.SavedDesign).where(models.SavedDesign.owner_email == user["email"])
    if design_type:
        stmt = stmt.where(models.SavedDesign.design_type == design_type)
    rows = db.scalars(stmt.order_by(models.SavedDesign.updated_at.desc())).all()
    return [saved_design_out(row) for row in rows]

@app.post("/api/designs", status_code=201)
def create_saved_design(payload: schemas.SavedDesignCreate,
                        db: Session = Depends(get_db), user=Depends(current_user)):
    item = models.SavedDesign(owner_email=user["email"], design_type=payload.design_type,
                              title=payload.title.strip(), data=json.dumps(payload.data, ensure_ascii=False))
    db.add(item)
    db.flush()
    audit(db, user["email"], "design.create", payload.design_type, item.id, {"title": item.title})
    db.commit()
    db.refresh(item)
    return saved_design_out(item)

@app.put("/api/designs/{design_id}")
def update_saved_design(design_id: int, payload: schemas.SavedDesignUpdate,
                        db: Session = Depends(get_db), user=Depends(current_user)):
    item = db.get(models.SavedDesign, design_id)
    if not item or item.owner_email != user["email"]:
        raise HTTPException(404, "Saved design not found")
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes:
        item.title = changes["title"].strip()
    if "data" in changes:
        item.data = json.dumps(changes["data"], ensure_ascii=False)
    audit(db, user["email"], "design.update", item.design_type, item.id, {"fields": list(changes)})
    db.commit()
    db.refresh(item)
    return saved_design_out(item)

@app.delete("/api/designs/{design_id}", status_code=204)
def delete_saved_design(design_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    item = db.get(models.SavedDesign, design_id)
    if not item or item.owner_email != user["email"]:
        raise HTTPException(404, "Saved design not found")
    audit(db, user["email"], "design.delete", item.design_type, item.id, {"title": item.title})
    db.delete(item)
    db.commit()
    return None

@app.get("/api/designs/{design_id}")
def get_saved_design(design_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    item = db.get(models.SavedDesign, design_id)
    if not item or item.owner_email != user["email"]:
        raise HTTPException(404, "Saved design not found")
    return saved_design_out(item)
