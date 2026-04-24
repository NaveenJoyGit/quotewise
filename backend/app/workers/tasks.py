"""Celery task: process an inbound WhatsApp message through the conversation engine.

Replaces the M1 echo stub. Now routes each inbound message through
ConversationEngine which owns the state machine and LLM calls.
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.whatsapp.payload import parse_inbound
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="process_inbound_message")
def process_inbound_message(payload: dict[str, Any]) -> dict[str, Any]:
    from app.db.base import SessionLocal
    from app.services.conversation.engine import ConversationEngine
    from app.services.llm.factory import get_llm_client
    from app.services.whatsapp.client import WhatsAppClient

    messages = parse_inbound(payload)
    if not messages:
        return {"processed": 0}

    llm = get_llm_client()
    db = SessionLocal()
    try:
        engine = ConversationEngine(db=db, llm=llm)
        wa = WhatsAppClient()
        processed = 0

        for msg in messages:
            try:
                outbound = engine.process(msg)
                if outbound:
                    wa.send_text(to=msg.from_phone, body=outbound)
                processed += 1
            except Exception as exc:
                logger.error(
                    "message.processing_error",
                    extra={
                        "event_type": "message.processing_error",
                        "from_phone": msg.from_phone,
                        "error": str(exc),
                    },
                    exc_info=True,
                )
    finally:
        db.close()

    return {"processed": processed}
