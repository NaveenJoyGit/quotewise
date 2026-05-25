"""Tests for admin prefix parsing (FR-001)."""
from app.db.enums import AdminFlowType
from app.services.contractor_admin.prefix import parse_admin_prefix


def test_parse_manage_rates():
    p = parse_admin_prefix("manage-rates")
    assert p is not None
    assert p.flow == AdminFlowType.manage_rates
    assert p.tail == ""


def test_parse_manage_rates_with_tail():
    p = parse_admin_prefix("MANAGE-RATES painting")
    assert p is not None
    assert p.flow == AdminFlowType.manage_rates
    assert p.tail == "painting"


def test_parse_onboard():
    p = parse_admin_prefix("onboard")
    assert p is not None
    assert p.flow == AdminFlowType.onboard


def test_parse_none():
    assert parse_admin_prefix("hello") is None
    assert parse_admin_prefix(None) is None
