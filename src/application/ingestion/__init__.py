"""Ingestion: read/split/extract/write documents into the knowledge graph.

Only IngestionPipeline is re-exported. Importing runner here would create a
circular import, because runner imports bootstrap, which imports this
subpackage's pipeline module. Import it directly instead:
``from src.application.ingestion.runner import ingest_directory``.
"""

from .pipeline import IngestionPipeline

__all__ = ["IngestionPipeline"]
