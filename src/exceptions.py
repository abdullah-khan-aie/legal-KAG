from __future__ import annotations

from typing import Any


class Error(Exception):
    """Base class for every application error.

    Args:
        message: Human-readable description of what went wrong.
        code: Stable, machine-readable error code. Defaults to the class name.
        details: Structured context (ids, paths, counts) for logs and responses.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} ({self.details})"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Serialize for a boundary response payload."""
        return {"error": self.code, "message": self.message, "details": self.details}


class ConfigurationError(Error):
    """Invalid or missing configuration (settings, credentials, schema path)."""


class DocumentReadError(Error):
    """A source document could not be read or parsed."""


class ChunkingError(Error):
    """Splitting a document into chunks failed."""


class ExtractionError(Error):
    """Entity, relation, or summary extraction failed."""


class EmbeddingError(Error):
    """Vectorization / embedding generation failed."""


class GraphStoreError(Error):
    """A graph-store (Neo4j) operation failed."""


class IngestionError(Error):
    """A document failed to complete the ingestion pipeline."""
