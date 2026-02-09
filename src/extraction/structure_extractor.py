"""
Document Structure Extractor.

Extracts hierarchical structure from documents using multiple strategies:
1. PDF native bookmarks (fastest, no LLM)
2. TOC detection and parsing (LLM on first pages)
3. Heading detection via formatting (regex + font size)
4. Content-based generation (LLM, most expensive)

Inspired by PageIndex (https://github.com/VectifyAI/PageIndex).
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional
import logging

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from ..core.models import DocumentNode, DocumentStructure, ExtractionMode
from ..core.exceptions import StructureExtractionError, DocumentProcessingError
from ..integrations.llm_base import LLMClientProtocol
from ..integrations.llm_factory import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class StructureExtractionConfig:
    """Configuration for structure extraction."""
    toc_check_pages: int = 15
    max_pages_per_node: int = 20
    generate_summaries: bool = True
    verification_sample_size: int = 5
    min_accuracy_threshold: float = 0.6


class DocumentStructureExtractor:
    """
    Extracts hierarchical structure from documents.
    Uses multiple strategies with fallbacks.
    """

    def __init__(
        self,
        claude_client: Optional[LLMClientProtocol] = None,
        config: Optional[StructureExtractionConfig] = None
    ):
        self.claude_client = claude_client or get_llm_client()
        self.config = config or StructureExtractionConfig()

        if fitz is None:
            logger.warning("PyMuPDF not installed. PDF processing will be limited.")

    async def extract(self, pdf_path: str) -> DocumentStructure:
        """
        Main entry point - extracts document structure.

        Tries strategies in order:
        1. PDF native bookmarks
        2. TOC with page numbers
        3. TOC without page numbers
        4. Heading detection
        5. Content generation
        """
        if fitz is None:
            raise DocumentProcessingError("PyMuPDF required for PDF processing")

        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        document_id = pdf_path  # Could be replaced with actual document ID

        logger.info(f"Extracting structure from {pdf_path} ({total_pages} pages)")

        # Strategy 1: Try PDF native bookmarks (instant, no LLM cost)
        structure = self._try_pdf_bookmarks(doc)
        if structure:
            logger.info("Structure extracted via PDF bookmarks")
            return DocumentStructure(
                document_id=document_id,
                root=structure,
                mode_used=ExtractionMode.PDF_BOOKMARKS,
                total_pages=total_pages
            )

        # Strategy 2: Look for TOC in first N pages
        toc_result = await self._detect_and_parse_toc(doc)
        if toc_result:
            structure, mode, toc_pages = toc_result

            # Verify structure accuracy
            accuracy = await self._verify_structure(doc, structure)
            if accuracy >= self.config.min_accuracy_threshold:
                logger.info(f"Structure extracted via {mode.value} (accuracy: {accuracy:.1%})")
                if self.config.generate_summaries:
                    await self._add_summaries(doc, structure)
                return DocumentStructure(
                    document_id=document_id,
                    root=structure,
                    mode_used=mode,
                    total_pages=total_pages,
                    toc_pages=toc_pages
                )
            else:
                logger.warning(f"TOC extraction accuracy too low: {accuracy:.1%}")

        # Strategy 3: Heading detection via formatting
        structure = self._detect_headings_by_formatting(doc)
        if structure and len(structure.children) >= 3:
            logger.info("Structure extracted via heading detection")
            if self.config.generate_summaries:
                await self._add_summaries(doc, structure)
            return DocumentStructure(
                document_id=document_id,
                root=structure,
                mode_used=ExtractionMode.HEADING_DETECTION,
                total_pages=total_pages
            )

        # Strategy 4: Generate structure from content (most expensive)
        logger.info("Falling back to content-based structure generation")
        structure = await self._generate_structure_from_content(doc)
        if self.config.generate_summaries:
            await self._add_summaries(doc, structure)
        return DocumentStructure(
            document_id=document_id,
            root=structure,
            mode_used=ExtractionMode.CONTENT_GENERATION,
            total_pages=total_pages
        )

    # =========================================================================
    # Strategy 1: PDF Native Bookmarks
    # =========================================================================

    def _try_pdf_bookmarks(self, doc) -> Optional[DocumentNode]:
        """Extract structure from PDF's native outline/bookmarks."""
        toc = doc.get_toc()  # [[level, title, page], ...]
        if not toc or len(toc) < 3:
            return None

        root = DocumentNode(id="root", title="Document", level=0, start_page=1)
        stack = [(0, root)]
        node_counter = 0

        for level, title, page in toc:
            node_counter += 1
            node = DocumentNode(
                id=f"node_{node_counter}",
                title=title.strip(),
                level=level,
                start_page=page
            )

            # Find correct parent
            while stack and stack[-1][0] >= level:
                stack.pop()

            parent = stack[-1][1]
            parent.children.append(node)
            stack.append((level, node))

        # Compute end pages
        self._compute_end_pages(root, len(doc))
        return root

    # =========================================================================
    # Strategy 2: TOC Detection and Parsing
    # =========================================================================

    async def _detect_and_parse_toc(
        self,
        doc
    ) -> Optional[tuple[DocumentNode, ExtractionMode, list[int]]]:
        """Detect TOC pages and parse them."""

        # Extract first N pages text
        first_pages = []
        for i in range(min(self.config.toc_check_pages, len(doc))):
            first_pages.append({
                "page": i + 1,
                "text": doc[i].get_text()[:3000]  # Limit text per page
            })

        # Ask LLM to identify TOC pages
        toc_detection = await self.claude_client.query_json(
            prompt=f"""Analyze these document pages and identify if there's a Table of Contents.

Pages:
{json.dumps(first_pages, indent=2)}

Return JSON:
{{
    "has_toc": true/false,
    "toc_pages": [list of page numbers containing TOC],
    "has_page_numbers": true/false,
    "toc_content": "raw TOC text if found"
}}""",
            max_tokens=4096
        )

        if not toc_detection.get("has_toc"):
            return None

        toc_pages = toc_detection.get("toc_pages", [])
        has_page_numbers = toc_detection.get("has_page_numbers", False)
        toc_content = toc_detection.get("toc_content", "")

        if has_page_numbers:
            structure = await self._parse_toc_with_pages(toc_content, len(doc))
            return structure, ExtractionMode.TOC_WITH_PAGES, toc_pages
        else:
            structure = await self._parse_toc_find_pages(toc_content, doc)
            return structure, ExtractionMode.TOC_WITHOUT_PAGES, toc_pages

    async def _parse_toc_with_pages(
        self,
        toc_content: str,
        total_pages: int
    ) -> DocumentNode:
        """Parse TOC that includes page numbers."""

        result = await self.claude_client.query_json(
            prompt=f"""Parse this Table of Contents into a structured hierarchy.

TOC Content:
{toc_content}

Return JSON with this structure:
{{
    "sections": [
        {{
            "title": "ARTICLE I DEFINITIONS",
            "page": 5,
            "level": 1,
            "children": [
                {{"title": "Section 1.01 Defined Terms", "page": 5, "level": 2}},
                {{"title": "Section 1.02 Accounting Terms", "page": 42, "level": 2}}
            ]
        }}
    ]
}}

Rules:
- Preserve exact titles as they appear
- Extract page numbers accurately
- level 1 = top level (Articles/Chapters), level 2 = sections, level 3 = subsections""",
            max_tokens=4096
        )

        return self._build_tree_from_sections(result.get("sections", []), total_pages)

    async def _parse_toc_find_pages(
        self,
        toc_content: str,
        doc
    ) -> DocumentNode:
        """Parse TOC without page numbers - find sections in document."""

        # First, get the structure without pages
        structure_result = await self.claude_client.query_json(
            prompt=f"""Parse this Table of Contents into a structured hierarchy.
Note: Page numbers may not be present - focus on the structure.

TOC Content:
{toc_content}

Return JSON:
{{
    "sections": [
        {{"title": "ARTICLE I DEFINITIONS", "level": 1, "children": [...]}},
        ...
    ]
}}"""
        )

        sections = structure_result.get("sections", [])

        # Build page text index for searching
        page_texts = []
        for i in range(len(doc)):
            page_texts.append(doc[i].get_text()[:2000])

        # Find each section in the document
        await self._find_section_pages(sections, page_texts)

        return self._build_tree_from_sections(sections, len(doc))

    async def _find_section_pages(self, sections: list, page_texts: list):
        """Find the page number for each section by searching the document."""
        for section in sections:
            title = section.get("title", "")

            # Simple search first
            found_page = self._find_title_in_pages(title, page_texts)
            if found_page:
                section["page"] = found_page
            else:
                # Default to page 1 if not found
                section["page"] = 1

            # Recurse for children
            if "children" in section:
                await self._find_section_pages(section["children"], page_texts)

    def _find_title_in_pages(self, title: str, page_texts: list) -> Optional[int]:
        """Simple string search for section title."""
        normalized = re.sub(r'\s+', ' ', title.strip().upper())

        for i, text in enumerate(page_texts):
            normalized_text = re.sub(r'\s+', ' ', text.upper())
            if normalized in normalized_text:
                return i + 1
        return None

    # =========================================================================
    # Strategy 3: Heading Detection via Formatting
    # =========================================================================

    def _detect_headings_by_formatting(self, doc) -> DocumentNode:
        """Detect headings based on font size, bold, patterns."""

        heading_patterns = [
            (r"^ARTICLE\s+[IVX]+", 1),
            (r"^Article\s+\d+", 1),
            (r"^SECTION\s+\d+\.\d+", 2),
            (r"^Section\s+\d+\.\d+", 2),
            (r"^SCHEDULE\s+", 1),
            (r"^EXHIBIT\s+[A-Z]", 1),
            (r"^APPENDIX\s+[A-Z]", 1),
            (r"^PART\s+[IVX\d]+", 1),
            (r"^CHAPTER\s+\d+", 1),
        ]

        headings = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" not in block:
                    continue

                for line in block["lines"]:
                    text = "".join(span["text"] for span in line["spans"]).strip()
                    if not text or len(text) < 5:
                        continue

                    # Check patterns
                    for pattern, level in heading_patterns:
                        if re.match(pattern, text, re.IGNORECASE):
                            headings.append({
                                "title": text[:200],  # Limit title length
                                "page": page_num + 1,
                                "level": level
                            })
                            break

        return self._build_tree_from_sections(headings, len(doc))

    # =========================================================================
    # Strategy 4: Generate Structure from Content
    # =========================================================================

    async def _generate_structure_from_content(self, doc) -> DocumentNode:
        """Generate structure by analyzing document content (most expensive)."""

        chunk_size = 20  # pages per chunk
        all_sections = []

        for start in range(0, len(doc), chunk_size):
            end = min(start + chunk_size, len(doc))
            chunk_text = ""
            for i in range(start, end):
                chunk_text += f"\n--- PAGE {i + 1} ---\n"
                chunk_text += doc[i].get_text()[:3000]

            result = await self.claude_client.query_json(
                prompt=f"""Analyze this document chunk and identify the major sections/headings.

Document pages {start + 1} to {end}:
{chunk_text}

Return JSON:
{{
    "sections": [
        {{"title": "Section Title", "page": page_number, "level": 1_or_2_or_3}},
        ...
    ]
}}

Focus on major structural elements (articles, sections, schedules, exhibits).""",
                max_tokens=2048
            )

            all_sections.extend(result.get("sections", []))

        return self._build_tree_from_sections(all_sections, len(doc))

    # =========================================================================
    # Verification
    # =========================================================================

    async def _verify_structure(
        self,
        doc,
        structure: DocumentNode,
    ) -> float:
        """Verify extracted structure by spot-checking sections."""
        import random

        nodes = []
        self._collect_nodes(structure, nodes)

        if not nodes:
            return 0.0

        sample = random.sample(nodes, min(self.config.verification_sample_size, len(nodes)))

        correct = 0
        for node in sample:
            if node.start_page > len(doc):
                continue

            page_text = doc[node.start_page - 1].get_text()[:1500]

            result = await self.claude_client.query_json(
                prompt=f"""Does this page contain or start with the section titled "{node.title}"?

Page {node.start_page} content:
{page_text}

Return JSON: {{"found": true/false, "confidence": 0.0-1.0}}""",
                max_tokens=200
            )

            if result.get("found") and result.get("confidence", 0) > 0.7:
                correct += 1

        return correct / len(sample) if sample else 0.0

    def _collect_nodes(self, node: DocumentNode, nodes: list):
        if node.level > 0:
            nodes.append(node)
        for child in node.children:
            self._collect_nodes(child, nodes)

    # =========================================================================
    # Summaries
    # =========================================================================

    async def _add_summaries(self, doc, structure: DocumentNode):
        """Add LLM-generated summaries to each node."""
        await self._add_summary_recursive(doc, structure)

    async def _add_summary_recursive(self, doc, node: DocumentNode):
        if node.level > 0 and node.start_page and node.end_page:
            section_text = ""
            for i in range(node.start_page - 1, min(node.end_page, node.start_page + 2)):
                if i < len(doc):
                    section_text += doc[i].get_text()[:1000]

            if section_text:
                result = await self.claude_client.query_json(
                    prompt=f"""Summarize this section in 1-2 sentences.

Section: {node.title}
Content:
{section_text[:2000]}

Return JSON: {{"summary": "brief summary"}}""",
                    max_tokens=200
                )
                node.summary = result.get("summary")

        for child in node.children:
            await self._add_summary_recursive(doc, child)

    # =========================================================================
    # Helpers
    # =========================================================================

    def _build_tree_from_sections(
        self,
        sections: list,
        total_pages: int
    ) -> DocumentNode:
        """Build tree from flat section list."""
        root = DocumentNode(id="root", title="Document", level=0, start_page=1)

        if not sections:
            root.end_page = total_pages
            return root

        stack = [(0, root)]
        node_counter = 0

        for section in sections:
            node_counter += 1
            level = section.get("level", 1)
            node = DocumentNode(
                id=f"node_{node_counter}",
                title=section.get("title", f"Section {node_counter}"),
                level=level,
                start_page=section.get("page", 1)
            )

            # Find correct parent
            while stack and stack[-1][0] >= level:
                stack.pop()

            if stack:
                parent = stack[-1][1]
                parent.children.append(node)

            stack.append((level, node))

            # Handle children if present
            if "children" in section:
                self._add_children_recursive(node, section["children"], node_counter)

        self._compute_end_pages(root, total_pages)
        return root

    def _add_children_recursive(self, parent: DocumentNode, children: list, counter: int):
        for child_section in children:
            counter += 1
            child = DocumentNode(
                id=f"node_{counter}",
                title=child_section.get("title", ""),
                level=child_section.get("level", parent.level + 1),
                start_page=child_section.get("page", parent.start_page)
            )
            parent.children.append(child)

            if "children" in child_section:
                self._add_children_recursive(child, child_section["children"], counter)

    def _compute_end_pages(self, node: DocumentNode, total_pages: int):
        """Compute end_page for each node based on next sibling/parent."""
        all_nodes = []
        self._flatten_nodes(node, all_nodes)
        all_nodes.sort(key=lambda n: n.start_page)

        for i, n in enumerate(all_nodes):
            if i + 1 < len(all_nodes):
                n.end_page = all_nodes[i + 1].start_page - 1
            else:
                n.end_page = total_pages

            if n.end_page < n.start_page:
                n.end_page = n.start_page

    def _flatten_nodes(self, node: DocumentNode, result: list):
        if node.start_page:
            result.append(node)
        for child in node.children:
            self._flatten_nodes(child, result)
