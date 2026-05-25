from unittest.mock import MagicMock

from app.core.config import Settings
from app.services.whatsapp.client import WhatsAppClient


def _twilio_settings(**overrides) -> Settings:
    base = dict(
        wa_provider="twilio",
        twilio_account_sid="",
        twilio_auth_token="",
        twilio_whatsapp_from="",
    )
    base.update(overrides)
    return Settings(**base)


def test_twilio_client_mock_mode():
    client = WhatsAppClient(settings=_twilio_settings())
    assert client.provider == "twilio"
    result = client.send_text(to="919876543210", body="hi")
    assert result["mock"] is True
    assert result["provider"] == "twilio"


def test_twilio_client_posts_messages_api():
    http = MagicMock()
    resp = MagicMock()
    resp.json.return_value = {"sid": "SM_OUT"}
    http.post.return_value = resp

    settings = _twilio_settings(
        twilio_account_sid="AC123",
        twilio_auth_token="token",
        twilio_whatsapp_from="whatsapp:+14155238886",
    )
    client = WhatsAppClient(settings=settings, http_client=http)
    out = client.send_text(to="919876543210", body="hello")

    http.post.assert_called_once()
    url = http.post.call_args.args[0]
    assert "/Accounts/AC123/Messages.json" in url
    data = http.post.call_args.kwargs["data"]
    assert data["From"] == "whatsapp:+14155238886"
    assert data["To"] == "whatsapp:+919876543210"
    assert data["Body"] == "hello"
    assert out == {"sid": "SM_OUT"}
