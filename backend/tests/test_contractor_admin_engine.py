"""Tests for contractor admin engine (FR-001)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.db.enums import AdminFlowType, AdminSessionState
from app.db.models import ContractorAdminSession
from app.services.contractor_admin.engine import ContractorAdminEngine
from app.services.rate_card.parser import ParsedRateCard
from app.services.whatsapp.payload import InboundMessage
from tests.test_onboarding_api import _VALID_RULES

_NOW = datetime(2026, 5, 25, 12, 0, 0, tzinfo=timezone.utc)
_CONTRACTOR_ID = uuid.uuid4()


def _inbound(text: str, phone: str = "919999900001") -> InboundMessage:
    return InboundMessage(
        whatsapp_message_id="wamid.1",
        from_phone=phone,
        message_type="text",
        text=text,
        raw={"type": "text", "text": {"body": text}},
    )


def _tenant():
    return SimpleNamespace(
        id=_CONTRACTOR_ID,
        phone="+919999900001",
        wa_phone_number_id="PHONE_ID",
        business_name="Tenant Co",
    )


def _registered():
    return SimpleNamespace(id=_CONTRACTOR_ID, phone="+919999900001")


@pytest.fixture
def engine_setup():
    db = MagicMock()
    llm = MagicMock()
    wa = MagicMock()
    settings = MagicMock(session_ttl_hours=72)
    engine = ContractorAdminEngine(
        db=db, llm=llm, wa=wa, clock=lambda: _NOW, settings=settings
    )
    return engine, db, llm, wa


def test_manage_rates_unregistered_rejected(engine_setup):
    engine, db, *_ = engine_setup
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    out = engine.process(_inbound("manage-rates"), _tenant(), None)
    assert out is not None
    assert "registered" in out.lower()


def test_manage_rates_starts_session(engine_setup):
    engine, db, *_ = engine_setup
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    with patch("app.services.contractor_admin.engine.admin_repo.create_session") as mock_create:
        mock_create.return_value = MagicMock()
        out = engine.process(_inbound("manage-rates"), _tenant(), _registered())

    assert "work type" in out.lower()
    mock_create.assert_called_once()
    call_kw = mock_create.call_args.kwargs
    assert call_kw["flow_type"] == AdminFlowType.manage_rates


def test_review_save_pricing(engine_setup):
    engine, db, llm, wa = engine_setup
    session = ContractorAdminSession(
        id=uuid.uuid4(),
        contractor_id=_CONTRACTOR_ID,
        admin_phone="+919999900001",
        flow_type=AdminFlowType.manage_rates,
        state=AdminSessionState.reviewing,
        work_type="painting",
        draft_rules=_VALID_RULES,
        parse_notes=[],
        validation_errors=[],
    )
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = session

    fake_config = SimpleNamespace(version=2)
    with patch("app.services.contractor_admin.engine.OnboardingService") as MockSvc:
        MockSvc.return_value.save_pricing_config.return_value = fake_config
        out = engine.process(_inbound("yes"), _tenant(), _registered())

    assert "saved" in out.lower()
    assert session.state == AdminSessionState.completed
