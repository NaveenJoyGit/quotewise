"""DB helpers for contractor admin sessions (FR-001)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session as DBSession

from app.db.enums import AdminFlowType, AdminSessionState
from app.db.models import AuditLog, ContractorAdminSession
from app.services.whatsapp.phone import normalize_phone_e164

logger = logging.getLogger(__name__)

_TERMINAL = frozenset({AdminSessionState.completed, AdminSessionState.cancelled})


def find_active_session(
    db: DBSession, admin_phone: str, now: datetime
) -> ContractorAdminSession | None:
    phone = normalize_phone_e164(admin_phone)
    return (
        db.query(ContractorAdminSession)
        .filter(
            ContractorAdminSession.admin_phone == phone,
            ContractorAdminSession.state.notin_(_TERMINAL),
            (ContractorAdminSession.expires_at == None)  # noqa: E711
            | (ContractorAdminSession.expires_at > now),
        )
        .order_by(ContractorAdminSession.created_at.desc())
        .first()
    )


def create_session(
    db: DBSession,
    *,
    admin_phone: str,
    flow_type: AdminFlowType,
    initial_state: AdminSessionState,
    contractor_id: uuid.UUID | None,
    work_type: str | None,
    now: datetime,
    ttl_hours: int,
) -> ContractorAdminSession:
    session = ContractorAdminSession(
        admin_phone=normalize_phone_e164(admin_phone),
        flow_type=flow_type,
        state=initial_state,
        contractor_id=contractor_id,
        work_type=work_type,
        draft_rules=None,
        draft_profile={} if flow_type == AdminFlowType.onboard else None,
        parse_notes=[],
        validation_errors=[],
        expires_at=now + timedelta(hours=ttl_hours),
    )
    db.add(session)
    db.flush()
    logger.info(
        "admin_session.created",
        extra={
            "event_type": "admin_session.created",
            "session_id": str(session.id),
            "flow_type": flow_type.value,
        },
    )
    return session


def close_session(session: ContractorAdminSession, state: AdminSessionState) -> None:
    session.state = state


def log_pricing_updated(
    db: DBSession,
    contractor_id: uuid.UUID,
    work_type: str,
    version: int,
) -> None:
    db.add(
        AuditLog(
            contractor_id=contractor_id,
            event_type="pricing.updated",
            payload={
                "source": "whatsapp_admin",
                "work_type": work_type,
                "version": version,
            },
        )
    )
