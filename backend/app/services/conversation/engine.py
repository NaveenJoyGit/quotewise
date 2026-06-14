"""ConversationEngine — orchestrator that wires DB, LLM, and handlers (SPEC §5).

This is the only place that touches the DB and dispatches to state handlers.
Handlers are pure and return HandlerResult; the engine owns all I/O.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy.orm import Session as DBSession

from app.core.config import Settings, get_settings
from app.db.enums import MessageDirection, MessageType, SessionSource, SessionState
from app.db.models import Contractor, Session as SessionModel
from app.services.conversation import session_repo
from app.services.conversation.handlers import UnknownStateError, get_handler
from app.services.conversation.types import HandlerDeps, HandlerResult
from app.services.llm.base import LLMClient
from app.services.whatsapp.payload import InboundMessage

logger = logging.getLogger(__name__)

_NON_TEXT_REFUSAL = (
    "I can only understand text messages for now. "
    "Please type your request and I'll be happy to help."
)
_UNKNOWN_STATE_REPLY = (
    "Your session has ended. "
    "Please start a new conversation by sending a message."
)
_MAX_CHAIN_ITERATIONS = 2


class ConversationEngine:
    def __init__(
        self,
        db: DBSession,
        llm: LLMClient,
        clock: Callable[[], datetime] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._db = db
        self._llm = llm
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._settings = settings or get_settings()
        # Populated after process() when a quote is generated; read by the task layer.
        self.pending_quote_snapshot: dict[str, Any] | None = None
        self.last_session: SessionModel | None = None

    def process(
        self,
        inbound: InboundMessage,
        *,
        contractor: Contractor | None = None,
        session: SessionModel | None = None,
    ) -> str | None:
        """Handle one inbound message; return outbound text (buyer or proxy contractor)."""
        self.pending_quote_snapshot = None
        self.last_session = None

        if inbound.message_type != "text":
            logger.info(
                "message.non_text",
                extra={
                    "event_type": "message.non_text",
                    "message_type": inbound.message_type,
                    "from_phone": inbound.from_phone,
                },
            )
            return _NON_TEXT_REFUSAL

        now = self._clock()
        contractor = contractor or session_repo.resolve_contractor(self._db)
        contractor_id = (
            contractor.id if hasattr(contractor, "id") else contractor.contractor_id
        )
        if session is None:
            session = session_repo.find_or_create_session(
                self._db,
                contractor_id,
                inbound.from_phone,
                now,
                self._settings.session_ttl_hours,
            )
        self.last_session = session
        proxy_mode = session.source == SessionSource.contractor_forward

        session_repo.log_message(
            self._db,
            session.id,
            direction=MessageDirection.inbound,
            message_type=MessageType.text,
            raw_content=inbound.text,
            normalized_content=None,
            wa_message_id=inbound.whatsapp_message_id,
        )

        available_work_types, pricing_rules_by_work_type = (
            self._load_available_work_types_and_rules(contractor)
        )

        outbound_text = ""
        for _ in range(_MAX_CHAIN_ITERATIONS):
            try:
                handler = get_handler(session.state)
            except UnknownStateError:
                logger.warning(
                    "state.unknown",
                    extra={
                        "event_type": "state.unknown",
                        "state": str(session.state),
                        "session_id": str(session.id),
                    },
                )
                outbound_text = _UNKNOWN_STATE_REPLY
                break

            pricing_rules = self._load_pricing_rules(session, contractor)
            deps = HandlerDeps(
                llm=self._llm,
                now=self._clock,
                business_name=contractor.business_name,
                pricing_rules=pricing_rules,
                available_work_types=available_work_types,
                pricing_rules_by_work_type=pricing_rules_by_work_type,
                proxy_mode=proxy_mode,
            )

            result: HandlerResult = handler.handle(session, inbound, deps)

            if result.quote_snapshot is not None:
                self.pending_quote_snapshot = result.quote_snapshot

            session_repo.apply_handler_result(
                session,
                new_state=result.new_state,
                collected_slots_update=result.collected_slots_update,
                missing_slots=result.missing_slots,
                work_type=result.work_type,
                now=now,
                ttl_hours=self._settings.session_ttl_hours,
            )

            if result.outbound_text:
                outbound_text = result.outbound_text
                break
            # Empty outbound_text signals chained dispatch (e.g. collecting → ready_to_quote).

        session_repo.log_message(
            self._db,
            session.id,
            direction=MessageDirection.outbound,
            message_type=MessageType.text,
            raw_content=None,
            normalized_content=outbound_text,
            wa_message_id=None,
        )

        self._db.commit()
        return outbound_text

    def _load_available_work_types_and_rules(
        self, contractor: Any
    ) -> tuple[list, dict[str, Any]]:
        """Return (available_work_types, pricing_rules_by_work_type) for the contractor."""
        from app.db.models import PricingConfig

        contractor_id = (
            contractor.contractor_id
            if hasattr(contractor, "contractor_id")
            else contractor.id
        )
        configs = (
            self._db.query(PricingConfig)
            .filter(
                PricingConfig.contractor_id == contractor_id,
                PricingConfig.is_active == True,  # noqa: E712
            )
            .all()
        )
        available = [c.work_type for c in configs]
        rules_map = {c.work_type.value: c.rules for c in configs}
        return available, rules_map

    def _load_pricing_rules(self, session: SessionModel, contractor: Any) -> dict:
        from app.db.enums import SessionState

        # During identifying_scope the work type is not yet known — return empty dict.
        # IdentifyingScopeHandler doesn't need rules; it only needs available_work_types.
        if session.state == SessionState.identifying_scope and session.work_type is None:
            return {}

        work_type = session.work_type or "painting"
        contractor_id = (
            contractor.contractor_id
            if hasattr(contractor, "contractor_id")
            else contractor.id
        )
        return session_repo.load_active_pricing_rules(self._db, contractor_id, work_type)
