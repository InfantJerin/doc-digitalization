"""Health and readiness routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from ...core.schemas import HealthStatus
from ...database.connection import get_database_manager
from ..dependencies import get_agent_orchestrator

router = APIRouter()


@router.get("", response_model=HealthStatus)
async def health() -> HealthStatus:
    return HealthStatus(
        status="healthy",
        timestamp=datetime.utcnow(),
        checks={
            "api": "ok",
        },
    )


@router.get("/readiness", response_model=HealthStatus)
async def readiness() -> HealthStatus:
    db_ok = await get_database_manager().health_check()
    orchestrator = get_agent_orchestrator()
    return HealthStatus(
        status="ready" if db_ok else "degraded",
        timestamp=datetime.utcnow(),
        checks={
            "database": "ok" if db_ok else "unavailable",
            "agent_runtime": "sdk" if orchestrator is not None else "unavailable",
        },
    )
