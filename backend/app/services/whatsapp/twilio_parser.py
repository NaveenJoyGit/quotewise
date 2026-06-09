"""Parse inbound messages from Twilio WhatsApp webhooks (application/x-www-form-urlencoded)."""
from __future__ import annotations

from typing import Any

from app.services.whatsapp.types import InboundMessage, MessageType
from app.services.whatsapp.phone import strip_whatsapp_prefix


def parse_twilio_inbound(params: dict[str, Any]) -> list[InboundMessage]:
    """Normalize a Twilio Messaging webhook POST body to InboundMessage list."""
    message_sid = str(params.get("MessageSid") or params.get("SmsSid") or "")
    if not message_sid:
        return []

    from_phone = _sender_phone(params)
    to_field = str(params.get("To") or "")
    routing_id = _routing_id(to_field)
    msg_type, text = _message_type_and_text(params)

    return [
        InboundMessage(
            whatsapp_message_id=message_sid,
            from_phone=from_phone,
            message_type=msg_type,
            text=text,
            raw=dict(params),
            phone_number_id=routing_id,
            is_forwarded=_is_forwarded(params),
        )
    ]


def _sender_phone(params: dict[str, Any]) -> str:
    """Prefer WaId (digits) else strip whatsapp: prefix from From."""
    wa_id = params.get("WaId")
    if wa_id:
        return str(wa_id).strip()
    return strip_whatsapp_prefix(str(params.get("From") or ""))


def _routing_id(to_field: str) -> str:
    """Tenant routing key stored on Contractor.wa_phone_number_id (E.164)."""
    cleaned = strip_whatsapp_prefix(to_field)
    if cleaned and not cleaned.startswith("+") and cleaned.isdigit():
        return f"+{cleaned}"
    return cleaned


def _is_forwarded(params: dict[str, Any]) -> bool:
    """Twilio sets Forwarded and/or FrequentlyForwarded on WhatsApp forwards."""
    for key in ("Forwarded", "FrequentlyForwarded"):
        if str(params.get(key, "")).lower() == "true":
            return True
    return False


def _message_type_and_text(params: dict[str, Any]) -> tuple[MessageType, str | None]:
    num_media = int(params.get("NumMedia") or 0)
    body = params.get("Body")
    text = str(body) if body is not None and str(body) != "" else None

    if num_media <= 0:
        return ("text" if text else "unsupported"), text

    content_type = str(params.get("MediaContentType0") or "").lower()
    if "pdf" in content_type or "document" in content_type:
        return "document", text
    if content_type.startswith("image/"):
        return "image", text
    if content_type.startswith("audio/"):
        return "voice", text
    return "document", text
