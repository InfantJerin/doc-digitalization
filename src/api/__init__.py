"""
API module.

FastAPI application and routes for the Document Digitalization Platform.
"""

from .app import create_app

__all__ = ["create_app"]
