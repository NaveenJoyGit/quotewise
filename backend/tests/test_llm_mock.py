"""Tests for MockLLMClient."""
import pytest

from app.services.llm.mock import MockLLMClient


def _slot_defs():
    return [{"name": "area_sqft", "type": "number", "options": None, "validation": {"min": 10, "max": 10000}}]


def test_extract_json_returns_default_empty_dict():
    client = MockLLMClient()
    resp = client.extract_json("slot_extraction", {"slot_defs": _slot_defs(), "buyer_message": "hi"})
    assert resp.data == {}
    assert resp.metadata.model == "mock"
    assert resp.metadata.success is True


def test_extract_json_returns_canned_dict():
    client = MockLLMClient(responses={"slot_extraction": {"area_sqft": 500}})
    resp = client.extract_json("slot_extraction", {"slot_defs": _slot_defs(), "buyer_message": "500 sqft"})
    assert resp.data == {"area_sqft": 500}


def test_extract_json_callable_response():
    def extractor(rendered_prompt: str) -> dict:
        assert "500 sqft" in rendered_prompt
        return {"area_sqft": 500}

    client = MockLLMClient(responses={"slot_extraction": extractor})
    resp = client.extract_json("slot_extraction", {"slot_defs": _slot_defs(), "buyer_message": "500 sqft"})
    assert resp.data == {"area_sqft": 500}


def test_generate_text_returns_canned_string():
    client = MockLLMClient()
    resp = client.generate_text("greeting", {"business_name": "ABC Painters"})
    assert isinstance(resp.text, str)
    assert len(resp.text) > 0
    assert resp.metadata.model == "mock"


def test_generate_text_callable_response():
    client = MockLLMClient(responses={"greeting": lambda _: "Hello from mock!"})
    resp = client.generate_text("greeting", {"business_name": "Test"})
    assert resp.text == "Hello from mock!"


def test_llm_call_log_emitted(caplog):
    import logging

    client = MockLLMClient()
    with caplog.at_level(logging.INFO, logger="app.services.llm.base"):
        client.generate_text("greeting", {"business_name": "Test"})

    log_events = [r.getMessage() for r in caplog.records]
    assert any("llm.call" in e for e in log_events)


def test_metadata_token_counts_are_non_negative():
    client = MockLLMClient(responses={"slot_extraction": {"area_sqft": 500}})
    resp = client.extract_json("slot_extraction", {"slot_defs": _slot_defs(), "buyer_message": "500 sqft"})
    assert resp.metadata.input_tokens >= 0
    assert resp.metadata.output_tokens >= 0
    assert resp.metadata.latency_ms >= 0


def test_template_error_surfaces_with_missing_var():
    """StrictUndefined in loader means missing vars raise UndefinedError even in mock."""
    from jinja2 import UndefinedError

    client = MockLLMClient()
    with pytest.raises(UndefinedError):
        client.generate_text("greeting", {})  # missing business_name


def test_extract_json_non_dict_value_returns_empty():
    client = MockLLMClient(responses={"slot_extraction": "not a dict"})
    resp = client.extract_json("slot_extraction", {"slot_defs": _slot_defs(), "buyer_message": "hi"})
    assert resp.data == {}
