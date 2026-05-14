"""Tests for the get_current_contractor FastAPI dependency (SPEC §3.3)."""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import create_app


def _client_with_db(contractor_return_value=None):
    """Return a TestClient where every DB query returns contractor_return_value."""
    from app.api.deps import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = contractor_return_value

    app = create_app()

    def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


class TestMissingKey:
    def test_no_header_returns_401(self):
        client = _client_with_db()
        resp = client.get("/api/v1/quotes")
        assert resp.status_code == 401
        assert "X-Contractor-Key" in resp.json()["detail"]

    def test_empty_string_header_returns_401(self):
        client = _client_with_db()
        resp = client.get("/api/v1/quotes", headers={"X-Contractor-Key": ""})
        assert resp.status_code == 401


class TestInvalidKeyFormat:
    def test_non_uuid_string_returns_401(self):
        client = _client_with_db()
        resp = client.get("/api/v1/quotes", headers={"X-Contractor-Key": "not-a-uuid"})
        assert resp.status_code == 401
        assert "Invalid API key format" in resp.json()["detail"]

    def test_truncated_uuid_returns_401(self):
        client = _client_with_db()
        resp = client.get("/api/v1/quotes", headers={"X-Contractor-Key": "abc123"})
        assert resp.status_code == 401


class TestUnknownKey:
    def test_valid_uuid_not_in_db_returns_401(self):
        client = _client_with_db(contractor_return_value=None)
        resp = client.get(
            "/api/v1/quotes",
            headers={"X-Contractor-Key": str(uuid.uuid4())},
        )
        assert resp.status_code == 401
        assert "Invalid API key" in resp.json()["detail"]


class TestValidKey:
    def test_known_key_reaches_endpoint(self):
        key = uuid.uuid4()
        contractor = SimpleNamespace(
            id=uuid.uuid4(),
            api_key=key,
        )
        from app.api.deps import get_db, get_current_contractor

        mock_db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value.all.return_value = []
        mock_db.query.return_value = q

        app = create_app()

        def override_db():
            yield mock_db

        def override_auth():
            return contractor

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_contractor] = override_auth
        client = TestClient(app)

        resp = client.get("/api/v1/quotes", headers={"X-Contractor-Key": str(key)})
        assert resp.status_code == 200
        assert resp.json() == []
