"""Shared types for the conversation layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from pydantic import BaseModel

from app.db.enums import SessionState, WorkType
from app.services.llm.base import LLMClient


@dataclass(frozen=True)
class HandlerDeps:
    llm: LLMClient
    now: Callable[[], datetime]
    business_name: str
    pricing_rules: dict[str, Any]  # raw rules JSONB for the contractor+work_type


@dataclass(frozen=True)
class HandlerResult:
    new_state: SessionState
    outbound_text: str
    collected_slots_update: dict[str, Any] = field(default_factory=dict)
    missing_slots: list[str] | None = None  # None = no change
    work_type: WorkType | None = None       # None = no change
    quote_snapshot: dict[str, Any] | None = None


class ExtractedSlots(BaseModel):
    """Pydantic container for LLM-extracted slot JSON."""
    model_config = {"extra": "allow"}

    def as_dict(self) -> dict[str, Any]:
        return dict(self.model_fields_set and self.model_dump() or {})
