"""App: server-free RAG / knowledge-graph ingestion and query.

Only the lightweight configuration accessor is re-exported at the top level.
The FastAPI ``app`` and the ingestion/query pipelines are intentionally NOT
imported here: doing so would pull the full Bedrock/Neo4j/kag dependency graph
(and risk a circular import via ``bootstrap``) on every ``import src``.
"""

from .config import get_settings

__all__ = ["get_settings"]
