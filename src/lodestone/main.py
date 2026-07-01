from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.lodestone.bootstrap import get_ingestion_pipeline, get_query_pipeline
from src.lodestone.config.settings import get_settings
from src.lodestone.observability import configure_logging, get_logger

logger = get_logger(__name__)


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


# Routers are registered here as they are built, e.g.:
#   from src.lodestone.api.routes import ingestion
#   app.include_router(ingestion.router)
