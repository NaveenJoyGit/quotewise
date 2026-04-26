"""AWAITING_APPROVAL handler — buyer messages while contractor is reviewing."""
from __future__ import annotations

from app.db.enums import SessionState
from app.db.models import Session as SessionModel
from app.services.conversation.handlers import StateHandler
from app.services.conversation.types import HandlerDeps, HandlerResult
from app.services.whatsapp.payload import InboundMessage

_HOLD_MESSAGE = (
    "Your quote is being reviewed by the contractor. "
    "We'll send it to you shortly!"
)


class AwaitingApprovalHandler(StateHandler):
    def handle(
        self,
        session: SessionModel,
        inbound: InboundMessage,
        deps: HandlerDeps,
    ) -> HandlerResult:
        return HandlerResult(
            new_state=SessionState.awaiting_approval,
            outbound_text=_HOLD_MESSAGE,
        )
