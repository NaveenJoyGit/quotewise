"""Tests for WorkTypeDetector."""
import pytest

from app.services.conversation.work_type_detector import WorkTypeDetector
from app.services.llm.base import LLMError
from app.services.llm.mock import MockLLMClient

AVAILABLE = ["painting", "false_ceiling"]


def _client(work_type_value: str) -> MockLLMClient:
    return MockLLMClient(
        responses={"work_type_detection": {"work_type": work_type_value}}
    )


def test_detect_painting():
    detector = WorkTypeDetector(_client("painting"))
    result = detector.detect("I want to paint my living room", AVAILABLE, "TestCo")
    assert result == "painting"


def test_detect_false_ceiling():
    detector = WorkTypeDetector(_client("false_ceiling"))
    result = detector.detect("Need gypsum board ceiling", AVAILABLE, "TestCo")
    assert result == "false_ceiling"


def test_detect_unclear_returns_none():
    detector = WorkTypeDetector(_client("unclear"))
    result = detector.detect("Hi, I need a quote", AVAILABLE, "TestCo")
    assert result is None


def test_detect_invalid_work_type_returns_none():
    # LLM returns a value not in available_work_types.
    detector = WorkTypeDetector(_client("plumbing"))
    result = detector.detect("Need plumbing work", AVAILABLE, "TestCo")
    assert result is None


def test_detect_llm_error_returns_none():
    class ErrorLLM(MockLLMClient):
        def extract_json(self, template_name, context, response_schema=None):
            raise LLMError("network down")

    detector = WorkTypeDetector(ErrorLLM())
    result = detector.detect("some message", AVAILABLE, "TestCo")
    assert result is None


def test_detect_single_work_type_painting():
    # Only painting available — LLM would say painting.
    detector = WorkTypeDetector(_client("painting"))
    result = detector.detect("hi", ["painting"], "TestCo")
    assert result == "painting"


def test_detect_with_empty_message():
    detector = WorkTypeDetector(_client("unclear"))
    result = detector.detect("", AVAILABLE, "TestCo")
    assert result is None
