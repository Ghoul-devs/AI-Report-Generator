import json
import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from google.genai import errors as genai_errors

from app.services.gemini import generate_text
from app.agents.pipeline import run_pipeline
from app.api.documents import router as documents_router
from app.services.web_research import search_web
from app.api.reports import router as reports_router, feedback_router
from app.api.auth import router as auth_router
from app.database.database import connect, init_db
from app.agents.pipeline import AGENTS
from app.services.auth import require_user

app = FastAPI(title="AI Research Report Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(reports_router)
app.include_router(feedback_router)
app.include_router(auth_router)
init_db()
generation_runs = {}


def gemini_http_exception(error: genai_errors.APIError) -> HTTPException:
    """Expose Gemini errors with their real HTTP status instead of a generic 500."""
    if error.code == 429:
        detail = (
            "Gemini API quota has been reached. Wait for the quota to reset or "
            "enable billing/increase the API quota, then try again."
        )
    else:
        detail = error.message or "Gemini could not generate a response."

    return HTTPException(status_code=error.code or 502, detail=detail)


class PromptRequest(BaseModel):
    prompt: str


class ReportRequest(BaseModel):
    topic: str
    report_type: str = "General Information Report"

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Topic cannot be empty.")
        return value


@app.get("/")
def home():
    return {
        "message": "AI Research Report Generator API is running!"
    }


@app.post("/generate", dependencies=[Depends(require_user)])
def generate(request: PromptRequest):
    try:
        result = generate_text(request.prompt)
        return {"response": result}

    except genai_errors.APIError as e:
        raise gemini_http_exception(e)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post("/generate-report", dependencies=[Depends(require_user)])
def generate_report(request: ReportRequest, x_run_id: str | None = Header(default=None)):
    run_id = x_run_id or str(uuid.uuid4())
    if len(generation_runs) >= 100:
        generation_runs.pop(next(iter(generation_runs)))
    generation_runs[run_id] = {"run_id": run_id, "status": "running", "agents": [{"agent_name": name, "status": "pending"} for name in AGENTS]}

    def update_stage(name, status):
        for stage in generation_runs[run_id]["agents"]:
            if stage["agent_name"] == name:
                stage["status"] = status

    try:
        result = run_pipeline(
            request.topic,
            request.report_type,
            on_stage=update_stage,
        )
        report_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        result.update({"id": report_id, "status": "completed", "created_at": now, "updated_at": now})
        with connect() as db:
            db.execute(
                "INSERT INTO reports(id,topic,report_type,status,content,payload,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (report_id, result["topic"], result["report_type"], "completed", result["report"], json.dumps(result), now, now),
            )
            for source in result.get("sources", []):
                db.execute(
                    "INSERT INTO sources(id,report_id,source_type,title,url,document_id,page,content,score) VALUES(?,?,?,?,?,?,?,?,?)",
                    (f"{report_id}:{source['id']}", report_id, source.get("source_type", "web"), source.get("title", ""), source.get("url"), source.get("document_id"), source.get("page"), source.get("content", ""), source.get("score")),
                )
            for agent in result.get("agent_runs", []):
                db.execute(
                    "INSERT INTO agent_runs(report_id,agent_name,status,started_at,completed_at,output_summary) VALUES(?,?,?,?,?,?)",
                    (report_id, agent["agent_name"], agent["status"], agent.get("started_at"), agent.get("completed_at"), agent.get("output_summary", "")),
                )
        generation_runs[run_id]["status"] = "completed"
        result["run_id"] = run_id
        return result

    except genai_errors.APIError as e:
        print("GEMINI ERROR:", repr(e))
        generation_runs[run_id]["status"] = "failed"
        raise gemini_http_exception(e)
    except Exception as e:
        print("PIPELINE ERROR:", repr(e))
        generation_runs[run_id]["status"] = "failed"

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.get("/generate-report/status/{run_id}", dependencies=[Depends(require_user)])
def get_generation_status(run_id: str):
    status = generation_runs.get(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Research run not found.")
    return status


@app.get("/web-search", dependencies=[Depends(require_user)])
def web_search(query: str):
    return {
        "query": query,
        "results": search_web(query)
    }
