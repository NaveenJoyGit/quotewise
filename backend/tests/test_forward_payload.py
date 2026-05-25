"""Tests for forwarded message detection (FR-002)."""
from app.services.whatsapp.payload import is_forwarded_message, parse_inbound
from tests.sample_payloads import forwarded_text_message, text_message


def test_is_forwarded_message_true():
    raw = {"type": "text", "context": {"forwarded": True}, "text": {"body": "hi"}}
    assert is_forwarded_message(raw) is True


def test_is_forwarded_message_false():
    assert is_forwarded_message({"type": "text", "text": {"body": "hi"}}) is False


def test_parse_inbound_forwarded_flag():
    msgs = parse_inbound(forwarded_text_message())
    assert len(msgs) == 1
    assert msgs[0].is_forwarded is True
    assert "1000 sqft" in (msgs[0].text or "")


def test_parse_inbound_normal_not_forwarded():
    msgs = parse_inbound(text_message())
    assert msgs[0].is_forwarded is False
