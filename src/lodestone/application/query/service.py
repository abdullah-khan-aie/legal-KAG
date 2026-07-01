from __future__ import annotations

from src.lodestone.bootstrap import get_query_pipeline


async def run_query(query: str, pipeline_name: str = "retriever") -> str:
    """Answer a query with the configured solver pipeline.

    The query-side use case (server-free equivalent of kag's ``do_qa_pipeline``):
    fetch the cached pipeline for ``pipeline_name`` and run it. The pipeline is
    stateless between calls -- each ``ainvoke`` builds its own ``Context`` -- so
    reusing the cached instance across requests is safe.

    Args:
        query: The natural-language question to answer.
        pipeline_name: Which solver pipeline to use ("retriever", "deep_thought",
            "kag_thinker", or "naive_rag").

    Returns:
        The generated answer (``"UNKNOWN"`` if the pipeline could not produce one).
    """
    pipeline = get_query_pipeline(pipeline_name)
    return await pipeline.ainvoke(query)
