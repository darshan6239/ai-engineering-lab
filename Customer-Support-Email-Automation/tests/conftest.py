import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Make sure "src" is importable when running `pytest` from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("MY_EMAIL", "me@example.com")
os.environ.setdefault("GROQ_API_KEY", "test-key")

from src import db as db_module  # noqa: E402
from src.state import Email  # noqa: E402


def make_email(**overrides):
    base = dict(
        id="msg-1", threadId="thread-1", messageId="<msg-1@mail.gmail.com>",
        references="", sender="customer@example.com", subject="Question about pricing",
        body="Hi, what are your pricing options?",
    )
    base.update(overrides)
    return Email(**base)


class FakeAgents:
    """Stand-in for src.agents.Agents — no network calls, fully scriptable
    canned responses so tests are deterministic and instant."""

    def __init__(self, *, category="product_enquiry", rag_queries=None,
                 rag_answer="We offer three pricing tiers.",
                 draft_email="Dear Customer,\n\nThanks for reaching out...\n\nBest regards,\nThe Agentia Team",
                 sendable=True, feedback="Looks good.",
                 raise_on=None):
        self._category = category
        self._rag_queries = rag_queries or ["What are the pricing options?"]
        self._rag_answer = rag_answer
        self._draft_email = draft_email
        self._sendable = sendable
        self._feedback = feedback
        self._raise_on = raise_on or set()
        self.calls = []

    def _maybe_raise(self, name):
        if name in self._raise_on:
            raise RuntimeError(f"simulated failure in {name}")

    def categorize_email(self, inputs):
        self.calls.append(("categorize_email", inputs))
        self._maybe_raise("categorize_email")
        return SimpleNamespace(category=SimpleNamespace(value=self._category))

    def design_rag_queries(self, inputs):
        self.calls.append(("design_rag_queries", inputs))
        self._maybe_raise("design_rag_queries")
        return SimpleNamespace(queries=self._rag_queries)

    def generate_rag_answer(self, query):
        self.calls.append(("generate_rag_answer", query))
        self._maybe_raise("generate_rag_answer")
        return self._rag_answer

    def email_writer(self, inputs):
        self.calls.append(("email_writer", inputs))
        self._maybe_raise("email_writer")
        return SimpleNamespace(email=self._draft_email)

    def email_proofreader(self, inputs):
        self.calls.append(("email_proofreader", inputs))
        self._maybe_raise("email_proofreader")
        return SimpleNamespace(send=self._sendable, feedback=self._feedback)


class FakeGmailTools:
    """Stand-in for src.tools.GmailTools.GmailToolsClass."""

    def __init__(self, incoming_emails=None, raise_on_fetch=False,
                 raise_on_draft=False, raise_on_send=False):
        self._incoming = incoming_emails if incoming_emails is not None else []
        self.raise_on_fetch = raise_on_fetch
        self.raise_on_draft = raise_on_draft
        self.raise_on_send = raise_on_send
        self.drafts_created = []
        self.sent = []

    def fetch_unanswered_emails(self, max_results=50):
        if self.raise_on_fetch:
            raise ConnectionError("simulated Gmail API outage")
        return self._incoming

    def create_draft_reply(self, email, reply_text):
        if self.raise_on_draft:
            raise RuntimeError("simulated draft creation failure")
        self.drafts_created.append((email, reply_text))
        return {"id": "draft-1"}

    def send_reply(self, email, reply_text):
        if self.raise_on_send:
            raise RuntimeError("simulated send failure")
        self.sent.append((email, reply_text))
        return {"id": "sent-1"}


@pytest.fixture
def clean_db(tmp_path, monkeypatch):
    """Point the DB at a throwaway sqlite file for this test only.
    Settings is a frozen dataclass (by design, so app code can't mutate
    config at runtime), so tests swap in a modified copy instead."""
    import dataclasses
    db_path = tmp_path / "test.db"
    test_settings = dataclasses.replace(db_module.settings, db_path=str(db_path))
    monkeypatch.setattr(db_module, "settings", test_settings)
    db_module.init_db()
    return db_module


@pytest.fixture
def make_nodes(monkeypatch, clean_db):
    """Factory fixture: build a Nodes() instance with fake Gmail + fake agents
    wired in, without touching real APIs."""
    import src.nodes as nodes_module

    def _make(agents_kwargs=None, gmail_kwargs=None):
        fake_agents = FakeAgents(**(agents_kwargs or {}))
        fake_gmail = FakeGmailTools(**(gmail_kwargs or {}))
        monkeypatch.setattr(nodes_module, "Agents", lambda: fake_agents)
        monkeypatch.setattr(nodes_module, "GmailToolsClass", lambda: fake_gmail)
        n = nodes_module.Nodes()
        return n, fake_agents, fake_gmail

    return _make


@pytest.fixture
def make_workflow(monkeypatch, clean_db):
    """Factory fixture: build a full compiled Workflow() with fakes wired in."""
    import src.nodes as nodes_module

    def _make(agents_kwargs=None, gmail_kwargs=None):
        fake_agents = FakeAgents(**(agents_kwargs or {}))
        fake_gmail = FakeGmailTools(**(gmail_kwargs or {}))
        monkeypatch.setattr(nodes_module, "Agents", lambda: fake_agents)
        monkeypatch.setattr(nodes_module, "GmailToolsClass", lambda: fake_gmail)

        from src.graph import Workflow
        wf = Workflow()
        return wf, fake_agents, fake_gmail

    return _make


def initial_state(**overrides):
    state = {
        "emails": [], "current_email": None, "email_category": "",
        "generated_email": "", "rag_queries": [], "retrieved_documents": "",
        "writer_messages": [], "sendable": False, "trials": 0, "_error": False,
    }
    state.update(overrides)
    return state
