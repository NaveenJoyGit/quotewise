"""Tests for forwarded quote auto-delivery (FR-002)."""
from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.db.enums import SessionSource, SessionState, WorkType
from app.db.models import Session as SessionModel
from app.services.forwarded_quote.delivery import deliver_to_contractor
from tests.test_onboarding_api import _VALID_RULES


def test_deliver_to_contractor_sends_pdf():
    contractor = SimpleNamespace(
        id=uuid.uuid4(),
        phone="+919999900001",
        business_name="Test Co",
    )
    session = SessionModel(
        id=uuid.uuid4(),
        contractor_id=contractor.id,
        buyer_phone="fwd:abc",
        source=SessionSource.contractor_forward,
        state=SessionState.ready_to_quote,
        work_type=WorkType.painting,
        collected_slots={},
        missing_slots=[],
    )
    snapshot = {
        "subtotal": Decimal("1000"),
        "gst_amount": Decimal("180"),
        "total": Decimal("1180"),
        "line_items": [],
        "confidence_score": 1.0,
    }
    db = MagicMock()
    wa = MagicMock()
    settings = MagicMock(quote_validity_days=30)

    fake_pc = SimpleNamespace(version=1)
    fake_quote = SimpleNamespace(
        id=uuid.uuid4(),
        total=Decimal("1180"),
        pdf_url=None,
        status=None,
        approved_at=None,
        sent_at=None,
    )

    with patch("app.services.forwarded_quote.delivery.session_repo") as repo:
        repo.load_active_pricing_config.return_value = fake_pc
        repo.create_quote.return_value = fake_quote
        with patch("app.services.forwarded_quote.delivery.PdfService") as PdfCls:
            PdfCls.return_value.generate.return_value = "http://example.com/q.pdf"
            deliver_to_contractor(db, contractor, session, snapshot, wa, settings)

    wa.send_text.assert_called_once()
    wa.send_document.assert_called_once()
    assert session.state == SessionState.quote_delivered
