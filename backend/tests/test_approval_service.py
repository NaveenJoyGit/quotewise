"""Unit tests for ApprovalService — mocked DB, WA client, and PDF service."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from app.db.enums import QuoteStatus, SessionState
from app.services.approval.service import (
    ApprovalService,
    _BUYER_REJECTED,
    _CONTRACTOR_NO_PENDING,
    _CONTRACTOR_UNKNOWN,
)
from app.services.whatsapp.payload import InboundMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _contractor(phone="919999900001"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        phone=phone,
        business_name="Test Contractor",
        gst_number=None,
    )


def _quote(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        buyer_phone="919876543210",
        work_type="painting",
        line_items=[],
        subtotal=Decimal("22000.00"),
        gst_amount=Decimal("3960.00"),
        total=Decimal("25960.00"),
        status=QuoteStatus.pending_approval,
        pdf_url=None,
        validity_date=date(2026, 5, 25),
        approved_at=None,
        sent_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _session(state=SessionState.awaiting_approval):
    return SimpleNamespace(id=uuid.uuid4(), state=state)


def _inbound(text: str) -> InboundMessage:
    return InboundMessage(
        whatsapp_message_id="wamid.test",
        from_phone="919999900001",
        message_type="text",
        text=text,
        raw={},
    )


def _make_service(quote=None, session_obj=None, pdf_url="http://localhost:8000/pdfs/q.pdf"):
    """Build ApprovalService with mocked dependencies."""
    db = MagicMock()
    wa = MagicMock()
    pdf_svc = MagicMock()
    pdf_svc.generate.return_value = pdf_url

    # DB.get(Session, ...) returns our mock session
    db.get.return_value = session_obj or _session()

    svc = ApprovalService(db=db, wa=wa, pdf_service=pdf_svc)

    return svc, db, wa, pdf_svc


# ---------------------------------------------------------------------------
# Tests: unknown keyword
# ---------------------------------------------------------------------------

def test_unknown_keyword_sends_help_to_contractor():
    svc, db, wa, _ = _make_service()
    contractor = _contractor()

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=_quote(),
    ):
        svc.process(contractor, _inbound("maybe later"))

    wa.send_text.assert_called_once()
    args = wa.send_text.call_args
    assert args.kwargs.get("to") == contractor.phone or args.args[0] == contractor.phone
    assert "approve" in (args.kwargs.get("body") or args.args[1]).lower()


def test_unknown_keyword_does_not_change_quote_status():
    svc, db, wa, _ = _make_service()
    contractor = _contractor()
    q = _quote()

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=q,
    ):
        svc.process(contractor, _inbound("hmm"))

    # Quote status should not be mutated
    assert q.status == QuoteStatus.pending_approval
    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: no pending quote
# ---------------------------------------------------------------------------

def test_no_pending_quote_sends_message_to_contractor():
    svc, db, wa, _ = _make_service()
    contractor = _contractor()

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=None,
    ):
        svc.process(contractor, _inbound("approve"))

    wa.send_text.assert_called_once()
    body = wa.send_text.call_args.kwargs.get("body") or wa.send_text.call_args.args[1]
    assert "pending" in body.lower() or "no" in body.lower()
    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: approve path
# ---------------------------------------------------------------------------

def test_approve_sets_quote_status_to_sent():
    contractor = _contractor()
    q = _quote()
    session_obj = _session()
    svc, db, wa, _ = _make_service(quote=q, session_obj=session_obj)

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=q,
    ), patch(
        "app.services.approval.service.session_repo.update_quote_pdf_url",
    ):
        svc.process(contractor, _inbound("approve"))

    assert q.status == QuoteStatus.sent
    assert q.approved_at is not None
    assert q.sent_at is not None


def test_approve_transitions_session_to_quote_delivered():
    contractor = _contractor()
    q = _quote()
    session_obj = _session()
    svc, db, wa, _ = _make_service(quote=q, session_obj=session_obj)

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=q,
    ), patch(
        "app.services.approval.service.session_repo.update_quote_pdf_url",
    ):
        svc.process(contractor, _inbound("yes"))

    assert session_obj.state == SessionState.quote_delivered


def test_approve_calls_send_document_with_buyer_phone():
    contractor = _contractor()
    q = _quote()
    svc, db, wa, pdf_svc = _make_service(quote=q)
    pdf_url = "http://localhost:8000/pdfs/quote_abc.pdf"
    pdf_svc.generate.return_value = pdf_url

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=q,
    ), patch(
        "app.services.approval.service.session_repo.update_quote_pdf_url",
    ):
        svc.process(contractor, _inbound("send"))

    wa.send_document.assert_called_once()
    call_kwargs = wa.send_document.call_args.kwargs
    assert call_kwargs.get("to") == q.buyer_phone
    assert call_kwargs.get("document_url") == pdf_url


def test_approve_commits_db():
    contractor = _contractor()
    q = _quote()
    svc, db, wa, _ = _make_service(quote=q)

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=q,
    ), patch(
        "app.services.approval.service.session_repo.update_quote_pdf_url",
    ):
        svc.process(contractor, _inbound("ok"))

    db.commit.assert_called_once()


def test_approve_reuses_existing_pdf_url():
    contractor = _contractor()
    existing_url = "http://localhost:8000/pdfs/quote_existing.pdf"
    q = _quote(pdf_url=existing_url)
    svc, db, wa, pdf_svc = _make_service(quote=q)

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=q,
    ), patch(
        "app.services.approval.service.session_repo.update_quote_pdf_url",
    ):
        svc.process(contractor, _inbound("approve"))

    pdf_svc.generate.assert_not_called()
    wa.send_document.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: reject path
# ---------------------------------------------------------------------------

def test_reject_sets_quote_status_to_rejected():
    contractor = _contractor()
    q = _quote()
    session_obj = _session()
    svc, db, wa, _ = _make_service(quote=q, session_obj=session_obj)

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=q,
    ):
        svc.process(contractor, _inbound("reject"))

    assert q.status == QuoteStatus.rejected


def test_reject_transitions_session_to_closed():
    contractor = _contractor()
    q = _quote()
    session_obj = _session()
    svc, db, wa, _ = _make_service(quote=q, session_obj=session_obj)

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=q,
    ):
        svc.process(contractor, _inbound("no"))

    assert session_obj.state == SessionState.closed


def test_reject_sends_message_to_buyer():
    contractor = _contractor()
    q = _quote()
    svc, db, wa, _ = _make_service(quote=q)

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=q,
    ):
        svc.process(contractor, _inbound("cancel"))

    wa.send_text.assert_called_once()
    call_kwargs = wa.send_text.call_args.kwargs
    assert call_kwargs.get("to") == q.buyer_phone


def test_reject_does_not_call_send_document():
    contractor = _contractor()
    q = _quote()
    svc, db, wa, _ = _make_service(quote=q)

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=q,
    ):
        svc.process(contractor, _inbound("reject"))

    wa.send_document.assert_not_called()


def test_reject_commits_db():
    contractor = _contractor()
    q = _quote()
    svc, db, wa, _ = _make_service(quote=q)

    with patch(
        "app.services.approval.service.session_repo.find_pending_quote_for_contractor",
        return_value=q,
    ):
        svc.process(contractor, _inbound("no"))

    db.commit.assert_called_once()
