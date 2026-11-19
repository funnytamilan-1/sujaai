import json, time
from sqlalchemy import select
from app.database import SessionLocal
from app.ai_models import AITrainingJob, AIChunk, AIDocument, AIKnowledge, AIModelVersion
from app.ai_service import embed

def run_one(db,job):
    job.status="running";job.stage="loading_approved_data";job.progress=10;job.logs="Loading administrator-approved content.";db.commit()
    rows=list(db.scalars(select(AIChunk).where(AIChunk.user_id==job.user_id)))
    approved=[]
    for row in rows:
        if row.knowledge_id:
            item=db.get(AIKnowledge,row.knowledge_id)
            if not item or item.approval_status!="approved": continue
        if row.document_id:
            doc=db.get(AIDocument,row.document_id)
            if not doc or doc.status!="approved": continue
        approved.append(row)
    if not approved: raise RuntimeError("No approved content found.")
    job.stage="generating_embeddings";job.progress=25;job.logs+="\nGenerating multilingual sentence embeddings.";db.commit()
    vectors=embed([r.text for r in approved])
    for row,vector in zip(approved,vectors): row.embedding_json=json.dumps(vector)
    job.stage="saving_retrieval_index";job.progress=85;job.logs+="\nSaved embeddings for "+str(len(approved))+" chunks.";db.commit()
    latest=db.scalar(select(AIModelVersion).where(AIModelVersion.user_id==job.user_id).order_by(AIModelVersion.id.desc()))
    version="rag-index-"+str((latest.id+1) if latest else 1)
    model=AIModelVersion(user_id=job.user_id,version=version,model_type="multilingual-embedding-index",status="active",metrics_json=json.dumps({"indexed_chunks":len(approved),"embedding_model":"paraphrase-multilingual-MiniLM-L12-v2","trained_weights":False}))
    db.add(model);db.flush()
    for old in db.scalars(select(AIModelVersion).where(AIModelVersion.user_id==job.user_id,AIModelVersion.id!=model.id,AIModelVersion.status=="active")): old.status="archived"
    job.status="completed";job.stage="completed";job.progress=100
    job.logs+="\nCompleted: semantic retrieval index updated. No language-model weights were fine-tuned."
    db.commit()

def main():
    print("SUJA AI worker started; polling queued jobs.")
    while True:
        db=SessionLocal()
        try:
            job=db.scalar(select(AITrainingJob).where(AITrainingJob.status=="queued").order_by(AITrainingJob.id).with_for_update(skip_locked=True).limit(1))
            if job:
                try: run_one(db,job)
                except Exception as exc:
                    job.status="failed";job.stage="failed";job.error=str(exc)[:2000];job.logs+="\nWorker failed.";db.commit()
            else:
                time.sleep(4)
        finally: db.close()

if __name__=="__main__": main()
