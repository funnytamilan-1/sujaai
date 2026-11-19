import json, time, uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User
from app.security import get_current_user
from app.ai_models import AIDocument, AIKnowledge, AIChunk, AITrainingJob, AIModelVersion, AIConversation, AIFeedback, AIAuditLog
from app.ai_service import extract_text, clean_text, retrieve

router=APIRouter(prefix="/api/ai",tags=["SUJA Insurance AI"])
CATEGORIES=["Life Insurance","Health Insurance","Motor Insurance","Vehicle Insurance","Term Insurance","General Insurance","Premium Information","Policy Details","Renewal Information","Claims Process","Insurance Documents","Customer FAQs","Insurance Regulations"]
ALLOWED={".pdf",".docx",".txt",".csv",".xlsx",".xlsm"}

def admin(user:User=Depends(get_current_user)):
    if not settings.admin_email or user.email.lower()!=settings.admin_email.lower().strip(): raise HTTPException(403,"Administrator access required")
    return user

def audit(db,user,action,kind,entity_id="",details=""):
    db.add(AIAuditLog(user_id=user.id,action=action,entity_type=kind,entity_id=str(entity_id),details=details[:2000]))

class KnowledgeIn(BaseModel):
    title:str=Field(min_length=1,max_length=255)
    category:str=Field(min_length=1,max_length=80)
    question:str=""
    answer:str=Field(min_length=1,max_length=20000)
    source:str="Admin entry"
class ChatIn(BaseModel):
    question:str=Field(min_length=2,max_length=4000)
class FeedbackIn(BaseModel):
    conversation_id:int
    rating:int=Field(ge=1,le=5)
    comment:str=Field(default="",max_length=2000)

@router.get("/overview")
def overview(db:Session=Depends(get_db),user:User=Depends(admin)):
    count=lambda model,*conds: db.scalar(select(func.count(model.id)).where(model.user_id==user.id,*conds)) or 0
    return {"knowledge_entries":count(AIKnowledge),"approved_knowledge":count(AIKnowledge,AIKnowledge.approval_status=="approved"),"pending_knowledge":count(AIKnowledge,AIKnowledge.approval_status=="pending"),"documents":count(AIDocument),"training_jobs":count(AITrainingJob),"active_models":count(AIModelVersion,AIModelVersion.status=="active")}

@router.get("/categories")
def categories(user:User=Depends(admin)): return CATEGORIES

@router.get("/knowledge")
def list_knowledge(db:Session=Depends(get_db),user:User=Depends(admin)):
    return [dict(id=x.id,title=x.title,category=x.category,question=x.question,answer=x.answer,source=x.source,approval_status=x.approval_status,version=x.version,created_at=x.created_at.isoformat()) for x in db.scalars(select(AIKnowledge).where(AIKnowledge.user_id==user.id).order_by(AIKnowledge.updated_at.desc()).limit(1000))]

@router.post("/knowledge")
def add_knowledge(payload:KnowledgeIn,db:Session=Depends(get_db),user:User=Depends(admin)):
    item=AIKnowledge(user_id=user.id,**payload.model_dump(),approval_status="pending");db.add(item);db.flush()
    audit(db,user,"knowledge.created","knowledge",item.id);db.commit();db.refresh(item)
    return {"id":item.id,"approval_status":item.approval_status}

@router.put("/knowledge/{item_id}")
def edit_knowledge(item_id:int,payload:KnowledgeIn,db:Session=Depends(get_db),user:User=Depends(admin)):
    item=db.scalar(select(AIKnowledge).where(AIKnowledge.id==item_id,AIKnowledge.user_id==user.id))
    if not item: raise HTTPException(404,"Knowledge entry not found")
    for k,v in payload.model_dump().items(): setattr(item,k,v)
    item.version+=1;item.approval_status="pending"
    db.query(AIChunk).filter(AIChunk.knowledge_id==item.id).delete()
    audit(db,user,"knowledge.updated","knowledge",item.id);db.commit()
    return {"id":item.id,"version":item.version,"approval_status":item.approval_status}

@router.delete("/knowledge/{item_id}")
def delete_knowledge(item_id:int,db:Session=Depends(get_db),user:User=Depends(admin)):
    item=db.scalar(select(AIKnowledge).where(AIKnowledge.id==item_id,AIKnowledge.user_id==user.id))
    if not item: raise HTTPException(404,"Knowledge entry not found")
    db.query(AIChunk).filter(AIChunk.knowledge_id==item.id).delete();db.delete(item)
    audit(db,user,"knowledge.deleted","knowledge",item_id);db.commit()
    return {"deleted":True}

@router.post("/knowledge/{item_id}/approve")
def approve_knowledge(item_id:int,db:Session=Depends(get_db),user:User=Depends(admin)):
    item=db.scalar(select(AIKnowledge).where(AIKnowledge.id==item_id,AIKnowledge.user_id==user.id))
    if not item: raise HTTPException(404,"Knowledge entry not found")
    item.approval_status="approved";body=(item.title+"\n"+item.question+"\n"+item.answer).strip()
    db.query(AIChunk).filter(AIChunk.knowledge_id==item.id).delete()
    db.add(AIChunk(user_id=user.id,knowledge_id=item.id,text=body))
    audit(db,user,"knowledge.approved","knowledge",item.id);db.commit()
    return {"approved":True,"note":"Approved content is eligible for retrieval. Run indexing to create embeddings."}

@router.post("/documents/upload")
async def upload_document(file:UploadFile=File(...),db:Session=Depends(get_db),user:User=Depends(admin)):
    name=Path(file.filename or "document").name;suffix=Path(name).suffix.lower()
    if suffix not in ALLOWED: raise HTTPException(400,"Supported: PDF, DOCX, TXT, CSV, XLSX, XLSM")
    content=await file.read()
    if not content or len(content)>settings.max_upload_mb*1024*1024: raise HTTPException(413,"File is empty or exceeds upload limit")
    folder=settings.upload_path/"private-ai"/str(user.id);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(uuid.uuid4().hex+suffix);path.write_bytes(content)
    doc=AIDocument(user_id=user.id,filename=name,stored_path=str(path),content_type=file.content_type or "application/octet-stream");db.add(doc);db.flush()
    try:
        extracted=clean_text(extract_text(str(path),suffix))
        if not extracted: raise ValueError("No readable text found")
        doc.extracted_chars=len(extracted);doc.status="extracted"
        db.add(AIChunk(user_id=user.id,document_id=doc.id,text=extracted[:500000]))
        audit(db,user,"document.uploaded","document",doc.id);db.commit()
        return {"id":doc.id,"filename":name,"status":doc.status,"characters":doc.extracted_chars,"approval_required":True}
    except Exception as exc:
        doc.status="extraction_failed";db.commit()
        raise HTTPException(422,"Document text extraction failed: "+str(exc)[:250])

@router.get("/documents")
def documents(db:Session=Depends(get_db),user:User=Depends(admin)):
    return [dict(id=x.id,filename=x.filename,status=x.status,extracted_chars=x.extracted_chars,created_at=x.created_at.isoformat()) for x in db.scalars(select(AIDocument).where(AIDocument.user_id==user.id).order_by(AIDocument.created_at.desc()))]

@router.post("/documents/{doc_id}/approve")
def approve_document(doc_id:int,db:Session=Depends(get_db),user:User=Depends(admin)):
    doc=db.scalar(select(AIDocument).where(AIDocument.id==doc_id,AIDocument.user_id==user.id))
    if not doc: raise HTTPException(404,"Document not found")
    doc.status="approved";audit(db,user,"document.approved","document",doc.id);db.commit()
    return {"approved":True,"note":"Approved document is eligible for indexing."}

@router.post("/training/start")
def start_training(db:Session=Depends(get_db),user:User=Depends(admin)):
    docs=db.scalar(select(func.count(AIDocument.id)).where(AIDocument.user_id==user.id,AIDocument.status=="approved")) or 0
    knowledge=db.scalar(select(func.count(AIKnowledge.id)).where(AIKnowledge.user_id==user.id,AIKnowledge.approval_status=="approved")) or 0
    if not docs and not knowledge: raise HTTPException(400,"Approve at least one document or knowledge entry first")
    job=AITrainingJob(user_id=user.id,status="queued",stage="waiting_for_worker",progress=0,logs="Queued for the separate worker. Model weights have not been changed.")
    db.add(job);db.flush();audit(db,user,"indexing.queued","training_job",job.id);db.commit()
    return {"job_id":job.id,"status":"queued","worker_required":True,"message":"Start the AI worker process on a persistent host."}

@router.get("/training/jobs")
def jobs(db:Session=Depends(get_db),user:User=Depends(admin)):
    return [dict(id=x.id,status=x.status,stage=x.stage,progress=x.progress,logs=x.logs,error=x.error,created_at=x.created_at.isoformat()) for x in db.scalars(select(AITrainingJob).where(AITrainingJob.user_id==user.id).order_by(AITrainingJob.created_at.desc()).limit(100))]

@router.post("/training/jobs/{job_id}/cancel")
def cancel(job_id:int,db:Session=Depends(get_db),user:User=Depends(admin)):
    job=db.scalar(select(AITrainingJob).where(AITrainingJob.id==job_id,AITrainingJob.user_id==user.id))
    if not job: raise HTTPException(404,"Job not found")
    if job.status in {"completed","failed","cancelled"}: raise HTTPException(409,"Job already finished")
    job.status="cancelled";job.stage="cancelled";db.commit()
    return {"cancelled":True}

@router.get("/models")
def models(db:Session=Depends(get_db),user:User=Depends(admin)):
    return [dict(id=x.id,version=x.version,model_type=x.model_type,status=x.status,metrics=json.loads(x.metrics_json or "{}"),created_at=x.created_at.isoformat()) for x in db.scalars(select(AIModelVersion).where(AIModelVersion.user_id==user.id).order_by(AIModelVersion.id.desc()))]

@router.post("/chat")
def chat(payload:ChatIn,db:Session=Depends(get_db),user:User=Depends(admin)):
    started=time.perf_counter()
    chunks=list(db.scalars(select(AIChunk).where(AIChunk.user_id==user.id).limit(5000)));approved=[]
    for c in chunks:
        if c.knowledge_id:
            k=db.get(AIKnowledge,c.knowledge_id)
            if not k or k.approval_status!="approved": continue
        if c.document_id:
            d=db.get(AIDocument,c.document_id)
            if not d or d.status!="approved": continue
        approved.append({"id":c.id,"text":c.text,"embedding_json":c.embedding_json,"source":"Knowledge #"+str(c.knowledge_id) if c.knowledge_id else "Document #"+str(c.document_id)})
    hits=retrieve(payload.question,approved)
    if hits:
        answer="Based only on approved SUJA knowledge:\n\n"+"\n\n".join(h["text"][:1200] for h in hits[:3])+"\n\nFor important decisions, verify details with an authorized insurance professional."
    else:
        answer="I could not find this information in the administrator-approved SUJA knowledge base. Please add and approve a reliable source, or contact an authorized insurance professional. I cannot determine eligibility or guarantee claim approval."
    latency=(time.perf_counter()-started)*1000
    sources=[{"source":h["source"],"chunk_id":h["id"],"score":h["score"]} for h in hits]
    conv=AIConversation(user_id=user.id,question=payload.question,answer=answer,sources_json=json.dumps(sources),latency_ms=latency)
    db.add(conv);db.commit();db.refresh(conv)
    return {"conversation_id":conv.id,"answer":answer,"sources":sources,"latency_ms":round(latency,2),"mode":"retrieval-grounded"}

@router.post("/feedback")
def feedback(payload:FeedbackIn,db:Session=Depends(get_db),user:User=Depends(admin)):
    conv=db.scalar(select(AIConversation).where(AIConversation.id==payload.conversation_id,AIConversation.user_id==user.id))
    if not conv: raise HTTPException(404,"Conversation not found")
    db.add(AIFeedback(user_id=user.id,conversation_id=conv.id,rating=payload.rating,comment=payload.comment));db.commit()
    return {"saved":True}
