"""VertexGeminiClient — real Gemini Flash via Google Vertex AI (SPEC §4.4).

Lazy-imports vertexai so tests don't need the SDK at collection time.
Uses JSON-mode (response_mime_type="application/json") with schema-in-prompt.
Splits Jinja output on {# SYSTEM #}/{# USER #} markers for system_instruction (SPEC §9).
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.prompts.loader import render_prompt
from app.services.llm.base import (
    LLMCallMetadata,
    LLMClient,
    LLMError,
    LLMJsonResponse,
    LLMParseError,
    LLMTextResponse,
    LLMTimeoutError,
    _log_call,
)

logger = logging.getLogger(__name__)

_SYSTEM_MARKER = "{# SYSTEM #}"
_USER_MARKER = "{# USER #}"


def _split_prompt(rendered: str) -> tuple[str, str]:
    """Split a rendered Jinja template into system and user parts."""
    if _USER_MARKER in rendered:
        parts = rendered.split(_USER_MARKER, 1)
        system = parts[0].replace(_SYSTEM_MARKER, "").strip()
        user = parts[1].strip()
    else:
        system = ""
        user = rendered.strip()
    return system, user


class VertexGeminiClient(LLMClient):
    def __init__(self, settings: Any) -> None:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=settings.gcp_project_id, location=settings.gcp_location)
        self._model_name = settings.vertex_model_flash
        self._timeout = settings.llm_call_timeout_seconds
        self._model = GenerativeModel(self._model_name)

    def _call(
        self,
        template_name: str,
        context: dict[str, Any],
        json_mode: bool,
    ) -> tuple[str, int, int, float]:
        from google.api_core.exceptions import DeadlineExceeded, GoogleAPICallError
        from vertexai.generative_models import GenerationConfig

        rendered = render_prompt(template_name, **context)
        system_text, user_text = _split_prompt(rendered)

        generation_config = GenerationConfig(
            response_mime_type="application/json" if json_mode else "text/plain",
            temperature=0.0 if json_mode else 0.4,
        )

        t0 = time.perf_counter()
        try:
            response = self._model.generate_content(
                user_text,
                generation_config=generation_config,
                system_instruction=system_text if system_text else None,
            )
        except DeadlineExceeded as exc:
            raise LLMTimeoutError(f"Vertex timeout on {template_name}") from exc
        except GoogleAPICallError as exc:
            raise LLMError(f"Vertex API error on {template_name}: {exc}") from exc

        latency_ms = (time.perf_counter() - t0) * 1000
        text = response.text
        usage = response.usage_metadata
        return text, usage.prompt_token_count, usage.candidates_token_count, latency_ms

    def extract_json(
        self,
        template_name: str,
        context: dict[str, Any],
        response_schema: type | dict | None = None,
    ) -> LLMJsonResponse:
        text, in_tok, out_tok, latency_ms = self._call(template_name, context, json_mode=True)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            meta = LLMCallMetadata(
                template_name=template_name,
                model=self._model_name,
                input_tokens=in_tok,
                output_tokens=out_tok,
                latency_ms=latency_ms,
                success=False,
                error=str(exc),
            )
            _log_call(meta)
            raise LLMParseError(f"JSON parse failed for {template_name}: {exc}") from exc

        meta = LLMCallMetadata(
            template_name=template_name,
            model=self._model_name,
            input_tokens=in_tok,
            output_tokens=out_tok,
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
        text, in_tok, out_tok, latency_ms = self._call(template_name, context, json_mode=False)
        meta = LLMCallMetadata(
            template_name=template_name,
            model=self._model_name,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency_ms,
            success=True,
        )
        _log_call(meta)
        return LLMTextResponse(text=text, metadata=meta)
