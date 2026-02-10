"""JSON file I/O for page index storage within workspace directories."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core.exceptions import IndexNotFoundError
from ..core.models import DealPageIndex, DocumentPageIndex

logger = logging.getLogger(__name__)


class IndexStore:
    """Manages persistence of page indexes as JSON files in a workspace.

    Directory layout::

        {workspace_root}/index/
            index_manifest.json
            doc_index_{doc_id}.json
            deal_index.json
    """

    def __init__(self, workspace_root: Path | str):
        self.workspace_root = Path(workspace_root)
        self.index_dir = self.workspace_root / "index"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.index_dir / "index_manifest.json"

    # ------------------------------------------------------------------
    # Document index
    # ------------------------------------------------------------------

    def save_document_index(self, index: DocumentPageIndex) -> Path:
        """Persist a document index to JSON."""
        filename = f"doc_index_{index.document_id}.json"
        path = self.index_dir / filename
        path.write_text(
            json.dumps(index.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._update_manifest(document_id=index.document_id, filename=filename)
        logger.debug("Saved document index for %s", index.document_id)
        return path

    def load_document_index(self, document_id: str) -> DocumentPageIndex:
        """Load a document index from JSON."""
        filename = f"doc_index_{document_id}.json"
        path = self.index_dir / filename
        if not path.exists():
            raise IndexNotFoundError(document_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return DocumentPageIndex.from_dict(data)

    def has_document_index(self, document_id: str) -> bool:
        """Check if a document index exists."""
        filename = f"doc_index_{document_id}.json"
        return (self.index_dir / filename).exists()

    def list_document_indexes(self) -> list[str]:
        """Return document IDs for all stored document indexes."""
        ids: list[str] = []
        for path in self.index_dir.glob("doc_index_*.json"):
            # Extract doc_id from filename: doc_index_{doc_id}.json
            doc_id = path.stem.removeprefix("doc_index_")
            ids.append(doc_id)
        return ids

    # ------------------------------------------------------------------
    # Deal index
    # ------------------------------------------------------------------

    def save_deal_index(self, index: DealPageIndex) -> Path:
        """Persist the deal-level index to JSON."""
        path = self.index_dir / "deal_index.json"
        path.write_text(
            json.dumps(index.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self._update_manifest(deal_id=index.deal_id)
        logger.debug("Saved deal index for %s", index.deal_id)
        return path

    def load_deal_index(self) -> DealPageIndex:
        """Load the deal-level index from JSON."""
        path = self.index_dir / "deal_index.json"
        if not path.exists():
            raise IndexNotFoundError("deal_index")
        data = json.loads(path.read_text(encoding="utf-8"))
        return DealPageIndex.from_dict(data)

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def _update_manifest(
        self,
        *,
        document_id: Optional[str] = None,
        filename: Optional[str] = None,
        deal_id: Optional[str] = None,
    ) -> None:
        """Update the index manifest with latest entry."""
        manifest = self._load_manifest()

        if document_id and filename:
            docs = manifest.setdefault("documents", {})
            docs[document_id] = {
                "filename": filename,
                "indexed_at": datetime.utcnow().isoformat(),
            }

        if deal_id:
            manifest["deal_id"] = deal_id
            manifest["deal_indexed_at"] = datetime.utcnow().isoformat()

        self._manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load_manifest(self) -> dict:
        """Load the manifest file, returning empty dict if absent."""
        if self._manifest_path.exists():
            return json.loads(self._manifest_path.read_text(encoding="utf-8"))
        return {}
