"""Worker routing tests for FR-002 forwarded quotes."""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.approval.keywords import ApprovalAction
from app.workers.tasks import _should_route_approval, _should_route_forward, process_inbound_message
from tests.sample_payloads import forwarded_text_message, text_message

_CONTRACTOR_PHONE = "919999900001"
_BUYER_PHONE = "919876543210"


def _contractor():
    return SimpleNamespace(
        id=uuid.uuid4(),
        phone=f"+{_CONTRACTOR_PHONE}",
        business_name="Test",
    )


def test_should_route_forward_on_forwarded_flag():
    contractor = _contractor()
    msg = MagicMock(is_forwarded=True, text="fwd")
    assert _should_route_forward(MagicMock(), contractor, msg) is True


def test_should_route_forward_on_typed_contractor_enquiry():
    contractor = _contractor()
    msg = MagicMock(
        is_forwarded=False,
        message_type="text",
        text="4000 sqft painting",
    )
    with patch(
        "app.services.forwarded_quote.session_repo.find_active_forward_session",
        return_value=None,
    ):
        assert _should_route_forward(MagicMock(), contractor, msg) is True


def test_should_not_route_forward_on_approval_keyword():
    contractor = _contractor()
    msg = MagicMock(
        is_forwarded=False,
        message_type="text",
        text="approve",
    )
    with patch(
        "app.services.forwarded_quote.session_repo.find_active_forward_session",
        return_value=None,
    ):
        assert _should_route_forward(MagicMock(), contractor, msg) is False


def test_should_route_approval_only_with_pending_direct_quote():
    contractor = _contractor()
    msg = MagicMock(text="approve")
    db = MagicMock()
    with patch("app.services.conversation.session_repo.find_pending_quote_for_contractor") as f:
        f.return_value = None
        assert _should_route_approval(msg, db, contractor) is False
        f.return_value = MagicMock()
        assert _should_route_approval(msg, db, contractor) is True


def test_contractor_typed_enquiry_routes_to_forwarded_engine():
    contractor = _contractor()
    mock_fwd_cls = MagicMock()
    payload = text_message(from_phone=_CONTRACTOR_PHONE, text="4000 sqft painting")

    with patch("app.db.base.SessionLocal", return_value=MagicMock()), \
         patch("app.core.config.get_settings", return_value=MagicMock(session_ttl_hours=72)), \
         patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()), \
         patch("app.services.whatsapp.client.WhatsAppClient", return_value=MagicMock()), \
         patch("app.services.conversation.session_repo.resolve_contractor", return_value=contractor), \
         patch("app.services.whatsapp.phone.find_contractor_by_phone", return_value=contractor), \
         patch("app.services.contractor_admin.routing.should_route_admin", return_value=False), \
         patch("app.services.forwarded_quote.engine.ForwardedQuoteEngine", mock_fwd_cls):
        process_inbound_message(payload)

    mock_fwd_cls.return_value.process.assert_called_once()


def test_forwarded_message_routes_to_forwarded_engine():
    contractor = _contractor()
    mock_fwd_cls = MagicMock()
    payload = forwarded_text_message(from_phone=_CONTRACTOR_PHONE)

    with patch("app.db.base.SessionLocal", return_value=MagicMock()), \
         patch("app.core.config.get_settings", return_value=MagicMock(session_ttl_hours=72)), \
         patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()), \
         patch("app.services.whatsapp.client.WhatsAppClient", return_value=MagicMock()), \
         patch("app.services.conversation.session_repo.resolve_contractor", return_value=contractor), \
         patch("app.services.whatsapp.phone.find_contractor_by_phone", return_value=contractor), \
         patch("app.services.contractor_admin.routing.should_route_admin", return_value=False), \
         patch("app.services.forwarded_quote.engine.ForwardedQuoteEngine", mock_fwd_cls):
        process_inbound_message(payload)

    mock_fwd_cls.return_value.process.assert_called_once()


def test_buyer_still_routes_to_conversation():
    contractor = _contractor()
    mock_conv_cls = MagicMock()
    mock_conv_cls.return_value.process.return_value = "Hi"
    mock_conv_cls.return_value.pending_quote_snapshot = None
    mock_conv_cls.return_value.last_session = None

    payload = text_message(from_phone=_BUYER_PHONE)

    with patch("app.db.base.SessionLocal", return_value=MagicMock()), \
         patch("app.core.config.get_settings", return_value=MagicMock(session_ttl_hours=72)), \
         patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()), \
         patch("app.services.whatsapp.client.WhatsAppClient", return_value=MagicMock()), \
         patch("app.services.conversation.session_repo.resolve_contractor", return_value=contractor), \
         patch("app.services.whatsapp.phone.find_contractor_by_phone", return_value=None), \
         patch("app.services.contractor_admin.routing.should_route_admin", return_value=False), \
         patch("app.services.conversation.engine.ConversationEngine", mock_conv_cls):
        process_inbound_message(payload)

    mock_conv_cls.return_value.process.assert_called_once()
