"""Idempotent dev seed: one contractor + one painting PricingConfig.

Run after `alembic upgrade head`:

    uv run python scripts/seed_data.py

Edits the placeholder phone / business_name below to your own values before
onboarding a real contractor in M5.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow running from project root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.logging import configure_logging  # noqa: E402
from app.db.base import SessionLocal  # noqa: E402
from app.db.enums import WorkType  # noqa: E402
from app.db.models import Contractor, PricingConfig  # noqa: E402
from app.services.pricing.seed_rules import PAINTING_RULES  # noqa: E402

DEV_CONTRACTOR = {
    "phone": "+919999900001",
    "business_name": "QuoteWise Dev Contractor",
    "city": "Bangalore",
    "whatsapp_link_slug": "dev",
}

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
            log.info("seed.contractor.exists", extra={"contractor_id": str(contractor.id)})

        existing = (
            session.query(PricingConfig)
            .filter_by(contractor_id=contractor.id, work_type=WorkType.painting, is_active=True)
            .one_or_none()
        )
        if existing is None:
            pc = PricingConfig(
                contractor_id=contractor.id,
                work_type=WorkType.painting,
                is_active=True,
                rules=PAINTING_RULES,
                version=1,
            )
            session.add(pc)
            log.info(
                "seed.pricing_config.created",
                extra={"contractor_id": str(contractor.id), "work_type": "painting"},
            )
        else:
            log.info(
                "seed.pricing_config.exists",
                extra={"contractor_id": str(contractor.id), "work_type": "painting"},
            )

        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    configure_logging()
    seed()
