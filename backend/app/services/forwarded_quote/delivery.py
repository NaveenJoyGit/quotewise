"""Auto-deliver forwarded quotes to the contractor (FR-002)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.core.config import Settings
from app.db.enums import QuoteStatus, SessionState
from app.db.models import AuditLog, Contractor
from app.db.models import Session as SessionModel
from app.services.conversation import session_repo
from app.services.pdf.service import PdfService
from app.services.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)


def deliver_to_contractor(
    db: DBSession,
    contractor: Contractor,
    session: SessionModel,
    snapshot: dict[str, Any],
    wa: WhatsAppClient,
    settings: Settings,
    pdf_service: PdfService | None = None,
) -> None:
    """Persist quote, generate PDF, send to contractor. No buyer approval step."""
    pc = session_repo.load_active_pricing_config(
        db, contractor.id, session.work_type or "painting"
    )
    quote = session_repo.create_quote(
        db=db,
        session=session,
        contractor=contractor,
        snapshot=snapshot,
        pricing_config_version=pc.version,
        validity_days=settings.quote_validity_days,
    )
    now = datetime.now(timezone.utc)
    quote.status = QuoteStatus.approved
    quote.approved_at = now

    svc = pdf_service or PdfService(settings=settings)
    pdf_url = svc.generate(quote, contractor)
    session_repo.update_quote_pdf_url(db, quote, pdf_url)

    work = session.work_type if session.work_type else "painting"
    summary = (
        f"Quote ready (forwarded enquiry)\n\n"
        f"Work: {work}\n"
        f"Total: Rs. {quote.total}\n\n"
        "PDF attached — share with your buyer."
    )
    wa.send_text(to=contractor.phone, body=summary)
    wa.send_document(
        to=contractor.phone,
        document_url=pdf_url,
        filename="quote.pdf",
        caption="Quote for forwarded buyer enquiry",
    )

    quote.status = QuoteStatus.sent
    quote.sent_at = now
    session.state = SessionState.quote_delivered

    db.add(
        AuditLog(
            contractor_id=contractor.id,
            session_id=session.id,
            event_type="quote.delivered_to_contractor",
            payload={"quote_id": str(quote.id), "total": str(quote.total)},
        )
    )
    db.commit()
    logger.info(
        "quote.delivered_to_contractor",
        extra={
            "event_type": "quote.delivered_to_contractor",
            "quote_id": str(quote.id),
            "contractor_id": str(contractor.id),
        },
    )
