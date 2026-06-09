"""Tests for forwarded-quote session repo (FR-002)."""
from __future__ import annotations

import uuid


def test_fwd_buyer_phone_fits_widened_column():
    """Synthetic buyer_phone must fit sessions.buyer_phone VARCHAR(48)."""
    sid = uuid.uuid4()
    buyer_phone = f"fwd:{sid}"
    assert len(buyer_phone) == 40
    assert len(buyer_phone) <= 48
