"""Tests for GET /api/v1/quotes — FastAPI TestClient, mocked DB."""
from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.enums import QuoteStatus
from app.main import create_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_contractor():
    return SimpleNamespace(
        id=uuid.uuid4(),
        created_at=datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc),
    )


def _make_quote(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        buyer_phone="919876543210",
        work_type="painting",
        subtotal=Decimal("22000.00"),
        gst_amount=Decimal("3960.00"),
        total=Decimal("25960.00"),
        status=QuoteStatus.pending_approval,
        pdf_url=None,
        validity_date=datetime.date(2026, 5, 25),
        created_at=datetime.datetime(2026, 4, 24, 10, 0, tzinfo=datetime.timezone.utc),
        approved_at=None,
        sent_at=None,
        line_items=[
            {"description": "Painting 1000 sqft", "quantity": "1000", "unit": "sqft", "rate": "22", "amount": "22000"}
        ],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_client_with_quotes(quotes: list, contractor=None):
    """Return a TestClient where auth and quotes DB queries are stubbed."""
    if contractor is None:
        contractor = _make_contractor()

    mock_db = MagicMock()
    quote_q = MagicMock()
    quote_q.filter.return_value = quote_q
    quote_q.order_by.return_value = quote_q
    quote_q.offset.return_value = quote_q
    quote_q.limit.return_value.all.return_value = quotes
    mock_db.query.return_value = quote_q

    app = create_app()
    from app.api.deps import get_current_contractor, get_db

    def override_db():
        yield mock_db

    def override_auth():
        return contractor

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_contractor] = override_auth
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_db_returns_empty_list():
    client = _make_client_with_quotes([])
    resp = client.get("/api/v1/quotes")
    assert resp.status_code == 200
    assert resp.json() == []


def test_returns_list_of_quotes():
    quotes = [_make_quote(), _make_quote()]
    client = _make_client_with_quotes(quotes)
    resp = client.get("/api/v1/quotes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_response_shape():
    quote = _make_quote()
    client = _make_client_with_quotes([quote])
    resp = client.get("/api/v1/quotes")
    data = resp.json()[0]

    assert "id" in data
    assert "buyer_phone" in data
    assert "work_type" in data
    assert "subtotal" in data
    assert "gst_amount" in data
    assert "total" in data
    assert "status" in data
    assert "created_at" in data


def test_total_is_correct():
    quote = _make_quote(total=Decimal("25960.00"))
    client = _make_client_with_quotes([quote])
    resp = client.get("/api/v1/quotes")
    assert resp.json()[0]["total"] == "25960.00"


def test_missing_auth_header_returns_401():
    from app.api.deps import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    app = create_app()

    def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    resp = client.get("/api/v1/quotes")
    assert resp.status_code == 401


def test_pdf_url_is_returned_when_set():
    quote = _make_quote(pdf_url="http://localhost:8000/pdfs/quote_abc.pdf")
    client = _make_client_with_quotes([quote])
    resp = client.get("/api/v1/quotes")
    assert resp.json()[0]["pdf_url"] == "http://localhost:8000/pdfs/quote_abc.pdf"


def test_pdf_url_is_none_when_not_set():
    quote = _make_quote(pdf_url=None)
    client = _make_client_with_quotes([quote])
    resp = client.get("/api/v1/quotes")
    assert resp.json()[0]["pdf_url"] is None


def test_approved_at_serialized():
    ts = datetime.datetime(2026, 4, 25, 12, 0, tzinfo=datetime.timezone.utc)
    quote = _make_quote(approved_at=ts, status=QuoteStatus.approved)
    client = _make_client_with_quotes([quote])
    resp = client.get("/api/v1/quotes")
    assert resp.json()[0]["approved_at"] is not None
