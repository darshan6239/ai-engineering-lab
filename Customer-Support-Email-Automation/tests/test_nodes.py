from tests.conftest import make_email, initial_state
from src.config import settings


def test_load_new_emails_happy_path(make_nodes):
    nodes, agents, gmail = make_nodes(gmail_kwargs={"incoming_emails": [{
        "id": "1", "threadId": "t1", "messageId": "<1@x>", "references": "",
        "sender": "a@b.com", "subject": "Hi", "body": "hello",
    }]})
    result = nodes.load_new_emails(initial_state())
    assert len(result["emails"]) == 1
    assert result["emails"][0].id == "1"


def test_load_new_emails_gmail_outage_returns_empty_not_crash(make_nodes):
    nodes, agents, gmail = make_nodes(gmail_kwargs={"raise_on_fetch": True})
    result = nodes.load_new_emails(initial_state())
    assert result["emails"] == []


def test_check_new_emails_empty_vs_process(make_nodes):
    nodes, *_ = make_nodes()
    assert nodes.check_new_emails(initial_state(emails=[])) == "empty"
    assert nodes.check_new_emails(initial_state(emails=[make_email()])) == "process"


def test_categorize_email_happy_path(make_nodes):
    nodes, agents, gmail = make_nodes(agents_kwargs={"category": "customer_complaint"})
    state = initial_state(emails=[make_email()])
    result = nodes.categorize_email(state)
    assert result["email_category"] == "customer_complaint"
    assert result["_error"] is False


def test_categorize_email_llm_failure_is_isolated(make_nodes):
    """A single bad email (or a flaky model call) must not crash the run —
    it should be recorded as failed and dropped from the queue."""
    nodes, agents, gmail = make_nodes(agents_kwargs={"raise_on": {"categorize_email"}})
    email = make_email()
    state = initial_state(emails=[email])
    result = nodes.categorize_email(state)
    assert result["_error"] is True
    assert email not in result["emails"]


def test_route_email_based_on_category(make_nodes):
    nodes, *_ = make_nodes()
    assert nodes.route_email_based_on_category(
        initial_state(email_category="product_enquiry")) == "product related"
    assert nodes.route_email_based_on_category(
        initial_state(email_category="unrelated")) == "unrelated"
    assert nodes.route_email_based_on_category(
        initial_state(email_category="customer_feedback")) == "not product related"
    assert nodes.route_email_based_on_category(initial_state(_error=True)) == "error"


def test_must_rewrite_sends_when_sendable(make_nodes):
    nodes, *_ = make_nodes()
    email = make_email()
    state = initial_state(emails=[email], current_email=email, sendable=True, trials=1)
    assert nodes.must_rewrite(state) == "send"
    assert state["emails"] == []  # popped


def test_must_rewrite_rewrites_under_trial_limit(make_nodes):
    nodes, *_ = make_nodes()
    email = make_email()
    state = initial_state(emails=[email], current_email=email, sendable=False, trials=1)
    assert nodes.must_rewrite(state) == "rewrite"
    assert state["emails"] == [email]  # not popped yet


def test_must_rewrite_stops_at_max_trials_without_crashing(make_nodes):
    """Regression test for the original bug: after giving up, the workflow
    must not try to categorize_email() on an now-empty queue."""
    nodes, *_ = make_nodes()
    email = make_email()
    state = initial_state(
        emails=[email], current_email=email, sendable=False, trials=settings.max_rewrite_trials,
    )
    outcome = nodes.must_rewrite(state)
    assert outcome == "stop"
    assert state["emails"] == []
    # simulate what graph.py does next: route "stop" -> handle_processing_error -> is_email_inbox_empty
    state2 = nodes.handle_processing_error(state)
    state3 = nodes.is_email_inbox_empty(state2)
    assert nodes.check_new_emails(state3) == "empty"  # no crash, correctly detects empty inbox


def test_skip_unrelated_email(make_nodes):
    nodes, *_ = make_nodes()
    email = make_email()
    state = initial_state(emails=[email])
    result = nodes.skip_unrelated_email(state)
    assert result["emails"] == []


def test_create_draft_response_gmail_failure_marks_failed_not_crash(make_nodes):
    nodes, agents, gmail = make_nodes(gmail_kwargs={"raise_on_draft": True})
    email = make_email()
    state = initial_state(current_email=email, generated_email="Some reply")
    # Should not raise even though Gmail draft creation fails internally.
    nodes.create_draft_response(state)
    from src import db
    stored = db.get_email(email.id)
    assert stored["status"] == "failed"


def test_construct_rag_queries_failure_is_isolated(make_nodes):
    nodes, agents, gmail = make_nodes(agents_kwargs={"raise_on": {"design_rag_queries"}})
    email = make_email()
    state = initial_state(emails=[email], current_email=email)
    result = nodes.construct_rag_queries(state)
    assert result["_error"] is True
