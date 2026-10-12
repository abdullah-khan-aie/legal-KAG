from __future__ import annotations

from fastapi import APIRouter

from src.api.schemas import IngestFileResult, IngestResponse
from src.application.ingestion.runner import ingest_directory
from src.config import get_settings

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("", response_model=IngestResponse)
async def ingest() -> IngestResponse:
    """Ingest every document in the configured scan folder.

    No request body: the directory scanner reads ``SCAN_DIR`` and the
    documents are ingested concurrently (bounded by ``MAX_CONCURRENCY``).
    """
    settings = get_settings()
    summary = await ingest_directory(settings.scan_dir, settings.max_concurrency)
    return IngestResponse(
        total=summary.total,
        ingested=summary.ingested,
        skipped=summary.skipped,
        failed=summary.failed,
        files=[IngestFileResult(**vars(f)) for f in summary.files],
    )
