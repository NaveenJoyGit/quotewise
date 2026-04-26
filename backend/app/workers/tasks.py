"""Celery task: route inbound WhatsApp messages through the conversation engine.

M4 routing:
  - Contractor phone → ApprovalService (approve/reject keyword processing)
  - Buyer phone     → ConversationEngine (state machine)
  After engine returns, if a quote was just generated, persist it to DB and
  notify the contractor.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.services.whatsapp.payload import InboundMessage, parse_inbound
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="process_inbound_message")
def process_inbound_message(payload: dict[str, Any]) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.db.base import SessionLocal
    from app.db.enums import WorkType
    from app.services.approval.service import ApprovalService
    from app.services.conversation import session_repo
    from app.services.conversation.engine import ConversationEngine
    from app.services.llm.factory import get_llm_client
    from app.services.whatsapp.client import WhatsAppClient

    messages = parse_inbound(payload)
    if not messages:
        return {"processed": 0}

    settings = get_settings()
    llm = get_llm_client()
    db = SessionLocal()
    try:
        wa = WhatsAppClient(settings=settings)
        contractor = session_repo.resolve_contractor(db)
        processed = 0

        for msg in messages:
            try:
                if msg.from_phone == contractor.phone:
                    _route_contractor_message(contractor, msg, db, wa, settings)
                else:
                    _route_buyer_message(contractor, msg, db, wa, llm, settings)
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

        return {"processed": processed}
    finally:
        db.close()


def _route_contractor_message(contractor, msg, db, wa, settings):
    """Forward contractor reply to ApprovalService (approve/reject keywords)."""
    from app.services.approval.service import ApprovalService
    ApprovalService(db=db, wa=wa, settings=settings).process(contractor, msg)


def _route_buyer_message(contractor, msg, db, wa, llm, settings):
    """Run buyer message through the conversation state machine."""
    from app.services.conversation.engine import ConversationEngine

    engine = ConversationEngine(db=db, llm=llm, settings=settings)
    outbound = engine.process(msg)
    if outbound:
        wa.send_text(to=msg.from_phone, body=outbound)

    if engine.pending_quote_snapshot is not None and engine.last_session is not None:
        _handle_quote_ready(db, engine, contractor, wa, settings)


def _handle_quote_ready(db, engine, contractor, wa, settings) -> None:
    """Persist the quote row and send contractor notification.

    Called once per conversation turn where ReadyToQuoteHandler fires.
    We commit before sending the WA notification so that if WA delivery fails
    the quote is not lost — the contractor can still find it via the dashboard.
    """
    from app.services.conversation import session_repo

    session = engine.last_session
    snapshot = engine.pending_quote_snapshot

    try:
        pc = session_repo.load_active_pricing_config(
            db, contractor.id, session.work_type or "painting"
        )
        quote = session_repo.create_quote(
            db=db,
            session=session,
            contractor=contractor,
            snapshot=snapshot,
            pricing_config_version=pc.version,
            validity_days=settings.quote_validity_days,
        )
        db.commit()
    except Exception:
        logger.error("quote.persist_failed", exc_info=True, extra={"event_type": "quote.persist_failed"})
        return

    notification = _format_contractor_notification(quote, session.buyer_phone)
    wa.send_text(to=contractor.phone, body=notification)
    logger.info(
        "contractor.notified",
        extra={
            "event_type": "contractor.notified",
            "quote_id": str(quote.id),
            "contractor_id": str(contractor.id),
        },
    )


def _format_contractor_notification(quote, buyer_phone: str) -> str:
    digits = "".join(c for c in str(buyer_phone) if c.isdigit())
    masked = f"+XX XXXXXX{digits[-4:]}" if len(digits) >= 4 else "XXXXXX"
    work = getattr(quote, "work_type", "painting")
    if hasattr(work, "value"):
        work = work.value
    return (
        f"New quote ready for your approval.\n\n"
        f"Buyer: {masked}\n"
        f"Work: {work}\n"
        f"Total: Rs. {quote.total}\n\n"
        f'Reply "approve" to send to buyer or "reject" to decline.'
    )
