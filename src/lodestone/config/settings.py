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

    # LLM + embeddings both run on Amazon Bedrock via boto3, authenticated with
    # the standard AWS credential chain -- e.g. an SSO profile (`aws sso login`),
    # environment credentials, or an instance role. There is no API key; select
    # the profile with AWS_PROFILE when running.

    # LLM: Anthropic Claude on Bedrock via the Converse API. Use the BARE model
    # id and call in-region (eu-west-2 / London) so the request is not re-routed:
    # the "eu.*" cross-region inference profiles forward to other EU regions
    # (e.g. eu-north-1), which the org SCP on this account denies. In-region
    # eu-west-2 keeps inference (and data) in the UK/EU.
    bedrock_region: str = "eu-west-2"
    llm_model: str = "anthropic.claude-sonnet-4-6"

    # Embeddings: same rule -- bare Cohere model id, called in eu-west-2 (own
    # region setting, independent of the LLM). input_type is "search_document"
    # for ingest ("search_query" for retrieval).
    embed_region: str = "eu-west-2"
    embed_model: str = "cohere.embed-v4:0"
    embed_input_type: str = "search_document"

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
    # documents to ingest concurrently (bounded to respect Bedrock rate limits).
    scan_dir: str = "ingest_docs"
    max_concurrency: int = 4

    log_level: str = "INFO"
    log_format: Literal["console", "json"] = "console"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
