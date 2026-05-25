"""WhatsApp client facade — dispatches to Meta or Twilio based on WA_PROVIDER."""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.whatsapp.meta_client import MetaWhatsAppClient
from app.services.whatsapp.twilio_client import TwilioWhatsAppClient


class WhatsAppClient:
    """Unified interface used by workers, approval, admin, and forward flows."""

    def __init__(self, settings: Settings | None = None, http_client: httpx.Client | None = None):
        self._settings = settings or get_settings()
        if self._settings.wa_provider == "twilio":
            self._backend: MetaWhatsAppClient | TwilioWhatsAppClient = TwilioWhatsAppClient(
                settings=self._settings, http_client=http_client
            )
        else:
            self._backend = MetaWhatsAppClient(
                settings=self._settings, http_client=http_client
            )

    @property
    def provider(self) -> str:
        return self._settings.wa_provider

    def send_text(self, to: str, body: str) -> dict[str, Any]:
        return self._backend.send_text(to=to, body=body)

    def send_document(
        self, to: str, document_url: str, filename: str, caption: str = ""
    ) -> dict[str, Any]:
        return self._backend.send_document(
            to=to, document_url=document_url, filename=filename, caption=caption
        )

    def download_media(self, media_id: str) -> tuple[bytes, str]:
        return self._backend.download_media(media_id)
