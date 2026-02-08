"""Workspace management for extraction runs."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..core.settings import Settings, get_settings


@dataclass(slots=True)
class ExtractionWorkspace:
    run_id: str
    root: Path
    documents_dir: Path
    artifacts_dir: Path


class ExtractionWorkspaceManager:
    """Creates and manages per-run working directories."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def create(self, run_id: str) -> ExtractionWorkspace:
        root = self.settings.extractions_root / run_id
        documents_dir = root / "documents"
        artifacts_dir = root / "artifacts"
        documents_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        return ExtractionWorkspace(
            run_id=run_id,
            root=root,
            documents_dir=documents_dir,
            artifacts_dir=artifacts_dir,
        )

    def cleanup(self, workspace: ExtractionWorkspace) -> None:
        if workspace.root.exists():
            shutil.rmtree(workspace.root, ignore_errors=True)
