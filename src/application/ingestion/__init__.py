"""Ingestion: read/split/extract/write documents into the knowledge graph.

Only ``IngestionPipeline`` is re-exported. ``runner`` (ingest_directory, etc.)
is deliberately NOT imported here because it imports ``bootstrap``, which in
turn imports this subpackage's ``pipeline`` module -- re-exporting it would
create a circular import at package-init time. Import it directly instead:
``from src.lodestone.application.ingestion.runner import ingest_directory``.
"""

from .pipeline import IngestionPipeline

__all__ = ["IngestionPipeline"]
