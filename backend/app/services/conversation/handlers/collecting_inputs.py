"""COLLECTING_INPUTS handler — extract slots, ask follow-ups, or advance to READY_TO_QUOTE."""
from __future__ import annotations

from app.db.enums import SessionState
from app.db.models import Session as SessionModel
from app.services.conversation.handlers import StateHandler
from app.services.conversation.question_phraser import QuestionPhraser
from app.services.conversation.slot_extractor import SlotExtractor
from app.services.conversation.types import HandlerDeps, HandlerResult
from app.services.pricing.schemas import PricingRules
from app.services.whatsapp.payload import InboundMessage


class CollectingInputsHandler(StateHandler):
    def handle(
        self,
        session: SessionModel,
        inbound: InboundMessage,
        deps: HandlerDeps,
    ) -> HandlerResult:
        parsed = PricingRules.model_validate(deps.pricing_rules)
        input_defs_by_name = {i.name: i for i in parsed.inputs}

        # Only extract against currently missing slots.
        missing_defs = [
            input_defs_by_name[name]
            for name in (session.missing_slots or [])
            if name in input_defs_by_name
        ]

        extracted = SlotExtractor(deps.llm).extract(
            inbound.text or "",
            missing_defs,
            session.collected_slots or {},
        )

        new_collected = {**(session.collected_slots or {}), **extracted}
        still_missing = [
            name for name in (session.missing_slots or [])
            if name not in new_collected
        ]

        if not still_missing:
            # All slots filled — signal chained dispatch with empty outbound_text.
            return HandlerResult(
                new_state=SessionState.ready_to_quote,
                outbound_text="",
                collected_slots_update=extracted,
                missing_slots=[],
            )

        # Still have open slots — ask the next one.
        next_name = still_missing[0]
        next_def = input_defs_by_name[next_name]
        phraser = QuestionPhraser(deps.llm)
        question = phraser.phrase_next(
            next_def, deps.business_name, new_collected, proxy_mode=deps.proxy_mode
        )

        return HandlerResult(
            new_state=SessionState.collecting_inputs,
            outbound_text=question,
            collected_slots_update=extracted,
            missing_slots=still_missing,
        )
