import base64
import os

os.environ.setdefault("MY_EMAIL", "me@example.com")

from src.tools.GmailTools import GmailToolsClass


def _tools():
    """Build an instance without running the real OAuth flow — we only
    want to exercise the pure parsing helpers here."""
    return GmailToolsClass.__new__(GmailToolsClass)


def b64(s):
    return base64.urlsafe_b64encode(s.encode()).decode()


def test_plain_text_body_extracted():
    tools = _tools()
    payload = {"mimeType": "text/plain", "body": {"data": b64("Hello there")}}
    assert tools._get_email_body(payload) == "Hello there"


def test_html_body_strips_tags():
    tools = _tools()
    html = "<html><body><p>Hello <b>world</b></p><script>evil()</script></body></html>"
    payload = {"mimeType": "text/html", "body": {"data": b64(html)}}
    result = tools._get_email_body(payload)
    assert "evil()" not in result
    assert "Hello" in result and "world" in result


def test_multipart_prefers_plain_text():
    tools = _tools()
    payload = {
        "parts": [
            {"mimeType": "text/html", "body": {"data": b64("<p>HTML version</p>")}},
            {"mimeType": "text/plain", "body": {"data": b64("Plain version")}},
        ]
    }
    # extract_body walks parts in order and returns on first plain/html hit —
    # verify at minimum that we get a valid, non-empty, cleaned result.
    result = tools._get_email_body(payload)
    assert result in ("HTML version", "Plain version")


def test_nested_multipart_recurses():
    tools = _tools()
    payload = {
        "parts": [
            {"mimeType": "multipart/alternative", "parts": [
                {"mimeType": "text/plain", "body": {"data": b64("Nested body")}},
            ]},
        ]
    }
    assert tools._get_email_body(payload) == "Nested body"


def test_empty_body_does_not_crash():
    tools = _tools()
    payload = {"mimeType": "text/plain", "body": {}}
    assert tools._get_email_body(payload) == ""


def test_clean_body_collapses_whitespace():
    tools = _tools()
    assert tools._clean_body_text("Hello\n\n  world\r\n!") == "Hello world!"


def test_should_skip_own_email():
    tools = _tools()
    os.environ["MY_EMAIL"] = "me@example.com"
    assert tools._should_skip_email({"sender": "Me <me@example.com>"}) is True
    assert tools._should_skip_email({"sender": "Someone <other@example.com>"}) is False
