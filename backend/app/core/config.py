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

    @property
    def wa_send_enabled(self) -> bool:
        return bool(self.wa_access_token and self.wa_phone_number_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
