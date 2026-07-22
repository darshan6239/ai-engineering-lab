"""
Serves:
  - GET  /                         the dashboard UI
  - GET  /api/health                startup/config check (Gmail, Groq, Ollama)
  - GET  /api/stats                 counts by status/category
  - GET  /api/emails?status=...      list processed emails
  - GET  /api/emails/{id}            single email + its full event log
  - POST /api/emails/{id}/send       actually send a drafted reply via Gmail
  - POST /api/emails/{id}/reject     discard a draft, mark rejected
  - POST /api/run                   trigger a workflow pass over the inbox now
  - GET  /api/run/status             is a run currently in progress
  - /workflow/*                     original Langserve routes (unchanged)
"""
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from langserve import add_routes

from src import db
from src.config import settings, validate_settings, check_ollama_reachable
from src.graph import Workflow
from src.tools.GmailTools import GmailToolsClass

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Email Automation Ops",
    version="2.0",
    description="LangGraph backend + dashboard for the AI email automation workflow",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"], expose_headers=["*"],
)

db.init_db()

_run_lock = threading.Lock()
_run_state = {"running": False, "started_at": None, "finished_at": None, "error": None}


def _get_runnable():
    return Workflow().app


runnable = _get_runnable()
add_routes(app, runnable, path="/workflow")


def _run_workflow_background():
    with _run_lock:
        if _run_state["running"]:
            return
        _run_state.update(running=True, started_at=time.time(), finished_at=None, error=None)

    try:
        initial_state = {
            "emails": [], "current_email": {
                "id": "", "threadId": "", "messageId": "", "references": "",
                "sender": "", "subject": "", "body": ""
            },
            "email_category": "", "generated_email": "", "rag_queries": [],
            "retrieved_documents": "", "writer_messages": [], "sendable": False,
            "trials": 0, "_error": False,
        }
        for _ in runnable.stream(initial_state, {"recursion_limit": 100}):
            pass
    except Exception as e:
        _run_state["error"] = str(e)
    finally:
        _run_state.update(running=False, finished_at=time.time())


@app.get("/api/health")
def health():
    problems = validate_settings(require_gmail=True)
    ollama_ok, ollama_msg = check_ollama_reachable()
    return {
        "ok": not problems and ollama_ok,
        "config_problems": problems,
        "ollama": {"ok": ollama_ok, "message": ollama_msg},
        "groq_model": settings.groq_model,
        "ollama_llm_model": settings.ollama_llm_model,
        "ollama_embed_model": settings.ollama_embed_model,
    }


@app.get("/api/stats")
def stats():
    return db.get_stats()


@app.get("/api/emails")
def list_emails(status: str | None = None, limit: int = 100):
    return db.get_emails(status=status, limit=limit)


@app.get("/api/emails/{email_id}")
def get_email(email_id: str):
    email = db.get_email(email_id)
    if not email:
        raise HTTPException(404, "Email not found")
    email["events"] = db.get_events(email_id=email_id)
    return email


@app.post("/api/emails/{email_id}/send")
def send_email(email_id: str):
    email = db.get_email(email_id)
    if not email:
        raise HTTPException(404, "Email not found")
    if email["status"] != "draft_created":
        raise HTTPException(400, f"Email is '{email['status']}', not ready to send")
    if not email.get("generated_email"):
        raise HTTPException(400, "No generated draft to send")

    try:
        gmail = GmailToolsClass()
        fake_email = type("E", (), {
            "sender": email["sender"], "subject": email["subject"],
            "threadId": email["thread_id"], "messageId": None, "references": "",
        })()
        gmail.send_reply(fake_email, email["generated_email"])
        db.upsert_email(email_id, status="sent")
        db.log_event(email_id, "dashboard", "Sent manually from dashboard")
    except Exception as e:
        db.upsert_email(email_id, status="failed", error=str(e))
        raise HTTPException(500, f"Failed to send: {e}")

    return {"ok": True}


@app.post("/api/emails/{email_id}/reject")
def reject_email(email_id: str):
    email = db.get_email(email_id)
    if not email:
        raise HTTPException(404, "Email not found")
    db.upsert_email(email_id, status="rejected")
    db.log_event(email_id, "dashboard", "Rejected manually from dashboard")
    return {"ok": True}


@app.post("/api/run")
def trigger_run():
    if _run_state["running"]:
        raise HTTPException(409, "A run is already in progress")
    thread = threading.Thread(target=_run_workflow_background, daemon=True)
    thread.start()
    return {"ok": True, "started": True}


@app.get("/api/run/status")
def run_status():
    return _run_state


# Static dashboard last, so /api/* above always takes priority
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR)), name="assets")


@app.get("/")
def dashboard_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
