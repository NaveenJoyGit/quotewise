from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["dev", "staging", "prod", "test"] = "dev"
    log_level: str = "INFO"

    wa_verify_token: str = Field(default="", description="Token echoed during Meta webhook setup")
    wa_app_secret: str = Field(default="", description="Used to HMAC-verify incoming webhooks")
    wa_access_token: str = Field(default="", description="Graph API bearer token; empty = mock mode")
    wa_phone_number_id: str = Field(default="", description="Meta phone_number_id for sending")
    wa_graph_api_version: str = "v21.0"

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+psycopg://quotewise:quotewise@localhost:5432/quotewise"

    # --- LLM ---
    llm_provider: Literal["mock", "vertex"] = "mock"
    gcp_project_id: str = Field(default="", description="GCP project for Vertex AI")
    gcp_location: str = "asia-south1"
    vertex_model_flash: str = "gemini-2.5-flash"
    vertex_model_pro: str = "gemini-2.5-pro"
    llm_call_timeout_seconds: int = 20

    # --- Session ---
    session_ttl_hours: int = 72

    # --- PDF & Quote delivery ---
    pdf_storage_dir: str = "data/pdfs"
    pdf_base_url: str = "http://localhost:8000"
    quote_validity_days: int = 30

    @property
    def wa_send_enabled(self) -> bool:
        return bool(self.wa_access_token and self.wa_phone_number_id)

    @property
    def llm_vertex_enabled(self) -> bool:
        return self.llm_provider == "vertex" and bool(self.gcp_project_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
