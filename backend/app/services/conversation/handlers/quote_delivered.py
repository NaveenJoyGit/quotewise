"""QUOTE_DELIVERED handler — buyer messages after the quote PDF has been sent."""
from __future__ import annotations

from app.db.enums import SessionState
from app.db.models import Session as SessionModel
from app.services.conversation.handlers import StateHandler
from app.services.conversation.types import HandlerDeps, HandlerResult
from app.services.whatsapp.payload import InboundMessage

_DELIVERED_MESSAGE = (
    "Your quote has already been sent to you. "
    "Please check above in this chat."
)


class QuoteDeliveredHandler(StateHandler):
    def handle(
        self,
        session: SessionModel,
        inbound: InboundMessage,
        deps: HandlerDeps,
    ) -> HandlerResult:
        return HandlerResult(
            new_state=SessionState.quote_delivered,
            outbound_text=_DELIVERED_MESSAGE,
        )
