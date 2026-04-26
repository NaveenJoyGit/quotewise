"""Tests for the approval keyword parser (SPEC §6.2 — deterministic, no LLM)."""
import pytest

from app.services.approval.keywords import ApprovalAction, parse_approval_keyword


@pytest.mark.parametrize(
    "text",
    ["approve", "APPROVE", "Approve", "yes", "YES", "ok", "OK", "Ok", "send", "SEND"],
)
def test_approve_keywords(text: str) -> None:
    assert parse_approval_keyword(text) == ApprovalAction.approve


@pytest.mark.parametrize(
    "text",
    ["reject", "REJECT", "Reject", "no", "NO", "No", "cancel", "CANCEL"],
)
def test_reject_keywords(text: str) -> None:
    assert parse_approval_keyword(text) == ApprovalAction.reject


@pytest.mark.parametrize(
    "text",
    ["", "   ", "edit: increase area", "maybe", "later", "help", "what?"],
)
def test_unknown_keywords(text: str) -> None:
    assert parse_approval_keyword(text) == ApprovalAction.unknown


def test_cannot_does_not_match_no() -> None:
    assert parse_approval_keyword("cannot") == ApprovalAction.unknown


def test_nobody_does_not_match_no() -> None:
    assert parse_approval_keyword("nobody") == ApprovalAction.unknown


def test_approve_takes_priority_over_cancel() -> None:
    # "approve or cancel" — approve regex runs first per SPEC §6.2
    assert parse_approval_keyword("approve or cancel") == ApprovalAction.approve


def test_whitespace_stripped() -> None:
    assert parse_approval_keyword("  approve  ") == ApprovalAction.approve


def test_mixed_case_reject() -> None:
    assert parse_approval_keyword("Reject this quote") == ApprovalAction.reject


def test_ok_in_sentence() -> None:
    assert parse_approval_keyword("ok looks good") == ApprovalAction.approve


def test_no_in_sentence() -> None:
    assert parse_approval_keyword("no thank you") == ApprovalAction.reject
