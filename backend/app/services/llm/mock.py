"""MockLLMClient — deterministic canned responses for tests and offline dev.

Mirrors WhatsAppClient's mock-or-real pattern from M1.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from app.prompts.loader import render_prompt
from app.services.llm.base import (
    LLMCallMetadata,
    LLMClient,
    LLMJsonResponse,
    LLMTextResponse,
    _log_call,
)

_DEFAULT_RESPONSES: dict[str, Any] = {
    "greeting": "Hi! I'm here to help you get a painting quote. Could you tell me a bit about the space you'd like painted?",
    "question_phrasing": None,  # falls back to slot_def.question_template rendering
    "slot_extraction": {},
}


class MockLLMClient(LLMClient):
    """Returns canned responses keyed by template name (without .jinja extension).

    Values can be:
    - dict / str — returned directly
    - callable — called with the rendered prompt context; must return dict or str
    - None — generate_text returns "", extract_json returns {}
    """

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self._responses: dict[str, Any] = {**_DEFAULT_RESPONSES, **(responses or {})}

    def _resolve(self, template_name: str, rendered_prompt: str) -> Any:
        key = template_name.removesuffix(".jinja")
        val = self._responses.get(key)
        if callable(val):
            return val(rendered_prompt)
        return val

    def extract_json(
        self,
        template_name: str,
        context: dict[str, Any],
        response_schema: type | dict | None = None,
    ) -> LLMJsonResponse:
        t0 = time.perf_counter()
        rendered = render_prompt(template_name, **context)
        val = self._resolve(template_name, rendered)
        data = val if isinstance(val, dict) else {}
        latency_ms = (time.perf_counter() - t0) * 1000
        meta = LLMCallMetadata(
            template_name=template_name,
            model="mock",
            input_tokens=len(rendered) // 4,
            output_tokens=len(str(data)) // 4,
            latency_ms=latency_ms,
            success=True,
        )
        _log_call(meta)
        return LLMJsonResponse(data=data, metadata=meta)

    def generate_text(
        self,
        template_name: str,
        context: dict[str, Any],
    ) -> LLMTextResponse:
        t0 = time.perf_counter()
        rendered = render_prompt(template_name, **context)
        val = self._resolve(template_name, rendered)
        text = val if isinstance(val, str) else ""
        latency_ms = (time.perf_counter() - t0) * 1000
        meta = LLMCallMetadata(
            template_name=template_name,
            model="mock",
            input_tokens=len(rendered) // 4,
            output_tokens=len(text) // 4,
            latency_ms=latency_ms,
            success=True,
        )
        _log_call(meta)
        return LLMTextResponse(text=text, metadata=meta)
