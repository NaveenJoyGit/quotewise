"""OnboardingService — create contractors and persist pricing configs (SPEC §10.5)."""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session as DBSession

from app.db.models import Contractor, PricingConfig
from app.services.pricing.schemas import PricingRules


class DuplicateError(ValueError):
    """Raised when a contractor with the same phone or slug already exists."""


class OnboardingService:
    def __init__(self, db: DBSession) -> None:
        self._db = db

    def create_contractor(
        self,
        business_name: str,
        phone: str,
        city: str | None,
        whatsapp_link_slug: str,
        gst_number: str | None = None,
        approval_mode: str = "always_approve",
        wa_phone_number_id: str | None = None,
    ) -> Contractor:
        if self._db.query(Contractor).filter(Contractor.phone == phone).first():
            raise DuplicateError(f"A contractor with phone {phone} already exists.")
        if (
            self._db.query(Contractor)
            .filter(Contractor.whatsapp_link_slug == whatsapp_link_slug)
            .first()
        ):
            raise DuplicateError(
                f"The slug '{whatsapp_link_slug}' is already taken. Choose a different one."
            )

        from app.db.enums import ApprovalMode
        mode = ApprovalMode(approval_mode) if approval_mode else ApprovalMode.always_approve

        contractor = Contractor(
            phone=phone,
            business_name=business_name,
            city=city,
            whatsapp_link_slug=whatsapp_link_slug,
            gst_number=gst_number,
            approval_mode=mode,
            wa_phone_number_id=wa_phone_number_id,
        )
        self._db.add(contractor)
        self._db.flush()
        return contractor

    def save_pricing_config(
        self,
        contractor_id: uuid.UUID,
        work_type: str,
        rules: dict[str, Any],
    ) -> PricingConfig:
        """Validate and persist a pricing config. Deactivates any existing active config."""
        PricingRules.model_validate(rules)  # Raises ValidationError on invalid rules.

        existing = (
            self._db.query(PricingConfig)
            .filter(
                PricingConfig.contractor_id == contractor_id,
                PricingConfig.work_type == work_type,
                PricingConfig.is_active == True,  # noqa: E712
            )
            .first()
        )
        new_version = (existing.version + 1) if existing else 1
        if existing:
            existing.is_active = False

        config = PricingConfig(
            contractor_id=contractor_id,
            work_type=work_type,
            is_active=True,
            rules=rules,
            version=new_version,
        )
        self._db.add(config)
        self._db.flush()
        return config
