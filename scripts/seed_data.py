"""Idempotent dev seed: one contractor + painting + false_ceiling PricingConfigs.

Run after `alembic upgrade head`:

    uv run python scripts/seed_data.py

The WA_PHONE_NUMBER_ID env var (if set) is stored on the contractor so the
multi-tenant webhook routing added in M5 can resolve the right contractor.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Allow running from project root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.logging import configure_logging  # noqa: E402
from app.db.base import SessionLocal  # noqa: E402
from app.db.enums import WorkType  # noqa: E402
from app.db.models import Contractor, PricingConfig  # noqa: E402
from app.services.pricing.seed_rules import FALSE_CEILING_RULES, PAINTING_RULES  # noqa: E402

DEV_CONTRACTOR = {
    "phone": "+919999900001",
    "business_name": "QuoteWise Dev Contractor",
    "city": "Bangalore",
    "whatsapp_link_slug": "dev",
    "wa_phone_number_id": os.environ.get("WA_PHONE_NUMBER_ID", "dev-phone-number-id"),
}

WORK_TYPES = [
    (WorkType.painting, PAINTING_RULES),
    (WorkType.false_ceiling, FALSE_CEILING_RULES),
]

log = logging.getLogger(__name__)


def seed() -> None:
    session = SessionLocal()
    try:
        contractor = (
            session.query(Contractor).filter_by(phone=DEV_CONTRACTOR["phone"]).one_or_none()
        )
        if contractor is None:
            contractor = Contractor(**DEV_CONTRACTOR)
            session.add(contractor)
            session.flush()
            log.info("seed.contractor.created", extra={"contractor_id": str(contractor.id)})
        else:
            # Update wa_phone_number_id in case env changed.
            contractor.wa_phone_number_id = DEV_CONTRACTOR["wa_phone_number_id"]
            log.info("seed.contractor.exists", extra={"contractor_id": str(contractor.id)})

        for work_type, rules in WORK_TYPES:
            existing = (
                session.query(PricingConfig)
                .filter_by(
                    contractor_id=contractor.id,
                    work_type=work_type,
                    is_active=True,
                )
                .one_or_none()
            )
            if existing is None:
                pc = PricingConfig(
                    contractor_id=contractor.id,
                    work_type=work_type,
                    is_active=True,
                    rules=rules,
                    version=1,
                )
                session.add(pc)
                log.info(
                    "seed.pricing_config.created",
                    extra={"contractor_id": str(contractor.id), "work_type": work_type.value},
                )
            else:
                log.info(
                    "seed.pricing_config.exists",
                    extra={"contractor_id": str(contractor.id), "work_type": work_type.value},
                )

        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    configure_logging()
    seed()
