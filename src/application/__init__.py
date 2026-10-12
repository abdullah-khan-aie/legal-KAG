"""Application layer: ingestion and query composition over the kag components."""

from .ingestion import IngestionPipeline
from .query import build_query_pipeline

__all__ = ["IngestionPipeline", "build_query_pipeline"]
