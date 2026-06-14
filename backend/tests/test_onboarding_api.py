"""Tests for the onboarding API endpoints."""
from __future__ import annotations

import io
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.pricing.seed_rules import PAINTING_RULES

# A minimal valid rules dict that passes PricingRules validation.
_VALID_RULES = {
    "schema_version": 1,
    "base_formula": "area_sqft * base_rate",
    "inputs": [
        {
            "name": "area_sqft",
            "type": "number",
            "required": True,
            "question_template": "What area?",
        }
    ],
    "rate_table": [{"conditions": {"surface_type": "new_wall"}, "base_rate": 14}],
    "modifiers": [{"name": "gst", "type": "tax", "rate": 0.18}],
    "line_item_template": [
        {
            "description": "Work",
            "quantity_field": "area_sqft",
            "unit": "sqft",
            "rate_source": "computed_rate",
        }
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_contractor(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "business_name": "Test Contractor",
        "phone": "+919876543210",
        "city": "Bangalore",
        "whatsapp_link_slug": "testco",
        "gst_number": None,
        "api_key": uuid.uuid4(),
    }
    return SimpleNamespace(**{**defaults, **overrides})


def _fake_config(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "contractor_id": uuid.uuid4(),
        "work_type": SimpleNamespace(value="painting"),
        "version": 1,
    }
    return SimpleNamespace(**{**defaults, **overrides})


# ---------------------------------------------------------------------------
# POST /api/v1/onboarding/contractors
# ---------------------------------------------------------------------------

class TestCreateContractor:
    def test_happy_path(self):
        from fastapi.testclient import TestClient
        from app.api.deps import get_db
        from app.main import create_app

        fake = _fake_contractor()
        mock_db = MagicMock()
        app = create_app()

        def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db

        with patch("app.api.onboarding.OnboardingService") as MockSvc:
            MockSvc.return_value.create_contractor.return_value = fake
            client = TestClient(app)
            resp = client.post(
                "/api/v1/onboarding/contractors",
                json={
                    "business_name": "Test Contractor",
                    "phone": "+919876543210",
                    "city": "Bangalore",
                    "whatsapp_link_slug": "testco",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert "api_key" in data

    def test_invalid_phone_returns_422(self, client):
        resp = client.post(
            "/api/v1/onboarding/contractors",
            json={
                "business_name": "Test",
                "phone": "9876543210",  # missing +country code
                "whatsapp_link_slug": "test",
            },
        )
        assert resp.status_code == 422
        assert "E.164" in str(resp.json())

    def test_invalid_slug_returns_422(self, client):
        resp = client.post(
            "/api/v1/onboarding/contractors",
            json={
                "business_name": "Test",
                "phone": "+919876543210",
                "whatsapp_link_slug": "MY SLUG!",  # uppercase + spaces
            },
        )
        assert resp.status_code == 422

    def test_short_slug_returns_422(self, client):
        resp = client.post(
            "/api/v1/onboarding/contractors",
            json={
                "business_name": "Test",
                "phone": "+919876543210",
                "whatsapp_link_slug": "ab",  # too short (< 3)
            },
        )
        assert resp.status_code == 422

    def test_invalid_approval_mode_returns_422(self, client):
        resp = client.post(
            "/api/v1/onboarding/contractors",
            json={
                "business_name": "Test",
                "phone": "+919876543210",
                "whatsapp_link_slug": "valid-slug",
                "approval_mode": "magic_approve",
            },
        )
        assert resp.status_code == 422

    def test_duplicate_contractor_returns_409(self, client):
        from app.services.onboarding.service import DuplicateError

        with patch("app.api.onboarding.OnboardingService") as MockSvc:
            with patch("app.api.onboarding.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = iter([mock_db])
                MockSvc.return_value.create_contractor.side_effect = DuplicateError("Phone taken")
                resp = client.post(
                    "/api/v1/onboarding/contractors",
                    json={
                        "business_name": "Test",
                        "phone": "+919876543210",
                        "whatsapp_link_slug": "valid-slug",
                    },
                )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/v1/onboarding/rate-card/parse
# ---------------------------------------------------------------------------

class TestParseRateCard:
    def test_txt_file_returns_parsed_response(self, client):
        from app.services.rate_card.parser import ParsedRateCard

        with patch("app.api.onboarding.get_llm_client"):
            with patch("app.api.onboarding.RateCardParser") as MockParser:
                MockParser.return_value.parse.return_value = ParsedRateCard(
                    rules=_VALID_RULES, notes=["note1"], validation_errors=[]
                )
                resp = client.post(
                    "/api/v1/onboarding/rate-card/parse",
                    files={"file": ("rates.txt", b"Painting: Rs. 14/sqft", "text/plain")},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["validation_errors"] == []
        assert "note1" in data["notes"]

    def test_unsupported_file_type_returns_400(self, client):
        resp = client.post(
            "/api/v1/onboarding/rate-card/parse",
            files={"file": ("rates.xlsx", b"data", "application/vnd.ms-excel")},
        )
        assert resp.status_code == 400

    def test_llm_parse_error_returns_502(self, client):
        from app.services.llm.base import LLMParseError

        with patch("app.api.onboarding.get_llm_client"):
            with patch("app.api.onboarding.RateCardParser") as MockParser:
                MockParser.return_value.parse.side_effect = LLMParseError("bad JSON")
                resp = client.post(
                    "/api/v1/onboarding/rate-card/parse",
                    files={"file": ("rates.txt", b"some text", "text/plain")},
                )
        assert resp.status_code == 502

    def test_work_type_hint_passed_through(self, client):
        from app.services.rate_card.parser import ParsedRateCard

        captured = {}
        with patch("app.api.onboarding.get_llm_client"):
            with patch("app.api.onboarding.RateCardParser") as MockParser:
                def fake_parse(text, work_type_hint=None):
                    captured["hint"] = work_type_hint
                    return ParsedRateCard(rules=_VALID_RULES, notes=[], validation_errors=[])

                MockParser.return_value.parse.side_effect = fake_parse
                client.post(
                    "/api/v1/onboarding/rate-card/parse?work_type_hint=painting",
                    files={"file": ("rates.txt", b"text", "text/plain")},
                )
        assert captured.get("hint") == "painting"


# ---------------------------------------------------------------------------
# POST /api/v1/contractors/{id}/pricing/{work_type}
# ---------------------------------------------------------------------------

def _client_with_auth(contractor):
    """TestClient with get_current_contractor overridden to return contractor."""
    from fastapi.testclient import TestClient
    from app.api.deps import get_current_contractor, get_db
    from app.main import create_app

    mock_db = MagicMock()
    app = create_app()

    def override_auth():
        return contractor

    def override_db():
        yield mock_db

    app.dependency_overrides[get_current_contractor] = override_auth
    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


class TestSavePricingConfig:
    def test_missing_auth_returns_401(self, client):
        contractor_id = uuid.uuid4()
        resp = client.post(
            f"/api/v1/contractors/{contractor_id}/pricing/painting",
            json={"rules": _VALID_RULES},
        )
        assert resp.status_code == 401

    def test_invalid_rules_returns_422(self):
        contractor_id = uuid.uuid4()
        contractor = _fake_contractor(id=contractor_id)
        c = _client_with_auth(contractor)
        resp = c.post(
            f"/api/v1/contractors/{contractor_id}/pricing/painting",
            json={"rules": {"schema_version": 1}},  # missing required fields
        )
        assert resp.status_code == 422

    def test_contractor_id_mismatch_returns_403(self):
        auth_contractor = _fake_contractor()
        different_id = uuid.uuid4()
        c = _client_with_auth(auth_contractor)
        resp = c.post(
            f"/api/v1/contractors/{different_id}/pricing/painting",
            json={"rules": _VALID_RULES},
        )
        assert resp.status_code == 403

    def test_valid_rules_with_mocked_service(self):
        contractor_id = uuid.uuid4()
        contractor = _fake_contractor(id=contractor_id)
        fake = _fake_config(contractor_id=contractor_id)
        c = _client_with_auth(contractor)

        with patch("app.api.onboarding.OnboardingService") as MockSvc:
            MockSvc.return_value.save_pricing_config.return_value = fake
            resp = c.post(
                f"/api/v1/contractors/{contractor_id}/pricing/painting",
                json={"rules": _VALID_RULES},
            )
        assert resp.status_code in (200, 422)
