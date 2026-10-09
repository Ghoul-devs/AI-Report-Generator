import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.database.database import connect
from app.services.auth import require_user
from app.services.email import send_email
from app.services.report_export import to_markdown, to_docx, to_pdf

router = APIRouter(prefix="/reports", tags=["Reports"], dependencies=[Depends(require_user)])
feedback_router = APIRouter(prefix="/feedback", tags=["Feedback"], dependencies=[Depends(require_user)])


class FeedbackRequest(BaseModel):
    report_id: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    comments: str = Field(default="", max_length=10_000)


@router.get("")
def list_reports():
    with connect() as db:
        rows = db.execute("SELECT id,topic,report_type,status,created_at,updated_at FROM reports ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@router.get("/{report_id}")
def read_report(report_id: str):
    with connect() as db:
        row = db.execute("SELECT payload FROM reports WHERE id=?", (report_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return json.loads(row["payload"])


@router.put("/{report_id}")
def update_report(report_id: str, body: dict):
    with connect() as db:
        row = db.execute("SELECT payload FROM reports WHERE id=?", (report_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Report not found.")
        current = json.loads(row["payload"])
        current["report"] = str(body.get("report", ""))
        now = datetime.now(timezone.utc).isoformat()
        db.execute("UPDATE reports SET content=?,payload=?,updated_at=? WHERE id=?", (current["report"], json.dumps(current), now, report_id))
    return current


@router.delete("/{report_id}")
def delete_report(report_id: str):
    with connect() as db:
        cursor = db.execute("DELETE FROM reports WHERE id=?", (report_id,))
    if not cursor.rowcount:
        raise HTTPException(status_code=404, detail="Report not found.")
    return {"deleted": True, "id": report_id}


@router.get("/{report_id}/export/{format}")
def export_report(report_id: str, format: str):
    with connect() as db:
        row = db.execute("SELECT payload FROM reports WHERE id=?", (report_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    payload = json.loads(row["payload"])
    if format == "md":
        data, media, ext = to_markdown(payload).encode(), "text/markdown; charset=utf-8", "md"
    elif format == "docx":
        data, media, ext = to_docx(payload), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    elif format == "pdf":
        data, media, ext = to_pdf(payload), "application/pdf", "pdf"
    else:
        raise HTTPException(status_code=400, detail="Supported exports: md, docx, pdf.")
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="report-{report_id}.{ext}"'})


@feedback_router.post("")
def create_feedback(body: FeedbackRequest):
    rating = body.rating
    created_at = datetime.now(timezone.utc).isoformat()
    comments = body.comments.strip()
    report_id = body.report_id
    send_email(
        "New Atlas Research feedback",
        f"Rating: {rating if rating is not None else 'Not provided'} / 5\n"
        f"Report ID: {report_id or 'Not provided'}\n"
        f"Submitted at: {created_at}\n\n"
        f"Comments:\n{comments or 'No comments provided.'}",
    )
    with connect() as db:
        db.execute("INSERT INTO feedback(report_id,rating,comments,created_at) VALUES(?,?,?,?)", (report_id, rating, comments, created_at))
    return {"saved": True, "created_at": created_at}
