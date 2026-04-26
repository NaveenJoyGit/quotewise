import logging
from typing import Any

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """Thin wrapper over Meta's Graph API messages endpoint.

    When WA_ACCESS_TOKEN / WA_PHONE_NUMBER_ID are empty, runs in mock mode:
    logs what would be sent and returns a stub response. Lets us prove the
    full pipeline end-to-end before Meta business verification completes.
    """

    def __init__(self, settings: Settings | None = None, http_client: httpx.Client | None = None):
        self._settings = settings or get_settings()
        self._http = http_client

    def send_text(self, to: str, body: str) -> dict[str, Any]:
        if not self._settings.wa_send_enabled:
            logger.info(
                "whatsapp.send_text.mock",
                extra={"event_type": "whatsapp.send_text.mock"},
            )
            logger.info("[MOCK WA] to=%s body=%s", to, body)
            return {"mock": True, "to": to, "body": body}

        url = (
            f"https://graph.facebook.com/{self._settings.wa_graph_api_version}"
            f"/{self._settings.wa_phone_number_id}/messages"
        )
        headers = {
            "Authorization": f"Bearer {self._settings.wa_access_token}",
            "Content-Type": "application/json",
        }
        body_payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }

        client = self._http or httpx.Client(timeout=10.0)
        try:
            resp = client.post(url, headers=headers, json=body_payload)
            resp.raise_for_status()
            return resp.json()
        finally:
            if self._http is None:
                client.close()

    def send_document(
        self, to: str, document_url: str, filename: str, caption: str = ""
    ) -> dict[str, Any]:
        if not self._settings.wa_send_enabled:
            logger.info(
                "whatsapp.send_document.mock",
                extra={"event_type": "whatsapp.send_document.mock"},
            )
            logger.info("[MOCK WA] send_document to=%s filename=%s url=%s", to, filename, document_url)
            return {"mock": True, "to": to, "filename": filename}

        url = (
            f"https://graph.facebook.com/{self._settings.wa_graph_api_version}"
            f"/{self._settings.wa_phone_number_id}/messages"
        )
        headers = {
            "Authorization": f"Bearer {self._settings.wa_access_token}",
            "Content-Type": "application/json",
        }
        body_payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "document",
            "document": {"link": document_url, "filename": filename, "caption": caption},
        }

        client = self._http or httpx.Client(timeout=10.0)
        try:
            resp = client.post(url, headers=headers, json=body_payload)
            resp.raise_for_status()
            return resp.json()
        finally:
            if self._http is None:
                client.close()
