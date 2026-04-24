"""IDENTIFYING_SCOPE handler — hardcode painting in M3, ask the first slot question."""
from __future__ import annotations

from app.db.enums import SessionState, WorkType
from app.db.models import Session as SessionModel
from app.services.conversation.handlers import StateHandler
from app.services.conversation.question_phraser import QuestionPhraser
from app.services.conversation.types import HandlerDeps, HandlerResult
from app.services.pricing.schemas import PricingRules
from app.services.whatsapp.payload import InboundMessage


class IdentifyingScopeHandler(StateHandler):
    def handle(
        self,
        session: SessionModel,
        inbound: InboundMessage,
        deps: HandlerDeps,
    ) -> HandlerResult:
        # M3: work_type is hardcoded to painting.
        # M5/M6 TODO: use LLM to detect work_type from buyer's message.
        work_type = WorkType.painting

        parsed = PricingRules.model_validate(deps.pricing_rules)

        # Required slots with no default value — preserve input order (SPEC §3.2).
        missing_slots = [
            i.name
            for i in parsed.inputs
            if i.required and i.default is None
        ]

        # Phrase the first question.
        first_def = next(i for i in parsed.inputs if i.name == missing_slots[0])
        phraser = QuestionPhraser(deps.llm)
        question = phraser.phrase_next(first_def, deps.business_name, {})

        return HandlerResult(
            new_state=SessionState.collecting_inputs,
            outbound_text=question,
            work_type=work_type,
            missing_slots=missing_slots,
        )
