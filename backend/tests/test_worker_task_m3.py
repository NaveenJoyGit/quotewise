"""Tests for the M3 worker task (replaces test_worker_echo.py)."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.workers.tasks import process_inbound_message
from tests.sample_payloads import text_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_task(payload: dict, engine_return: str | None = "Hello!") -> dict:
    """Run process_inbound_message with ConversationEngine and WhatsAppClient mocked.

    Imports inside the task body are deferred, so we patch at their source modules.
    """
    mock_engine_cls = MagicMock()
    mock_engine = mock_engine_cls.return_value
    mock_engine.process.return_value = engine_return

    mock_wa_cls = MagicMock()
    mock_wa = mock_wa_cls.return_value

    mock_db = MagicMock()
    mock_db.close = MagicMock()

    tenant = MagicMock(phone="+919999900001")

    with (
        patch("app.db.base.SessionLocal", return_value=mock_db),
        patch("app.core.config.get_settings", return_value=MagicMock(session_ttl_hours=72)),
        patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()),
        patch("app.services.conversation.engine.ConversationEngine", mock_engine_cls),
        patch("app.services.whatsapp.client.WhatsAppClient", mock_wa_cls),
        patch("app.services.conversation.session_repo.resolve_contractor", return_value=tenant),
        patch(
            "app.services.contractor_admin.session_repo.find_active_session",
            return_value=None,
        ),
        patch("app.services.whatsapp.phone.find_contractor_by_phone", return_value=None),
    ):
        result = process_inbound_message(payload)

    return result, mock_engine, mock_wa


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_text_message_routes_through_engine():
    payload = text_message(from_phone="919876543210", text="hello")
    result, engine, wa = _run_task(payload, engine_return="Hi there!")
    assert result["processed"] == 1
    engine.process.assert_called_once()
    wa.send_text.assert_called_once_with(to="919876543210", body="Hi there!")


def test_engine_returns_none_does_not_send():
    payload = text_message(from_phone="919876543210", text="hello")
    result, engine, wa = _run_task(payload, engine_return=None)
    assert result["processed"] == 1
    wa.send_text.assert_not_called()


def test_status_only_payload_skips_processing():
    # A status-only payload has no messages array — parse_inbound returns []
    status_payload: dict[str, Any] = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.xxx", "status": "delivered"}]}}]}],
    }
    result, engine, wa = _run_task(status_payload)
    assert result["processed"] == 0
    engine.process.assert_not_called()
    wa.send_text.assert_not_called()


def test_empty_payload_returns_zero():
    result, engine, wa = _run_task({})
    assert result["processed"] == 0


def test_db_session_closed_on_success():
    payload = text_message(from_phone="919876543210", text="hello")
    mock_db = MagicMock()

    with (
        patch("app.db.base.SessionLocal", return_value=mock_db),
        patch("app.core.config.get_settings", return_value=MagicMock(session_ttl_hours=72)),
        patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()),
        patch("app.services.conversation.engine.ConversationEngine", return_value=MagicMock(**{"process.return_value": "ok"})),
        patch("app.services.whatsapp.client.WhatsAppClient", return_value=MagicMock()),
        patch("app.services.conversation.session_repo.resolve_contractor", return_value=MagicMock()),
        patch("app.services.contractor_admin.session_repo.find_active_session", return_value=None),
        patch("app.services.whatsapp.phone.find_contractor_by_phone", return_value=None),
    ):
        process_inbound_message(payload)

    mock_db.close.assert_called_once()


def test_db_session_closed_on_engine_exception():
    payload = text_message(from_phone="919876543210", text="hello")
    mock_db = MagicMock()
    mock_engine = MagicMock()
    mock_engine.process.side_effect = RuntimeError("boom")

    with (
        patch("app.db.base.SessionLocal", return_value=mock_db),
        patch("app.core.config.get_settings", return_value=MagicMock(session_ttl_hours=72)),
        patch("app.services.llm.factory.get_llm_client", return_value=MagicMock()),
        patch("app.services.conversation.engine.ConversationEngine", return_value=mock_engine),
        patch("app.services.whatsapp.client.WhatsAppClient", return_value=MagicMock()),
        patch("app.services.conversation.session_repo.resolve_contractor", return_value=MagicMock()),
        patch("app.services.contractor_admin.session_repo.find_active_session", return_value=None),
        patch("app.services.whatsapp.phone.find_contractor_by_phone", return_value=None),
        patch("app.workers.tasks._should_route_admin", return_value=False),
    ):
        result = process_inbound_message(payload)

    # Exception is caught per-message (not re-raised), DB is closed
    mock_db.close.assert_called_once()
    assert result["processed"] == 0
