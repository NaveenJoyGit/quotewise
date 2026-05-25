"""Celery task: route inbound WhatsApp messages through the conversation engine.

Routing (priority):
  1. FR-001 contractor admin
  2. FR-002 forwarded buyer quotes (proxy)
  3. Contractor approve/reject (direct buyer quotes only)
  4. Buyer conversation
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.whatsapp.payload import parse_inbound
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_CONTRACTOR_HELP = (
    "Forward a buyer's WhatsApp message to get a quote, "
    "or send *manage-rates* / *onboard* for account setup. "
    'Reply "approve" or "reject" when a direct buyer quote is pending.'
)


@celery_app.task(name="process_inbound_message")
def process_inbound_message(payload: dict[str, Any]) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.db.base import SessionLocal
    from app.services.conversation import session_repo
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
        processed = 0

        for msg in messages:
            try:
                contractor = session_repo.resolve_contractor(
                    db, wa_phone_number_id=msg.phone_number_id or None
                )
                from app.services.whatsapp.phone import find_contractor_by_phone, phones_match

                registered = find_contractor_by_phone(db, msg.from_phone)
                if _should_route_admin(db, msg, registered):
                    _route_admin_message(msg, db, wa, llm, settings, registered, contractor)
                elif registered and _should_route_forward(db, registered, msg):
                    _route_forwarded_quote(registered, msg, db, wa, llm, settings)
                elif registered and _should_route_approval(msg, db, registered):
                    _route_contractor_approval(contractor, msg, db, wa, settings)
                elif registered and phones_match(msg.from_phone, contractor.phone):
                    wa.send_text(to=contractor.phone, body=_CONTRACTOR_HELP)
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


def _should_route_admin(db, msg, registered) -> bool:
    from app.services.contractor_admin.routing import should_route_admin

    return should_route_admin(db, msg, registered)


def _should_route_forward(db, contractor, msg) -> bool:
    from datetime import datetime, timezone

    from app.services.forwarded_quote import session_repo as forward_repo

    if msg.is_forwarded:
        return True
    active = forward_repo.find_active_forward_session(
        db, contractor.id, datetime.now(timezone.utc)
    )
    return active is not None


def _should_route_approval(msg, db, contractor) -> bool:
    from app.services.approval.keywords import ApprovalAction, parse_approval_keyword
    from app.services.conversation import session_repo

    action = parse_approval_keyword(msg.text or "")
    if action == ApprovalAction.unknown:
        return False
    return session_repo.find_pending_quote_for_contractor(db, contractor.id) is not None


def _route_admin_message(msg, db, wa, llm, settings, registered, tenant_contractor):
    from app.services.contractor_admin.engine import ContractorAdminEngine

    engine = ContractorAdminEngine(db=db, llm=llm, wa=wa, settings=settings)
    outbound = engine.process(msg, tenant_contractor, registered)
    if outbound:
        wa.send_text(to=msg.from_phone, body=outbound)


def _route_forwarded_quote(contractor, msg, db, wa, llm, settings):
    from app.services.forwarded_quote.engine import ForwardedQuoteEngine

    ForwardedQuoteEngine(db=db, llm=llm, wa=wa, settings=settings).process(contractor, msg)


def _route_contractor_approval(contractor, msg, db, wa, settings):
    from app.services.approval.service import ApprovalService

    ApprovalService(db=db, wa=wa, settings=settings).process(contractor, msg)


def _route_buyer_message(contractor, msg, db, wa, llm, settings):
    from app.services.conversation.engine import ConversationEngine

    engine = ConversationEngine(db=db, llm=llm, settings=settings)
    outbound = engine.process(msg)
    if outbound:
        wa.send_text(to=msg.from_phone, body=outbound)

    if engine.pending_quote_snapshot is not None and engine.last_session is not None:
        _handle_quote_ready(db, engine, contractor, wa, settings)


def _handle_quote_ready(db, engine, contractor, wa, settings) -> None:
    """Persist direct-buyer quote and notify contractor for approval."""
    from app.db.enums import SessionSource
    from app.services.conversation import session_repo

    session = engine.last_session
    if session is None or session.source != SessionSource.buyer_direct:
        return

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
