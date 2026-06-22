"""Composition root — wires ports to adapters in one place.

Swap a stub for a real adapter here (and nowhere else) to go from demo to
production: e.g. InMemoryKnowledgeGraph -> Neo4jKnowledgeGraph.
"""

from __future__ import annotations

from lodestone.adapters.outbound.stub_adapters import (
    FakeEmbedder,
    HttpDocumentSource,
    InMemoryKnowledgeGraph,
    RegexEntityExtractor,
    SlidingWindowChunker,
)
from lodestone.application.ingestion.service import IngestionService


def build_ingestion_service() -> IngestionService:
    return IngestionService(
        source=HttpDocumentSource(),
        chunker=SlidingWindowChunker(),
        extractor=RegexEntityExtractor(),
        embedder=FakeEmbedder(),
        graph=InMemoryKnowledgeGraph(),
    )


if __name__ == "__main__":
    import asyncio
    import logging

    from lodestone.domain.models.document import SourceRef

    logging.basicConfig(level=logging.INFO)

    async def _demo() -> None:
        service = build_ingestion_service()
        result = await service.ingest(
            SourceRef(
                url="https://example-bucket.s3/contract-001.pdf",
                title="Contract 001",
            )
        )
        print(result)

    asyncio.run(_demo())
