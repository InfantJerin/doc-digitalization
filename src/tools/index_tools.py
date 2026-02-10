"""Navigation tools for the PageIndex system.

Follows the existing tool pattern (``StructureTools``, ``PDFTools``).
All methods operate on pre-built ``DealPageIndex`` data.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..core.models import (
    CrossDocumentReference,
    DealPageIndex,
    DocumentNode,
    DocumentPageIndex,
    KeywordEntry,
)


class IndexTools:
    """Agent-accessible navigation tools over a pre-built DealPageIndex."""

    def __init__(self, deal_index: DealPageIndex):
        self._index = deal_index

    # ------------------------------------------------------------------
    # Section navigation
    # ------------------------------------------------------------------

    def find_section(
        self, query: str, doc_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Find sections matching a query across documents.

        Args:
            query: Search term (e.g. "covenant", "definitions").
            doc_id: Optional document ID to restrict search.

        Returns:
            List of matching sections with doc_id, node_id, title, path, pages.
        """
        results: list[dict[str, Any]] = []
        needle = query.lower()

        indexes = self._resolve_indexes(doc_id)
        for did, doc_index in indexes.items():
            if not doc_index.structure:
                continue
            for node in doc_index.structure.get_all_nodes():
                if needle in node.title.lower():
                    results.append({
                        "doc_id": did,
                        "node_id": node.id,
                        "title": node.title,
                        "path": self._node_path(node, doc_index),
                        "start_page": node.start_page,
                        "end_page": node.end_page,
                    })

        # Fallback 1: query via keyword index -> resolve to section nodes
        if not results:
            for did, doc_index in indexes.items():
                if not doc_index.structure:
                    continue
                section_names: set[str] = set()
                for kw in doc_index.keyword_index:
                    if needle in kw.canonical_term or needle in kw.term.lower():
                        for section in kw.sections:
                            section_names.add(section)
                if not section_names:
                    continue
                for node in doc_index.structure.get_all_nodes():
                    if node.title in section_names:
                        results.append({
                            "doc_id": did,
                            "node_id": node.id,
                            "title": node.title,
                            "path": self._node_path(node, doc_index),
                            "start_page": node.start_page,
                            "end_page": node.end_page,
                        })

        # Fallback 2: scan page text and map hits back to containing section ranges
        if not results:
            for did, doc_index in indexes.items():
                if not doc_index.structure:
                    continue
                hit_pages = set()
                for layout in doc_index.page_layouts:
                    content = " ".join(layout.headers + layout.paragraphs).lower()
                    if needle in content:
                        hit_pages.add(layout.page_number)
                if not hit_pages:
                    continue
                for node in doc_index.structure.get_all_nodes():
                    end_page = node.end_page or node.start_page
                    for page in hit_pages:
                        if node.start_page <= page <= end_page:
                            results.append({
                                "doc_id": did,
                                "node_id": node.id,
                                "title": node.title,
                                "path": self._node_path(node, doc_index),
                                "start_page": node.start_page,
                                "end_page": node.end_page,
                            })
                            break

        # Deduplicate by doc+node
        dedup: dict[tuple[str, str], dict[str, Any]] = {}
        for item in results:
            key = (item["doc_id"], item["node_id"])
            dedup[key] = item
        results = list(dedup.values())

        return results

    def lookup_keyword(self, term: str) -> list[dict[str, Any]]:
        """Look up a term in the unified keyword index.

        Returns:
            List of matching entries with term, pages, sections, type.
        """
        needle = term.lower()
        results: list[dict[str, Any]] = []

        for kw in self._index.unified_keywords:
            if needle in kw.canonical_term or needle in kw.term.lower():
                results.append({
                    "term": kw.term,
                    "canonical_term": kw.canonical_term,
                    "pages": kw.pages,
                    "sections": kw.sections,
                    "term_type": kw.term_type.value,
                    "definition_page": kw.definition_page,
                })

        return results

    def find_term_across_docs(self, term: str) -> list[dict[str, Any]]:
        """Search for a term across all documents in the deal.

        Returns per-document results with doc_id, doc_type, pages, sections.
        """
        needle = term.lower()
        results: list[dict[str, Any]] = []

        for doc_id, doc_index in self._index.document_indexes.items():
            matching_pages: list[int] = []
            matching_sections: list[str] = []

            for kw in doc_index.keyword_index:
                if needle in kw.canonical_term or needle in kw.term.lower():
                    matching_pages.extend(p for p in kw.pages if p not in matching_pages)
                    matching_sections.extend(
                        s for s in kw.sections if s not in matching_sections
                    )

            if matching_pages:
                results.append({
                    "doc_id": doc_id,
                    "doc_type": doc_index.document_type,
                    "pages": sorted(matching_pages),
                    "sections": matching_sections,
                })

        return results

    def get_definition(self, term: str) -> Optional[dict[str, Any]]:
        """Find the formal definition of a term.

        Returns the term's definition location (doc_id, page, context) if found.
        """
        needle = term.lower()

        # Check unified keywords first
        for kw in self._index.unified_keywords:
            if (needle == kw.canonical_term or needle == kw.term.lower()) and kw.definition_page:
                # Find which document has this definition page
                for doc_id, doc_index in self._index.document_indexes.items():
                    for doc_kw in doc_index.keyword_index:
                        if doc_kw.canonical_term == kw.canonical_term and doc_kw.definition_page:
                            context = self._get_page_text_snippet(
                                doc_index, doc_kw.definition_page, needle
                            )
                            return {
                                "term": kw.term,
                                "doc_id": doc_id,
                                "page": doc_kw.definition_page,
                                "context": context,
                            }

        return None

    def get_subtree(
        self, node_id: str, doc_id: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Get a section node and its children.

        Args:
            node_id: The node ID to look up.
            doc_id: Optional document ID to restrict search.

        Returns:
            Node dict with children, or None if not found.
        """
        indexes = self._resolve_indexes(doc_id)
        for did, doc_index in indexes.items():
            if not doc_index.structure:
                continue
            node = self._find_node_by_id(doc_index.structure.root, node_id)
            if node:
                return self._node_to_dict(node, did)
        return None

    def get_page_content(
        self, doc_id: str, pages: list[int]
    ) -> list[dict[str, Any]]:
        """Retrieve page layout data for specific pages.

        Args:
            doc_id: Document ID.
            pages: List of page numbers to retrieve.

        Returns:
            List of page layout dicts.
        """
        doc_index = self._index.document_indexes.get(doc_id)
        if not doc_index:
            return []

        results: list[dict[str, Any]] = []
        page_map = {pl.page_number: pl for pl in doc_index.page_layouts}

        for page_num in pages:
            layout = page_map.get(page_num)
            if layout:
                results.append(layout.to_dict())

        return results

    def search_in_section(
        self, node_id: str, query: str, doc_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Search for text within a specific section's page range.

        Args:
            node_id: Section node ID.
            query: Search text.
            doc_id: Optional document ID.

        Returns:
            List of matching pages with context.
        """
        needle = query.lower()
        indexes = self._resolve_indexes(doc_id)
        results: list[dict[str, Any]] = []

        for did, doc_index in indexes.items():
            if not doc_index.structure:
                continue
            node = self._find_node_by_id(doc_index.structure.root, node_id)
            if not node:
                continue

            end_page = node.end_page or node.start_page
            page_map = {pl.page_number: pl for pl in doc_index.page_layouts}

            for page_num in range(node.start_page, end_page + 1):
                layout = page_map.get(page_num)
                if not layout:
                    continue
                full_text = " ".join(layout.headers + layout.paragraphs).lower()
                if needle in full_text:
                    # Extract context around match
                    idx = full_text.find(needle)
                    start = max(0, idx - 100)
                    end = min(len(full_text), idx + len(needle) + 100)
                    results.append({
                        "doc_id": did,
                        "page": page_num,
                        "context": full_text[start:end],
                    })

        return results

    def resolve_reference(
        self, doc_id: str, page: int
    ) -> list[dict[str, Any]]:
        """Find cross-document references originating from a specific page.

        Args:
            doc_id: Source document ID.
            page: Source page number.

        Returns:
            List of resolved references with target details.
        """
        results: list[dict[str, Any]] = []

        for ref in self._index.cross_references:
            if ref.source_document_id == doc_id and ref.source_page == page:
                results.append({
                    "reference_text": ref.reference_text,
                    "target_doc_id": ref.target_document_id,
                    "target_doc_type": self._index.document_registry.get(
                        ref.target_document_id, ""
                    ),
                    "target_node_id": ref.target_node_id,
                    "target_page": ref.target_page,
                    "confidence": ref.confidence,
                })

        return results

    def get_amendments_for_section(
        self, node_id: str
    ) -> list[dict[str, Any]]:
        """Find cross-references that target a specific section.

        Useful for finding amendments or modifications to a section.

        Args:
            node_id: Target section node ID.

        Returns:
            List of references pointing to this section.
        """
        results: list[dict[str, Any]] = []

        for ref in self._index.cross_references:
            if ref.target_node_id == node_id:
                results.append({
                    "source_doc_id": ref.source_document_id,
                    "source_doc_type": self._index.document_registry.get(
                        ref.source_document_id, ""
                    ),
                    "source_page": ref.source_page,
                    "reference_text": ref.reference_text,
                    "confidence": ref.confidence,
                })

        return results

    def get_index_summary(self) -> dict[str, Any]:
        """High-level summary of the deal index for agent prompts.

        Returns:
            Summary with document list, keyword count, cross-reference count,
            and top keywords.
        """
        docs: list[dict[str, Any]] = []
        for doc_id, doc_index in self._index.document_indexes.items():
            top_sections: list[str] = []
            if doc_index.structure:
                for node in doc_index.structure.get_all_nodes()[:8]:
                    top_sections.append(node.title)

            docs.append({
                "doc_id": doc_id,
                "doc_type": doc_index.document_type,
                "total_pages": doc_index.total_pages,
                "keyword_count": len(doc_index.keyword_index),
                "top_sections": top_sections,
            })

        top_keywords = [
            {"term": kw.term, "pages": len(kw.pages), "type": kw.term_type.value}
            for kw in self._index.unified_keywords[:20]
        ]

        return {
            "deal_id": self._index.deal_id,
            "document_count": len(self._index.document_indexes),
            "documents": docs,
            "total_unified_keywords": len(self._index.unified_keywords),
            "top_keywords": top_keywords,
            "cross_reference_count": len(self._index.cross_references),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_indexes(
        self, doc_id: Optional[str]
    ) -> dict[str, DocumentPageIndex]:
        """Return indexes to search, optionally restricted to one doc."""
        if doc_id:
            idx = self._index.document_indexes.get(doc_id)
            return {doc_id: idx} if idx else {}
        return self._index.document_indexes

    def _find_node_by_id(
        self, node: DocumentNode, node_id: str
    ) -> Optional[DocumentNode]:
        """Recursively find a node by its ID."""
        if node.id == node_id:
            return node
        for child in node.children:
            found = self._find_node_by_id(child, node_id)
            if found:
                return found
        return None

    def _node_path(
        self, target: DocumentNode, doc_index: DocumentPageIndex
    ) -> str:
        """Build a breadcrumb path for a node (e.g. 'Article I > Section 1.01')."""
        if not doc_index.structure:
            return target.title

        path_parts: list[str] = []
        self._build_path(doc_index.structure.root, target.id, path_parts)
        return " > ".join(path_parts) if path_parts else target.title

    def _build_path(
        self,
        node: DocumentNode,
        target_id: str,
        path: list[str],
    ) -> bool:
        """Recursively build path from root to target node."""
        if node.id == target_id:
            if node.level > 0:
                path.append(node.title)
            return True
        for child in node.children:
            if self._build_path(child, target_id, path):
                if node.level > 0:
                    path.insert(len(path) - 1, node.title)
                return True
        return False

    def _node_to_dict(self, node: DocumentNode, doc_id: str) -> dict[str, Any]:
        """Convert a node and its children to a dict."""
        return {
            "doc_id": doc_id,
            "node_id": node.id,
            "title": node.title,
            "level": node.level,
            "start_page": node.start_page,
            "end_page": node.end_page,
            "summary": node.summary,
            "children": [
                self._node_to_dict(child, doc_id) for child in node.children
            ],
        }

    def _get_page_text_snippet(
        self,
        doc_index: DocumentPageIndex,
        page_num: int,
        term: str,
    ) -> str:
        """Extract a text snippet around a term on a given page."""
        page_map = {pl.page_number: pl for pl in doc_index.page_layouts}
        layout = page_map.get(page_num)
        if not layout:
            return ""

        full_text = " ".join(layout.headers + layout.paragraphs)
        lower = full_text.lower()
        idx = lower.find(term.lower())
        if idx < 0:
            return full_text[:300]

        start = max(0, idx - 50)
        end = min(len(full_text), idx + len(term) + 200)
        return full_text[start:end]
