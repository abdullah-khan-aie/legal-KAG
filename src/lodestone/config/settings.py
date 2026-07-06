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
        )
        return init_settings, aws_secrets

    # NOTE ON DEFAULTS: config is supplied by the environment -- a ``.env`` file
    # locally, or the AWS Secrets Manager secret (``lodestone/env``) in deployment.
    # The fields below carry NO in-code defaults, so a key missing from every
    # source fails startup loudly instead of silently falling back to a stale
    # hardcoded value (e.g. a non-"global" model id). The only exceptions are the
    # three fields NOT stored in the secret -- ``llm_max_rate``, ``llm_time_period``
    # and ``index_list`` -- which keep defaults so they stay optional; move them
    # into the secret and drop their defaults to make them required too.

    schema_path: str
    bedrock_region: str
    llm_model: str

    # kag's LLMClient has a built-in request limiter (an AsyncLimiter keyed by
    # client name, process-global and shared across every extractor sub-call).
    # It ships defaulted to no-op (max_rate=1000, time_period=1); the frameworks
    # rely on concurrency (model_execute_num) instead. On this ContractorSandbox
    # Bedrock account, concurrency=1 alone still throttles (ThrottlingException),
    # because a per-minute quota is indifferent to how many workers we run. A rate
    # limiter caps calls-per-minute directly, which relieves BOTH the RPM and TPM
    # ceilings at once, so we wire it. Tune empirically (we can't see the quota):
    # allow llm_max_rate calls per llm_time_period seconds; lower the rate if
    # throttling persists, raise it once clean. Applied via chat_llm_config so
    # every extractor client shares the one limiter, and (with SummaryExtractor
    # now on the async path) all sub-calls draw from the single async bucket.
    # NOT in the secret: kept optional/tunable via .env while we calibrate the
    # Bedrock throttle. Add to the secret to make required.
    llm_max_rate: float = 1
    llm_time_period: float = 6

    # Embeddings: bare Cohere model id, called in its own region (independent of
    # the LLM). input_type is "search_document" for ingest ("search_query" for
    # retrieval).
    embed_region: str
    embed_model: str
    embed_input_type: str

    # Neo4j graph store (the pipeline always persists + entity-links against it).
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: SecretStr
    neo4j_database: str

    # Label namespace prefix (empty = labels used as-is, e.g. "Contract").
    namespace: str

    # Active KAG indices. Each name maps to a KAGIndexManager that contributes
    # BOTH its extractor(s) at ingest time and its retriever(s) at query time,
    # so ingestion and retrieval stay in lockstep. Set via LODESTONE_INDEX_LIST as
    # a JSON array, e.g. '["summary_index","chunk_index","atomic_query_index"]'.
    # NOT in the secret: kept defaulted. Add to the secret to make required.
    index_list: list[str] = ["spo_graph_index", "summary_index"]

    # Ingestion: local folder the directory scanner reads, and how many documents
    # to ingest concurrently (bounded to respect Bedrock rate limits).
    scan_dir: str
    max_concurrency: int

    # Global cap on how many chunk-extraction tasks run at once, shared across
    # all in-flight documents. Ported from OpenSPG-KAG's `modelExecuteNum`: the
    # Java builder (LLMNlExtractProcessor) drives extraction through a single
    # fixed-size worker pool -- one task per chunk, bounded queue, backpressure --
    # rather than a rate limiter. We port that exactly with an asyncio.Queue plus
    # this many worker coroutines (see IngestionPipeline).
    #
    # NOTE: each extraction task fans out internally into ~4 concurrent LLM
    # sub-calls (NER/SPO/event/std), so true in-flight calls ~= this x 4. KAG
    # defaults to 5 because its model endpoint is provisioned for it; on this
    # low-RPM Bedrock account keep it at 1 (concurrency is the sole control, as in
    # the frameworks). Raise once the Bedrock quota is increased.
    model_execute_num: int

    log_level: str
    log_format: Literal["console", "json"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
