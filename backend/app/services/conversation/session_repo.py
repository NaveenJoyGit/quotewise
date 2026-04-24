"""Thin DB helpers for the conversation layer (SPEC §8.1 single responsibility).

M3: single-tenant dev — resolve_contractor returns the first contractor.
M5 debt: add wa_phone_number_id to Contractor and route by it.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.db.enums import MessageDirection, MessageType, SessionState, WorkType
from app.db.models import Contractor, Message, PricingConfig
from app.db.models import Session as SessionModel
from app.services.whatsapp.payload import InboundMessage

logger = logging.getLogger(__name__)


def resolve_contractor(db: DBSession) -> Contractor:
    """Return the first (and in M3, only) contractor.

    M5 TODO: resolve by wa_phone_number_id from the inbound payload.
    """
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
