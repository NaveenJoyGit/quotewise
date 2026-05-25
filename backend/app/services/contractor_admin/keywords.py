"""Deterministic confirm/cancel keywords for admin sessions (FR-001)."""
from __future__ import annotations

import enum
import re


class AdminConfirmAction(str, enum.Enum):
    save = "save"
    cancel = "cancel"
    unknown = "unknown"


_SAVE_RE = re.compile(r"\b(yes|save|confirm|ok)\b", re.IGNORECASE)
_CANCEL_RE = re.compile(r"\b(cancel|no|abort|stop)\b", re.IGNORECASE)


def parse_admin_confirm(text: str) -> AdminConfirmAction:
    text = text.strip()
    if _SAVE_RE.search(text):
        return AdminConfirmAction.save
    if _CANCEL_RE.search(text):
        return AdminConfirmAction.cancel
    return AdminConfirmAction.unknown
