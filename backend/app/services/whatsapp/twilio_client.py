"""Twilio Programmable Messaging API for WhatsApp."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings, get_settings
from app.services.whatsapp.phone import normalize_phone_e164, strip_whatsapp_prefix

logger = logging.getLogger(__name__)

_TWILIO_API = "https://api.twilio.com/2010-04-01"


class TwilioWhatsAppClient:
    """Twilio Messages API for WhatsApp; mock mode when credentials are empty."""

    def __init__(self, settings: Settings | None = None, http_client: httpx.Client | None = None):
        self._settings = settings or get_settings()
        self._http = http_client

    @property
    def send_enabled(self) -> bool:
        return bool(
            self._settings.twilio_account_sid
            and self._settings.twilio_auth_token
            and self._settings.twilio_whatsapp_from
        )

    def send_text(self, to: str, body: str) -> dict[str, Any]:
        return self._send_message(to=to, body=body)

    def send_document(
        self, to: str, document_url: str, filename: str, caption: str = ""
    ) -> dict[str, Any]:
        # Twilio uses MediaUrl; caption goes in Body when provided.
        body = caption or f"Quote: {filename}"
        return self._send_message(to=to, body=body, media_url=document_url)

    def download_media(self, media_id: str) -> tuple[bytes, str]:
        """media_id is MediaUrl0 from webhook or a Twilio Media SID."""
        if not self.send_enabled:
            logger.info(
                "whatsapp.download_media.mock",
                extra={"event_type": "whatsapp.download_media.mock", "provider": "twilio"},
            )
            fixture = b"Painting rates (per sqft):\nBasic: Rs. 14\nPremium: Rs. 22\n"
            return fixture, "mock_rates.txt"

        if media_id.startswith("http://") or media_id.startswith("https://"):
            client = self._http or httpx.Client(timeout=30.0)
            try:
                resp = client.get(
                    media_id,
                    auth=(self._settings.twilio_account_sid, self._settings.twilio_auth_token),
                )
                resp.raise_for_status()
                name = _filename_from_url(media_id)
                return resp.content, name
            finally:
                if self._http is None:
                    client.close()

        return self._download_media_by_sid(media_id)

    def _send_message(
        self,
        *,
        to: str,
        body: str,
        media_url: str | None = None,
    ) -> dict[str, Any]:
        if not self.send_enabled:
            logger.info(
                "whatsapp.send.mock",
                extra={"event_type": "whatsapp.send.mock", "provider": "twilio"},
            )
            logger.info(
                "[MOCK WA twilio] to=%s body=%s media=%s",
                to,
                body,
                media_url,
            )
            return {"mock": True, "to": to, "body": body, "provider": "twilio"}

        data: dict[str, str] = {
            "From": self._format_from(),
            "To": self._format_to(to),
            "Body": body,
        }
        if media_url:
            data["MediaUrl"] = media_url

        url = (
            f"{_TWILIO_API}/Accounts/{self._settings.twilio_account_sid}/Messages.json"
        )
        client = self._http or httpx.Client(timeout=15.0)
        try:
            resp = client.post(
                url,
                data=data,
                auth=(self._settings.twilio_account_sid, self._settings.twilio_auth_token),
            )
            resp.raise_for_status()
            return resp.json()
        finally:
            if self._http is None:
                client.close()

    def _download_media_by_sid(self, media_sid: str) -> tuple[bytes, str]:
        account = self._settings.twilio_account_sid
        meta_url = f"{_TWILIO_API}/Accounts/{account}/Messages/{media_sid}/Media.json"
        client = self._http or httpx.Client(timeout=30.0)
        auth = (account, self._settings.twilio_auth_token)
        try:
            meta_resp = client.get(meta_url, auth=auth)
            meta_resp.raise_for_status()
            media_list = meta_resp.json().get("media_list") or meta_resp.json()
            if isinstance(media_list, dict):
                items = media_list.get("media", [])
            else:
                items = media_list
            if not items:
                raise ValueError(f"No media for sid={media_sid}")
            uri = items[0].get("uri", "")
            if uri.startswith("/"):
                download_url = f"https://api.twilio.com{uri}"
            else:
                download_url = uri
            file_resp = client.get(download_url, auth=auth)
            file_resp.raise_for_status()
            return file_resp.content, media_sid
        finally:
            if self._http is None:
                client.close()

    def _format_from(self) -> str:
        raw = self._settings.twilio_whatsapp_from.strip()
        if raw.lower().startswith("whatsapp:"):
            return raw
        e164 = normalize_phone_e164(strip_whatsapp_prefix(raw))
        return f"whatsapp:{e164}"

    def _format_to(self, to: str) -> str:
        if to.lower().startswith("whatsapp:"):
            return to
        e164 = normalize_phone_e164(strip_whatsapp_prefix(to))
        return f"whatsapp:{e164}"


def _filename_from_url(url: str) -> str:
    path = url.split("?")[0]
    if "/" in path:
        tail = path.rsplit("/", 1)[-1]
        if tail:
            return tail
    return "upload.bin"
