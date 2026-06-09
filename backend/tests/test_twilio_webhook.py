from unittest.mock import patch

from tests.sample_twilio_payloads import twilio_text_message


def test_twilio_webhook_enqueues(client):
    params = twilio_text_message(body="hello")
    with patch("app.api.twilio_webhook.process_inbound_message.delay") as delay:
        resp = client.post(
            "/webhooks/twilio/whatsapp",
            data=params,
        )
    assert resp.status_code == 200
    assert "Response" in resp.text
    delay.assert_called_once()
    envelope = delay.call_args[0][0]
    assert envelope["provider"] == "twilio"
    assert envelope["data"]["Body"] == "hello"


def test_twilio_webhook_rejects_bad_signature(client):
    from app.core.config import Settings

    locked = Settings(
        app_env="test",
        twilio_auth_token="real-secret",
        twilio_webhook_public_url="https://api.example.com/webhooks/twilio/whatsapp",
    )
    params = twilio_text_message()
    with patch("app.api.twilio_webhook.get_settings", return_value=locked), \
         patch("app.api.twilio_webhook.process_inbound_message.delay"):
        resp = client.post("/webhooks/twilio/whatsapp", data=params)
    assert resp.status_code == 403


def test_twilio_webhook_accepts_valid_signature(client):
    from app.core.config import Settings
    from app.services.whatsapp.twilio_auth import compute_twilio_signature

    webhook_url = "https://api.example.com/webhooks/twilio/whatsapp"
    auth_token = "real-secret"
    locked = Settings(
        app_env="test",
        twilio_auth_token=auth_token,
        twilio_webhook_public_url=webhook_url,
    )
    params = twilio_text_message(body="manage-rates")
    signature = compute_twilio_signature(auth_token, webhook_url, params)
    with patch("app.api.twilio_webhook.get_settings", return_value=locked), \
         patch("app.api.twilio_webhook.process_inbound_message.delay") as delay:
        resp = client.post(
            "/webhooks/twilio/whatsapp",
            data=params,
            headers={"X-Twilio-Signature": signature},
        )
    assert resp.status_code == 200
    delay.assert_called_once()
