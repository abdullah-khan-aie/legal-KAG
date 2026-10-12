from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import (
    AWSSecretsManagerSettingsSource,
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """Application settings for the ingestion and query pipelines.

    Field ``foo_bar`` maps to the ``FOO_BAR`` key in the secret.
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Load all config from one AWS Secrets Manager secret.

        The env and .env sources are dropped on purpose, so only
        AWS_SECRETS_MANAGER_SECRET_ID and AWS credentials come from the environment.
        """
        secret_id = os.getenv("AWS_SECRETS_MANAGER_SECRET_ID")
        if not secret_id:
            raise RuntimeError(
                "AWS_SECRETS_MANAGER_SECRET_ID is not set. All configuration is "
                "read exclusively from AWS Secrets Manager (no .env / env "
                "fallback); set it to the secret id, e.g. 'env'."
            )
        aws_secrets = AWSSecretsManagerSettingsSource(
            settings_cls,
            secret_id,
            region_name=os.getenv("AWS_SECRETS_MANAGER_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or os.getenv("AWS_REGION"),
            # Without this, UPPER_CASE secret keys never bind to the lower-case
            # field names, because the source defaults to case_sensitive=True.
            case_sensitive=False,
        )
        return init_settings, aws_secrets

    # Most fields below have no default, so a key missing from the secret fails
    # startup loudly rather than running on a stale hardcoded value.

    schema_path: str
    llm_model: str

    # Bare Cohere model id, e.g. "embed-v4.0". Ingest uses "search_document";
    # retrieval switches to "search_query".
    embed_model: str
    embed_input_type: str
    # Also sizes the Neo4j vector indexes, so query and indexed vectors always
    # match. Changing it after the indexes exist means dropping them first.
    embed_dimension: int = 1536

    # SecretStr keeps the key masked in logs. Unset falls back to the SDK's own
    # ANTHROPIC_API_KEY / CO_API_KEY variables.
    anthropic_api_key: SecretStr | None = None
    cohere_api_key: SecretStr | None = None

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = "test1234"
    neo4j_database: str = "neo4j"

    # Label prefix. Empty means labels are used as-is, e.g. "Contract".
    namespace: str

    # Each index contributes both an ingest extractor and a query retriever, so
    # listing one here keeps ingestion and retrieval in lockstep.
    index_list: list[str] = [
        "spo_graph_index",
        "summary_index",
        "chunk_index",
        "atomic_query_index",
    ]

    scan_dir: str = "ingest_docs"
    max_concurrency: int

    # Caps concurrent chunk extractions across all in-flight documents. Each task
    # fans out into several LLM sub-calls, so real in-flight calls are a multiple
    # of this. Raise it only as far as the Anthropic rate limit allows.
    model_execute_num: int

    log_level: str
    log_format: Literal["console", "json"]

    # Tracing stays off unless explicitly enabled. When it is on, all three
    # Langfuse keys must be present or the client cannot start.
    enable_observability: bool = False
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: SecretStr | None = None
    environment: str = "dev"

    # USD per single token, not per million. Used to price each traced call.
    llm_input_cost_per_token: float
    llm_output_cost_per_token: float
    embed_cost_per_token: float


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
