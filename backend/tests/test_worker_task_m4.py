"""M4 worker tests: contractor routing, quote-ready side-effects, approval dispatch."""
from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.workers.tasks import _format_contractor_notification, process_inbound_message
from tests.sample_payloads import text_message


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_CONTRACTOR_PHONE = "919999900001"
_BUYER_PHONE = "919876543210"


def _make_contractor(phone=_CONTRACTOR_PHONE):
    return SimpleNamespace(
        id=uuid.uuid4(),
        phone=phone,
        business_name="Test Contractor",
    )


def _make_mock_engine(
    outbound: str | None = "Thanks!",
    has_snapshot: bool = False,
):
    engine = MagicMock()
    engine.process.return_value = outbound
    engine.pending_quote_snapshot = {"total": Decimal("25960.00")} if has_snapshot else None
    if has_snapshot:
        engine.last_session = SimpleNamespace(
            id=uuid.uuid4(),
            buyer_phone=_BUYER_PHONE,
            work_type=None,
        )
    else:
        engine.last_session = None
    return engine


def _make_quote():
    return SimpleNamespace(
        id=uuid.uuid4(),
        total=Decimal("25960.00"),
        work_type="painting",
        buyer_phone=_BUYER_PHONE,
    )


# ---------------------------------------------------------------------------
# Context manager stack for common patches
# ---------------------------------------------------------------------------

def _common_patches(contractor, mock_engine_cls, mock_wa_cls, mock_approval_svc_cls):
    """Return a list of patch context managers for common infrastructure."""
    return [
        patch("app.db.base.SessionLocal", return_value=MagicMock()),
        patch("app.core.config.get_settings", return_value=MagicMock(quote_validity_days=30)),
        patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()),
        patch("app.services.conversation.engine.ConversationEngine", mock_engine_cls),
        patch("app.services.whatsapp.client.WhatsAppClient", mock_wa_cls),
        patch("app.services.approval.service.ApprovalService", mock_approval_svc_cls),
        patch(
            "app.services.conversation.session_repo.resolve_contractor",
            return_value=contractor,
        ),
        patch(
            "app.services.conversation.session_repo.load_active_pricing_config",
            return_value=SimpleNamespace(version=1),
        ),
        patch(
            "app.services.conversation.session_repo.create_quote",
            return_value=_make_quote(),
        ),
    ]


# ---------------------------------------------------------------------------
# Tests: contractor message routing
# ---------------------------------------------------------------------------

def test_contractor_message_routes_to_approval_service():
    contractor = _make_contractor()
    engine = _make_mock_engine()
    engine_cls = MagicMock(return_value=engine)
    wa_cls = MagicMock()
    approval_cls = MagicMock()

    payload = text_message(from_phone=_CONTRACTOR_PHONE, text="approve")

    with patch("app.db.base.SessionLocal", return_value=MagicMock()), \
         patch("app.core.config.get_settings", return_value=MagicMock(quote_validity_days=30)), \
         patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()), \
         patch("app.services.conversation.engine.ConversationEngine", engine_cls), \
         patch("app.services.whatsapp.client.WhatsAppClient", wa_cls), \
         patch("app.services.approval.service.ApprovalService", approval_cls), \
         patch("app.services.conversation.session_repo.resolve_contractor", return_value=contractor):

        result = process_inbound_message(payload)

    approval_cls.return_value.process.assert_called_once()
    engine.process.assert_not_called()
    assert result["processed"] == 1


def test_buyer_message_routes_to_engine():
    contractor = _make_contractor()
    engine = _make_mock_engine()
    engine_cls = MagicMock(return_value=engine)
    wa_cls = MagicMock()
    approval_cls = MagicMock()

    payload = text_message(from_phone=_BUYER_PHONE, text="hello")

    with patch("app.db.base.SessionLocal", return_value=MagicMock()), \
         patch("app.core.config.get_settings", return_value=MagicMock(quote_validity_days=30)), \
         patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()), \
         patch("app.services.conversation.engine.ConversationEngine", engine_cls), \
         patch("app.services.whatsapp.client.WhatsAppClient", wa_cls), \
         patch("app.services.approval.service.ApprovalService", approval_cls), \
         patch("app.services.conversation.session_repo.resolve_contractor", return_value=contractor):

        result = process_inbound_message(payload)

    engine.process.assert_called_once()
    approval_cls.return_value.process.assert_not_called()
    assert result["processed"] == 1


def test_snapshot_triggers_contractor_notification():
    contractor = _make_contractor()
    engine = _make_mock_engine(has_snapshot=True)
    engine_cls = MagicMock(return_value=engine)
    wa_cls = MagicMock()
    wa = wa_cls.return_value
    approval_cls = MagicMock()

    payload = text_message(from_phone=_BUYER_PHONE, text="1000sqft premium")

    with patch("app.db.base.SessionLocal", return_value=MagicMock()), \
         patch("app.core.config.get_settings", return_value=MagicMock(quote_validity_days=30)), \
         patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()), \
         patch("app.services.conversation.engine.ConversationEngine", engine_cls), \
         patch("app.services.whatsapp.client.WhatsAppClient", wa_cls), \
         patch("app.services.approval.service.ApprovalService", approval_cls), \
         patch("app.services.conversation.session_repo.resolve_contractor", return_value=contractor), \
         patch("app.services.conversation.session_repo.load_active_pricing_config", return_value=SimpleNamespace(version=1)), \
         patch("app.services.conversation.session_repo.create_quote", return_value=_make_quote()):

        result = process_inbound_message(payload)

    # Contractor notification must be sent
    contractor_calls = [
        c for c in wa.send_text.call_args_list
        if c.kwargs.get("to") == contractor.phone
    ]
    assert len(contractor_calls) == 1
    assert "approve" in contractor_calls[0].kwargs["body"].lower()


def test_no_snapshot_does_not_notify_contractor():
    contractor = _make_contractor()
    engine = _make_mock_engine(has_snapshot=False)
    engine_cls = MagicMock(return_value=engine)
    wa_cls = MagicMock()
    wa = wa_cls.return_value
    approval_cls = MagicMock()

    payload = text_message(from_phone=_BUYER_PHONE, text="hello")

    with patch("app.db.base.SessionLocal", return_value=MagicMock()), \
         patch("app.core.config.get_settings", return_value=MagicMock(quote_validity_days=30)), \
         patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()), \
         patch("app.services.conversation.engine.ConversationEngine", engine_cls), \
         patch("app.services.whatsapp.client.WhatsAppClient", wa_cls), \
         patch("app.services.approval.service.ApprovalService", approval_cls), \
         patch("app.services.conversation.session_repo.resolve_contractor", return_value=contractor):

        process_inbound_message(payload)

    contractor_calls = [
        c for c in wa.send_text.call_args_list
        if c.kwargs.get("to") == contractor.phone
    ]
    assert len(contractor_calls) == 0


def test_exception_in_approval_does_not_abort_batch():
    contractor = _make_contractor()
    mock_db = MagicMock()
    approval_cls = MagicMock()
    approval_cls.return_value.process.side_effect = RuntimeError("DB down")

    payload = text_message(from_phone=_CONTRACTOR_PHONE, text="approve")

    with patch("app.db.base.SessionLocal", return_value=mock_db), \
         patch("app.core.config.get_settings", return_value=MagicMock(quote_validity_days=30)), \
         patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()), \
         patch("app.services.conversation.engine.ConversationEngine", MagicMock()), \
         patch("app.services.whatsapp.client.WhatsAppClient", MagicMock()), \
         patch("app.services.approval.service.ApprovalService", approval_cls), \
         patch("app.services.conversation.session_repo.resolve_contractor", return_value=contractor):

        result = process_inbound_message(payload)

    assert result["processed"] == 0
    mock_db.close.assert_called_once()


def test_db_always_closed_on_success():
    contractor = _make_contractor()
    mock_db = MagicMock()

    payload = text_message(from_phone=_BUYER_PHONE, text="hi")

    with patch("app.db.base.SessionLocal", return_value=mock_db), \
         patch("app.core.config.get_settings", return_value=MagicMock(quote_validity_days=30)), \
         patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()), \
         patch("app.services.conversation.engine.ConversationEngine", MagicMock(
             return_value=_make_mock_engine(has_snapshot=False),
         )), \
         patch("app.services.whatsapp.client.WhatsAppClient", MagicMock()), \
         patch("app.services.conversation.session_repo.resolve_contractor", return_value=contractor):

        process_inbound_message(payload)

    mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: _format_contractor_notification
# ---------------------------------------------------------------------------

def test_format_notification_masks_phone():
    quote = SimpleNamespace(total=Decimal("25960.00"), work_type="painting")
    msg = _format_contractor_notification(quote, "919876543210")
    assert "3210" in msg
    assert "9876" not in msg


def test_format_notification_includes_total():
    quote = SimpleNamespace(total=Decimal("25960.00"), work_type="painting")
    msg = _format_contractor_notification(quote, "919876543210")
    assert "25960.00" in msg


def test_format_notification_includes_work_type():
    quote = SimpleNamespace(total=Decimal("25960.00"), work_type="painting")
    msg = _format_contractor_notification(quote, "919876543210")
    assert "painting" in msg.lower()


def test_format_notification_has_approve_and_reject():
    quote = SimpleNamespace(total=Decimal("1000.00"), work_type="painting")
    msg = _format_contractor_notification(quote, "919876543210")
    assert "approve" in msg.lower()
    assert "reject" in msg.lower()
