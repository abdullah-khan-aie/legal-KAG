from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from kag.solver.reporter.queue_reporter import DONE, QueueReporter
from src.lodestone.bootstrap import get_query_pipeline


async def stream_query_events(
    query: str, pipeline_name: str = "retriever"
) -> AsyncIterator[dict[str, Any]]:
    """Run the query pipeline and yield its report events as they occur.

    Drives ``pipeline.ainvoke`` as a background task with a ``QueueReporter``,
    yielding each event (step progress, answer-token deltas) as it arrives, then
    a terminal ``done`` event carrying the full answer (or an ``error`` event).
    """
    reporter = QueueReporter()
    pipeline = get_query_pipeline(pipeline_name)
    result: dict[str, Any] = {}

    async def _run() -> None:
        try:
            result["answer"] = await pipeline.ainvoke(query, reporter=reporter)
        finally:
            reporter.signal_done()

    task = asyncio.create_task(_run())
    while True:
        event = await reporter.queue.get()
        if event is DONE:
            break
        yield event

    try:
        await task
    except Exception as err:  # surface pipeline failure as a stream event
        yield {"segment": "error", "tag": None, "content": str(err), "status": "ERROR"}
        return
    yield {"segment": "done", "tag": None, "content": result.get("answer", ""), "status": "FINISH"}
