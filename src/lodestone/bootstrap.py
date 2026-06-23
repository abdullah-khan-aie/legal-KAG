"""Composition root: bind adapters to ports and build the ingestion pipeline.

``get_ingestion_pipeline()`` returns an lru-cached singleton — it reads settings,
constructs the model adapters, binds them to the ports, and builds the pipeline
once (the schema and prompt templates are loaded here), then reuses it for every
document. ``build_ingestion_pipeline()`` is the explicit constructor for tests or
custom wiring.
"""

from __future__ import annotations

from functools import lru_cache

from src.lodestone.adapters.outbound.model_adapters import (
    OpenAICompatibleEmbeddingModel,
    OpenAICompatibleLanguageModel,
)
from src.lodestone.application.ingestion.pipeline import IngestionPipeline
from src.lodestone.config.settings import IngestionSettings, get_settings
from src.lodestone.domain.ports.ingestion import EmbeddingModelPort, LanguageModelPort


def build_ingestion_pipeline(
    llm: LanguageModelPort,
    embedder: EmbeddingModelPort,
    schema_path: str,
) -> IngestionPipeline:
    """Build a pipeline from explicit collaborators (tests / custom wiring)."""
    return IngestionPipeline(llm=llm, embedder=embedder, schema_path=schema_path)


@lru_cache(maxsize=1)
def get_ingestion_pipeline() -> IngestionPipeline:
    """Return the cached pipeline singleton, wired from settings."""
    settings: IngestionSettings = get_settings()
    llm = OpenAICompatibleLanguageModel(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
    )
    embedder = OpenAICompatibleEmbeddingModel(
        base_url=settings.embed_base_url,
        api_key=settings.embed_api_key.get_secret_value(),
        model=settings.embed_model,
    )
    return build_ingestion_pipeline(llm, embedder, settings.schema_path)
