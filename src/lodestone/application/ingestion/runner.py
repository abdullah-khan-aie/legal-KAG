from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field

from kag.builder.component.scanner.directory_scanner import DirectoryScanner
from src.lodestone.bootstrap import get_ingestion_pipeline

logger = logging.getLogger(__name__)


@dataclass
class FileResult:
    """Per-document ingestion outcome."""

    path: str
    status: str  # "ingested" | "skipped" | "failed"
    nodes: int = 0
    edges: int = 0
    error: str | None = None


@dataclass
class IngestSummary:
    """Aggregate outcome of a directory ingestion run."""

    total: int = 0
    ingested: int = 0
    skipped: int = 0
    failed: int = 0
    files: list[FileResult] = field(default_factory=list)


def _file_hash(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def ingest_directory(directory: str, max_concurrency: int = 4) -> IngestSummary:
    """Scan a directory and ingest its documents with bounded concurrency.

    Mirrors kag's ``BuilderChainRunner.ainvoke``: a producer puts file paths on
    a bounded ``asyncio.Queue`` and ``max_concurrency`` consumers pull and run
    each through the ingestion pipeline. The queue's ``maxsize`` is backpressure
    -- so we keep only N documents in flight and never overwhelm the LLM's rate
    limits. Documents are de-duplicated by content hash within the run (the
    "seen?" gate); cross-run/durable dedup arrives with the persistent job store.
    """
    scanner = DirectoryScanner()
    pipeline = get_ingestion_pipeline()
    summary = IngestSummary()
    seen: set[str] = set()
    lock = asyncio.Lock()
    queue: asyncio.Queue = asyncio.Queue(maxsize=max_concurrency * 10)

    async def process(path: str) -> FileResult:
        try:
            digest = await asyncio.to_thread(_file_hash, path)
            async with lock:
                if digest in seen:
                    return FileResult(path=path, status="skipped")
                seen.add(digest)
            subgraph = await pipeline.ingest(path)
            nodes = len(getattr(subgraph, "nodes", []) or [])
            edges = len(getattr(subgraph, "edges", []) or [])
            return FileResult(path=path, status="ingested", nodes=nodes, edges=edges)
        except Exception as err:  # one bad document must not stop the batch
            logger.exception("ingestion failed for %s", path)
            return FileResult(path=path, status="failed", error=str(err))

    async def producer() -> None:
        for path in scanner.generate(directory):
            await queue.put(path)
        for _ in range(max_concurrency):
            await queue.put(None)  # one sentinel per consumer

    async def consumer() -> None:
        while True:
            path = await queue.get()
            if path is None:
                queue.task_done()
                break
            result = await process(path)
            async with lock:
                summary.total += 1
                summary.files.append(result)
                summary.ingested += result.status == "ingested"
                summary.skipped += result.status == "skipped"
                summary.failed += result.status == "failed"
            queue.task_done()

    producer_task = asyncio.create_task(producer())
    consumers = [asyncio.create_task(consumer()) for _ in range(max_concurrency)]
    await producer_task
    await queue.join()
    await asyncio.gather(*consumers)
    return summary
