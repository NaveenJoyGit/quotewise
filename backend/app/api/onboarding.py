"""Onboarding API — contractor signup, rate card parsing, pricing config save (SPEC §10.5)."""
from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session as DBSession

from app.api.deps import get_current_contractor, get_db
from app.db.enums import ApprovalMode
from app.db.models import Contractor
from app.services.llm.base import LLMParseError
from app.services.llm.factory import get_llm_client
from app.services.onboarding.service import DuplicateError, OnboardingService
from app.services.rate_card.extractor import UnsupportedFormatError, extract_text
from app.services.rate_card.parser import RateCardParser

router = APIRouter(prefix="/api/v1", tags=["onboarding"])

_E164_RE = re.compile(r"^\+\d{10,15}$")
_SLUG_RE = re.compile(r"^[a-z0-9-]{3,64}$")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ContractorCreateRequest(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=255)
    phone: str
    city: str | None = None
    whatsapp_link_slug: str
    gst_number: str | None = None
    approval_mode: str = "always_approve"
    wa_phone_number_id: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not _E164_RE.match(v):
            raise ValueError("Phone must be E.164 format, e.g. +919876543210")
        return v

    @field_validator("whatsapp_link_slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "Slug must be 3–64 lowercase alphanumeric characters or hyphens, e.g. 'my-business'"
            )
        return v

    @field_validator("approval_mode")
    @classmethod
    def validate_approval_mode(cls, v: str) -> str:
        valid = {m.value for m in ApprovalMode}
        if v not in valid:
            raise ValueError(f"approval_mode must be one of: {sorted(valid)}")
        return v


class ContractorResponse(BaseModel):
    id: uuid.UUID
    business_name: str
    phone: str
    city: str | None
    whatsapp_link_slug: str
    gst_number: str | None
    api_key: uuid.UUID


class ParsedRulesResponse(BaseModel):
    rules: dict[str, Any]
    work_type_hint: str | None
    notes: list[str]
    validation_errors: list[str]


class PricingConfigSaveRequest(BaseModel):
    rules: dict[str, Any]


class PricingConfigResponse(BaseModel):
    id: uuid.UUID
    contractor_id: uuid.UUID
    work_type: str
    version: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/onboarding/contractors", response_model=ContractorResponse, status_code=201)
def create_contractor(
    req: ContractorCreateRequest,
    db: DBSession = Depends(get_db),
) -> ContractorResponse:
    """Step 1 of onboarding: create a contractor account."""
    svc = OnboardingService(db)
    try:
        contractor = svc.create_contractor(
            business_name=req.business_name,
            phone=req.phone,
            city=req.city,
            whatsapp_link_slug=req.whatsapp_link_slug,
            gst_number=req.gst_number,
            approval_mode=req.approval_mode,
            wa_phone_number_id=req.wa_phone_number_id,
        )
        db.commit()
    except DuplicateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return ContractorResponse(
        id=contractor.id,
        business_name=contractor.business_name,
        phone=contractor.phone,
        city=contractor.city,
        whatsapp_link_slug=contractor.whatsapp_link_slug,
        gst_number=contractor.gst_number,
        api_key=contractor.api_key,
    )


@router.post("/onboarding/rate-card/parse", response_model=ParsedRulesResponse)
async def parse_rate_card(
    file: UploadFile,
    work_type_hint: str | None = None,
) -> ParsedRulesResponse:
    """Step 2 of onboarding: upload a rate card file and parse it with Gemini Pro."""
    file_bytes = await file.read()
    filename = file.filename or "upload"

    try:
        text = extract_text(file_bytes, filename)
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    llm = get_llm_client(model="pro")
    try:
        result = RateCardParser(llm).parse(text, work_type_hint=work_type_hint)
    except LLMParseError as exc:
        raise HTTPException(status_code=502, detail=f"AI parsing failed: {exc}")

    return ParsedRulesResponse(
        rules=result.rules,
        work_type_hint=work_type_hint,
        notes=result.notes,
        validation_errors=result.validation_errors,
    )


@router.post(
    "/contractors/{contractor_id}/pricing/{work_type}",
    response_model=PricingConfigResponse,
)
def save_pricing_config(
    contractor_id: uuid.UUID,
    work_type: str,
    req: PricingConfigSaveRequest,
    auth_contractor: Contractor = Depends(get_current_contractor),
    db: DBSession = Depends(get_db),
) -> PricingConfigResponse:
    """Step 3 of onboarding: save (or replace) a pricing config for a work type."""
    if auth_contractor.id != contractor_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to update this contractor's pricing.",
        )

    from pydantic import ValidationError as PydanticValidationError

    svc = OnboardingService(db)
    try:
        config = svc.save_pricing_config(
            contractor_id=contractor_id,
            work_type=work_type,
            rules=req.rules,
        )
        db.commit()
    except PydanticValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
    return PricingConfigResponse(
        id=config.id,
        contractor_id=config.contractor_id,
        work_type=config.work_type,
        version=config.version,
    )
