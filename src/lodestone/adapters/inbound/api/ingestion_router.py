"""Inbound HTTP adapter — drives the ingestion use case.

Framework-light: if FastAPI isn't installed this module still imports, so the
demo/core works without web deps. `build_router()` returns a FastAPI router
when available.
"""

from __future__ import annotations

from dataclasses import dataclass

from lodestone.domain.models.document import SourceRef
from lodestone.domain.ports.ingestion import IngestDocumentUseCase


@dataclass
class IngestRequest:
    url: str
    title: str | None = None
    document_id: str | None = None


def to_source(req: IngestRequest) -> SourceRef:
    kwargs: dict = {"url": req.url, "title": req.title}
    if req.document_id:
        kwargs["document_id"] = req.document_id
    return SourceRef(**kwargs)


def build_router(use_case: IngestDocumentUseCase):
    """Construct a FastAPI router bound to the ingestion use case."""
    from fastapi import APIRouter  # local import: optional dependency

    router = APIRouter(prefix="/ingestion", tags=["ingestion"])

    @router.post("/documents")
    async def ingest_document(req: IngestRequest):
        result = await use_case.ingest(to_source(req))
        return {
            "document_id": result.document_id,
            "status": result.status.value,
            "chunks": result.chunk_count,
            "entities": result.entity_count,
            "triples": result.triple_count,
            "error": result.error,
        }

    return router
