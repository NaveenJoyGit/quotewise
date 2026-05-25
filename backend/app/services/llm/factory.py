"""LLM client factory — picks Vertex or Mock based on settings (SPEC §4.4)."""
from __future__ import annotations

import logging
from typing import Literal

from app.core.config import Settings, get_settings
from app.services.llm.base import LLMClient
from app.services.llm.mock import MockLLMClient

logger = logging.getLogger(__name__)


def get_llm_client(
    model: Literal["flash", "pro"] = "flash",
    settings: Settings | None = None,
) -> LLMClient:
    """Return an LLMClient for the given model tier.

    `model="pro"` uses Gemini Pro (rate card ingestion — runs rarely, accuracy > speed).
    `model="flash"` uses Gemini Flash (all high-frequency calls).
    """
    s = settings or get_settings()
    if s.llm_vertex_enabled:
        from app.services.llm.vertex import VertexGeminiClient

        model_name = s.vertex_model_pro if model == "pro" else s.vertex_model_flash
        logger.info(
            "llm.provider.selected",
            extra={
                "event_type": "llm.provider.selected",
                "provider": "vertex",
                "model": model_name,
                "tier": model,
                "project": s.gcp_project_id,
            },
        )
        return VertexGeminiClient(s, model_name=model_name)

    if s.llm_provider == "vertex":
        logger.warning(
            "llm.provider.fallback",
            extra={
                "event_type": "llm.provider.fallback",
                "reason": "LLM_PROVIDER=vertex but GCP_PROJECT_ID not set; falling back to mock",
            },
        )

    logger.info(
        "llm.provider.selected",
        extra={"event_type": "llm.provider.selected", "provider": "mock", "tier": model},
    )
    return MockLLMClient()
