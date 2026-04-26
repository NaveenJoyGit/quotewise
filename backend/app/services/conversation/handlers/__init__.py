"""State handler registry (SPEC §5.2 strategy pattern).

One handler per SessionState. Handlers are pure — they return HandlerResult
and never touch the DB or WA client directly. The engine does I/O.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.db.enums import SessionState
from app.db.models import Session as SessionModel
from app.services.conversation.types import HandlerDeps, HandlerResult
from app.services.whatsapp.payload import InboundMessage


class StateHandler(ABC):
    @abstractmethod
    def handle(
        self,
        session: SessionModel,
        inbound: InboundMessage,
        deps: HandlerDeps,
    ) -> HandlerResult:
        ...


class UnknownStateError(Exception):
    pass


def _build_registry() -> dict[SessionState, StateHandler]:
    from app.services.conversation.handlers.awaiting_approval import AwaitingApprovalHandler
    from app.services.conversation.handlers.collecting_inputs import CollectingInputsHandler
    from app.services.conversation.handlers.greeting import GreetingHandler
    from app.services.conversation.handlers.identifying_scope import IdentifyingScopeHandler
    from app.services.conversation.handlers.quote_delivered import QuoteDeliveredHandler
    from app.services.conversation.handlers.ready_to_quote import ReadyToQuoteHandler

    return {
        SessionState.greeting: GreetingHandler(),
        SessionState.identifying_scope: IdentifyingScopeHandler(),
        SessionState.collecting_inputs: CollectingInputsHandler(),
        SessionState.ready_to_quote: ReadyToQuoteHandler(),
        SessionState.awaiting_approval: AwaitingApprovalHandler(),
        SessionState.quote_delivered: QuoteDeliveredHandler(),
    }


_registry: dict[SessionState, StateHandler] | None = None


def get_handler(state: SessionState) -> StateHandler:
    global _registry
    if _registry is None:
        _registry = _build_registry()
    handler = _registry.get(state)
    if handler is None:
        raise UnknownStateError(
            f"No handler for state '{state}'. "
            "This state is deferred to a later milestone (M4/M6)."
        )
    return handler
