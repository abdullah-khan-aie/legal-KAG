"""Ingestion orchestration — the application core.

Wires the outbound ports into the canonical graph-RAG ingestion pipeline:

    fetch -> chunk -> extract (entities/triples) -> embed -> write

It depends ONLY on port Protocols, so the same logic runs against KAG,
LangChain+Neo4j, or test doubles.
"""

from __future__ import annotations

import logging
from datetime import UTC

from lodestone.domain.models.document import (
    Entity,
    IngestionResult,
    IngestionStatus,
    SourceRef,
    Triple,
)
from lodestone.domain.ports.ingestion import (
    ChunkerPort,
    DocumentSourcePort,
    EmbedderPort,
    EntityExtractorPort,
    KnowledgeGraphPort,
)

logger = logging.getLogger(__name__)


class IngestionService:
    """Implements the IngestDocumentUseCase inbound port."""

    def __init__(
        self,
        source: DocumentSourcePort,
        chunker: ChunkerPort,
        extractor: EntityExtractorPort,
        embedder: EmbedderPort,
        graph: KnowledgeGraphPort,
    ) -> None:
        self._source = source
        self._chunker = chunker
        self._extractor = extractor
        self._embedder = embedder
        self._graph = graph

    async def ingest(self, source: SourceRef) -> IngestionResult:
        result = IngestionResult(document_id=source.document_id, status=IngestionStatus.PENDING)
        try:
            logger.info("Fetching %s", source.url)
            result.status = IngestionStatus.FETCHING
            document = await self._source.fetch(source)

            result.status = IngestionStatus.CHUNKING
            chunks = self._chunker.split(document)
            result.chunk_count = len(chunks)

            result.status = IngestionStatus.EXTRACTING
            entities: list[Entity] = []
            triples: list[Triple] = []
            for chunk in chunks:
                ents, trips = await self._extractor.extract(chunk)
                entities.extend(ents)
                triples.extend(trips)
            result.entity_count = len(entities)
            result.triple_count = len(triples)

            result.status = IngestionStatus.EMBEDDING
            chunks = await self._embedder.embed(chunks)

            result.status = IngestionStatus.WRITING
            await self._graph.write_chunks(chunks)
            await self._graph.write_graph(entities, triples)

            result.status = IngestionStatus.COMPLETED
            logger.info(
                "Ingested %s: %d chunks, %d entities, %d triples",
                source.url,
                result.chunk_count,
                result.entity_count,
                result.triple_count,
            )
        except Exception as exc:  # noqa: BLE001 - boundary: record & surface
            logger.exception("Ingestion failed for %s", source.url)
            result.status = IngestionStatus.FAILED
            result.error = str(exc)

        from datetime import datetime

        result.finished_at = datetime.now(UTC)
        return result
