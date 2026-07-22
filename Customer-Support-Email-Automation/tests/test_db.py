from src import db


def test_upsert_insert_then_update(clean_db):
    db.upsert_email("e1", sender="a@b.com", subject="Hi", status="queued")
    row = db.get_email("e1")
    assert row["status"] == "queued"

    db.upsert_email("e1", status="sent")
    row = db.get_email("e1")
    assert row["status"] == "sent"
    assert row["sender"] == "a@b.com"  # untouched fields preserved


def test_get_emails_filters_by_status(clean_db):
    db.upsert_email("a", status="queued")
    db.upsert_email("b", status="sent")
    db.upsert_email("c", status="sent")
    assert len(db.get_emails(status="sent")) == 2
    assert len(db.get_emails()) == 3


def test_stats_aggregate_correctly(clean_db):
    db.upsert_email("a", status="sent", category="product_enquiry", trials=2)
    db.upsert_email("b", status="failed", category="customer_complaint", trials=3)
    stats = db.get_stats()
    assert stats["total"] == 2
    assert stats["by_status"]["sent"] == 1
    assert stats["by_status"]["failed"] == 1
    assert stats["by_category"]["product_enquiry"] == 1
    assert stats["avg_trials"] == 2.5


def test_events_logged_in_order(clean_db):
    db.log_event("a", "categorize_email", "first")
    db.log_event("a", "email_writer", "second")
    events = db.get_events(email_id="a")
    assert [e["message"] for e in events] == ["first", "second"]


def test_writer_history_accumulates(clean_db):
    db.upsert_email("a", status="drafting")
    db.append_writer_history("a", "Draft 1: hello")
    db.append_writer_history("a", "Feedback: needs work")
    email = db.get_email("a")
    import json
    history = json.loads(email["writer_history"])
    assert history == ["Draft 1: hello", "Feedback: needs work"]
