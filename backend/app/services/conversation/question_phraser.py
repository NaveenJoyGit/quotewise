"""QuestionPhraser — single responsibility: pick the next slot question text (SPEC §4.1 USE CASE 2)."""
from __future__ import annotations

import logging
from typing import Any

from app.services.llm.base import LLMClient, LLMError
from app.services.pricing.schemas import InputDef

logger = logging.getLogger(__name__)


class QuestionPhraser:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def phrase_next(
        self,
        slot_def: InputDef,
        business_name: str,
        collected_so_far: dict[str, Any],
        proxy_mode: bool = False,
    ) -> str:
        """Return a conversationally phrased question for slot_def.

        Falls back to slot_def.question_template on any LLM error or empty response.
        A turn must never fail because of a phrasing hiccup.
        """
        fallback = slot_def.question_template or f"Could you tell me the {slot_def.name}?"
        if proxy_mode and fallback:
            fallback = f"For the buyer's enquiry: {fallback}"

        slot_context = {
            "name": slot_def.name,
            "type": slot_def.type,
            "options": slot_def.options,
            "validation": (
                {"min": slot_def.validation.min, "max": slot_def.validation.max}
                if slot_def.validation
                else None
            ),
            "question_template": slot_def.question_template or "",
        }

        try:
            resp = self._llm.generate_text(
                "question_phrasing",
                {
                    "slot_def": slot_context,
                    "business_name": business_name,
                    "collected_so_far": collected_so_far,
                    "proxy_mode": proxy_mode,
                },
            )
            text = resp.text.strip()
        except LLMError:
            logger.warning(
                "question_phrasing.llm_error",
                extra={"event_type": "question_phrasing.llm_error", "slot": slot_def.name},
            )
            return fallback

        return text if text else fallback
