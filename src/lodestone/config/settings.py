"""Application configuration, loaded from the environment via pydantic-settings.

Values are read from environment variables prefixed with ``INGEST_`` (or a local
``.env`` file). The defaults let the pipeline run out of the box against a sample
schema and public model endpoints; secrets default to empty and must be supplied
to call real models.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    """Settings for the ingestion pipeline and its model adapters.

    Field ``foo_bar`` maps to the ``INGEST_FOO_BAR`` environment variable.
    """

    model_config = SettingsConfigDict(env_prefix="INGEST_", env_file=".env", extra="ignore")

    schema_path: str = "legal_schema.yaml"

    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "deepseek-chat"

    embed_base_url: str = "https://api.siliconflow.cn/v1"
    embed_api_key: SecretStr = SecretStr("")
    embed_model: str = "BAAI/bge-m3"


@lru_cache(maxsize=1)
def get_settings() -> IngestionSettings:
    """Return the process-wide settings singleton."""
    return IngestionSettings()
