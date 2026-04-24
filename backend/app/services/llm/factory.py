"""LLM client factory — picks Vertex or Mock based on settings (SPEC §4.4)."""
from __future__ import annotations

import logging

from app.core.config import Settings, get_settings
from app.services.llm.base import LLMClient
from app.services.llm.mock import MockLLMClient

logger = logging.getLogger(__name__)


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    s = settings or get_settings()
    if s.llm_vertex_enabled:
        from app.services.llm.vertex import VertexGeminiClient

        logger.info(
            "llm.provider.selected",
            extra={
                "event_type": "llm.provider.selected",
                "provider": "vertex",
                "model": s.vertex_model_flash,
                "project": s.gcp_project_id,
            },
        )
        return VertexGeminiClient(s)

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
        extra={"event_type": "llm.provider.selected", "provider": "mock"},
    )
    return MockLLMClient()
