"""Per-handler unit tests using in-memory Session objects (no DB)."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.db.enums import SessionState, WorkType
from app.services.conversation.handlers.awaiting_approval import AwaitingApprovalHandler
from app.services.conversation.handlers.collecting_inputs import CollectingInputsHandler
from app.services.conversation.handlers.greeting import GreetingHandler
from app.services.conversation.handlers.identifying_scope import IdentifyingScopeHandler
from app.services.conversation.handlers.quote_delivered import QuoteDeliveredHandler
from app.services.conversation.handlers.ready_to_quote import ReadyToQuoteHandler
from app.services.conversation.types import HandlerDeps
from app.services.llm.mock import MockLLMClient
from app.services.pricing.seed_rules import PAINTING_RULES
from app.services.whatsapp.payload import InboundMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _inbound(text: str = "hi") -> InboundMessage:
    return InboundMessage(
        whatsapp_message_id="wamid.test",
        from_phone="919876543210",
        message_type="text",
        text=text,
        raw={},
    )


def _session(
    state: SessionState = SessionState.greeting,
    collected_slots: dict | None = None,
    missing_slots: list | None = None,
    work_type: WorkType | None = None,
) -> object:
    """Return a lightweight namespace with the attributes handlers need."""
    from types import SimpleNamespace
    return SimpleNamespace(
        id=uuid.uuid4(),
        contractor_id=uuid.uuid4(),
        state=state,
        collected_slots=collected_slots if collected_slots is not None else {},
        missing_slots=missing_slots if missing_slots is not None else [],
        work_type=work_type,
    )


def _deps(llm=None, pricing_rules=None) -> HandlerDeps:
    return HandlerDeps(
        llm=llm or MockLLMClient(),
        now=lambda: datetime.now(timezone.utc),
        business_name="Test Contractor",
        pricing_rules=pricing_rules or PAINTING_RULES,
    )


_FULL_SLOTS = {
    "area_sqft": 1000,
    "surface_type": "new_wall",
    "paint_brand_tier": "premium",
}


# ---------------------------------------------------------------------------
# GreetingHandler
# ---------------------------------------------------------------------------

class TestGreetingHandler:
    def test_transitions_to_identifying_scope(self):
        handler = GreetingHandler()
        result = handler.handle(_session(), _inbound(), _deps())
        assert result.new_state == SessionState.identifying_scope

    def test_outbound_text_is_nonempty(self):
        handler = GreetingHandler()
        result = handler.handle(_session(), _inbound(), _deps())
        assert len(result.outbound_text) > 0

    def test_uses_business_name(self):
        client = MockLLMClient(responses={"greeting": "Hello from Test Corp!"})
        handler = GreetingHandler()
        result = handler.handle(_session(), _inbound(), _deps(llm=client))
        assert result.outbound_text == "Hello from Test Corp!"

    def test_fallback_on_empty_llm_response(self):
        client = MockLLMClient(responses={"greeting": ""})
        handler = GreetingHandler()
        result = handler.handle(_session(), _inbound(), _deps(llm=client))
        assert len(result.outbound_text) > 0


# ---------------------------------------------------------------------------
# IdentifyingScopeHandler
# ---------------------------------------------------------------------------

class TestIdentifyingScopeHandler:
    def test_transitions_to_collecting_inputs(self):
        handler = IdentifyingScopeHandler()
        result = handler.handle(_session(), _inbound(), _deps())
        assert result.new_state == SessionState.collecting_inputs

    def test_hardcodes_painting_work_type(self):
        handler = IdentifyingScopeHandler()
        result = handler.handle(_session(), _inbound(), _deps())
        assert result.work_type == WorkType.painting

    def test_missing_slots_excludes_slots_with_defaults(self):
        handler = IdentifyingScopeHandler()
        result = handler.handle(_session(), _inbound(), _deps())
        # 'coats' has default=2 in PAINTING_RULES, so it should NOT be in missing_slots
        assert "coats" not in (result.missing_slots or [])

    def test_missing_slots_includes_required_slots(self):
        handler = IdentifyingScopeHandler()
        result = handler.handle(_session(), _inbound(), _deps())
        for name in ["area_sqft", "surface_type", "paint_brand_tier"]:
            assert name in (result.missing_slots or [])

    def test_asks_a_question(self):
        handler = IdentifyingScopeHandler()
        result = handler.handle(_session(), _inbound(), _deps())
        assert len(result.outbound_text) > 0


# ---------------------------------------------------------------------------
# CollectingInputsHandler
# ---------------------------------------------------------------------------

class TestCollectingInputsHandler:
    def _session_collecting(self, collected=None, missing=None):
        return _session(
            state=SessionState.collecting_inputs,
            collected_slots=collected or {},
            missing_slots=missing or ["area_sqft", "surface_type", "paint_brand_tier"],
        )

    def test_extracts_slots_and_stays_collecting_when_more_needed(self):
        client = MockLLMClient(responses={"slot_extraction": {"area_sqft": 1000}})
        handler = CollectingInputsHandler()
        result = handler.handle(
            self._session_collecting(),
            _inbound("1000 sqft"),
            _deps(llm=client),
        )
        assert result.new_state == SessionState.collecting_inputs
        assert result.collected_slots_update == {"area_sqft": 1000.0}
        # Still missing surface_type and paint_brand_tier
        assert "area_sqft" not in (result.missing_slots or [])

    def test_transitions_to_ready_when_all_filled(self):
        client = MockLLMClient(responses={
            "slot_extraction": {"surface_type": "new_wall", "paint_brand_tier": "premium"},
        })
        handler = CollectingInputsHandler()
        result = handler.handle(
            self._session_collecting(
                collected={"area_sqft": 1000},
                missing=["surface_type", "paint_brand_tier"],
            ),
            _inbound("new wall premium"),
            _deps(llm=client),
        )
        assert result.new_state == SessionState.ready_to_quote
        assert result.outbound_text == ""  # triggers chained dispatch
        assert result.missing_slots == []

    def test_empty_extraction_keeps_same_missing_slots(self):
        client = MockLLMClient(responses={"slot_extraction": {}})
        handler = CollectingInputsHandler()
        result = handler.handle(
            self._session_collecting(missing=["area_sqft"]),
            _inbound("hmm"),
            _deps(llm=client),
        )
        assert result.new_state == SessionState.collecting_inputs
        assert "area_sqft" in (result.missing_slots or [])


# ---------------------------------------------------------------------------
# ReadyToQuoteHandler
# ---------------------------------------------------------------------------

class TestReadyToQuoteHandler:
    def test_logs_quote_generated(self, caplog):
        session = _session(
            state=SessionState.ready_to_quote,
            collected_slots=_FULL_SLOTS,
        )
        handler = ReadyToQuoteHandler()
        with caplog.at_level(logging.INFO, logger="app.services.conversation.handlers.ready_to_quote"):
            result = handler.handle(session, _inbound(), _deps())

        log_events = [r.getMessage() for r in caplog.records]
        assert any("quote.generated" in e for e in log_events)

    def test_quote_totals_correct_for_premium_new_wall_1000sqft(self, caplog):
        session = _session(
            state=SessionState.ready_to_quote,
            collected_slots=_FULL_SLOTS,
        )
        handler = ReadyToQuoteHandler()
        with caplog.at_level(logging.INFO, logger="app.services.conversation.handlers.ready_to_quote"):
            result = handler.handle(session, _inbound(), _deps())

        # Premium / new_wall / 1000 sqft / 2 coats (default)
        # rate=22, subtotal=22000, GST=3960, total=25960
        snapshot = result.quote_snapshot
        assert snapshot["subtotal"] == Decimal("22000.00")
        assert snapshot["gst_amount"] == Decimal("3960.00")
        assert snapshot["total"] == Decimal("25960.00")

    def test_outbound_text_is_ack_message(self):
        session = _session(
            state=SessionState.ready_to_quote,
            collected_slots=_FULL_SLOTS,
        )
        handler = ReadyToQuoteHandler()
        result = handler.handle(session, _inbound(), _deps())
        assert "contractor" in result.outbound_text.lower()

    def test_quote_snapshot_is_set(self):
        session = _session(
            state=SessionState.ready_to_quote,
            collected_slots=_FULL_SLOTS,
        )
        handler = ReadyToQuoteHandler()
        result = handler.handle(session, _inbound(), _deps())
        assert result.quote_snapshot is not None
        assert "total" in result.quote_snapshot

    def test_state_transitions_to_awaiting_approval(self):
        session = _session(
            state=SessionState.ready_to_quote,
            collected_slots=_FULL_SLOTS,
        )
        handler = ReadyToQuoteHandler()
        result = handler.handle(session, _inbound(), _deps())
        assert result.new_state == SessionState.awaiting_approval


# ---------------------------------------------------------------------------
# AwaitingApprovalHandler
# ---------------------------------------------------------------------------

class TestAwaitingApprovalHandler:
    def test_returns_hold_message(self):
        handler = AwaitingApprovalHandler()
        result = handler.handle(
            _session(state=SessionState.awaiting_approval),
            _inbound("anything"),
            _deps(),
        )
        assert len(result.outbound_text) > 0
        assert "contractor" in result.outbound_text.lower() or "reviewed" in result.outbound_text.lower()

    def test_state_stays_awaiting_approval(self):
        handler = AwaitingApprovalHandler()
        result = handler.handle(
            _session(state=SessionState.awaiting_approval),
            _inbound("are you there?"),
            _deps(),
        )
        assert result.new_state == SessionState.awaiting_approval

    def test_no_quote_snapshot(self):
        handler = AwaitingApprovalHandler()
        result = handler.handle(
            _session(state=SessionState.awaiting_approval),
            _inbound(),
            _deps(),
        )
        assert result.quote_snapshot is None


# ---------------------------------------------------------------------------
# QuoteDeliveredHandler
# ---------------------------------------------------------------------------

class TestQuoteDeliveredHandler:
    def test_returns_delivered_message(self):
        handler = QuoteDeliveredHandler()
        result = handler.handle(
            _session(state=SessionState.quote_delivered),
            _inbound("thanks"),
            _deps(),
        )
        assert len(result.outbound_text) > 0
        assert "quote" in result.outbound_text.lower()

    def test_state_stays_quote_delivered(self):
        handler = QuoteDeliveredHandler()
        result = handler.handle(
            _session(state=SessionState.quote_delivered),
            _inbound("hello again"),
            _deps(),
        )
        assert result.new_state == SessionState.quote_delivered

    def test_no_quote_snapshot(self):
        handler = QuoteDeliveredHandler()
        result = handler.handle(
            _session(state=SessionState.quote_delivered),
            _inbound(),
            _deps(),
        )
        assert result.quote_snapshot is None
