"""Inbound webhook normalization — Meta Cloud API and Twilio Messaging."""
from __future__ import annotations

from typing import Any

from app.services.whatsapp.meta_parser import parse_meta_inbound
from app.services.whatsapp.twilio_parser import parse_twilio_inbound
from app.services.whatsapp.types import DocumentInfo, InboundMessage, MessageType, is_forwarded_message

__all__ = [
    "DocumentInfo",
    "InboundMessage",
    "MessageType",
    "is_forwarded_message",
    "parse_inbound",
    "extract_document_info",
    "detect_webhook_provider",
]


def detect_webhook_provider(payload: dict[str, Any]) -> str:
    """Return 'twilio' or 'meta' from envelope or payload shape."""
    explicit = payload.get("provider")
    if explicit in ("twilio", "meta"):
        return explicit
    if "MessageSid" in payload or ("From" in payload and "Body" in payload):
        return "twilio"
    return "meta"


def parse_inbound(payload: dict[str, Any]) -> list[InboundMessage]:
    """Parse Meta JSON webhook, Twilio form envelope, or raw Twilio form dict."""
    provider = detect_webhook_provider(payload)
    if provider == "twilio":
        data = payload.get("data", payload)
        return parse_twilio_inbound(data)
    return parse_meta_inbound(payload)


def extract_document_info(raw: dict[str, Any]) -> DocumentInfo | None:
    """Return document metadata for Meta or Twilio inbound raw dict."""
    if raw.get("type") == "document":
        doc = raw.get("document") or {}
        media_id = doc.get("id")
        if not media_id:
            return None
        return DocumentInfo(
            media_id=media_id,
            filename=doc.get("filename") or "upload.pdf",
            mime_type=doc.get("mime_type"),
        )

    num_media = int(raw.get("NumMedia") or 0)
    if num_media > 0:
        media_url = raw.get("MediaUrl0")
        if not media_url:
            return None
        content_type = str(raw.get("MediaContentType0") or "")
        filename = "upload.pdf" if "pdf" in content_type else "upload.bin"
        return DocumentInfo(
            media_id=str(media_url),
            filename=filename,
            mime_type=content_type or None,
        )
    return None
