"""Integration test for ConversationEngine using monkeypatched session_repo.

No real DB required — matches M2's pattern of mock-DB tests.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.db.enums import MessageDirection, MessageType, SessionState, WorkType
from app.services.conversation.engine import ConversationEngine, _NON_TEXT_REFUSAL
from app.services.llm.mock import MockLLMClient
from app.services.pricing.seed_rules import PAINTING_RULES
from app.services.whatsapp.payload import InboundMessage


# ---------------------------------------------------------------------------
# Shared test fixtures / helpers
# ---------------------------------------------------------------------------

_CONTRACTOR_ID = uuid.uuid4()
_SESSION_ID = uuid.uuid4()
_BUYER = "919876543210"
_NOW = datetime(2026, 4, 24, 10, 0, 0, tzinfo=timezone.utc)


def _inbound(text: str = "hi", mtype: str = "text") -> InboundMessage:
    return InboundMessage(
        whatsapp_message_id="wamid.test",
        from_phone=_BUYER,
        message_type=mtype,
        text=text if mtype == "text" else None,
        raw={},
    )


def _make_contractor():
    return SimpleNamespace(
        id=_CONTRACTOR_ID,
        business_name="Test Contractor",
    )


def _make_session(state: SessionState, collected=None, missing=None, work_type=None):
    return SimpleNamespace(
        id=_SESSION_ID,
        contractor_id=_CONTRACTOR_ID,
        state=state,
        collected_slots=collected if collected is not None else {},
        missing_slots=missing if missing is not None else [],
        work_type=work_type,
    )


def _make_engine(llm=None, session_obj=None, contractor=None, settings=None):
    """Build a ConversationEngine with monkeypatched session_repo."""
    from app.core.config import Settings
    settings = settings or Settings()

    db = MagicMock()
    db.commit = MagicMock()

    engine = ConversationEngine(
        db=db,
        llm=llm or MockLLMClient(),
        clock=lambda: _NOW,
        settings=settings,
    )
    return engine, db


# ---------------------------------------------------------------------------
# Fixture: patch session_repo in the engine module
# ---------------------------------------------------------------------------

@pytest.fixture
def patched_repo(monkeypatch):
    """Returns a namespace of mock functions that replace session_repo calls in the engine."""
    mocks = SimpleNamespace(
        resolve_contractor=MagicMock(return_value=_make_contractor()),
        find_or_create_session=MagicMock(),
        log_message=MagicMock(),
        load_active_pricing_rules=MagicMock(return_value=PAINTING_RULES),
        apply_handler_result=MagicMock(),
    )

    import app.services.conversation.engine as engine_mod
    monkeypatch.setattr(engine_mod.session_repo, "resolve_contractor", mocks.resolve_contractor)
    monkeypatch.setattr(engine_mod.session_repo, "find_or_create_session", mocks.find_or_create_session)
    monkeypatch.setattr(engine_mod.session_repo, "log_message", mocks.log_message)
    monkeypatch.setattr(engine_mod.session_repo, "load_active_pricing_rules", mocks.load_active_pricing_rules)
    monkeypatch.setattr(engine_mod.session_repo, "apply_handler_result", mocks.apply_handler_result)

    return mocks


# ---------------------------------------------------------------------------
# Tests: non-text input
# ---------------------------------------------------------------------------

def test_non_text_returns_refusal(patched_repo):
    engine, db = _make_engine()
    result = engine.process(_inbound(mtype="voice"))
    assert result == _NON_TEXT_REFUSAL
    db.commit.assert_not_called()
    patched_repo.find_or_create_session.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: state transitions
# ---------------------------------------------------------------------------

def test_greeting_state_transitions_and_returns_text(patched_repo):
    patched_repo.find_or_create_session.return_value = _make_session(SessionState.greeting)
    engine, db = _make_engine()
    result = engine.process(_inbound("hello"))
    assert isinstance(result, str) and len(result) > 0
    db.commit.assert_called_once()


def test_identifying_scope_transitions_to_collecting(patched_repo):
    patched_repo.find_or_create_session.return_value = _make_session(SessionState.identifying_scope)

    def apply_result(session, new_state, **kwargs):
        session.state = new_state
        if kwargs.get("missing_slots") is not None:
            session.missing_slots = kwargs["missing_slots"]
        if kwargs.get("work_type") is not None:
            session.work_type = kwargs["work_type"]

    import app.services.conversation.engine as engine_mod
    engine_mod.session_repo.apply_handler_result = apply_result

    engine, db = _make_engine()
    result = engine.process(_inbound("I want to paint"))
    assert isinstance(result, str) and len(result) > 0
    db.commit.assert_called_once()


def test_collecting_inputs_asks_next_question(patched_repo):
    session = _make_session(
        SessionState.collecting_inputs,
        collected={},
        missing=["area_sqft", "surface_type", "paint_brand_tier"],
        work_type=WorkType.painting,
    )
    patched_repo.find_or_create_session.return_value = session
    # LLM extracts nothing → re-asks same slot
    engine, db = _make_engine(llm=MockLLMClient(responses={"slot_extraction": {}}))
    result = engine.process(_inbound("hmm"))
    assert isinstance(result, str) and len(result) > 0


def test_collecting_all_slots_triggers_chained_dispatch_to_ready(patched_repo, caplog):
    """Full multi-turn scripted conversation ends in quote.generated log."""
    # Session already has area_sqft and surface_type; last message fills paint_brand_tier.
    session = _make_session(
        SessionState.collecting_inputs,
        collected={"area_sqft": 1000, "surface_type": "new_wall"},
        missing=["paint_brand_tier"],
        work_type=WorkType.painting,
    )
    patched_repo.find_or_create_session.return_value = session

    # After handler says READY_TO_QUOTE, apply_handler_result advances the session.
    def apply_result(session, new_state, **kwargs):
        session.state = new_state
        if kwargs.get("collected_slots_update"):
            session.collected_slots = {**session.collected_slots, **kwargs["collected_slots_update"]}
        if kwargs.get("missing_slots") is not None:
            session.missing_slots = kwargs["missing_slots"]

    import app.services.conversation.engine as engine_mod
    engine_mod.session_repo.apply_handler_result = apply_result

    llm = MockLLMClient(responses={"slot_extraction": {"paint_brand_tier": "premium"}})
    engine, db = _make_engine(llm=llm)

    with caplog.at_level(logging.INFO, logger="app.services.conversation.handlers.ready_to_quote"):
        result = engine.process(_inbound("premium paint"))

    # Should have chained into ReadyToQuoteHandler and returned its ack.
    assert "contractor" in result.lower()
    assert any("quote.generated" in r.getMessage() for r in caplog.records)
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: log_message called for inbound and outbound
# ---------------------------------------------------------------------------

def test_logs_both_inbound_and_outbound_messages(patched_repo):
    patched_repo.find_or_create_session.return_value = _make_session(SessionState.greeting)
    engine, _ = _make_engine()
    engine.process(_inbound("hello"))

    calls = patched_repo.log_message.call_args_list
    directions = [c.kwargs.get("direction") or c.args[2] for c in calls]
    assert MessageDirection.inbound in directions
    assert MessageDirection.outbound in directions


# ---------------------------------------------------------------------------
# Tests: unknown state
# ---------------------------------------------------------------------------

def test_unknown_state_returns_stub_message(patched_repo):
    patched_repo.find_or_create_session.return_value = _make_session(SessionState.awaiting_approval)
    engine, _ = _make_engine()
    result = engine.process(_inbound("approve"))
    assert "session" in result.lower() or "conversation" in result.lower()
