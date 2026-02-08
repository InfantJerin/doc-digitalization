"""Document structure lookup tools for extraction skills."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..core.models import DocumentNode, DocumentStructure, ExtractionMode


class StructureTools:
    """Loads serialized structure trees and resolves sections."""

    def structure_load(self, structure_path: str) -> DocumentStructure:
        payload = json.loads(Path(structure_path).read_text(encoding="utf-8"))
        return DocumentStructure(
            document_id=payload.get("document_id", ""),
            root=DocumentNode.from_dict(payload["root"]),
            mode_used=ExtractionMode(payload.get("mode_used", ExtractionMode.PDF_BOOKMARKS.value)),
            total_pages=payload.get("total_pages", 0),
            toc_pages=payload.get("toc_pages", []),
        )

    def structure_find_section(self, structure: DocumentStructure, section_title: str) -> Optional[dict]:
        node = structure.get_node_by_title(section_title)
        if not node:
            return None
        return {
            "title": node.title,
            "start_page": node.start_page,
            "end_page": node.end_page,
            "summary": node.summary,
        }
