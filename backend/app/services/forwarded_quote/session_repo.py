"""DB helpers for contractor-forward quote sessions (FR-002)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session as DBSession

from app.db.enums import SessionSource, SessionState
from app.db.models import Session as SessionModel

logger = logging.getLogger(__name__)

_TERMINAL = frozenset({SessionState.quote_delivered, SessionState.closed})


def find_active_forward_session(
    db: DBSession,
    contractor_id: uuid.UUID,
    now: datetime,
) -> SessionModel | None:
    return (
        db.query(SessionModel)
        .filter(
            SessionModel.contractor_id == contractor_id,
            SessionModel.source == SessionSource.contractor_forward,
            SessionModel.state.notin_(_TERMINAL),
            (SessionModel.expires_at == None)  # noqa: E711
            | (SessionModel.expires_at > now),
        )
        .order_by(SessionModel.created_at.desc())
        .first()
    )


def create_forward_session(
    db: DBSession,
    contractor_id: uuid.UUID,
    now: datetime,
    ttl_hours: int,
    first_wa_message_id: str | None,
) -> SessionModel:
    session = SessionModel(
        contractor_id=contractor_id,
        buyer_phone="fwd:pending",
        source=SessionSource.contractor_forward,
        state=SessionState.identifying_scope,
        collected_slots={},
        missing_slots=[],
        forward_metadata={
            "first_forward_wa_message_id": first_wa_message_id,
            "forward_count": 1,
        },
        last_message_at=now,
        expires_at=now + timedelta(hours=ttl_hours),
    )
    db.add(session)
    db.flush()
    # fwd:{uuid} is 40 chars — requires buyer_phone VARCHAR(48) (migration 0006).
    session.buyer_phone = f"fwd:{session.id}"
    logger.info(
        "forward_session.created",
        extra={
            "event_type": "forward_session.created",
            "session_id": str(session.id),
            "contractor_id": str(contractor_id),
        },
    )
    return session


def bump_forward_count(session: SessionModel) -> None:
    meta = dict(session.forward_metadata or {})
    meta["forward_count"] = int(meta.get("forward_count", 1)) + 1
    session.forward_metadata = meta
