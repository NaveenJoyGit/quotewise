"""Tests for get_llm_client factory."""
import logging

from app.services.llm.factory import get_llm_client
from app.services.llm.mock import MockLLMClient


def test_factory_returns_mock_when_provider_mock(settings):
    assert settings.llm_provider == "mock"
    client = get_llm_client(settings=settings)
    assert isinstance(client, MockLLMClient)


def test_factory_flash_returns_mock_in_test_env(settings):
    client = get_llm_client(model="flash", settings=settings)
    assert isinstance(client, MockLLMClient)


def test_factory_pro_returns_mock_in_test_env(settings):
    client = get_llm_client(model="pro", settings=settings)
    assert isinstance(client, MockLLMClient)


def test_factory_returns_mock_when_vertex_but_no_project_id(settings, caplog):
    settings.model_config  # just access config
    import os
    os.environ["LLM_PROVIDER"] = "vertex"
    os.environ["GCP_PROJECT_ID"] = ""
    from app.core.config import Settings
    s = Settings()
    with caplog.at_level(logging.WARNING, logger="app.services.llm.factory"):
        client = get_llm_client(settings=s)
    assert isinstance(client, MockLLMClient)
    assert any("fallback" in r.getMessage().lower() for r in caplog.records)
    # restore
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ.pop("GCP_PROJECT_ID", None)


def test_factory_logs_provider_selected(caplog):
    from app.core.config import Settings
    s = Settings()
    with caplog.at_level(logging.INFO, logger="app.services.llm.factory"):
        get_llm_client(settings=s)
    assert any("llm.provider.selected" in r.getMessage() for r in caplog.records)
