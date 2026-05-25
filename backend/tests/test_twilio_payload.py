"""Tests for Twilio WhatsApp inbound parsing."""
from app.services.whatsapp.payload import extract_document_info, parse_inbound
from tests.sample_twilio_payloads import twilio_document_message, twilio_text_message


def test_parse_twilio_text():
    params = twilio_text_message(body="manage-rates", wa_id="919999900001")
    msgs = parse_inbound({"provider": "twilio", "data": params})
    assert len(msgs) == 1
    m = msgs[0]
    assert m.from_phone == "919999900001"
    assert m.text == "manage-rates"
    assert m.message_type == "text"
    assert m.phone_number_id == "+14155238886"
    assert m.is_forwarded is False


def test_parse_twilio_forwarded():
    params = twilio_text_message(
        body="Need painting 1000 sqft",
        forwarded=True,
    )
    msgs = parse_inbound({"provider": "twilio", "data": params})
    assert msgs[0].is_forwarded is True


def test_parse_twilio_raw_shape_detection():
    params = twilio_text_message()
    msgs = parse_inbound(params)
    assert len(msgs) == 1


def test_extract_document_twilio():
    params = twilio_document_message()
    info = extract_document_info(params)
    assert info is not None
    assert info.media_id.startswith("https://")
    assert info.filename == "upload.pdf"
