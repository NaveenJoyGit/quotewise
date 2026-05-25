"""ContractorAdminEngine — WhatsApp onboarding and pricing updates (FR-001)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy.orm import Session as DBSession

from app.core.config import Settings, get_settings
from app.db.enums import AdminSessionState
from app.db.models import Contractor
from app.services.contractor_admin import session_repo as admin_repo
from app.services.contractor_admin.handlers import handle_message, handle_start
from app.services.contractor_admin.prefix import parse_admin_prefix
from app.services.contractor_admin.types import AdminHandlerDeps
from app.services.llm.base import LLMClient
from app.services.onboarding.service import OnboardingService
from app.services.whatsapp.client import WhatsAppClient
from app.services.whatsapp.payload import InboundMessage
from app.services.whatsapp.phone import normalize_phone_e164

logger = logging.getLogger(__name__)


class ContractorAdminEngine:
    def __init__(
        self,
        db: DBSession,
        llm: LLMClient,
        wa: WhatsAppClient,
        clock: Callable[[], datetime] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._db = db
        self._llm = llm
        self._wa = wa
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._settings = settings or get_settings()

    def process(
        self,
        inbound: InboundMessage,
        tenant_contractor: Contractor,
        registered_contractor: Contractor | None,
    ) -> str | None:
        now = self._clock()
        phone = normalize_phone_e164(inbound.from_phone)
        session = admin_repo.find_active_session(self._db, phone, now)

        deps = AdminHandlerDeps(
            db=self._db,
            llm=self._llm,
            onboarding=OnboardingService(self._db),
            wa=self._wa,
            now=self._clock,
            tenant_contractor=tenant_contractor,
            registered_contractor=registered_contractor,
        )

        prefix = (
            parse_admin_prefix(inbound.text)
            if inbound.message_type == "text" and inbound.text
            else None
        )

        if session is None:
            if prefix is None:
                return None
            start_result = handle_start(prefix=prefix, deps=deps)
            if start_result.new_state in (
                AdminSessionState.cancelled,
                AdminSessionState.completed,
            ):
                return start_result.outbound_text

            session = admin_repo.create_session(
                self._db,
                admin_phone=phone,
                flow_type=prefix.flow,
                initial_state=start_result.new_state,
                contractor_id=start_result.contractor_id or (
                    registered_contractor.id if registered_contractor else None
                ),
                work_type=start_result.work_type,
                now=now,
                ttl_hours=self._settings.session_ttl_hours,
            )
            self._db.commit()
            return start_result.outbound_text

        result = handle_message(session, inbound, deps)
        self._apply_result(session, result, now)
        self._db.commit()
        return result.outbound_text

    def _apply_result(self, session, result, now: datetime) -> None:
        session.state = result.new_state
        if result.work_type is not None:
            session.work_type = result.work_type
        if result.draft_rules is not None:
            session.draft_rules = result.draft_rules
        if result.draft_profile is not None:
            session.draft_profile = result.draft_profile
        if result.parse_notes is not None:
            session.parse_notes = result.parse_notes
        if result.validation_errors is not None:
            session.validation_errors = result.validation_errors
        if result.contractor_id is not None:
            session.contractor_id = result.contractor_id
        session.expires_at = now + timedelta(hours=self._settings.session_ttl_hours)
