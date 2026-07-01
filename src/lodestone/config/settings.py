from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    """Settings for the ingestion pipeline and its model clients.

    Field ``foo_bar`` maps to the ``INGEST_FOO_BAR`` environment variable.
    """

    model_config = SettingsConfigDict(env_prefix="INGEST_", env_file=".env", extra="ignore")

    schema_path: str = "legal_schema.yaml"

    # LLM: Azure OpenAI, served via kag's AzureOpenAIClient (official Azure SDK).
    llm_base_url: str = "https://your-resource.openai.azure.com"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "gpt-4o"
    llm_azure_deployment: str = ""
    llm_api_version: str = "2024-12-01-preview"

    # Embeddings: Azure-hosted Cohere via azure-ai-inference (AzureCohereVectorizeModel).
    cohere_endpoint: str = "https://your-cohere-endpoint.models.ai.azure.com"
    cohere_api_key: SecretStr = SecretStr("")
    cohere_input_type: str = "document"

    # Neo4j graph store (required — the app won't start without a password; the
    # pipeline always persists + entity-links against it).
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr
    neo4j_database: str = "neo4j"

    # Label namespace prefix (empty = labels used as-is, e.g. "Contract").
    namespace: str = ""

    # Logging. Logs are written only to stdout (12-factor: the platform captures
    # and routes the stream). ``log_format`` picks the stdout formatter:
    #   - "console": human-readable, for local development;
    #   - "json": single-line JSON, for production log collectors
    #     (Datadog / CloudWatch / Azure Monitor all parse JSON from stdout).
    log_level: str = "INFO"
    log_format: Literal["console", "json"] = "console"


@lru_cache(maxsize=1)
def get_settings() -> IngestionSettings:
    """Return the process-wide settings singleton."""
    return IngestionSettings()
