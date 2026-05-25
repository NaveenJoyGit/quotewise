from app.services.whatsapp.payload import parse_inbound
from tests.sample_payloads import status_only, text_message


def test_parse_text_message():
    msgs = parse_inbound(text_message(from_phone="911234567890", text="hello world", message_id="wamid.ABC"))
    assert len(msgs) == 1
    m = msgs[0]
    assert m.from_phone == "911234567890"
    assert m.text == "hello world"
    assert m.message_type == "text"
    assert m.whatsapp_message_id == "wamid.ABC"
    assert m.phone_number_id == "PHONE_NUMBER_ID"


def test_parse_phone_number_id_extracted_from_metadata():
    msgs = parse_inbound(text_message())
    assert msgs[0].phone_number_id == "PHONE_NUMBER_ID"


def test_parse_phone_number_id_defaults_to_empty_when_missing():
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{"from": "919", "id": "w1", "type": "text", "text": {"body": "hi"}}]
                }
            }]
        }]
    }
    msgs = parse_inbound(payload)
    assert msgs[0].phone_number_id == ""


def test_parse_status_only_returns_empty():
    assert parse_inbound(status_only()) == []


def test_parse_empty_payload():
    assert parse_inbound({}) == []


def test_parse_non_text_maps_to_type():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": "919", "id": "wamid.X", "type": "audio", "audio": {"id": "m1"}}
                            ]
                        }
                    }
                ]
            }
        ]
    }
    msgs = parse_inbound(payload)
    assert len(msgs) == 1
    assert msgs[0].message_type == "voice"
    assert msgs[0].text is None
