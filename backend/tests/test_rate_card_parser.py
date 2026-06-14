"""Tests for RateCardParser and rate card extractor."""
import io

import pytest

from app.services.llm.base import LLMParseError
from app.services.llm.mock import MockLLMClient
from app.services.pricing.seed_rules import PAINTING_RULES
from app.services.rate_card.extractor import UnsupportedFormatError, extract_text
from app.services.rate_card.parser import RateCardParser

# ---------------------------------------------------------------------------
# Minimal valid rules that match PricingRules schema
# ---------------------------------------------------------------------------
_VALID_RULES = {
    "schema_version": 1,
    "base_formula": "area_sqft * base_rate",
    "inputs": [
        {
            "name": "area_sqft",
            "type": "number",
            "required": True,
            "question_template": "What area?",
        }
    ],
    "rate_table": [{"conditions": {"surface_type": "new_wall"}, "base_rate": 14}],
    "modifiers": [{"name": "gst", "type": "tax", "rate": 0.18}],
    "line_item_template": [
        {"description": "Work", "quantity_field": "area_sqft", "unit": "sqft", "rate_source": "computed_rate"}
    ],
}


# ---------------------------------------------------------------------------
# RateCardParser tests
# ---------------------------------------------------------------------------

class TestRateCardParser:
    def test_valid_rules_no_validation_errors(self):
        llm = MockLLMClient(responses={"rate_card_ingest": dict(_VALID_RULES)})
        result = RateCardParser(llm).parse("painting rates: Rs. 14 per sqft")
        assert result.validation_errors == []
        assert result.notes == []
        assert result.rules["base_formula"] == "area_sqft * base_rate"

    def test_notes_stripped_from_rules_and_returned(self):
        rules_with_notes = {**_VALID_RULES, "_notes": ["Assumed 18% GST"]}
        llm = MockLLMClient(responses={"rate_card_ingest": rules_with_notes})
        result = RateCardParser(llm).parse("some rate card")
        assert "_notes" not in result.rules
        assert "Assumed 18% GST" in result.notes

    def test_invalid_rules_returns_validation_errors_but_still_returns(self):
        # Missing required 'base_formula' field.
        incomplete = {
            "schema_version": 1,
            "inputs": [],
            "rate_table": [],
            "line_item_template": [],
        }
        llm = MockLLMClient(responses={"rate_card_ingest": incomplete})
        result = RateCardParser(llm).parse("bad rate card")
        assert len(result.validation_errors) > 0
        # Still returns the raw dict (not raises).
        assert result.rules is not None

    def test_llm_parse_error_propagates(self):
        class BadLLM(MockLLMClient):
            def extract_json(self, template_name, context, response_schema=None):
                raise LLMParseError("bad JSON")

        with pytest.raises(LLMParseError):
            RateCardParser(BadLLM()).parse("something")

    def test_work_type_hint_passed_to_llm(self):
        captured = {}

        class CaptureLLM(MockLLMClient):
            def extract_json(self, template_name, context, response_schema=None):
                captured["context"] = context
                return super().extract_json(template_name, context, response_schema)

        llm = CaptureLLM(responses={"rate_card_ingest": dict(_VALID_RULES)})
        RateCardParser(llm).parse("text", work_type_hint="painting")
        assert captured["context"]["work_type_hint"] == "painting"

    def test_real_painting_rules_pass_validation(self):
        llm = MockLLMClient(responses={"rate_card_ingest": dict(PAINTING_RULES)})
        result = RateCardParser(llm).parse("painting rate card")
        assert result.validation_errors == []


# ---------------------------------------------------------------------------
# Text extractor tests
# ---------------------------------------------------------------------------

class TestExtractor:
    def test_txt_file_decoded(self):
        content = "Painting: Rs. 14/sqft"
        result = extract_text(content.encode("utf-8"), "rates.txt")
        assert result == content

    def test_csv_file_decoded(self):
        content = "type,rate\nnew_wall,14"
        result = extract_text(content.encode("utf-8"), "rates.csv")
        assert result == content

    def test_unsupported_extension_raises(self):
        with pytest.raises(UnsupportedFormatError):
            extract_text(b"data", "rates.xlsx")

    def test_unsupported_image_raises(self):
        with pytest.raises(UnsupportedFormatError):
            extract_text(b"\xff\xd8\xff", "rates.jpg")

    def test_pdf_with_text_layer(self):
        # Create a minimal PDF with text using pypdf writer.
        import pypdf
        from pypdf import PdfWriter

        writer = PdfWriter()
        page = writer.add_blank_page(width=200, height=200)
        buf = io.BytesIO()
        writer.write(buf)
        pdf_bytes = buf.getvalue()
        # Blank page has no text — result should be empty string (not raise).
        result = extract_text(pdf_bytes, "blank.pdf")
        assert isinstance(result, str)
