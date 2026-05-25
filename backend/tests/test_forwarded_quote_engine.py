"""Tests for ForwardedQuoteEngine (FR-002)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.db.enums import SessionSource, SessionState, WorkType
from app.db.models import Session as SessionModel
from app.services.forwarded_quote.engine import ForwardedQuoteEngine
from app.services.whatsapp.payload import InboundMessage

_NOW = datetime(2026, 5, 25, 12, 0, 0, tzinfo=timezone.utc)


def _contractor():
    return SimpleNamespace(id=uuid.uuid4(), phone="+919999900001", business_name="Co")


def _forward_inbound(text: str = "1000 sqft painting") -> InboundMessage:
    return InboundMessage(
        whatsapp_message_id="wamid.fwd",
        from_phone="919999900001",
        message_type="text",
        text=text,
        raw={"type": "text", "context": {"forwarded": True}, "text": {"body": text}},
        is_forwarded=True,
    )


def test_forward_start_creates_session_and_processes():
    contractor = _contractor()
    db = MagicMock()
    llm = MagicMock()
    wa = MagicMock()
    settings = MagicMock(session_ttl_hours=72)

    engine = ForwardedQuoteEngine(db=db, llm=llm, wa=wa, clock=lambda: _NOW, settings=settings)

    with patch("app.services.forwarded_quote.engine.forward_repo") as frepo:
        frepo.find_active_forward_session.return_value = None
        created = SessionModel(
            id=uuid.uuid4(),
            contractor_id=contractor.id,
            buyer_phone="fwd:pending",
            source=SessionSource.contractor_forward,
            state=SessionState.identifying_scope,
            work_type=None,
            collected_slots={},
            missing_slots=[],
        )
        frepo.create_forward_session.return_value = created

        with patch("app.services.forwarded_quote.engine.ConversationEngine") as Conv:
            conv = MagicMock()
            conv.process.return_value = "What area?"
            conv.pending_quote_snapshot = None
            conv.last_session = created
            Conv.return_value = conv

            engine.process(contractor, _forward_inbound())

    frepo.create_forward_session.assert_called_once()
    assert wa.send_text.call_count >= 2  # intro + question


def test_idle_contractor_gets_help():
    contractor = _contractor()
    wa = MagicMock()
    engine = ForwardedQuoteEngine(
        db=MagicMock(),
        llm=MagicMock(),
        wa=wa,
        clock=lambda: _NOW,
        settings=MagicMock(session_ttl_hours=72),
    )
    with patch("app.services.forwarded_quote.engine.forward_repo") as frepo:
        frepo.find_active_forward_session.return_value = None
        inbound = InboundMessage(
            whatsapp_message_id="1",
            from_phone="919999900001",
            message_type="text",
            text="hello",
            raw={},
            is_forwarded=False,
        )
        engine.process(contractor, inbound)
    wa.send_text.assert_called_once()
    assert "Forward" in wa.send_text.call_args.kwargs["body"]
