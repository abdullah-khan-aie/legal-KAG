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
    """Application settings for the ingestion + query pipelines and their clients.

    Field ``foo_bar`` maps to the ``LODESTONE_FOO_BAR`` environment variable.
    """

    model_config = SettingsConfigDict(env_prefix="LODESTONE_", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Load ALL application config solely from the AWS Secrets Manager secret.

        Secrets Manager is the single source of truth: there is deliberately NO
        fallback to environment variables or a ``.env`` file for ``LODESTONE_*``
        config -- the ``env``, ``.env`` and file-secret sources are dropped. Only
        the bootstrap values needed to REACH the secret are read from the real
        environment, and they are not app settings:

        * AWS credentials -- an SSO profile / ``AWS_*`` keys locally, or the EC2
          instance IAM role -- consumed by the boto3 client, not by pydantic.
        * ``AWS_SECRETS_MANAGER_SECRET_ID`` -- the secret to load (e.g.
          ``lodestone/env``); optionally ``AWS_SECRETS_MANAGER_REGION``.

        The secret is one JSON object whose keys match the ``LODESTONE_``-prefixed
        field names (the source inherits this model's ``env_prefix``).

        ``init_settings`` is kept first so explicit ``Settings(...)`` construction
        (e.g. in tests) still works; it contributes nothing at runtime since the
        app builds ``Settings()`` with no args.

        Raises:
            RuntimeError: if ``AWS_SECRETS_MANAGER_SECRET_ID`` is unset. With no
            fallback source, we fail fast rather than start mis-configured.
        """
        secret_id = os.getenv("AWS_SECRETS_MANAGER_SECRET_ID")
        if not secret_id:
            raise RuntimeError(
                "AWS_SECRETS_MANAGER_SECRET_ID is not set. All configuration is "
                "read exclusively from AWS Secrets Manager (no .env / env "
                "fallback); set it to the secret id, e.g. 'lodestone/env'."
            )
        aws_secrets = AWSSecretsManagerSettingsSource(
            settings_cls,
            secret_id,
            region_name=os.getenv("AWS_SECRETS_MANAGER_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or os.getenv("AWS_REGION"),
            # The source defaults to case_sensitive=True, so UPPER_CASE secret
            # keys (LODESTONE_NEO4J_PASSWORD) would not bind to the lower-case field
            # names. Match case-insensitively like normal env settings.
            case_sensitive=False,
        )
        return init_settings, aws_secrets

    # NOTE ON DEFAULTS: configuration is loaded solely from AWS Secrets Manager
    # (the ``lodestone/env`` secret). Most fields below carry NO in-code default, so
    # a key missing from the secret fails startup loudly instead of silently
    # falling back to a stale hardcoded value (e.g. a non-"global" model id). The
    # fields that DO keep a default are called out inline below.

    schema_path: str
    bedrock_region: str
    llm_model: str

    # Embeddings: called directly against Cohere's API (not Bedrock). embed_model
    # is a bare Cohere Embed model id, e.g. "embed-v4.0". input_type is
    # "search_document" for ingest ("search_query" for retrieval).
    embed_model: str
    embed_input_type: str
    # Embedding length. Single source of truth: it's both requested from Cohere
    # (output_dimension) and used to size the Neo4j vector indexes, so the indexed
    # vectors and query vectors always match. 1536 is Embed v4's native (untruncated)
    # size -- highest retrieval fidelity; 256/512/1024 are smaller Matryoshka
    # truncations. Changing this after indexes exist requires dropping them first.
    embed_dimension: int = 1536

    # Amazon Bedrock credentials, read from the secret and passed explicitly to the
    # LLM + embedding clients, so Bedrock calls use a Bedrock-scoped IAM user
    # independent of the infra credentials (terminal env / instance role) that
    # reach Secrets Manager. Leave unset to fall back to boto3's default chain
    # (e.g. an instance role scoped to Bedrock on EC2).
    bedrock_access_key_id: SecretStr | None = None
    bedrock_secret_access_key: SecretStr | None = None

    # Cohere API key for the direct (non-Bedrock) embedding client, read from the
    # secret and passed as a SecretStr so it stays masked in logs (unwrapped only
    # when the Cohere SDK client is constructed). Leave unset to fall back to the
    # SDK's CO_API_KEY environment variable.
    cohere_api_key: SecretStr | None = None

    # Neo4j graph store (the pipeline always persists + entity-links against it).
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = "test1234"
    neo4j_database: str = "neo4j"

    # Label namespace prefix (empty = labels used as-is, e.g. "Contract").
    namespace: str

    # Active KAG indices. Each name maps to a KAGIndexManager that contributes
    # BOTH its extractor(s) at ingest time and its retriever(s) at query time,
    # so ingestion and retrieval stay in lockstep. Set via LODESTONE_INDEX_LIST as
    # a JSON array, e.g. '["summary_index","chunk_index","atomic_query_index"]'.
    # NOT in the secret: kept defaulted. Add to the secret to make required.
    index_list: list[str] = ["spo_graph_index", "summary_index", "chunk_index"]

    # Ingestion: local folder the directory scanner reads, and how many documents
    # to ingest concurrently (bounded to respect Bedrock rate limits).
    # scan_dir has a TEMPORARY default; note the secret's LODESTONE_SCAN_DIR (if
    # present) still overrides it, so remove it from the secret to use this value.
    scan_dir: str = "ingest_docs"
    max_concurrency: int

    # Global cap on how many chunk-extraction tasks run at once, shared across all
    # in-flight documents: a single fixed-size pool of worker coroutines drains a
    # bounded queue (see IngestionPipeline). NOTE: each extraction task fans out
    # internally into ~4 concurrent LLM sub-calls (NER / relation / event /
    # standardization), so true in-flight calls are roughly this x 4. On this
    # low-quota Bedrock account keep it at 1; raise once the quota is increased.
    model_execute_num: int

    log_level: str
    log_format: Literal["console", "json"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
