"""SlotExtractor — single responsibility: LLM text → validated slot dict (SPEC §4.1 USE CASE 1)."""
from __future__ import annotations

import logging
from typing import Any

from app.services.llm.base import LLMClient, LLMError
from app.services.pricing.errors import InvalidSlotValueError
from app.services.pricing.evaluator import validate_slot_value
from app.services.pricing.schemas import InputDef

logger = logging.getLogger(__name__)


class SlotExtractor:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def extract(
        self,
        message: str,
        missing_slot_defs: list[InputDef],
        collected_so_far: dict[str, Any],
    ) -> dict[str, Any]:
        """Return validated slot values extracted from message.

        Values that fail type/range validation are dropped and logged — not propagated.
        """
        if not missing_slot_defs:
            return {}

        slot_context = [
            {
                "name": d.name,
                "type": d.type,
                "options": d.options,
                "validation": (
                    {"min": d.validation.min, "max": d.validation.max}
                    if d.validation
                    else None
                ),
            }
            for d in missing_slot_defs
        ]

        try:
            resp = self._llm.extract_json(
                "slot_extraction",
                {
                    "slot_defs": slot_context,
                    "buyer_message": message,
                    "collected": collected_so_far,
                },
            )
            raw = resp.data
        except LLMError:
            logger.warning("slot.extraction.llm_error", extra={"event_type": "slot.extraction.llm_error"})
            return {}

        defs_by_name = {d.name: d for d in missing_slot_defs}
        result: dict[str, Any] = {}

        for name, value in raw.items():
            if value is None:
                continue
            idef = defs_by_name.get(name)
            if idef is None:
                continue

            # Coerce string representations of numbers (LLMs sometimes return "1000")
            value = _coerce_numeric(idef, value)

            try:
                validated = validate_slot_value(idef, value)
            except InvalidSlotValueError as exc:
                logger.warning(
                    "slot.extraction.invalid",
                    extra={
                        "event_type": "slot.extraction.invalid",
                        "slot": name,
                        "value": str(value),
                        "reason": str(exc),
                    },
                )
                continue

            result[name] = validated

        return result


def _coerce_numeric(idef: InputDef, value: Any) -> Any:
    if idef.type == "number" and isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
    if idef.type == "integer" and isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    return value
