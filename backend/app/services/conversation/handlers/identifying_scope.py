"""IDENTIFYING_SCOPE handler — detects work type, asks the first slot question."""
from __future__ import annotations

from app.db.enums import SessionState, WorkType
from app.db.models import Session as SessionModel
from app.services.conversation.handlers import StateHandler
from app.services.conversation.question_phraser import QuestionPhraser
from app.services.conversation.types import HandlerDeps, HandlerResult
from app.services.conversation.work_type_detector import WorkTypeDetector
from app.services.pricing.schemas import PricingRules
from app.services.whatsapp.payload import InboundMessage

_WORK_TYPE_LABELS = {
    WorkType.painting: "painting",
    WorkType.false_ceiling: "false ceiling",
}


class IdentifyingScopeHandler(StateHandler):
    def handle(
        self,
        session: SessionModel,
        inbound: InboundMessage,
        deps: HandlerDeps,
    ) -> HandlerResult:
        work_type = self._resolve_work_type(session, inbound, deps)
        if work_type is None:
            # Ambiguous — ask buyer to choose and stay in this state.
            labels = " or ".join(
                _WORK_TYPE_LABELS.get(wt, wt.value) for wt in deps.available_work_types
            )
            prefix = "For the buyer's enquiry: " if deps.proxy_mode else ""
            return HandlerResult(
                new_state=SessionState.identifying_scope,
                outbound_text=(
                    f"{prefix}Are you looking for {labels} work? "
                    "Please let me know so I can get an accurate quote."
                ),
            )

        # Look up the detected work type's rules from the all-types map, falling back to
        # deps.pricing_rules (which is {} during identifying_scope but populated in tests
        # that pass pricing_rules directly).
        rules = deps.pricing_rules_by_work_type.get(work_type.value) or deps.pricing_rules
        parsed = PricingRules.model_validate(rules)

        # Required slots with no default — preserve input order (SPEC §3.2).
        missing_slots = [
            i.name
            for i in parsed.inputs
            if i.required and i.default is None
        ]

        first_def = next(i for i in parsed.inputs if i.name == missing_slots[0])
        phraser = QuestionPhraser(deps.llm)
        question = phraser.phrase_next(
            first_def, deps.business_name, {}, proxy_mode=deps.proxy_mode
        )

        return HandlerResult(
            new_state=SessionState.collecting_inputs,
            outbound_text=question,
            work_type=work_type,
            missing_slots=missing_slots,
        )

    def _resolve_work_type(
        self,
        session: SessionModel,
        inbound: InboundMessage,
        deps: HandlerDeps,
    ) -> WorkType | None:
        available = deps.available_work_types

        if not available:
            # Fallback: single-tenant dev with no config loaded yet.
            return WorkType.painting

        if len(available) == 1:
            return available[0]

        # Multiple work types — use LLM to detect from buyer message.
        return WorkTypeDetector(deps.llm).detect(
            buyer_message=inbound.text or "",
            available_work_types=available,
            business_name=deps.business_name,
        )
