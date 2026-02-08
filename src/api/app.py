"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core.settings import get_settings
from .dependencies import get_db_manager
from .routes import documents, extraction, generation, health, review

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    db_manager = get_db_manager()

    logger.info("Starting %s (%s)", settings.app_name, settings.environment)
    try:
        yield
    finally:
        await db_manager.dispose()
        logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="API for document extraction and generation pipelines",
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(extraction.router, prefix="/api/v1/extractions", tags=["Extraction"])
    app.include_router(generation.router, prefix="/api/v1/generations", tags=["Generation"])
    app.include_router(review.router, prefix="/api/v1/reviews", tags=["Review"])
    app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
    app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])

    # Backwards-compatible health endpoint.
    @app.get("/health")
    async def health_check() -> dict:
        return {"status": "healthy"}

    @app.get("/")
    async def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        }

    return app


app = create_app()
