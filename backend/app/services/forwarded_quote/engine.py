"""ForwardedQuoteEngine — proxy buyer conversation for forwarded messages (FR-002)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session as DBSession

from app.core.config import Settings, get_settings
from app.db.models import Contractor
from app.services.conversation.engine import ConversationEngine
from app.services.forwarded_quote import session_repo as forward_repo
from app.services.forwarded_quote.delivery import deliver_to_contractor
from app.services.llm.base import LLMClient
from app.services.whatsapp.client import WhatsAppClient
from app.services.whatsapp.payload import InboundMessage

logger = logging.getLogger(__name__)

_INTRO_ACK = (
    "Got it — I'll ask you anything that's missing from the buyer's message, "
    "then send the quote PDF here."
)
_NON_TEXT = (
    "For forwarded quotes I need text only. "
    "Forward the buyer's text message, or type the enquiry details."
)
_HELP_IDLE = (
    "Forward a buyer's WhatsApp message to get a quote, "
    "or send manage-rates / onboard for account setup."
)


class ForwardedQuoteEngine:
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

    def process(self, contractor: Contractor, inbound: InboundMessage) -> None:
        """Handle one contractor message (forwarded or follow-up). Sends replies to contractor."""
        now = self._clock()
        session = forward_repo.find_active_forward_session(self._db, contractor.id, now)

        if session is None:
            if inbound.message_type != "text":
                self._wa.send_text(to=contractor.phone, body=_NON_TEXT)
                return
            session = forward_repo.create_forward_session(
                self._db,
                contractor.id,
                now,
                self._settings.session_ttl_hours,
                inbound.whatsapp_message_id,
            )
            self._db.commit()
            self._wa.send_text(to=contractor.phone, body=_INTRO_ACK)
        elif inbound.is_forwarded:
            forward_repo.bump_forward_count(session)

        if inbound.message_type != "text":
            self._wa.send_text(to=contractor.phone, body=_NON_TEXT)
            return

        conv = ConversationEngine(
            db=self._db, llm=self._llm, clock=self._clock, settings=self._settings
        )
        outbound = conv.process(inbound, contractor=contractor, session=session)
        if outbound:
            self._wa.send_text(to=contractor.phone, body=outbound)

        if conv.pending_quote_snapshot is not None and conv.last_session is not None:
            deliver_to_contractor(
                self._db,
                contractor,
                conv.last_session,
                conv.pending_quote_snapshot,
                self._wa,
                self._settings,
            )
