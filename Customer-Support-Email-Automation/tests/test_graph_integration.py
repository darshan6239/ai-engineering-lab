from tests.conftest import make_email, initial_state
from src import db


def run(app, state, limit=25):
    """Drain the graph stream and return the final merged state snapshot
    plus the ordered list of node names visited (useful for asserting on
    the path taken through the graph)."""
    visited = []
    final = dict(state)
    for step, output in enumerate(app.stream(state, {"recursion_limit": 100})):
        if step > limit:
            raise AssertionError("graph did not terminate — possible infinite loop")
        for key, value in output.items():
            visited.append(key)
            if isinstance(value, dict):
                final.update(value)
    return final, visited


def test_empty_inbox_ends_immediately(make_workflow):
    wf, agents, gmail = make_workflow(gmail_kwargs={"incoming_emails": []})
    final, visited = run(wf.app, initial_state())
    assert "load_inbox_emails" in visited
    assert not gmail.drafts_created
    assert not gmail.sent


def test_unrelated_email_is_skipped_not_sent(make_workflow):
    incoming = [{
        "id": "u1", "threadId": "t1", "messageId": "<u1@x>", "references": "",
        "sender": "spam@example.com", "subject": "lol", "body": "unrelated nonsense",
    }]
    wf, agents, gmail = make_workflow(
        agents_kwargs={"category": "unrelated"}, gmail_kwargs={"incoming_emails": incoming},
    )
    final, visited = run(wf.app, initial_state())
    assert "skip_unrelated_email" in visited
    assert not gmail.drafts_created
    assert db.get_email("u1")["status"] == "skipped"


def test_product_enquiry_full_happy_path_creates_draft(make_workflow):
    incoming = [{
        "id": "p1", "threadId": "t2", "messageId": "<p1@x>", "references": "",
        "sender": "buyer@example.com", "subject": "Pricing?", "body": "What do you charge?",
    }]
    wf, agents, gmail = make_workflow(
        agents_kwargs={"category": "product_enquiry", "sendable": True},
        gmail_kwargs={"incoming_emails": incoming},
    )
    final, visited = run(wf.app, initial_state())
    assert "construct_rag_queries" in visited
    assert "retrieve_from_rag" in visited
    assert len(gmail.drafts_created) == 1
    assert db.get_email("p1")["status"] == "draft_created"


def test_complaint_needs_one_rewrite_then_sends(make_workflow):
    """Proofreader rejects the first draft, approves the second."""
    incoming = [{
        "id": "c1", "threadId": "t3", "messageId": "<c1@x>", "references": "",
        "sender": "angry@example.com", "subject": "Not happy", "body": "This is broken!",
    }]
    wf, agents, gmail = make_workflow(
        agents_kwargs={"category": "customer_complaint"},
        gmail_kwargs={"incoming_emails": incoming},
    )

    call_count = {"n": 0}
    original = agents.email_proofreader

    def flaky_then_ok(inputs):
        call_count["n"] += 1
        agents._sendable = call_count["n"] >= 2
        return original(inputs)

    agents.email_proofreader = flaky_then_ok
    final, visited = run(wf.app, initial_state())
    assert visited.count("email_writer") == 2
    assert len(gmail.drafts_created) == 1


def test_max_rewrite_trials_gives_up_without_crashing(make_workflow):
    """The known original bug: exhausting trials on the *last* email in the
    queue used to crash with IndexError. Must now terminate cleanly."""
    incoming = [{
        "id": "hard1", "threadId": "t4", "messageId": "<hard1@x>", "references": "",
        "sender": "impossible@example.com", "subject": "Never good enough", "body": "...",
    }]
    wf, agents, gmail = make_workflow(
        agents_kwargs={"category": "customer_feedback", "sendable": False},
        gmail_kwargs={"incoming_emails": incoming},
    )
    final, visited = run(wf.app, initial_state())  # must not raise
    assert not gmail.drafts_created
    assert not gmail.sent
    stored = db.get_email("hard1")
    assert stored["status"] == "failed"


def test_categorizer_model_failure_does_not_crash_the_batch(make_workflow):
    incoming = [{
        "id": "bad1", "threadId": "t5", "messageId": "<bad1@x>", "references": "",
        "sender": "x@example.com", "subject": "hi", "body": "hi",
    }]
    wf, agents, gmail = make_workflow(
        agents_kwargs={"raise_on": {"categorize_email"}},
        gmail_kwargs={"incoming_emails": incoming},
    )
    final, visited = run(wf.app, initial_state())
    assert "handle_processing_error" in visited
    assert db.get_email("bad1")["status"] == "failed"


def test_gmail_outage_on_fetch_ends_gracefully(make_workflow):
    wf, agents, gmail = make_workflow(gmail_kwargs={"raise_on_fetch": True})
    final, visited = run(wf.app, initial_state())
    assert final["emails"] == []


def test_multiple_emails_processed_in_sequence(make_workflow):
    incoming = [
        {"id": f"m{i}", "threadId": f"t{i}", "messageId": f"<m{i}@x>", "references": "",
         "sender": f"user{i}@example.com", "subject": f"Q{i}", "body": "pricing please"}
        for i in range(3)
    ]
    wf, agents, gmail = make_workflow(
        agents_kwargs={"category": "product_enquiry", "sendable": True},
        gmail_kwargs={"incoming_emails": incoming},
    )
    final, visited = run(wf.app, initial_state(), limit=60)
    assert len(gmail.drafts_created) == 3
