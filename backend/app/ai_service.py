import json, re
from pathlib import Path
from functools import lru_cache

def extract_text(path: str, suffix: str) -> str:
    p=Path(path)
    if suffix==".txt": return p.read_text(encoding="utf-8",errors="replace")
    if suffix==".pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(p)).pages)
    if suffix==".docx":
        from docx import Document
        return "\n".join(x.text for x in Document(str(p)).paragraphs)
    if suffix==".csv":
        import csv
        with p.open(encoding="utf-8-sig",newline="") as f: return "\n".join(" | ".join(str(v or "") for v in row) for row in csv.reader(f))
    if suffix in {".xlsx",".xlsm"}:
        from openpyxl import load_workbook
        wb=load_workbook(p,read_only=True,data_only=True)
        try:
            lines=[]
            for ws in wb.worksheets:
                lines.append("Sheet: "+ws.title)
                for row in ws.iter_rows(values_only=True):
                    vals=[str(v) for v in row if v is not None]
                    if vals: lines.append(" | ".join(vals))
            return "\n".join(lines)
        finally: wb.close()
    raise ValueError("Unsupported document type")

def clean_text(text: str) -> str:
    return re.sub(r"[ \t]+"," ",re.sub(r"\n{3,}","\n\n",text.replace("\x00"," "))).strip()

def chunk_text(text: str):
    words=clean_text(text).split()
    chunks=[]
    start=0
    while start<len(words):
        end=min(start+160,len(words))
        part=" ".join(words[start:end])
        if len(part)>=40: chunks.append(part[:1800])
        if end==len(words): break
        start=max(start+1,end-20)
    return chunks

@lru_cache(maxsize=1)
def _encoder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

def embed(texts:list[str])->list[list[float]]:
    return _encoder().encode(texts,normalize_embeddings=True,show_progress_bar=False).tolist()

def retrieve(query:str,rows:list[dict],limit:int=5):
    if not rows: return []
    try:
        q=embed([query])[0]
        scored=[]
        for row in rows:
            v=json.loads(row["embedding_json"]) if row.get("embedding_json") else None
            if v: scored.append((sum(a*b for a,b in zip(q,v)),row))
        scored.sort(key=lambda x:x[0],reverse=True)
        if scored and scored[0][0]>0.12: return [{"score":round(s,4),**r} for s,r in scored[:limit]]
    except (ImportError,OSError,RuntimeError,ValueError): pass
    terms=set(re.findall(r"\w+",query.lower()))
    scored=[]
    for row in rows:
        body=row.get("text","").lower()
        overlap=len(terms & set(re.findall(r"\w+",body)))
        if overlap: scored.append((overlap/max(1,len(terms)),row))
    scored.sort(key=lambda x:x[0],reverse=True)
    return [{"score":round(s,4),**r} for s,r in scored[:limit]]
