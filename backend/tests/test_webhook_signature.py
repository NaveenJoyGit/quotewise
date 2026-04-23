import hashlib
import hmac
import json
from unittest.mock import patch

from tests.sample_payloads import text_message


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_post_accepts_valid_signature_and_enqueues(client):
    payload = text_message(text="hi there")
    body = json.dumps(payload).encode()
    sig = _sign(body, "test-app-secret")

    with patch("app.api.whatsapp_webhook.process_inbound_message.delay") as delay:
        resp = client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "enqueued"}
    delay.assert_called_once()
    enqueued_payload = delay.call_args.args[0]
    assert enqueued_payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"] == "hi there"


def test_post_rejects_invalid_signature(client):
    payload = text_message()
    body = json.dumps(payload).encode()
    bad_sig = "sha256=" + "0" * 64

    with patch("app.api.whatsapp_webhook.process_inbound_message.delay") as delay:
        resp = client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={"X-Hub-Signature-256": bad_sig, "Content-Type": "application/json"},
        )

    assert resp.status_code == 403
    delay.assert_not_called()


def test_post_rejects_missing_signature(client):
    payload = text_message()
    body = json.dumps(payload).encode()

    with patch("app.api.whatsapp_webhook.process_inbound_message.delay") as delay:
        resp = client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 403
    delay.assert_not_called()


def test_post_does_not_call_whatsapp_api_in_request_thread(client):
    """SPEC §2.2: webhook must not do synchronous outbound work.
    Verify the webhook path does not touch WhatsAppClient at all — it only enqueues.
    """
    payload = text_message()
    body = json.dumps(payload).encode()
    sig = _sign(body, "test-app-secret")

    with patch("app.api.whatsapp_webhook.process_inbound_message.delay"), \
         patch("app.services.whatsapp.client.httpx.Client") as http_cls:
        resp = client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )

    assert resp.status_code == 200
    http_cls.assert_not_called()
