"""Dependency injection providers for API routes."""

from __future__ import annotations

from functools import lru_cache

from ..agent.orchestrator import AgentOrchestrator
from ..core.config_loader import ConfigLoader
from ..core.settings import Settings, get_settings
from ..database.connection import DatabaseManager, get_database_manager
from ..database.repositories.extraction_repo import ExtractionRepository
from ..database.repositories.review_repo import ReviewRepository
from ..extraction.service import ExtractionService
from ..extraction.workspace import ExtractionWorkspaceManager
from ..integrations.dms_client import DMSClient
from ..workflow.review_handler import ReviewHandler
from ..workflow.service import WorkflowService


@lru_cache(maxsize=1)
def get_config_loader() -> ConfigLoader:
    settings = get_settings()
    return ConfigLoader(str(settings.config_dir))


@lru_cache(maxsize=1)
def get_db_manager() -> DatabaseManager:
    return get_database_manager()


@lru_cache(maxsize=1)
def get_dms_client() -> DMSClient:
    settings = get_settings()
    return DMSClient(base_url=settings.dms_base_url, api_key=settings.dms_api_key)


@lru_cache(maxsize=1)
def get_extraction_repository() -> ExtractionRepository:
    manager = get_db_manager()
    return ExtractionRepository(session_factory=manager.session_factory)


@lru_cache(maxsize=1)
def get_review_repository() -> ReviewRepository:
    manager = get_db_manager()
    return ReviewRepository(session_factory=manager.session_factory)


@lru_cache(maxsize=1)
def get_agent_orchestrator() -> AgentOrchestrator:
    settings = get_settings()
    return AgentOrchestrator(
        settings=settings,
        config_loader=get_config_loader(),
    )


@lru_cache(maxsize=1)
def get_workspace_manager() -> ExtractionWorkspaceManager:
    return ExtractionWorkspaceManager(get_settings())


@lru_cache(maxsize=1)
def get_extraction_service() -> ExtractionService:
    return ExtractionService(
        dms_client=get_dms_client(),
        config_loader=get_config_loader(),
        extraction_repo=get_extraction_repository(),
        review_repo=get_review_repository(),
        orchestrator=get_agent_orchestrator(),
        workspace_manager=get_workspace_manager(),
    )


@lru_cache(maxsize=1)
def get_workflow_service() -> WorkflowService:
    return WorkflowService(
        review_repo=get_review_repository(),
        extraction_repo=get_extraction_repository(),
    )


@lru_cache(maxsize=1)
def get_review_handler() -> ReviewHandler:
    return ReviewHandler(
        review_repo=get_review_repository(),
        extraction_repo=get_extraction_repository(),
    )
