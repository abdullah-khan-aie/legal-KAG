from __future__ import annotations

from fastapi import APIRouter

from src.lodestone.api.schemas import IngestFileResult, IngestResponse
from src.lodestone.application.ingestion.runner import ingest_directory
from src.lodestone.config.settings import get_settings

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("", response_model=IngestResponse)
async def ingest() -> IngestResponse:
    """Ingest every document in the configured scan folder.

    No request body: the directory scanner reads ``INGEST_SCAN_DIR`` and the
    documents are ingested concurrently (bounded by ``INGEST_MAX_CONCURRENCY``).
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
