"""Deterministic approval keyword parser (SPEC §6.2 — never use LLM for this)."""
from __future__ import annotations

import enum
import re


class ApprovalAction(str, enum.Enum):
    approve = "approve"
    reject = "reject"
    unknown = "unknown"


# Word-boundary patterns so "cannot" doesn't match "no", "nobody" doesn't match "no", etc.
_APPROVE_RE = re.compile(r"\b(approve|yes|ok|send)\b", re.IGNORECASE)
_REJECT_RE = re.compile(r"\b(reject|no|cancel)\b", re.IGNORECASE)


def parse_approval_keyword(text: str) -> ApprovalAction:
    """Return the contractor's intent from a raw WhatsApp reply.

    Approve patterns take priority over reject (so "approve or cancel" → approve).
    """
    text = text.strip()
    if _APPROVE_RE.search(text):
        return ApprovalAction.approve
    if _REJECT_RE.search(text):
        return ApprovalAction.reject
    return ApprovalAction.unknown
