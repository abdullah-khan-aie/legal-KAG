from __future__ import annotations

from functools import lru_cache

from kag.common.graphstore.neo4j_graph_store import Neo4jClient
from kag.common.llm.openai_client import AzureOpenAIClient
from kag.common.vectorize_model.azure_cohere_model import AzureCohereVectorizeModel
from kag.interface import LLMClient
from src.lodestone.application.ingestion.pipeline import IngestionPipeline
from src.lodestone.config.settings import IngestionSettings, get_settings


def _build_embedder(settings: IngestionSettings) -> AzureCohereVectorizeModel:
    """Build the Azure-hosted Cohere embedder (kag pattern, async)."""
    return AzureCohereVectorizeModel(
        endpoint=settings.cohere_endpoint,
        api_key=settings.cohere_api_key.get_secret_value(),
        model=settings.cohere_model or None,
        input_type=settings.cohere_input_type,
    )


def _build_graph_store(settings: IngestionSettings) -> Neo4jClient:
    """Build the Neo4j graph store (the password is a required setting)."""
    return Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password.get_secret_value(),
        database=settings.neo4j_database,
    )


def build_ingestion_pipeline(
    llm: LLMClient,
    embedder,
    schema_path: str,
    graph_store,
    namespace: str = "",
) -> IngestionPipeline:
    """Build a pipeline from explicit collaborators (tests / custom wiring)."""
    return IngestionPipeline(
        llm=llm,
        embedder=embedder,
        schema_path=schema_path,
        graph_store=graph_store,
        namespace=namespace,
    )


@lru_cache(maxsize=1)
def get_ingestion_pipeline() -> IngestionPipeline:
    """Return the cached pipeline singleton, wired from settings."""
    settings: IngestionSettings = get_settings()
    # kag's AzureOpenAIClient is itself an LLMClient, used directly as the pipeline's
    # model seam (no app-side adapter). Config is injected here from settings.
    llm = AzureOpenAIClient(
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        azure_deployment=settings.llm_azure_deployment,
        api_version=settings.llm_api_version,
    )
    return build_ingestion_pipeline(
        llm,
        _build_embedder(settings),
        settings.schema_path,
        graph_store=_build_graph_store(settings),
        namespace=settings.namespace,
    )
