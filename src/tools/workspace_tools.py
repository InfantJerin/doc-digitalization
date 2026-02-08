"""Workspace file tools for agent runs."""

from __future__ import annotations

from pathlib import Path


class WorkspaceTools:
    """Read/write helper methods constrained to a run workspace."""

    def __init__(self, workspace: str):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def workspace_write_result(self, relative_path: str, content: str) -> str:
        target = (self.workspace / relative_path).resolve()
        if self.workspace not in target.parents and target != self.workspace:
            raise ValueError("path escapes workspace")

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def workspace_read_file(self, relative_path: str) -> str:
        target = (self.workspace / relative_path).resolve()
        if self.workspace not in target.parents and target != self.workspace:
            raise ValueError("path escapes workspace")
        return target.read_text(encoding="utf-8")
