"""Application settings loaded from environment variables."""

from simpli_core.connectors.settings import SalesforceSettings
from simpli_core.settings import CustomFieldSettings, SimpliSettings


class Settings(SimpliSettings, SalesforceSettings, CustomFieldSettings):
    app_port: int = 8006

    workers: int = 1

    # LLM
    litellm_model: str = "openrouter/google/gemini-2.5-flash-lite"

    # Optional integrations
    database_url: str | None = None
    redis_url: str | None = None


settings = Settings()
