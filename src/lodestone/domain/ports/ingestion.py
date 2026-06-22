"""Inbound & outbound ports for the ingestion pipeline (hexagonal core).

Ports are Protocols: the application depends on these abstractions, and the
adapters/ layer provides concrete implementations (HTTP fetcher, LLM
extractor, Neo4j writer, ...). This is what lets us swap KAG/OpenSPG for a
plain LangChain + Neo4j stack without touching application logic.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from lodestone.domain.models.document import (
    Chunk,
    Entity,
    IngestionResult,
    RawDocument,
    SourceRef,
    Triple,
)

# --------------------------------------------------------------------------- #
# Inbound port — what the outside world (API, queue worker) calls.
# --------------------------------------------------------------------------- #


@runtime_checkable
class IngestDocumentUseCase(Protocol):
    """Driving port: ingest a single document identified by a source URL."""

    async def ingest(self, source: SourceRef) -> IngestionResult: ...


# --------------------------------------------------------------------------- #
# Outbound ports — what the pipeline needs from the outside.
# --------------------------------------------------------------------------- #


@runtime_checkable
class DocumentSourcePort(Protocol):
    """Fetches the document content from its URL. Transient: no persistence."""

    async def fetch(self, source: SourceRef) -> RawDocument: ...


@runtime_checkable
class ChunkerPort(Protocol):
    """Splits a document into retrieval-sized, provenance-tagged chunks."""

    def split(self, document: RawDocument) -> list[Chunk]: ...


@runtime_checkable
class EmbedderPort(Protocol):
    """Generates vector embeddings for chunks (batch)."""

    async def embed(self, chunks: list[Chunk]) -> list[Chunk]: ...


@runtime_checkable
class EntityExtractorPort(Protocol):
    """LLM-driven extraction of entities and SPO triples from a chunk."""

    async def extract(self, chunk: Chunk) -> tuple[list[Entity], list[Triple]]: ...


@runtime_checkable
class KnowledgeGraphPort(Protocol):
    """Writes chunks (text + vector) and graph (entities/triples) to storage.

    The single sink that hides Neo4j / OpenSPG / KAG behind one interface.
    """

    async def write_chunks(self, chunks: list[Chunk]) -> None: ...

    async def write_graph(self, entities: list[Entity], triples: list[Triple]) -> None: ...
