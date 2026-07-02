from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for the ingestion + query pipelines and their clients.

    Field ``foo_bar`` maps to the ``LODESTONE_FOO_BAR`` environment variable.
    """

    model_config = SettingsConfigDict(env_prefix="LODESTONE_", env_file=".env", extra="ignore")

    schema_path: str = "legal_schema.yaml"

    # LLM: Azure OpenAI on the v1 API surface -- base_url ends in /openai/v1/,
    # no api-version, and llm_model is the deployment name. Shared by ingestion
    # and query.
    llm_base_url: str = "https://your-resource.openai.azure.com/openai/v1/"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "gpt-4o"

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

    # Active KAG indices. Each name maps to a KAGIndexManager that contributes
    # BOTH its extractor(s) at ingest time and its retriever(s) at query time,
    # so ingestion and retrieval stay in lockstep. Set via LODESTONE_INDEX_LIST as
    # a JSON array, e.g. '["summary_index","chunk_index","atomic_query_index"]'.
    index_list: list[str] = ["spo_graph_index", "summary_index"]

    # Ingestion: local folder the directory scanner reads, and how many
    # documents to ingest concurrently (bounded to respect Azure rate limits).
    scan_dir: str = "ingest_docs"
    max_concurrency: int = 4

    log_level: str = "INFO"
    log_format: Literal["console", "json"] = "console"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
