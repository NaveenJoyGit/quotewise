"""RateCardParser — uses Gemini Pro to parse rate card text into PricingRules (SPEC §4.1 USE CASE 5)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.services.llm.base import LLMClient, LLMParseError
from app.services.pricing.schemas import PricingRules

logger = logging.getLogger(__name__)


@dataclass
class ParsedRateCard:
    """Result of parsing a rate card. Always returned — never raises on validation failure."""

    rules: dict  # Raw dict from LLM (with _notes stripped)
    notes: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)


class RateCardParser:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def parse(self, text: str, work_type_hint: str | None = None) -> ParsedRateCard:
        """Parse rate card text into a ParsedRateCard.

        Raises LLMParseError if the LLM response is not valid JSON.
        Never raises on PricingRules validation failure — errors are collected into the result.
        """
        context = {
            "rate_card_content": text,
            "work_type_hint": work_type_hint or "",
        }
        # Raises LLMParseError if JSON is unparseable — let the caller handle this.
        response = self._llm.extract_json("rate_card_ingest", context)
        raw: dict = dict(response.data)

        # Extract and remove the _notes key before validation.
        notes: list[str] = []
        if "_notes" in raw:
            raw_notes = raw.pop("_notes")
            if isinstance(raw_notes, list):
                notes = [str(n) for n in raw_notes]

        # Validate the rules against the PricingRules schema.
        validation_errors: list[str] = []
        try:
            PricingRules.model_validate(raw)
        except ValidationError as exc:
            for err in exc.errors():
                loc = " → ".join(str(l) for l in err["loc"])
                validation_errors.append(f"{loc}: {err['msg']}")

        result = ParsedRateCard(rules=raw, notes=notes, validation_errors=validation_errors)
        logger.info(
            "rate_card.parsed",
            extra={
                "event_type": "rate_card.parsed",
                "notes_count": len(notes),
                "validation_errors_count": len(validation_errors),
            },
        )
        return result
