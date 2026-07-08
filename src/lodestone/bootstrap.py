from __future__ import annotations

from functools import lru_cache

from kag.common.conf import KAG_CONFIG, KAG_PROJECT_CONF
from kag.common.graphstore.neo4j_graph_store import Neo4jClient
from kag.common.llm.bedrock_claude_client import BedrockClaudeClient
from kag.common.vectorize_model.cohere_model import CohereVectorizeModel
from kag.interface import LLMClient
from kag.schema.client import SchemaClient
from src.lodestone.application.ingestion.pipeline import IngestionPipeline
from src.lodestone.application.query.builder import (
    _bedrock_credentials,
    _cohere_credentials,
    build_query_pipeline,
    chat_llm_config,
)
from src.lodestone.config.settings import Settings, get_settings


def _build_embedder(settings: Settings) -> CohereVectorizeModel:
    """Build the direct Cohere embedder (Cohere API, not Bedrock)."""
    return CohereVectorizeModel(
        model=settings.embed_model,
        input_type=settings.embed_input_type,
        output_dimension=settings.embed_dimension,
        **_cohere_credentials(settings),
    )


def initialize_graph_schema(settings: Settings) -> None:
    """Create the Neo4j vector/text indexes for the schema up front (idempotent).

    This mirrors the OpenSPG server's schema-registration step
    (Neo4jSyncer.syncSchema -> Neo4jGraph.initializeSchema(spgTypes, dimensions)),
    which the server runs on schema commit -- not on document writes. With a
    static local schema, startup IS the registration moment, and the underlying
    CREATE VECTOR INDEX ... IF NOT EXISTS makes re-running a no-op. Indexes are
    sized to embed_dimension so they match the vectors Cohere produces.

    This is also the composition root that seeds the vendored kag runtime config
    from Settings. Settings stays the single source of truth; the kag
    retriever/schema code reads ``KAG_PROJECT_CONF`` for BOTH the namespace and the
    schema path (``LocalSchemaLoader.load`` needs the latter to build its label
    map -- without it the schema map is empty and every label resolves bare). We
    seed both here, before the pipelines are built, so the writer, indexes, and
    retriever all agree on ``<namespace>.<Type>`` labels instead of drifting apart.

    We also seed the default chat-LLM config into ``KAG_CONFIG.all_config`` so the
    upstream fallback in ``get_default_chat_llm_config`` resolves to the real
    Bedrock client. Some executors (e.g. ``KAGHybridRetrievalExecutor``'s summary
    and context-select LLMs when ``enable_summary`` is on) aren't wired an llm in
    the pipeline yaml and rely on this default; without the seed they'd fall back
    to a bare base ``LLMClient`` whose sync call raises ``NotImplementedError``.
    """
    KAG_PROJECT_CONF.namespace = settings.namespace
    KAG_PROJECT_CONF.schema_path = settings.schema_path
    KAG_CONFIG.all_config["chat_llm"] = chat_llm_config(settings)
    schema = SchemaClient(schema_path=settings.schema_path).load()
    _build_graph_store(settings).initialize_schema(
        schema, vector_dimensions=settings.embed_dimension, namespace=settings.namespace
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
    index (``build_extractor_config`` -> ``ExtractorABC.from_config``). It is the
    mirror of the query-side retriever assembly, so enabling an index wires both
    its ingest extractor and its query retriever at once.
    """
    from kag.common.registry import import_modules_from_path
    from kag.indexer import KAGIndexManager
    from kag.interface import ExtractorABC
    from src.lodestone.application.query.builder import (
        chat_llm_config,
        vectorize_model_config,
    )

    # Register index managers, builder extractors and their prompts so
    # ``from_config`` can resolve every type referenced by the index_list.
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
    """Build a pipeline from explicit collaborators (tests / custom wiring)."""
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
    # BedrockClaudeClient is the pipeline's LLM client. Extraction throughput is
    # bounded by the worker pool (model_execute_num), not a client-side rate limiter.
    llm = BedrockClaudeClient(
        region=settings.bedrock_region,
        model=settings.llm_model,
        **_bedrock_credentials(settings),
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
    """Return the cached query (solver) pipeline for ``pipeline_name``, wired from settings.

    Builds the Neo4j graph store and injects it into the config-driven
    ``neo4j_search_api`` / ``neo4j_graph_api`` retrievers (no global state).
    """
    settings = get_settings()
    return build_query_pipeline(pipeline_name, settings, graph_store=_build_graph_store(settings))
