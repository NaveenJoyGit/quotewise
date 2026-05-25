"""Parse inbound messages from Meta WhatsApp Cloud API webhooks."""
from __future__ import annotations

from typing import Any

from app.services.whatsapp.types import InboundMessage, MessageType, is_forwarded_message


def parse_meta_inbound(payload: dict[str, Any]) -> list[InboundMessage]:
    """Extract messages from entry[].changes[].value.messages[] (Meta shape)."""
    messages: list[InboundMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
            for msg in value.get("messages", []) or []:
                messages.append(_build_message(msg, phone_number_id))
    return messages


def _build_message(msg: dict[str, Any], phone_number_id: str = "") -> InboundMessage:
    msg_type = msg.get("type", "unsupported")
    text = msg["text"]["body"] if msg_type == "text" and "text" in msg else None
    normalized_type: MessageType
    if msg_type == "text":
        normalized_type = "text"
    elif msg_type in ("audio", "voice"):
        normalized_type = "voice"
    elif msg_type == "image":
        normalized_type = "image"
    elif msg_type == "document":
        normalized_type = "document"
    else:
        normalized_type = "unsupported"

    return InboundMessage(
        whatsapp_message_id=msg.get("id", ""),
        from_phone=msg.get("from", ""),
        message_type=normalized_type,
        text=text,
        raw=msg,
        phone_number_id=phone_number_id,
        is_forwarded=is_forwarded_message(msg),
    )
