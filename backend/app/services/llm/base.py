"""LLM client abstraction (SPEC §4.4).

Concrete implementations (Vertex, Mock) swap freely; business logic only depends on this ABC.
Every call logs template_name, model, tokens, latency per SPEC §8.3.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMParseError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


@dataclass(frozen=True)
class LLMCallMetadata:
    template_name: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class LLMTextResponse:
    text: str
    metadata: LLMCallMetadata


@dataclass(frozen=True)
class LLMJsonResponse:
    data: dict[str, Any]
    metadata: LLMCallMetadata


def _log_call(metadata: LLMCallMetadata) -> None:
    logger.info(
        "llm.call",
        extra={
            "event_type": "llm.call",
            "template_name": metadata.template_name,
            "model": metadata.model,
            "input_tokens": metadata.input_tokens,
            "output_tokens": metadata.output_tokens,
            "latency_ms": round(metadata.latency_ms, 1),
            "success": metadata.success,
            "error": metadata.error,
        },
    )


class LLMClient(ABC):
    @abstractmethod
    def extract_json(
        self,
        template_name: str,
        context: dict[str, Any],
        response_schema: type | dict | None = None,
    ) -> LLMJsonResponse:
        """Render template_name with context, call LLM, parse + return JSON dict."""

    @abstractmethod
    def generate_text(
        self,
        template_name: str,
        context: dict[str, Any],
    ) -> LLMTextResponse:
        """Render template_name with context, call LLM, return text."""
