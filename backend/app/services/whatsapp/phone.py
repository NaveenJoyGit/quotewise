"""Phone normalization for WhatsApp routing (FR-001).

Meta webhooks send numbers  ids without a leading '+'; contractors are stored E.164 (+91…).
All inbound routing must use these helpers — never raw string equality.
"""
from __future__ import annotations

from sqlalchemy.orm import Session as DBSession

from app.db.models import Contractor


def strip_whatsapp_prefix(raw: str) -> str:
    """Strip Twilio's whatsapp: channel prefix from From/To."""
    stripped = raw.strip()
    if stripped.lower().startswith("whatsapp:"):
        return stripped[9:].strip()
    return stripped


def phone_digits(raw: str) -> str:
    """Return digits-only representation for comparison."""
    return "".join(c for c in raw if c.isdigit())


def normalize_phone_e164(raw: str) -> str:
    """Best-effort E.164 normalization for Indian contractor phones."""
    stripped = raw.strip()
    digits = phone_digits(stripped)
    if not digits:
        return stripped

    # 10-digit local Indian mobile → +91
    if len(digits) == 10:
        return f"+91{digits}"
    # Already includes country code (e.g. 919876543210)
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if stripped.startswith("+"):
        return stripped
    return f"+{digits}"


def phones_match(a: str, b: str) -> bool:
    """True if two phone strings refer to the same number."""
    return phone_digits(normalize_phone_e164(a)) == phone_digits(normalize_phone_e164(b))


def find_contractor_by_phone(db: DBSession, raw_phone: str) -> Contractor | None:
    """Look up a contractor by phone, tolerating + prefix and Meta format differences."""
    target_digits = phone_digits(normalize_phone_e164(raw_phone))
    for contractor in db.query(Contractor).all():
        if phone_digits(normalize_phone_e164(contractor.phone)) == target_digits:
            return contractor
    return None
