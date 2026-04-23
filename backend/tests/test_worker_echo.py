from unittest.mock import patch

from app.workers.tasks import process_inbound_message
from tests.sample_payloads import status_only, text_message


def test_worker_echoes_text_message():
    payload = text_message(from_phone="919876543210", text="hello bot")

    with patch("app.workers.tasks.WhatsAppClient") as client_cls:
        sender = client_cls.return_value
        result = process_inbound_message(payload)

    assert result == {"processed": 1}
    sender.send_text.assert_called_once_with(to="919876543210", body="Got it: hello bot")


def test_worker_ignores_status_only_callbacks():
    with patch("app.workers.tasks.WhatsAppClient") as client_cls:
        sender = client_cls.return_value
        result = process_inbound_message(status_only())

    assert result == {"processed": 0}
    sender.send_text.assert_not_called()


def test_worker_echoes_non_text_with_type_tag():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": "9199", "id": "wamid.V", "type": "audio", "audio": {"id": "x"}}
                            ]
                        }
                    }
                ]
            }
        ]
    }

    with patch("app.workers.tasks.WhatsAppClient") as client_cls:
        sender = client_cls.return_value
        result = process_inbound_message(payload)

    assert result == {"processed": 1}
    sender.send_text.assert_called_once_with(to="9199", body="Got it: [voice]")
