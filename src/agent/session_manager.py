"""Agent session lifecycle and checkpointing helpers."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class AgentSession:
    session_id: str
    workspace: Path
    checkpoint_path: Path
    created_at: datetime
    resumed: bool = False


class SessionManager:
    """Manages session IDs and file-based checkpoints per workspace."""

    CHECKPOINT_FILE = "agent_session_checkpoint.json"

    def open(self, workspace_path: Path) -> AgentSession:
        checkpoint_path = workspace_path / self.CHECKPOINT_FILE
        if checkpoint_path.exists():
            payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            session_id = payload.get("session_id") or str(uuid.uuid4())
            return AgentSession(
                session_id=session_id,
                workspace=workspace_path,
                checkpoint_path=checkpoint_path,
                created_at=datetime.fromisoformat(payload.get("created_at")),
                resumed=True,
            )

        session = AgentSession(
            session_id=str(uuid.uuid4()),
            workspace=workspace_path,
            checkpoint_path=checkpoint_path,
            created_at=datetime.utcnow(),
            resumed=False,
        )
        self.save(session)
        return session

    def save(self, session: AgentSession, extra: Optional[dict] = None) -> None:
        payload = {
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        if extra:
            payload.update(extra)
        session.checkpoint_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def clear(self, workspace_path: Path) -> None:
        checkpoint_path = workspace_path / self.CHECKPOINT_FILE
        if checkpoint_path.exists():
            checkpoint_path.unlink()
