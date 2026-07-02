from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PipelineName(str, Enum):  # noqa: UP042  (str, Enum is FastAPI's documented idiom)
    """Query pipelines the frontend can select.

    ``retriever`` is the simple retrieval pipeline (default); ``deep_thought``
    and ``kag_thinker`` are the reasoning toggles. Validated at the request
    boundary, so an unknown value is rejected before reaching the engine.
    """

    retriever = "retriever"
    deep_thought = "deep_thought"
    kag_thinker = "kag_thinker"


class QueryRequest(BaseModel):
    """Request body for the streaming query endpoint."""

    query: str = Field(min_length=1, description="The user's natural-language question.")
    pipeline: PipelineName = Field(
        default=PipelineName.retriever,
        description="Which query pipeline to run (retrieval by default).",
    )


class IngestFileResult(BaseModel):
    """Per-document outcome of an ingestion run."""

    path: str
    status: str  # "ingested" | "skipped" | "failed"
    nodes: int = 0
    edges: int = 0
    error: str | None = None


class IngestResponse(BaseModel):
    """Summary returned by the directory-ingestion endpoint."""

    total: int
    ingested: int
    skipped: int
    failed: int
    files: list[IngestFileResult]
