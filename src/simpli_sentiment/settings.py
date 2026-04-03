"""Application settings loaded from environment variables."""

from simpli_core.connectors.settings import SalesforceSettings
from simpli_core.settings import SimpliSettings


class Settings(SimpliSettings, SalesforceSettings):
    workers: int = 1

    # Optional integrations
    database_url: str | None = None
    redis_url: str | None = None


settings = Settings()
