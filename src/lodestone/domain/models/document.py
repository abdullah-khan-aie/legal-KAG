"""Core domain models for the ingestion pipeline.

These are deliberately storage-agnostic: nothing here knows about Neo4j,
the graph engine, or any vendor. They describe *what* flows through the
pipeline, not *how* it is persisted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


def _new_id() -> str:
    return uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class IngestionStatus(StrEnum):
    PENDING = "pending"
    FETCHING = "fetching"
    CHUNKING = "chunking"
    EXTRACTING = "extracting"
    EMBEDDING = "embedding"
    WRITING = "writing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class SourceRef:
    """Pointer back to the original document.

    For the legal use case we keep ONLY this reference (e.g. an S3 / signed
    URL), never the original binary. Every chunk carries it so an answer can
    be traced to its source without us storing the file.
    """

    url: str
    document_id: str = field(default_factory=_new_id)
    title: str | None = None
    content_type: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RawDocument:
    """A document fetched transiently for processing. Held in memory only."""

    source: SourceRef
    text: str


@dataclass(frozen=True)
class Chunk:
    """A semantically coherent unit of text plus its provenance."""

    text: str
    source: SourceRef
    ordinal: int
    chunk_id: str = field(default_factory=_new_id)
    embedding: list[float] | None = None


@dataclass(frozen=True)
class Entity:
    name: str
    type: str
    chunk_id: str


@dataclass(frozen=True)
class Triple:
    """Subject - predicate - object fact extracted from a chunk."""

    subject: str
    predicate: str
    object: str
    chunk_id: str


@dataclass
class IngestionResult:
    document_id: str
    status: IngestionStatus
    chunk_count: int = 0
    entity_count: int = 0
    triple_count: int = 0
    error: str | None = None
    started_at: datetime = field(default_factory=_now)
    finished_at: datetime | None = None
