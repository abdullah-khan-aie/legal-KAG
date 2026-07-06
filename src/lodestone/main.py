from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import ingestion_router, query_router
from .bootstrap import get_ingestion_pipeline, get_query_pipeline
from .config import get_settings
from .observability import configure_logging, get_logger

logger = get_logger(__name__)

# Repository-root Frontend/ dir (this file is src/lodestone/main.py, so the root
# is three parents up). Served as static files so the browser talks to the query
# API same-origin (no CORS).
_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "Frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run startup/shutdown once per worker process."""
    # Startup: configure logging before anything logs or serves a request.
    configure_logging(get_settings())
    # Build the (cached) ingestion and query pipelines once at startup -- this
    # establishes the Neo4j connections, model clients, and registered
    # extractors/retrievers now, rather than on the first request.
    get_ingestion_pipeline()
    get_query_pipeline()
    logger.info("application startup complete")
    yield
    # Shutdown: release resources here as they are added (DB drivers, clients).
    logger.info("application shutdown")


app = FastAPI(title="Lodestone", lifespan=lifespan)
app.include_router(query_router)
app.include_router(ingestion_router)

# Serve the minimal query UI. Mounted after the API routers so it never shadows
# them; the mount is optional so the API still boots if Frontend/ is absent.
if _FRONTEND_DIR.is_dir():

    @app.get("/", include_in_schema=False)
    async def _root() -> RedirectResponse:
        """Redirect the bare host to the query UI."""
        return RedirectResponse(url="/ui/")

    app.mount("/ui", StaticFiles(directory=_FRONTEND_DIR, html=True), name="ui")
