"""Worker routing tests for contractor admin flow (FR-001)."""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.workers.tasks import process_inbound_message
from tests.sample_payloads import text_message

_CONTRACTOR_PHONE = "919999900001"
_BUYER_PHONE = "919876543210"


def _make_contractor(phone=_CONTRACTOR_PHONE):
    return SimpleNamespace(
        id=uuid.uuid4(),
        phone=f"+{phone}" if not phone.startswith("+") else phone,
        business_name="Test Contractor",
    )


def test_manage_rates_routes_to_admin_engine():
    contractor = _make_contractor()
    mock_engine_cls = MagicMock()
    instance = MagicMock()
    instance.process.return_value = "Which work type?"
    mock_engine_cls.return_value = instance

    payload = text_message(from_phone=_CONTRACTOR_PHONE, text="manage-rates")

    with patch("app.db.base.SessionLocal", return_value=MagicMock()), \
         patch("app.core.config.get_settings", return_value=MagicMock(session_ttl_hours=72)), \
         patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()), \
         patch("app.services.whatsapp.client.WhatsAppClient") as mock_wa_cls, \
         patch("app.services.conversation.session_repo.resolve_contractor", return_value=contractor), \
         patch("app.services.whatsapp.phone.find_contractor_by_phone", return_value=contractor), \
         patch("app.services.contractor_admin.engine.ContractorAdminEngine", mock_engine_cls), \
         patch("app.services.conversation.engine.ConversationEngine") as mock_buyer:
        mock_wa = MagicMock()
        mock_wa_cls.return_value = mock_wa
        result = process_inbound_message(payload)

    assert result["processed"] == 1
    instance.process.assert_called_once()
    mock_buyer.assert_not_called()
    mock_wa.send_text.assert_called_once()


def test_buyer_still_routes_to_conversation_engine():
    contractor = _make_contractor()
    mock_engine = MagicMock()
    mock_engine.return_value.process.return_value = "Hi!"
    mock_engine.return_value.pending_quote_snapshot = None
    mock_engine.return_value.last_session = None

    payload = text_message(from_phone=_BUYER_PHONE, text="hello")

    with patch("app.db.base.SessionLocal", return_value=MagicMock()), \
         patch("app.core.config.get_settings", return_value=MagicMock(session_ttl_hours=72)), \
         patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()), \
         patch("app.services.whatsapp.client.WhatsAppClient") as mock_wa_cls, \
         patch("app.services.conversation.session_repo.resolve_contractor", return_value=contractor), \
         patch("app.services.whatsapp.phone.find_contractor_by_phone", return_value=None), \
         patch("app.services.contractor_admin.routing.should_route_admin", return_value=False), \
         patch("app.services.conversation.engine.ConversationEngine", mock_engine):
        mock_wa_cls.return_value = MagicMock()
        process_inbound_message(payload)

    mock_engine.return_value.process.assert_called_once()
