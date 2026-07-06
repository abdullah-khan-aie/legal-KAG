from __future__ import annotations

from functools import lru_cache

from kag.common.graphstore.neo4j_graph_store import Neo4jClient
from kag.common.llm.bedrock_claude_client import BedrockClaudeClient
from kag.common.vectorize_model.bedrock_cohere_model import BedrockCohereVectorizeModel
from kag.interface import LLMClient
from src.lodestone.application.ingestion.pipeline import IngestionPipeline
from src.lodestone.application.query.builder import build_query_pipeline
from src.lodestone.config.settings import Settings, get_settings


def _build_embedder(settings: Settings) -> BedrockCohereVectorizeModel:
    """Build the Bedrock-hosted Cohere embedder (kag pattern, sync + to_thread)."""
    return BedrockCohereVectorizeModel(
        region=settings.embed_region,
        model=settings.embed_model,
        input_type=settings.embed_input_type,
    )


def _build_graph_store(settings: Settings) -> Neo4jClient:
    """Build the Neo4j graph store (the password is a required setting)."""
    return Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password.get_secret_value(),
        database=settings.neo4j_database,
    )


def _build_extractors(settings: Settings) -> list:
    """Assemble ingestion extractors from the active ``index_list``.

    The ingestion half of the extractor/retriever symmetry: for each active
    index, its ``KAGIndexManager`` contributes the extractor(s) that build that
    index (``build_extractor_config`` -> ``ExtractorABC.from_config``). This
    mirrors ``main_solver``'s query-side retriever assembly, so enabling an
    index wires both its ingest extractor and its query retriever at once.
    """
    from kag.common.registry import import_modules_from_path
    from kag.indexer import KAGIndexManager
    from kag.interface import ExtractorABC
    from src.lodestone.application.query.builder import (
        _chat_llm_config,
        _vectorize_model_config,
    )

    # Register index managers, builder extractors and their prompts so
    # ``from_config`` can resolve every type referenced by the index_list.
    for path in ("kag/indexer", "kag/builder"):
        import_modules_from_path(path)

    llm_config = _chat_llm_config(settings)
    vectorize_config = _vectorize_model_config(settings, input_type="document")

    extractors: list = []
    for index_name in settings.index_list:
        manager = KAGIndexManager.from_config(
            {
                "type": index_name,
                "llm_config": llm_config,
                "vectorize_model_config": vectorize_config,
            }
        )
        for cfg in manager.build_extractor_config(
            llm_config, vectorize_config, schema_path=settings.schema_path
        ):
            extractors.append(ExtractorABC.from_config(cfg))
    return extractors


def build_ingestion_pipeline(
    llm: LLMClient,
    embedder,
    schema_path: str,
    graph_store,
    extractors: list | None = None,
    namespace: str = "",
) -> IngestionPipeline:
    """Build a pipeline from explicit collaborators (tests / custom wiring)."""
    return IngestionPipeline(
        llm=llm,
        embedder=embedder,
        schema_path=schema_path,
        graph_store=graph_store,
        extractors=extractors,
        namespace=namespace,
    )


@lru_cache(maxsize=1)
def get_ingestion_pipeline() -> IngestionPipeline:
    """Return the cached pipeline singleton, wired from settings."""
    settings: Settings = get_settings()
    # kag's BedrockClaudeClient is itself an LLMClient, used directly as the pipeline's
    # model seam (no app-side adapter). Config is injected here from settings.
    llm = BedrockClaudeClient(
        region=settings.bedrock_region,
        model=settings.llm_model,
    )
    return build_ingestion_pipeline(
        llm,
        _build_embedder(settings),
        settings.schema_path,
        graph_store=_build_graph_store(settings),
        extractors=_build_extractors(settings),
        namespace=settings.namespace,
    )


@lru_cache
def get_query_pipeline(pipeline_name: str = "retriever"):
    """Return the cached query (solver) pipeline for ``pipeline_name``, wired from settings.

    Builds the Neo4j graph store and injects it into the config-driven
    ``neo4j_search_api`` / ``neo4j_graph_api`` retrievers (no global state).
    """
    settings = get_settings()
    return build_query_pipeline(
        pipeline_name, settings, graph_store=_build_graph_store(settings)
    )
