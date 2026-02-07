"""
FastAPI Application.

Main entry point for the API server.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import extraction, generation, review, documents

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Document Digitalization API")
    yield
    # Shutdown
    logger.info("Shutting down Document Digitalization API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="Document Digitalization Platform",
        description="API for document extraction and generation pipelines",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(
        extraction.router,
        prefix="/api/v1/extractions",
        tags=["Extraction"]
    )
    app.include_router(
        generation.router,
        prefix="/api/v1/generations",
        tags=["Generation"]
    )
    app.include_router(
        review.router,
        prefix="/api/v1/reviews",
        tags=["Review"]
    )
    app.include_router(
        documents.router,
        prefix="/api/v1/documents",
        tags=["Documents"]
    )

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": "Document Digitalization Platform",
            "version": "1.0.0",
            "docs": "/docs"
        }

    return app


# Create app instance
app = create_app()
