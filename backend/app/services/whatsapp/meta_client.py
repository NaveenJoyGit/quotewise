"""Meta WhatsApp Cloud API (Graph API) outbound + media."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class MetaWhatsAppClient:
    """Graph API messages endpoint; mock mode when credentials are empty."""

    def __init__(self, settings: Settings | None = None, http_client: httpx.Client | None = None):
        self._settings = settings or get_settings()
        self._http = http_client

    @property
    def send_enabled(self) -> bool:
        return bool(self._settings.wa_access_token and self._settings.wa_phone_number_id)

    def send_text(self, to: str, body: str) -> dict[str, Any]:
        if not self.send_enabled:
            logger.info(
                "whatsapp.send_text.mock",
                extra={"event_type": "whatsapp.send_text.mock", "provider": "meta"},
            )
            logger.info("[MOCK WA meta] to=%s body=%s", to, body)
            return {"mock": True, "to": to, "body": body, "provider": "meta"}

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
        return self._post(url, headers, body_payload)

    def send_document(
        self, to: str, document_url: str, filename: str, caption: str = ""
    ) -> dict[str, Any]:
        if not self.send_enabled:
            logger.info(
                "whatsapp.send_document.mock",
                extra={"event_type": "whatsapp.send_document.mock", "provider": "meta"},
            )
            logger.info(
                "[MOCK WA meta] send_document to=%s filename=%s url=%s",
                to,
                filename,
                document_url,
            )
            return {"mock": True, "to": to, "filename": filename, "provider": "meta"}

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
        return self._post(url, headers, body_payload)

    def download_media(self, media_id: str) -> tuple[bytes, str]:
        if not self.send_enabled:
            logger.info(
                "whatsapp.download_media.mock",
                extra={"event_type": "whatsapp.download_media.mock", "provider": "meta"},
            )
            fixture = b"Painting rates (per sqft):\nBasic: Rs. 14\nPremium: Rs. 22\n"
            return fixture, "mock_rates.txt"

        headers = {"Authorization": f"Bearer {self._settings.wa_access_token}"}
        meta_url = (
            f"https://graph.facebook.com/{self._settings.wa_graph_api_version}/{media_id}"
        )
        client = self._http or httpx.Client(timeout=30.0)
        try:
            meta_resp = client.get(meta_url, headers=headers)
            meta_resp.raise_for_status()
            media_url = meta_resp.json().get("url")
            if not media_url:
                raise ValueError(f"No download URL for media_id={media_id}")

            file_resp = client.get(media_url, headers=headers)
            file_resp.raise_for_status()
            return file_resp.content, media_id
        finally:
            if self._http is None:
                client.close()

    def _post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        client = self._http or httpx.Client(timeout=10.0)
        try:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            return resp.json()
        finally:
            if self._http is None:
                client.close()
