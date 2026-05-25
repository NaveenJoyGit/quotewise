"""Deterministic admin prefix parser (FR-001)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.db.enums import AdminFlowType

_MANAGE_RATES = re.compile(r"^manage-rates(?:\s+(.*))?$", re.IGNORECASE)
_ONBOARD = re.compile(r"^onboard(?:\s+(.*))?$", re.IGNORECASE)


@dataclass(frozen=True)
class AdminPrefix:
    flow: AdminFlowType
    tail: str


def parse_admin_prefix(text: str | None) -> AdminPrefix | None:
    if not text:
        return None
    stripped = text.strip()
    m = _MANAGE_RATES.match(stripped)
    if m:
        return AdminPrefix(
            flow=AdminFlowType.manage_rates,
            tail=(m.group(1) or "").strip(),
        )
    m = _ONBOARD.match(stripped)
    if m:
        return AdminPrefix(
            flow=AdminFlowType.onboard,
            tail=(m.group(1) or "").strip(),
        )
    return None
