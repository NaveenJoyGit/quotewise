"""Routing helpers for contractor admin WhatsApp flows (FR-001)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from app.db.models import Contractor
from app.services.contractor_admin.prefix import parse_admin_prefix
from app.services.contractor_admin import session_repo as admin_repo
from app.services.whatsapp.payload import InboundMessage


def should_route_admin(
    db: DBSession,
    msg: InboundMessage,
    registered: Contractor | None,
) -> bool:
    """True if this message should go to ContractorAdminEngine."""
    now = datetime.now(timezone.utc)
    if admin_repo.find_active_session(db, msg.from_phone, now) is not None:
        return True
    if msg.message_type != "text" or not msg.text:
        return False
    prefix = parse_admin_prefix(msg.text)
    if prefix is None:
        return False
    # Route manage-rates even when unregistered so we can send a clear rejection.
    return True


def resolve_admin_contractor(
    registered: Contractor | None,
    tenant_contractor: Contractor,
) -> Contractor | None:
    """Contractor context for admin engine (registered sender or session-linked tenant)."""
    return registered or tenant_contractor
