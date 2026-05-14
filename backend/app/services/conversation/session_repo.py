"""Thin DB helpers for the conversation layer (SPEC §8.1 single responsibility)."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.db.enums import MessageDirection, MessageType, QuoteStatus, SessionState, WorkType
from app.db.models import Contractor, Message, PricingConfig, Quote
from app.db.models import Session as SessionModel
from app.services.whatsapp.payload import InboundMessage

logger = logging.getLogger(__name__)


class ContractorNotFoundError(RuntimeError):
    """Raised when a wa_phone_number_id is provided but matches no contractor."""


def resolve_contractor(db: DBSession, wa_phone_number_id: str | None = None) -> Contractor:
    """Resolve the contractor for an inbound message.

    - wa_phone_number_id provided and found → return that contractor.
    - wa_phone_number_id provided but NOT found → raise ContractorNotFoundError
      (prevents silent mis-routing between contractors in multi-tenant deployments).
    - wa_phone_number_id is None → fall back to first contractor by created_at
      (dev / mock-mode compat where Meta envelope has no phone_number_id).
    """
    if wa_phone_number_id:
        contractor = (
            db.query(Contractor)
            .filter(Contractor.wa_phone_number_id == wa_phone_number_id)
            .first()
        )
        if contractor is not None:
            return contractor
        raise ContractorNotFoundError(
            f"No contractor with wa_phone_number_id={wa_phone_number_id!r}. "
            "Register this WA phone number ID during onboarding."
        )

    contractor = db.query(Contractor).order_by(Contractor.created_at).first()
    if contractor is None:
        raise RuntimeError("No contractor found. Run scripts/seed_data.py first.")
    return contractor


def find_or_create_session(
    db: DBSession,
    contractor_id: uuid.UUID,
    buyer_phone: str,
    now: datetime,
    ttl_hours: int,
) -> SessionModel:
    """Return the latest open, unexpired session for (contractor, buyer), or create a new one."""
    existing = (
        db.query(SessionModel)
        .filter(
            SessionModel.contractor_id == contractor_id,
            SessionModel.buyer_phone == buyer_phone,
            SessionModel.state != SessionState.closed,
            (SessionModel.expires_at == None) | (SessionModel.expires_at > now),  # noqa: E711
        )
        .order_by(SessionModel.created_at.desc())
        .first()
    )
    if existing:
        return existing

    session = SessionModel(
        contractor_id=contractor_id,
        buyer_phone=buyer_phone,
        state=SessionState.greeting,
        collected_slots={},
        missing_slots=[],
        last_message_at=now,
        expires_at=now + timedelta(hours=ttl_hours),
    )
    db.add(session)
    db.flush()  # get the UUID without committing
    logger.info(
        "session.created",
        extra={
            "event_type": "session.created",
            "session_id": str(session.id),
            "contractor_id": str(contractor_id),
        },
    )
    return session


def load_active_pricing_rules(
    db: DBSession,
    contractor_id: uuid.UUID,
    work_type: WorkType,
) -> dict[str, Any]:
    config = (
        db.query(PricingConfig)
        .filter(
            PricingConfig.contractor_id == contractor_id,
            PricingConfig.work_type == work_type,
            PricingConfig.is_active == True,  # noqa: E712
        )
        .first()
    )
    if config is None:
        raise RuntimeError(
            f"No active PricingConfig for contractor {contractor_id} / {work_type}"
        )
    return config.rules


def log_message(
    db: DBSession,
    session_id: uuid.UUID,
    direction: MessageDirection,
    message_type: MessageType,
    raw_content: str | None,
    normalized_content: str | None,
    wa_message_id: str | None,
) -> Message:
    msg = Message(
        session_id=session_id,
        direction=direction,
        message_type=message_type,
        raw_content=raw_content,
        normalized_content=normalized_content,
        whatsapp_message_id=wa_message_id,
    )
    db.add(msg)
    return msg


def load_active_pricing_config(
    db: DBSession,
    contractor_id: uuid.UUID,
    work_type: WorkType,
) -> PricingConfig:
    config = (
        db.query(PricingConfig)
        .filter(
            PricingConfig.contractor_id == contractor_id,
            PricingConfig.work_type == work_type,
            PricingConfig.is_active == True,  # noqa: E712
        )
        .first()
    )
    if config is None:
        raise RuntimeError(
            f"No active PricingConfig for contractor {contractor_id} / {work_type}"
        )
    return config


def create_quote(
    db: DBSession,
    session: SessionModel,
    contractor: Contractor,
    snapshot: dict[str, Any],
    pricing_config_version: int,
    validity_days: int = 30,
) -> Quote:
    """Persist a Quote row from an EvaluatedQuote snapshot. Status → pending_approval."""
    from app.db.enums import WorkType as WT

    work_type = session.work_type or WT.painting
    line_items = snapshot.get("line_items", [])
    # Snapshots from EvaluatedQuote use Decimal-serialised strings; normalise to str for JSONB.
    serialised_items = [
        {k: str(v) if isinstance(v, Decimal) else v for k, v in item.items()}
        for item in line_items
    ]

    quote = Quote(
        session_id=session.id,
        contractor_id=contractor.id,
        buyer_phone=session.buyer_phone,
        work_type=work_type,
        line_items=serialised_items,
        subtotal=Decimal(str(snapshot["subtotal"])),
        gst_amount=Decimal(str(snapshot["gst_amount"])),
        total=Decimal(str(snapshot["total"])),
        confidence_score=float(snapshot.get("confidence_score", 1.0)),
        status=QuoteStatus.pending_approval,
        validity_date=date.today() + timedelta(days=validity_days),
        pricing_config_version=pricing_config_version,
    )
    db.add(quote)
    db.flush()
    logger.info(
        "quote.persisted",
        extra={
            "event_type": "quote.persisted",
            "quote_id": str(quote.id),
            "session_id": str(session.id),
            "total": str(quote.total),
        },
    )
    return quote


def update_quote_pdf_url(db: DBSession, quote: Quote, pdf_url: str) -> None:
    quote.pdf_url = pdf_url


def find_pending_quote_for_contractor(
    db: DBSession, contractor_id: uuid.UUID
) -> Quote | None:
    return (
        db.query(Quote)
        .filter(
            Quote.contractor_id == contractor_id,
            Quote.status == QuoteStatus.pending_approval,
        )
        .order_by(Quote.created_at.asc())
        .first()
    )


def apply_handler_result(
    session: SessionModel,
    new_state: SessionState,
    collected_slots_update: dict[str, Any],
    missing_slots: list[str] | None,
    work_type: WorkType | None,
    now: datetime,
    ttl_hours: int,
) -> None:
    """Apply state transition + slot updates to the session row in-place."""
    old_state = session.state
    session.state = new_state
    if collected_slots_update:
        session.collected_slots = {**session.collected_slots, **collected_slots_update}
    if missing_slots is not None:
        session.missing_slots = missing_slots
    if work_type is not None:
        session.work_type = work_type
    session.last_message_at = now
    session.expires_at = now + timedelta(hours=ttl_hours)

    if old_state != new_state:
        logger.info(
            "state.transition",
            extra={
                "event_type": "state.transition",
                "session_id": str(session.id),
                "from_state": old_state,
                "to_state": new_state,
            },
        )
