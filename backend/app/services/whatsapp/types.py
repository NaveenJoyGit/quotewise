from dataclasses import dataclass
from typing import Any, Literal

MessageType = Literal["text", "voice", "image", "document", "unsupported"]


def is_forwarded_message(raw: dict[str, Any]) -> bool:
    """Meta: context.forwarded. Twilio: Forwarded / FrequentlyForwarded (see twilio_parser)."""
    context = raw.get("context") or {}
    if context.get("forwarded"):
        return True
    for key in ("Forwarded", "FrequentlyForwarded"):
        if str(raw.get(key, "")).lower() == "true":
            return True
    return False


@dataclass(frozen=True)
class InboundMessage:
    """Normalized representation of a single WhatsApp inbound message."""

    whatsapp_message_id: str
    from_phone: str
    message_type: MessageType
    text: str | None
    raw: dict[str, Any]
    phone_number_id: str = ""  # Meta phone_number_id or Twilio To (E.164) for routing
    is_forwarded: bool = False


@dataclass(frozen=True)
class DocumentInfo:
    """Extracted document metadata from an inbound WA message."""

    media_id: str
    filename: str
    mime_type: str | None = None
