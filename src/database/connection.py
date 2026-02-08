"""Database connection utilities."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from ..core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

try:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import (
        AsyncEngine,
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in environments without sqlalchemy
    AsyncEngine = object  # type: ignore[assignment]
    AsyncSession = object  # type: ignore[assignment]
    async_sessionmaker = object  # type: ignore[assignment]
    create_async_engine = None
    text = None
    SQLALCHEMY_AVAILABLE = False


class DatabaseManager:
    """Owns the async SQLAlchemy engine/session lifecycle."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None

    def initialize(self) -> None:
        """Create engine and session factory when SQLAlchemy is available."""
        if not SQLALCHEMY_AVAILABLE:
            logger.warning("SQLAlchemy not installed; running without persistent DB")
            return

        if self._engine is not None:
            return

        self._engine = create_async_engine(
            self.settings.database_url,
            future=True,
            echo=False,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    @property
    def is_enabled(self) -> bool:
        return SQLALCHEMY_AVAILABLE and self._engine is not None

    @property
    def session_factory(self) -> Optional[async_sessionmaker]:
        return self._session_factory

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[Optional[AsyncSession], None]:
        """Yield an async session when available, else `None`."""
        if self._session_factory is None:
            yield None
            return

        async with self._session_factory() as session:
            yield session

    async def health_check(self) -> bool:
        """Return True if DB ping succeeds or DB is intentionally disabled."""
        if not self.is_enabled:
            return True

        assert self._engine is not None
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True

    async def dispose(self) -> None:
        """Dispose engine resources."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None


_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Return singleton database manager."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.initialize()
    return _db_manager
