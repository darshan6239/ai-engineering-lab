import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("MY_EMAIL", "me@example.com")
os.environ.setdefault("GROQ_API_KEY", "test-key")

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeAgents, FakeGmailTools


@pytest.fixture
def client(monkeypatch, tmp_path):
    import dataclasses
    import src.nodes as nodes_module
    from src import db as db_module

    test_settings = dataclasses.replace(db_module.settings, db_path=str(tmp_path / "dash.db"))
    monkeypatch.setattr(db_module, "settings", test_settings)
    db_module.init_db()

    fake_gmail = FakeGmailTools(incoming_emails=[{
        "id": "d1", "threadId": "t1", "messageId": "<d1@x>", "references": "",
        "sender": "buyer@example.com", "subject": "Pricing", "body": "how much?",
    }])
    fake_agents = FakeAgents(category="product_enquiry", sendable=True)
    monkeypatch.setattr(nodes_module, "Agents", lambda: fake_agents)
    monkeypatch.setattr(nodes_module, "GmailToolsClass", lambda: fake_gmail)

    import dashboard.server as server_module
    monkeypatch.setattr(server_module, "db", db_module)
    monkeypatch.setattr(server_module.GmailToolsClass, "__init__", lambda self: setattr(self, "_fake", fake_gmail))
    # Patch the dashboard's own GmailToolsClass reference used for manual send
    monkeypatch.setattr(server_module, "GmailToolsClass", lambda: fake_gmail)
    server_module.runnable = server_module.Workflow.__new__(server_module.Workflow)
    from src.graph import Workflow as RealWorkflow
    server_module.runnable = RealWorkflow().app

    return TestClient(server_module.app), fake_gmail


def test_health_endpoint_reports_config(client):
    c, _ = client
    r = c.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert "ollama_llm_model" in body
    assert "groq_model" in body


def test_stats_endpoint_starts_empty(client):
    c, _ = client
    r = c.get("/api/stats")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_run_then_approval_queue_and_send_flow(client):
    c, gmail = client
    r = c.post("/api/run")
    assert r.status_code == 200

    # background thread — poll briefly for it to land (this project's tests
    # run fully synchronously otherwise, so give the daemon thread a moment)
    import time
    for _ in range(50):
        status = c.get("/api/run/status").json()
        if not status["running"]:
            break
        time.sleep(0.05)

    emails = c.get("/api/emails?status=draft_created").json()
    assert len(emails) == 1
    email_id = emails[0]["id"]

    send_resp = c.post(f"/api/emails/{email_id}/send")
    assert send_resp.status_code == 200
    assert len(gmail.sent) == 1

    final = c.get(f"/api/emails/{email_id}").json()
    assert final["status"] == "sent"
    assert len(final["events"]) > 0


def test_reject_unknown_email_404s(client):
    c, _ = client
    r = c.post("/api/emails/does-not-exist/reject")
    assert r.status_code == 404
