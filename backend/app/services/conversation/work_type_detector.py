"""WorkTypeDetector — LLM-based work type classification (SPEC §4.1, USE CASE 1 variant).

Only called when a contractor has 2+ active work types. If a single work type
is configured, IdentifyingScopeHandler uses it directly with no LLM call.
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.llm.base import LLMClient, LLMError

logger = logging.getLogger(__name__)


class WorkTypeDetector:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def detect(
        self,
        buyer_message: str,
        available_work_types: list[str],
        business_name: str,
    ) -> str | None:
        """Return the detected WorkType, or None if ambiguous / parse failure."""
        context: dict[str, Any] = {
            "buyer_message": buyer_message,
            "available_work_types": available_work_types,
            "business_name": business_name,
        }
        try:
            response = self._llm.extract_json("work_type_detection", context)
        except LLMError as exc:
            logger.warning(
                "work_type.detection_failed",
                extra={"event_type": "work_type.detection_failed", "error": str(exc)},
            )
            return None

        raw = response.data.get("work_type", "unclear")
        if raw == "unclear":
            return None

        # Validate the returned string is actually a known work type for this contractor.
        for wt in available_work_types:
            if wt == raw:
                logger.info(
                    "work_type.detected",
                    extra={
                        "event_type": "work_type.detected",
                        "work_type": raw,
                    },
                )
                return wt

        logger.warning(
            "work_type.detection_invalid",
            extra={
                "event_type": "work_type.detection_invalid",
                "returned": raw,
                "available": available_work_types,
            },
        )
        return None
