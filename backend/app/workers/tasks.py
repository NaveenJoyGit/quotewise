import logging
from typing import Any

from app.services.whatsapp.client import WhatsAppClient
from app.services.whatsapp.payload import parse_inbound
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="process_inbound_message")
def process_inbound_message(payload: dict[str, Any]) -> dict[str, Any]:
    """Milestone 1 handler: echo 'Got it: <text>' back to the sender.

    This is plumbing only — no LLM, no state machine, no persistence yet.
    Handles text messages; for other types, echoes a type-tagged placeholder.
    """
    messages = parse_inbound(payload)
    if not messages:
        logger.info("process_inbound_message.no_messages")
        return {"processed": 0}

    client = WhatsAppClient()
    for msg in messages:
        reply = _compose_echo(msg.message_type, msg.text)
        logger.info(
            "process_inbound_message.echo",
            extra={"event_type": "whatsapp.echo"},
        )
        client.send_text(to=msg.from_phone, body=reply)

    return {"processed": len(messages)}


def _compose_echo(message_type: str, text: str | None) -> str:
    if message_type == "text" and text is not None:
        return f"Got it: {text}"
    return f"Got it: [{message_type}]"
