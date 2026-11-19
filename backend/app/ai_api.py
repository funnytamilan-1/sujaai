import json, time, uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from app.config import settings
from app.database import get_db
from app.models import User
from app.security import get_current_user
from app.ai_models import AIDocument, AIKnowledge, AIChunk, AITrainingJob, AIModelVersion, AIConversation, AIChatMessage, AIFeedback, AIAuditLog
from app.ai_service import extract_text, clean_text, chunk_text, retrieve

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
    conversation_id:int|None=None
    model:str="auto"
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
    folder=settings.upload_path.parent/"sujaai-private-ai"/str(user.id);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(uuid.uuid4().hex+suffix);path.write_bytes(content)
    doc=AIDocument(user_id=user.id,filename=name,stored_path=str(path),content_type=file.content_type or "application/octet-stream");db.add(doc);db.flush()
    try:
        extracted=clean_text(extract_text(str(path),suffix))
        if not extracted: raise ValueError("No readable text found")
        doc.extracted_chars=len(extracted);doc.status="extracted"
        for part in chunk_text(extracted[:500000]):
            db.add(AIChunk(user_id=user.id,document_id=doc.id,text=part))
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

def build_answer(db:Session,user:User,question:str,documents_only:bool=False):
    chunks=list(db.scalars(select(AIChunk).where(AIChunk.user_id==user.id).limit(5000)));approved=[]
    for item in chunks:
        if item.knowledge_id:
            k=db.get(AIKnowledge,item.knowledge_id)
            if not k or k.approval_status!="approved": continue
        if item.document_id:
            d=db.get(AIDocument,item.document_id)
            if not d or d.status!="approved": continue
        if documents_only and not item.document_id: continue
        approved.append({"id":item.id,"text":item.text,"embedding_json":item.embedding_json,"source":"Knowledge #"+str(item.knowledge_id) if item.knowledge_id else "Document #"+str(item.document_id)})
    hits=retrieve(question,approved)
    if hits:
        answer="Based only on approved SUJA insurance information:\n\n"+"\n\n".join(h["text"][:1200] for h in hits[:3])+"\n\nThis is general information, not a claim or eligibility decision. Verify important decisions with an authorized insurance professional."
    else:
        answer="I could not find this information in the administrator-approved SUJA knowledge base. Please add and approve a reliable source, or contact an authorized insurance professional. I cannot determine eligibility or guarantee claim approval."
    return answer,[{"source":h["source"],"chunk_id":h["id"],"score":h["score"]} for h in hits]

def owned_conversation(db,user,conversation_id):
    conv=db.scalar(select(AIConversation).where(AIConversation.id==conversation_id,AIConversation.user_id==user.id))
    if not conv: raise HTTPException(404,"Conversation not found")
    return conv

@router.get("/conversations")
def list_conversations(q:str="",archived:bool=False,limit:int=100,db:Session=Depends(get_db),user:User=Depends(admin)):
    rows=list(db.scalars(select(AIConversation).where(AIConversation.user_id==user.id,AIConversation.archived==archived).order_by(AIConversation.pinned.desc(),AIConversation.updated_at.desc()).limit(max(1,min(limit,200)))))
    if q.strip(): rows=[x for x in rows if q.strip().lower() in (x.title or "").lower() or q.strip().lower() in (x.question or "").lower()]
    return [dict(id=x.id,title=x.title,pinned=x.pinned,archived=x.archived,updated_at=x.updated_at.isoformat()) for x in rows]

@router.post("/conversations")
def create_conversation(db:Session=Depends(get_db),user:User=Depends(admin)):
    conv=AIConversation(user_id=user.id,title="New chat",question="",answer="",sources_json="[]")
    db.add(conv);db.commit();db.refresh(conv)
    return {"id":conv.id,"title":conv.title,"pinned":False,"archived":False}

@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id:int,db:Session=Depends(get_db),user:User=Depends(admin)):
    conv=owned_conversation(db,user,conversation_id)
    rows=list(db.scalars(select(AIChatMessage).where(AIChatMessage.conversation_id==conv.id,AIChatMessage.user_id==user.id).order_by(AIChatMessage.id.asc()).limit(500)))
    if not rows and conv.question:
        return {"id":conv.id,"title":conv.title,"pinned":conv.pinned,"archived":conv.archived,"messages":[{"id":conv.id*2,"role":"user","content":conv.question,"sources":[]},{"id":conv.id*2+1,"role":"assistant","content":conv.answer,"sources":json.loads(conv.sources_json or "[]")}]}
    return {"id":conv.id,"title":conv.title,"pinned":conv.pinned,"archived":conv.archived,"messages":[dict(id=m.id,role=m.role,content=m.content,sources=json.loads(m.sources_json or "[]")) for m in rows]}

@router.patch("/conversations/{conversation_id}")
def update_conversation(conversation_id:int,payload:dict,db:Session=Depends(get_db),user:User=Depends(admin)):
    conv=owned_conversation(db,user,conversation_id)
    if "title" in payload: conv.title=str(payload["title"]).strip()[:240] or "New chat"
    if "pinned" in payload: conv.pinned=bool(payload["pinned"])
    if "archived" in payload: conv.archived=bool(payload["archived"])
    db.commit()
    return {"updated":True}

@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id:int,db:Session=Depends(get_db),user:User=Depends(admin)):
    conv=owned_conversation(db,user,conversation_id)
    db.query(AIChatMessage).filter(AIChatMessage.conversation_id==conv.id,AIChatMessage.user_id==user.id).delete()
    db.delete(conv);db.commit()
    return {"deleted":True}

@router.post("/chat")
def chat(payload:ChatIn,db:Session=Depends(get_db),user:User=Depends(admin)):
    started=time.perf_counter()
    conv=owned_conversation(db,user,payload.conversation_id) if payload.conversation_id else AIConversation(user_id=user.id,title=payload.question[:60],question="",answer="",sources_json="[]")
    if not payload.conversation_id: db.add(conv);db.flush()
    answer,sources=build_answer(db,user,payload.question,payload.model=="documents")
    db.add(AIChatMessage(conversation_id=conv.id,user_id=user.id,role="user",content=payload.question))
    db.add(AIChatMessage(conversation_id=conv.id,user_id=user.id,role="assistant",content=answer,sources_json=json.dumps(sources)))
    if not conv.question: conv.question=payload.question
    conv.answer=answer;conv.sources_json=json.dumps(sources)
    if conv.title=="New chat": conv.title=payload.question[:60]
    conv.updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    latency=(time.perf_counter()-started)*1000;conv.latency_ms=latency
    db.commit();db.refresh(conv)
    return {"conversation_id":conv.id,"answer":answer,"sources":sources,"latency_ms":round(latency,2),"mode":"retrieval-grounded"}

@router.post("/chat/stream")
def chat_stream(payload:ChatIn,request:Request,db:Session=Depends(get_db),user:User=Depends(admin)):
    result=chat(payload,db,user)
    def events():
        yield "event: meta\ndata: "+json.dumps({"conversation_id":result["conversation_id"],"sources":result["sources"],"mode":result["mode"]})+"\n\n"
        for offset in range(0,len(result["answer"]),48):
            yield "event: token\ndata: "+json.dumps({"text":result["answer"][offset:offset+48]},ensure_ascii=False)+"\n\n"
        yield "event: done\ndata: {}\n\n"
    return StreamingResponse(events(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@router.post("/chat/regenerate")
def regenerate(payload:dict,db:Session=Depends(get_db),user:User=Depends(admin)):
    conv=owned_conversation(db,user,int(payload.get("conversation_id",0)))
    last=db.scalar(select(AIChatMessage).where(AIChatMessage.conversation_id==conv.id,AIChatMessage.role=="user").order_by(AIChatMessage.id.desc()))
    if not last: raise HTTPException(400,"No user message to regenerate")
    answer,sources=build_answer(db,user,last.content)
    db.add(AIChatMessage(conversation_id=conv.id,user_id=user.id,role="assistant",content=answer,sources_json=json.dumps(sources)))
    conv.answer=answer;conv.sources_json=json.dumps(sources);db.commit()
    return {"conversation_id":conv.id,"answer":answer,"sources":sources}

@router.get("/models")
def chat_models(db:Session=Depends(get_db),user:User=Depends(admin)):
    active=db.scalar(select(AIModelVersion).where(AIModelVersion.user_id==user.id,AIModelVersion.status=="active").order_by(AIModelVersion.id.desc()))
    version=active.version if active else "lexical-fallback"
    return [
        {"id":"auto","name":"SUJA AI Auto","description":"Approved insurance knowledge retrieval.","available":True,"version":version},
        {"id":"knowledge","name":"SUJA Insurance Knowledge AI","description":"Approved insurance FAQs and knowledge entries.","available":True,"version":version},
        {"id":"documents","name":"SUJA Document Assistant","description":"Approved uploaded documents only.","available":True,"version":version},
        {"id":"neural","name":"SUJA Neural Model","description":"Experimental classifier; no conversational checkpoint is deployed.","available":False,"version":"not-deployed"}
    ]

@router.post("/feedback")
def feedback(payload:FeedbackIn,db:Session=Depends(get_db),user:User=Depends(admin)):
    conv=db.scalar(select(AIConversation).where(AIConversation.id==payload.conversation_id,AIConversation.user_id==user.id))
    if not conv: raise HTTPException(404,"Conversation not found")
    db.add(AIFeedback(user_id=user.id,conversation_id=conv.id,rating=payload.rating,comment=payload.comment));db.commit()
    return {"saved":True}
