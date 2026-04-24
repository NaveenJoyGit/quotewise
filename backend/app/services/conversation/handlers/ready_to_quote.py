"""READY_TO_QUOTE handler — compute the quote, log it, ack the buyer (SPEC §10.3)."""
from __future__ import annotations

import logging
from dataclasses import asdict

from app.db.enums import SessionState
from app.db.models import Session as SessionModel
from app.services.conversation.handlers import StateHandler
from app.services.conversation.types import HandlerDeps, HandlerResult
from app.services.pricing.evaluator import evaluate_quote
from app.services.whatsapp.payload import InboundMessage

logger = logging.getLogger(__name__)

_BUYER_ACK = (
    "Thanks — I've got all the details. "
    "Your contractor will confirm the quote shortly."
)


class ReadyToQuoteHandler(StateHandler):
    def handle(
        self,
        session: SessionModel,
        inbound: InboundMessage,
        deps: HandlerDeps,
    ) -> HandlerResult:
        quote = evaluate_quote(deps.pricing_rules, session.collected_slots or {})
        snapshot = asdict(quote)

        logger.info(
            "quote.generated",
            extra={
                "event_type": "quote.generated",
                "session_id": str(session.id),
                "contractor_id": str(session.contractor_id),
                "payload": snapshot,
            },
        )

        return HandlerResult(
            new_state=SessionState.ready_to_quote,
            outbound_text=_BUYER_ACK,
            quote_snapshot=snapshot,
        )
