import os

# Set test env vars before any app imports read settings.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("WA_VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("WA_APP_SECRET", "test-app-secret")
# Leave WA_ACCESS_TOKEN empty → client runs in mock mode (no network).

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def client():
    return TestClient(create_app())
