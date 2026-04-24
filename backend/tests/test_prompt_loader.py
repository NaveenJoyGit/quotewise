"""Tests for the Jinja2 prompt loader."""
import pytest
from jinja2 import UndefinedError

from app.prompts.loader import list_templates, render_prompt

EXPECTED_TEMPLATES = {"greeting.jinja", "question_phrasing.jinja", "slot_extraction.jinja"}


def test_list_templates_includes_expected():
    templates = set(list_templates())
    assert EXPECTED_TEMPLATES.issubset(templates)


def test_render_greeting():
    out = render_prompt("greeting", business_name="ABC Painters")
    assert "ABC Painters" in out


def test_render_greeting_with_extension():
    out = render_prompt("greeting.jinja", business_name="ABC Painters")
    assert "ABC Painters" in out


def test_render_slot_extraction_contains_invariants():
    slot_defs = [
        {"name": "area_sqft", "type": "number", "options": None, "validation": {"min": 10, "max": 10000}},
        {"name": "surface_type", "type": "enum", "options": ["new_wall", "repaint_good_condition", "repaint_damaged"], "validation": None},
    ]
    out = render_prompt("slot_extraction", slot_defs=slot_defs, buyer_message="I want to paint 1000 sqft")
    assert "Return ONLY valid JSON" in out
    assert "area_sqft" in out
    assert "surface_type" in out
    assert "1000 sqft" in out
    assert "new_wall" in out


def test_render_question_phrasing():
    slot_def = {
        "name": "area_sqft",
        "type": "number",
        "options": None,
        "validation": {"min": 10, "max": 10000},
        "question_template": "What's the approximate area in square feet?",
    }
    out = render_prompt(
        "question_phrasing",
        slot_def=slot_def,
        business_name="ABC Painters",
        collected_so_far={},
    )
    assert "area_sqft" in out
    assert "ABC Painters" in out


def test_strict_undefined_raises_on_missing_var():
    with pytest.raises(UndefinedError):
        render_prompt("greeting")  # missing business_name


def test_slot_extraction_untrusted_input_marker():
    slot_defs = [{"name": "area_sqft", "type": "number", "options": None, "validation": None}]
    out = render_prompt("slot_extraction", slot_defs=slot_defs, buyer_message="test")
    assert "untrusted" in out.lower()
