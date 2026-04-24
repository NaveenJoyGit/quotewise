"""Tests for SlotExtractor."""
import logging

import pytest

from app.services.conversation.slot_extractor import SlotExtractor
from app.services.llm.mock import MockLLMClient
from app.services.pricing.schemas import InputDef, InputValidation


def _make_def(name, type_, options=None, min_=None, max_=None, required=True):
    validation = InputValidation(min=min_, max=max_) if min_ is not None or max_ is not None else None
    return InputDef(name=name, type=type_, required=required, options=options, validation=validation)


AREA_DEF = _make_def("area_sqft", "number", min_=10, max_=10000)
SURFACE_DEF = _make_def("surface_type", "enum", options=["new_wall", "repaint_good_condition", "repaint_damaged"])
COATS_DEF = _make_def("coats", "integer", min_=1, max_=5)
TIER_DEF = _make_def("paint_brand_tier", "enum", options=["basic", "premium", "luxury"])


def test_happy_path_all_slots_returned():
    client = MockLLMClient(responses={
        "slot_extraction": {"area_sqft": 1000, "surface_type": "new_wall", "paint_brand_tier": "premium"},
    })
    extractor = SlotExtractor(client)
    result = extractor.extract("1000 sqft new wall premium", [AREA_DEF, SURFACE_DEF, TIER_DEF], {})
    assert result == {"area_sqft": 1000.0, "surface_type": "new_wall", "paint_brand_tier": "premium"}


def test_string_numeric_coercion():
    client = MockLLMClient(responses={"slot_extraction": {"area_sqft": "1000"}})
    extractor = SlotExtractor(client)
    result = extractor.extract("1000 sqft", [AREA_DEF], {})
    assert result["area_sqft"] == 1000.0


def test_integer_string_coercion():
    client = MockLLMClient(responses={"slot_extraction": {"coats": "3"}})
    extractor = SlotExtractor(client)
    result = extractor.extract("3 coats", [COATS_DEF], {})
    assert result["coats"] == 3


def test_null_values_skipped():
    client = MockLLMClient(responses={"slot_extraction": {"area_sqft": None, "surface_type": "new_wall"}})
    extractor = SlotExtractor(client)
    result = extractor.extract("new wall", [AREA_DEF, SURFACE_DEF], {})
    assert "area_sqft" not in result
    assert result["surface_type"] == "new_wall"


def test_below_min_value_dropped(caplog):
    client = MockLLMClient(responses={"slot_extraction": {"area_sqft": 5}})
    extractor = SlotExtractor(client)
    with caplog.at_level(logging.WARNING, logger="app.services.conversation.slot_extractor"):
        result = extractor.extract("5 sqft", [AREA_DEF], {})
    assert "area_sqft" not in result
    assert any("slot.extraction.invalid" in r.getMessage() for r in caplog.records)


def test_bad_enum_value_dropped(caplog):
    client = MockLLMClient(responses={"slot_extraction": {"surface_type": "marble"}})
    extractor = SlotExtractor(client)
    with caplog.at_level(logging.WARNING, logger="app.services.conversation.slot_extractor"):
        result = extractor.extract("marble walls", [SURFACE_DEF], {})
    assert "surface_type" not in result
    assert any("slot.extraction.invalid" in r.getMessage() for r in caplog.records)


def test_unknown_slot_name_ignored():
    client = MockLLMClient(responses={"slot_extraction": {"unknown_slot": "value"}})
    extractor = SlotExtractor(client)
    result = extractor.extract("something", [AREA_DEF], {})
    assert "unknown_slot" not in result


def test_empty_missing_defs_returns_empty():
    client = MockLLMClient()
    extractor = SlotExtractor(client)
    result = extractor.extract("some message", [], {})
    assert result == {}


def test_non_numeric_string_not_coerced_for_number_slot():
    """If LLM returns a non-numeric string for a number slot, validation should drop it."""
    client = MockLLMClient(responses={"slot_extraction": {"area_sqft": "large room"}})
    extractor = SlotExtractor(client)
    result = extractor.extract("large room", [AREA_DEF], {})
    # "large room" can't be coerced and will fail type validation — dropped
    assert "area_sqft" not in result


def test_non_numeric_string_not_coerced_for_integer_slot():
    """If LLM returns a non-parseable string for an integer slot, it should be dropped."""
    client = MockLLMClient(responses={"slot_extraction": {"coats": "two"}})
    extractor = SlotExtractor(client)
    result = extractor.extract("two coats", [COATS_DEF], {})
    # "two" can't be int() parsed — fails validation
    assert "coats" not in result


def test_llm_error_returns_empty(caplog):
    from app.services.llm.base import LLMError, LLMClient, LLMJsonResponse, LLMTextResponse

    class FailingClient(LLMClient):
        def extract_json(self, template_name, context, response_schema=None):
            raise LLMError("boom")
        def generate_text(self, template_name, context):
            raise LLMError("boom")

    extractor = SlotExtractor(FailingClient())
    with caplog.at_level(logging.WARNING, logger="app.services.conversation.slot_extractor"):
        result = extractor.extract("some message", [AREA_DEF], {})
    assert result == {}
