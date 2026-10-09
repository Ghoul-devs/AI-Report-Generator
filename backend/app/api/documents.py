import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException

from app.rag.loader import load_pdf_pages
from app.rag.chunker import chunk_text
from app.rag.retriever import vector_store
from app.rag.reranker import rerank
from app.rag.embeddings import get_embedding_mode
from app.database.database import connect
from app.services.auth import require_user

router = APIRouter(prefix="/documents", tags=["Documents"], dependencies=[Depends(require_user)])
UPLOAD_DIR = Path(__file__).resolve().parents[2].parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    filename = Path(file.filename or "document.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF files must be 20 MB or smaller.")
    document_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{document_id}.pdf"
    file_path.write_bytes(content)
    try:
        pages = load_pdf_pages(str(file_path))
        if not pages:
            raise HTTPException(status_code=400, detail="Could not extract text from PDF.")
        chunks = []
        for page in pages:
            for text in chunk_text(page["text"]):
                chunks.append({
                    "document_id": document_id,
                    "filename": filename,
                    "page": page["page"],
                    "chunk_id": f"{document_id}-{len(chunks) + 1}",
                    "text": text,
                })
        vector_store.add_documents(chunks)
    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=503,
            detail=f"PDF processing could not finish. Check the embedding model availability and retry. ({type(exc).__name__})",
        ) from exc

    uploaded_at = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        db.execute(
            "INSERT INTO documents(id,filename,path,uploaded_at,status) VALUES(?,?,?,?,?)",
            (document_id, filename, str(file_path), uploaded_at, "ready"),
        )
    embedding_mode = get_embedding_mode()
    return {
        "document_id": document_id,
        "filename": filename,
        "status": "ready",
        "chunks_created": len(chunks),
        "embedding_mode": embedding_mode,
        "message": "Document processed successfully." if embedding_mode == "sentence_transformer" else "Indexed with offline lexical fallback; semantic model was unavailable.",
    }


@router.get("")
def list_documents():
    with connect() as db:
        rows = db.execute("SELECT id,filename,uploaded_at,status FROM documents ORDER BY uploaded_at DESC").fetchall()
    return [dict(row) for row in rows]


@router.get("/search")
def search_document(query: str, top_k: int = 5):
    try:
        candidates = vector_store.hybrid_search(query, top_k=20)
        results = rerank(query, candidates, top_k=top_k)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Document search is temporarily unavailable.") from exc
    return {"query": query, "results": results, "retrieval": "hybrid (FAISS + BM25) with cross-encoder reranking when available"}
