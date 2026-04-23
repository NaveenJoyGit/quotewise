from dataclasses import dataclass
from typing import Any, Literal

MessageType = Literal["text", "voice", "image", "document", "unsupported"]


@dataclass(frozen=True)
class InboundMessage:
    """Normalized representation of a single WhatsApp inbound message."""

    whatsapp_message_id: str
    from_phone: str
    message_type: MessageType
    text: str | None
    raw: dict[str, Any]


def parse_inbound(payload: dict[str, Any]) -> list[InboundMessage]:
    """Extract InboundMessage objects from a Meta webhook payload.

    Meta delivers messages nested under entry[].changes[].value.messages[].
    Status-only callbacks (read/delivered) have no 'messages' key and produce an empty list.
    """
    messages: list[InboundMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []) or []:
                messages.append(_build_message(msg))
    return messages


def _build_message(msg: dict[str, Any]) -> InboundMessage:
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
    )
