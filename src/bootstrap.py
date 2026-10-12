from __future__ import annotations

from functools import lru_cache

from kag.common.conf import KAG_CONFIG, KAG_PROJECT_CONF
from kag.common.graphstore.neo4j_graph_store import Neo4jClient
from kag.common.llm.anthropic_client import AnthropicLLMClient
from kag.common.vectorize_model.cohere_model import CohereVectorizeModel
from kag.interface import LLMClient
from kag.schema.client import SchemaClient
from src.application.ingestion.pipeline import IngestionPipeline
from src.application.query.builder import (
    _anthropic_credentials,
    _cohere_credentials,
    build_query_pipeline,
    chat_llm_config,
)
from src.config import Settings, get_settings


def _build_embedder(settings: Settings) -> CohereVectorizeModel:
    """Build the Cohere embedder."""
    return CohereVectorizeModel(
        model=settings.embed_model,
        input_type=settings.embed_input_type,
        output_dimension=settings.embed_dimension,
        **_cohere_credentials(settings),
    )


def initialize_graph_schema(settings: Settings) -> None:
    """Create the schema's Neo4j indexes up front. Idempotent, so re-running is a no-op.

    Also the composition root that seeds the vendored kag runtime from Settings,
    which must happen before any pipeline is built.
    """
    KAG_PROJECT_CONF.namespace = settings.namespace
    # Without schema_path the label map loads empty and every label resolves
    # bare, so the writer, indexes and retriever quietly stop agreeing.
    KAG_PROJECT_CONF.schema_path = settings.schema_path
    # Executors that are not given an llm in the pipeline yaml fall back to this
    # default. Without it they get a base LLMClient whose sync call raises.
    KAG_CONFIG.all_config["chat_llm"] = chat_llm_config(settings)
    schema = SchemaClient(schema_path=settings.schema_path).load()
    # Sized to embed_dimension so the indexes match the vectors Cohere returns.
    _build_graph_store(settings).initialize_schema(
        schema, vector_dimensions=settings.embed_dimension, namespace=settings.namespace
    )


def _build_graph_store(settings: Settings) -> Neo4jClient:
    """Build the Neo4j graph store."""
    return Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password.get_secret_value(),
        database=settings.neo4j_database,
    )


def _build_extractors(settings: Settings) -> list:
    """Assemble ingestion extractors from the active index_list.

    Mirrors the query-side retriever assembly, so enabling an index wires both
    its ingest extractor and its query retriever at once.
    """
    from kag.common.registry import import_modules_from_path
    from kag.indexer import KAGIndexManager
    from kag.interface import ExtractorABC
    from src.application.query.builder import (
        chat_llm_config,
        vectorize_model_config,
    )

    # from_config can only resolve types that have been imported already.
    for path in ("kag/indexer", "kag/builder"):
        import_modules_from_path(path)

    llm_config = chat_llm_config(settings)
    vectorize_config = vectorize_model_config(settings, input_type="document")

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
    model_execute_num: int = 1,
) -> IngestionPipeline:
    """Build a pipeline from explicit collaborators, for tests or custom wiring."""
    return IngestionPipeline(
        llm=llm,
        embedder=embedder,
        schema_path=schema_path,
        graph_store=graph_store,
        extractors=extractors,
        namespace=namespace,
        model_execute_num=model_execute_num,
    )


@lru_cache(maxsize=1)
def get_ingestion_pipeline() -> IngestionPipeline:
    """Return the cached pipeline singleton, wired from settings."""
    settings: Settings = get_settings()
    # Throughput is bounded by the extraction worker pool, not by any
    # client-side rate limiter.
    llm = AnthropicLLMClient(
        model=settings.llm_model,
        **_anthropic_credentials(settings),
    )
    return build_ingestion_pipeline(
        llm,
        _build_embedder(settings),
        settings.schema_path,
        graph_store=_build_graph_store(settings),
        extractors=_build_extractors(settings),
        namespace=settings.namespace,
        model_execute_num=settings.model_execute_num,
    )


@lru_cache
def get_query_pipeline(pipeline_name: str = "retriever"):
    """Return the cached query pipeline for pipeline_name, wired from settings.

    The graph store is injected into the config-driven retrievers, avoiding global state.
    """
    settings = get_settings()
    return build_query_pipeline(pipeline_name, settings, graph_store=_build_graph_store(settings))
