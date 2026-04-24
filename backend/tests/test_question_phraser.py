"""Tests for QuestionPhraser."""
from app.services.conversation.question_phraser import QuestionPhraser
from app.services.llm.base import LLMClient, LLMError, LLMJsonResponse, LLMTextResponse
from app.services.llm.mock import MockLLMClient
from app.services.pricing.schemas import InputDef


def _area_def():
    return InputDef(
        name="area_sqft",
        type="number",
        question_template="What's the approximate area in square feet?",
    )


def test_happy_path_returns_llm_text():
    client = MockLLMClient(responses={"question_phrasing": "Could you tell me the area in sqft?"})
    phraser = QuestionPhraser(client)
    result = phraser.phrase_next(_area_def(), "ABC Painters", {})
    assert result == "Could you tell me the area in sqft?"


def test_empty_response_falls_back_to_template():
    client = MockLLMClient(responses={"question_phrasing": ""})
    phraser = QuestionPhraser(client)
    result = phraser.phrase_next(_area_def(), "ABC Painters", {})
    assert result == "What's the approximate area in square feet?"


def test_llm_error_falls_back_to_template():
    class FailingClient(LLMClient):
        def extract_json(self, t, c, rs=None):
            raise LLMError("boom")
        def generate_text(self, t, c):
            raise LLMError("boom")

    phraser = QuestionPhraser(FailingClient())
    result = phraser.phrase_next(_area_def(), "ABC Painters", {})
    assert result == "What's the approximate area in square feet?"


def test_no_question_template_uses_generic_fallback():
    idef = InputDef(name="area_sqft", type="number", question_template=None)
    client = MockLLMClient(responses={"question_phrasing": ""})
    phraser = QuestionPhraser(client)
    result = phraser.phrase_next(idef, "ABC Painters", {})
    assert "area_sqft" in result
