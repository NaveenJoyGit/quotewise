"""DB integration tests for session_repo using a real PostgreSQL container.

Run with:  uv run pytest backend/tests/test_session_repo_db.py -v -m integration
Skipped in the fast unit-test suite (requires Docker).
"""
from __future__ import annotations

import os
import subprocess
import uuid
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("testcontainers", reason="testcontainers not installed")

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Module-scoped Postgres container + migrated DB
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_session():
    """Spin up postgres:16-alpine, run alembic upgrade head, yield a DB session."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url()
        # psycopg3 driver required by the app — rewrite the DSN scheme.
        url_psycopg3 = url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
        if "postgresql://" in url_psycopg3 and "psycopg" not in url_psycopg3:
            url_psycopg3 = url_psycopg3.replace("postgresql://", "postgresql+psycopg://", 1)

        env = {**os.environ, "DATABASE_URL": url_psycopg3}
        subprocess.run(
            ["uv", "run", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
            check=True,
            env=env,
        )

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(url_psycopg3)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()
            engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 4, 27, 10, 0, 0, tzinfo=timezone.utc)


def _make_contractor(session, phone: str, slug: str, wa_id: str | None = None):
    from app.db.models import Contractor

    c = Contractor(
        phone=phone,
        business_name="Test Contractor",
        city="Bangalore",
        whatsapp_link_slug=slug,
        wa_phone_number_id=wa_id,
    )
    session.add(c)
    session.flush()
    return c


def _make_pricing_config(session, contractor_id, work_type):
    from app.db.models import PricingConfig
    from app.services.pricing.seed_rules import FALSE_CEILING_RULES, PAINTING_RULES

    rules = PAINTING_RULES if work_type == "painting" else FALSE_CEILING_RULES
    pc = PricingConfig(
        contractor_id=contractor_id,
        work_type=work_type,
        is_active=True,
        rules=rules,
        version=1,
    )
    session.add(pc)
    session.flush()
    return pc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_resolve_contractor_by_wa_phone_number_id(db_session):
    from app.services.conversation import session_repo

    c = _make_contractor(db_session, "+911111111101", "test-wa-1", wa_id="wa-id-abc")
    db_session.commit()

    found = session_repo.resolve_contractor(db_session, wa_phone_number_id="wa-id-abc")
    assert found.id == c.id
    assert found.wa_phone_number_id == "wa-id-abc"


def test_resolve_contractor_fallback_to_first(db_session):
    from app.services.conversation import session_repo

    # No wa_phone_number_id provided → first contractor by created_at.
    found = session_repo.resolve_contractor(db_session, wa_phone_number_id=None)
    assert found is not None


def test_resolve_contractor_unknown_wa_id_raises(db_session):
    from app.services.conversation import session_repo
    from app.services.conversation.session_repo import ContractorNotFoundError

    with pytest.raises(ContractorNotFoundError):
        session_repo.resolve_contractor(db_session, wa_phone_number_id="no-such-id")


def test_find_or_create_session_new(db_session):
    from app.services.conversation import session_repo

    c = _make_contractor(db_session, "+911111111102", "test-sess-new")
    db_session.commit()

    buyer = "+919000000001"
    session = session_repo.find_or_create_session(db_session, c.id, buyer, _NOW, ttl_hours=72)
    db_session.commit()

    assert session.contractor_id == c.id
    assert session.buyer_phone == buyer


def test_find_or_create_session_existing_returns_same(db_session):
    from app.services.conversation import session_repo

    c = _make_contractor(db_session, "+911111111103", "test-sess-exist")
    db_session.commit()

    buyer = "+919000000002"
    s1 = session_repo.find_or_create_session(db_session, c.id, buyer, _NOW, ttl_hours=72)
    db_session.commit()
    s2 = session_repo.find_or_create_session(db_session, c.id, buyer, _NOW, ttl_hours=72)

    assert s1.id == s2.id


def test_session_ttl_expired_creates_new(db_session):
    from app.services.conversation import session_repo

    c = _make_contractor(db_session, "+911111111104", "test-sess-ttl")
    db_session.commit()

    buyer = "+919000000003"
    past = _NOW - timedelta(hours=100)
    s1 = session_repo.find_or_create_session(db_session, c.id, buyer, past, ttl_hours=72)
    db_session.commit()

    # Now request at _NOW — s1 is expired so a new session should be created.
    s2 = session_repo.find_or_create_session(db_session, c.id, buyer, _NOW, ttl_hours=72)
    db_session.commit()

    assert s1.id != s2.id


def test_log_message(db_session):
    from app.db.enums import MessageDirection, MessageType
    from app.services.conversation import session_repo

    c = _make_contractor(db_session, "+911111111105", "test-log-msg")
    db_session.commit()
    buyer = "+919000000004"
    sess = session_repo.find_or_create_session(db_session, c.id, buyer, _NOW, ttl_hours=72)
    db_session.commit()

    msg = session_repo.log_message(
        db_session,
        sess.id,
        direction=MessageDirection.inbound,
        message_type=MessageType.text,
        raw_content="hello",
        normalized_content="hello",
        wa_message_id="wamid.test1",
    )
    db_session.commit()

    assert msg.id is not None
    assert msg.direction == MessageDirection.inbound


def test_create_quote(db_session):
    from app.db.enums import QuoteStatus
    from app.services.conversation import session_repo
    from app.services.pricing.evaluator import evaluate_quote
    from app.services.pricing.seed_rules import PAINTING_RULES

    c = _make_contractor(db_session, "+911111111106", "test-create-quote")
    pc = _make_pricing_config(db_session, c.id, "painting")
    db_session.commit()

    buyer = "+919000000005"
    sess = session_repo.find_or_create_session(db_session, c.id, buyer, _NOW, ttl_hours=72)
    sess.work_type = "painting"
    db_session.commit()

    evaluated = evaluate_quote(
        PAINTING_RULES,
        {"area_sqft": 500, "surface_type": "new_wall", "coats": 2, "paint_brand_tier": "basic"},
    )
    snapshot = {
        "line_items": [
            {
                "description": li.description,
                "quantity": li.quantity,
                "unit": li.unit,
                "rate": li.rate,
                "amount": li.amount,
            }
            for li in evaluated.line_items
        ],
        "subtotal": evaluated.subtotal,
        "gst_amount": evaluated.gst_amount,
        "total": evaluated.total,
        "confidence_score": evaluated.confidence_score,
    }

    quote = session_repo.create_quote(
        db_session, sess, c, snapshot, pricing_config_version=pc.version
    )
    db_session.commit()

    assert quote.id is not None
    assert quote.status == QuoteStatus.pending_approval
    assert quote.total is not None


def test_apply_handler_result_state_transition(db_session):
    from app.db.enums import SessionState
    from app.services.conversation import session_repo

    c = _make_contractor(db_session, "+911111111107", "test-apply-handler")
    db_session.commit()
    buyer = "+919000000006"
    sess = session_repo.find_or_create_session(db_session, c.id, buyer, _NOW, ttl_hours=72)
    db_session.commit()

    assert sess.state == SessionState.greeting

    session_repo.apply_handler_result(
        sess,
        new_state=SessionState.identifying_scope,
        collected_slots_update={},
        missing_slots=None,
        work_type=None,
        now=_NOW,
        ttl_hours=72,
    )
    db_session.commit()

    assert sess.state == SessionState.identifying_scope
