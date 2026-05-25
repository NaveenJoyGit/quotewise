"""Tests for WhatsApp phone normalization (FR-001)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.services.whatsapp.phone import (
    find_contractor_by_phone,
    normalize_phone_e164,
    phones_match,
    phone_digits,
)


def test_phone_digits_strips_formatting():
    assert phone_digits("+91 98765-43210") == "919876543210"


def test_normalize_indian_meta_format():
    assert normalize_phone_e164("919876543210") == "+919876543210"


def test_normalize_e164_passthrough():
    assert normalize_phone_e164("+919876543210") == "+919876543210"


def test_normalize_ten_digit_local():
    assert normalize_phone_e164("9876543210") == "+919876543210"


def test_phones_match_meta_vs_e164():
    assert phones_match("919876543210", "+919876543210")


def test_find_contractor_by_phone():
    contractor = MagicMock(phone="+919999900001", id=uuid.uuid4())
    db = MagicMock()
    db.query.return_value.all.return_value = [contractor]
    found = find_contractor_by_phone(db, "919999900001")
    assert found is contractor


def test_find_contractor_by_phone_not_found():
    db = MagicMock()
    db.query.return_value.all.return_value = []
    assert find_contractor_by_phone(db, "919999900099") is None
