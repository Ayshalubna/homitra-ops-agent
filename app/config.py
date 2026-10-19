"""Configuration, loaded from environment / .env. All settings are optional."""
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "stub"          # stub | openai | anthropic | groq
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""

    supabase_url: str = ""
    supabase_service_role_key: str = ""

    auto_approve: bool = False

    # --- production hardening (optional; empty = open, for local/offline use) ---
    api_token: str = ""                 # if set, callers must send Authorization: Bearer <token>
    cors_origins: str = "*"             # comma-separated allowed origins for the browser admin console

    @property
    def use_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]


settings = Settings()
