"""Contractor approval service — processes "approve" / "reject" replies (SPEC §6).

All keyword matching is deterministic (no LLM). SPEC §6.2 is explicit:
"Pattern-match on these commands deterministically (regex/keyword). Don't use LLM for this."
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session as DBSession

from app.core.config import Settings, get_settings
from app.db.enums import QuoteStatus, SessionState
from app.db.models import AuditLog, Contractor, Quote
from app.db.models import Session as SessionModel
from app.services.approval.keywords import ApprovalAction, parse_approval_keyword
from app.services.conversation import session_repo
from app.services.pdf.service import PdfService
from app.services.whatsapp.client import WhatsAppClient
from app.services.whatsapp.payload import InboundMessage

logger = logging.getLogger(__name__)

_BUYER_REJECTED = (
    "The contractor is unable to provide a quote at this time. "
    "Thank you for your enquiry."
)
_BUYER_APPROVED_CAPTION = "Here is your quote. Please review and let us know if you have any questions."
_CONTRACTOR_UNKNOWN = (
    'Please reply "approve" to send the quote to the buyer, or "reject" to decline.'
)
_CONTRACTOR_NO_PENDING = "No pending quotes found for your account."


class ApprovalService:
    def __init__(
        self,
        db: DBSession,
        wa: WhatsAppClient,
        settings: Settings | None = None,
        pdf_service: PdfService | None = None,
    ) -> None:
        self._db = db
        self._wa = wa
        self._settings = settings or get_settings()
        self._pdf_service = pdf_service  # None → constructed on demand (real mode)

    def process(self, contractor: Contractor, inbound: InboundMessage) -> None:
        """Parse and act on a contractor's WhatsApp approval reply."""
        action = parse_approval_keyword(inbound.text or "")

        if action == ApprovalAction.unknown:
            logger.info(
                "approval.unknown_keyword",
                extra={
                    "event_type": "approval.unknown_keyword",
                    "contractor_id": str(contractor.id),
                    "text": inbound.text,
                },
            )
            self._wa.send_text(to=contractor.phone, body=_CONTRACTOR_UNKNOWN)
            return

        quote = session_repo.find_pending_quote_for_contractor(self._db, contractor.id)
        if quote is None:
            logger.warning(
                "approval.no_pending_quote",
                extra={
                    "event_type": "approval.no_pending_quote",
                    "contractor_id": str(contractor.id),
                },
            )
            self._wa.send_text(to=contractor.phone, body=_CONTRACTOR_NO_PENDING)
            return

        session = self._db.get(SessionModel, quote.session_id)
        now = datetime.now(timezone.utc)

        if action == ApprovalAction.approve:
            self._approve(contractor, quote, session, now)
        else:
            self._reject(contractor, quote, session, now)

        self._db.commit()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _approve(
        self,
        contractor: Contractor,
        quote: Quote,
        session: SessionModel | None,
        now: datetime,
    ) -> None:
        quote.status = QuoteStatus.approved
        quote.approved_at = now

        pdf_url = self._get_pdf_url(quote, contractor)
        session_repo.update_quote_pdf_url(self._db, quote, pdf_url)

        self._wa.send_document(
            to=quote.buyer_phone,
            document_url=pdf_url,
            filename="quote.pdf",
            caption=_BUYER_APPROVED_CAPTION,
        )

        quote.status = QuoteStatus.sent
        quote.sent_at = now

        if session is not None:
            session.state = SessionState.quote_delivered

        self._log_audit(
            contractor_id=contractor.id,
            session_id=quote.session_id,
            event_type="quote.approved",
            payload={"quote_id": str(quote.id), "total": str(quote.total)},
        )
        logger.info(
            "quote.approved",
            extra={
                "event_type": "quote.approved",
                "quote_id": str(quote.id),
                "contractor_id": str(contractor.id),
            },
        )

    def _reject(
        self,
        contractor: Contractor,
        quote: Quote,
        session: SessionModel | None,
        now: datetime,
    ) -> None:
        quote.status = QuoteStatus.rejected

        self._wa.send_text(to=quote.buyer_phone, body=_BUYER_REJECTED)

        if session is not None:
            session.state = SessionState.closed

        self._log_audit(
            contractor_id=contractor.id,
            session_id=quote.session_id,
            event_type="quote.rejected",
            payload={"quote_id": str(quote.id)},
        )
        logger.info(
            "quote.rejected",
            extra={
                "event_type": "quote.rejected",
                "quote_id": str(quote.id),
                "contractor_id": str(contractor.id),
            },
        )

    def _get_pdf_url(self, quote: Quote, contractor: Contractor) -> str:
        if quote.pdf_url:
            return quote.pdf_url
        svc = self._pdf_service or PdfService(settings=self._settings)
        return svc.generate(quote, contractor)

    def _log_audit(
        self,
        contractor_id: uuid.UUID,
        session_id: uuid.UUID | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        entry = AuditLog(
            contractor_id=contractor_id,
            session_id=session_id,
            event_type=event_type,
            payload=payload,
        )
        self._db.add(entry)
