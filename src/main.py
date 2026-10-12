from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import ingestion_router, query_router
from .bootstrap import get_ingestion_pipeline, get_query_pipeline, initialize_graph_schema
from .config import get_settings
from .observability import configure_logging, get_logger

logger = get_logger(__name__)

# Served as static files so the browser calls the query API same-origin and we
# avoid CORS entirely.
_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "Frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run startup and shutdown once per worker process."""
    settings = get_settings()
    configure_logging(settings)
    # Entity linking and query-time vector search need their Neo4j indexes to
    # exist before the first write.
    initialize_graph_schema(settings)
    # Build the cached pipelines now so the first request does not pay for
    # opening Neo4j connections and model clients.
    get_ingestion_pipeline()
    get_query_pipeline()
    logger.info("application startup complete")
    yield
    logger.info("application shutdown")


app = FastAPI(title="legal-KAG", lifespan=lifespan)
app.include_router(query_router)
app.include_router(ingestion_router)

# Mounted after the routers so it can never shadow an API path, and kept
# optional so the API still boots when Frontend/ is missing.
if _FRONTEND_DIR.is_dir():

    @app.get("/", include_in_schema=False)
    async def _root() -> RedirectResponse:
        """Redirect the bare host to the query UI."""
        return RedirectResponse(url="/ui/")

    app.mount("/ui", StaticFiles(directory=_FRONTEND_DIR, html=True), name="ui")
