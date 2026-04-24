"""GREETING state handler — greet the buyer, advance to IDENTIFYING_SCOPE."""
from __future__ import annotations

from app.db.enums import SessionState
from app.db.models import Session as SessionModel
from app.services.conversation.handlers import StateHandler
from app.services.conversation.types import HandlerDeps, HandlerResult
from app.services.whatsapp.payload import InboundMessage

_FALLBACK = "Hi! I'm here to help you get a painting quote. What space would you like painted?"


class GreetingHandler(StateHandler):
    def handle(
        self,
        session: SessionModel,
        inbound: InboundMessage,
        deps: HandlerDeps,
    ) -> HandlerResult:
        resp = deps.llm.generate_text(
            "greeting",
            {"business_name": deps.business_name},
        )
        text = resp.text.strip() or _FALLBACK
        return HandlerResult(
            new_state=SessionState.identifying_scope,
            outbound_text=text,
        )
