"""Shared types for contractor admin flows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from app.db.enums import AdminSessionState, WorkType
from app.db.models import Contractor
from app.services.llm.base import LLMClient
from app.services.onboarding.service import OnboardingService
from app.services.whatsapp.client import WhatsAppClient


@dataclass(frozen=True)
class AdminHandlerDeps:
    db: DBSession
    llm: LLMClient
    onboarding: OnboardingService
    wa: WhatsAppClient
    now: Callable[[], datetime]
    tenant_contractor: Contractor
    registered_contractor: Contractor | None


@dataclass(frozen=True)
class AdminHandlerResult:
    new_state: AdminSessionState
    outbound_text: str
    work_type: WorkType | None = None
    draft_rules: dict[str, Any] | None = None
    draft_profile: dict[str, Any] | None = None
    parse_notes: list[str] | None = None
    validation_errors: list[str] | None = None
    contractor_id: Any = None  # uuid after signup
