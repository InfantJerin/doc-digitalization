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
        self.claude_client = claude_client
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
            self._augment_special_sections(doc, structure)
            self._compute_end_pages(structure, total_pages)
            logger.info("Structure extracted via PDF bookmarks")
            return DocumentStructure(
                document_id=document_id,
                root=structure,
                mode_used=ExtractionMode.PDF_BOOKMARKS,
                total_pages=total_pages
            )

        # Strategy 2: Programmatic TOC parsing (no LLM)
        toc_result = self._detect_and_parse_toc_programmatic(doc)
        if toc_result:
            structure, mode, toc_pages = toc_result
            self._augment_special_sections(doc, structure)
            self._compute_end_pages(structure, total_pages)
            logger.info("Structure extracted via programmatic TOC parsing")
            if self.config.generate_summaries and self.claude_client:
                await self._add_summaries(doc, structure)
            return DocumentStructure(
                document_id=document_id,
                root=structure,
                mode_used=mode,
                total_pages=total_pages,
                toc_pages=toc_pages
            )

        # Strategy 3: LLM-assisted TOC detection/parsing
        if self.claude_client:
            toc_result = await self._detect_and_parse_toc(doc)
            if toc_result:
                structure, mode, toc_pages = toc_result
                self._augment_special_sections(doc, structure)
                self._compute_end_pages(structure, total_pages)

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

        # Strategy 4: Heading detection via formatting
        structure = self._detect_headings_by_formatting(doc)
        if structure and len(structure.children) >= 3:
            self._augment_special_sections(doc, structure)
            self._compute_end_pages(structure, total_pages)
            logger.info("Structure extracted via heading detection")
            if self.config.generate_summaries and self.claude_client:
                await self._add_summaries(doc, structure)
            return DocumentStructure(
                document_id=document_id,
                root=structure,
                mode_used=ExtractionMode.HEADING_DETECTION,
                total_pages=total_pages
            )

        # Strategy 5: Generate structure from content (most expensive, LLM only)
        if not self.claude_client:
            logger.warning("No LLM client available; returning minimal fallback structure")
            root = DocumentNode(id="root", title="Document", level=0, start_page=1, end_page=total_pages)
            return DocumentStructure(
                document_id=document_id,
                root=root,
                mode_used=ExtractionMode.HEADING_DETECTION,
                total_pages=total_pages
            )

        logger.info("Falling back to content-based structure generation")
        structure = await self._generate_structure_from_content(doc)
        self._augment_special_sections(doc, structure)
        self._compute_end_pages(structure, total_pages)
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

    # =========================================================================
    # Strategy 2a: Programmatic TOC Detection and Parsing (No LLM)
    # =========================================================================

    def _detect_and_parse_toc_programmatic(
        self,
        doc
    ) -> Optional[tuple[DocumentNode, ExtractionMode, list[int]]]:
        """Detect and parse TOC pages using deterministic regex heuristics."""
        max_pages = min(self.config.toc_check_pages, len(doc))
        toc_pages: list[int] = []
        toc_lines: list[str] = []
        started = False

        for i in range(max_pages):
            text = doc[i].get_text()
            lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
            lower_text = text.lower()

            if "table of contents" in lower_text:
                started = True
                toc_pages.append(i + 1)
                toc_lines.extend(lines)
                continue

            if not started:
                continue

            page_toc_hits = sum(1 for ln in lines if self._looks_like_toc_entry(ln))
            if page_toc_hits >= 2:
                toc_pages.append(i + 1)
                toc_lines.extend(lines)
            else:
                break

        if not toc_pages:
            return None

        sections = self._parse_toc_lines(toc_lines, len(doc))
        if len(sections) < 3:
            return None

        return (
            self._build_tree_from_sections(sections, len(doc)),
            ExtractionMode.TOC_WITH_PAGES,
            toc_pages,
        )

    def _looks_like_toc_entry(self, line: str) -> bool:
        """Return True if line appears to be a TOC entry or continuation."""
        cleaned = re.sub(r"\s+", " ", line.strip())
        if not cleaned:
            return False
        if re.match(r"^(ARTICLE|Section|SCHEDULE|Schedule|EXHIBIT|Exhibit|APPENDIX|Appendix|PART|CHAPTER)\b", cleaned):
            return True
        if re.search(r"\.{2,}\s*\d{1,4}\s*$", cleaned):
            return True
        if re.match(r"^\d{1,4}$", cleaned):
            return True
        return False

    def _parse_toc_lines(self, lines: list[str], total_pages: int) -> list[dict]:
        """Parse TOC text lines into section dictionaries with page and level."""
        sections: list[dict] = []
        pending_title: Optional[str] = None

        def emit(title: str, page: int):
            title = re.sub(r"\s+", " ", title).strip(" .")
            if not title:
                return
            if page < 1 or page > total_pages:
                return
            sections.append({
                "title": title,
                "page": page,
                "level": self._infer_toc_level(title),
            })

        for raw in lines:
            line = re.sub(r"\s+", " ", raw).strip()
            if not line:
                continue
            if line.upper() in {"TABLE OF CONTENTS", "PAGE"}:
                continue
            if re.match(r"^[ivxlcdm]+$", line.lower()):
                continue
            if re.match(r"^#\d", line):
                continue

            dotted = re.match(r"^(?P<title>.+?)\.{2,}\s*(?P<page>\d{1,4})$", line)
            if dotted:
                full_title = dotted.group("title").strip()
                if pending_title:
                    full_title = f"{pending_title} {full_title}"
                    pending_title = None
                emit(full_title, int(dotted.group("page")))
                continue

            combined = re.match(
                r"^(?P<title>(?:ARTICLE|Section|SCHEDULE|Schedule|EXHIBIT|Exhibit|APPENDIX|Appendix|PART|CHAPTER)\b.+?)\s+(?P<page>\d{1,4})$",
                line,
                re.IGNORECASE,
            )
            if combined:
                emit(combined.group("title"), int(combined.group("page")))
                pending_title = None
                continue

            if pending_title and re.match(r"^\d{1,4}$", line):
                emit(pending_title, int(line))
                pending_title = None
                continue

            if re.match(
                r"^(ARTICLE|Section|SCHEDULE|Schedule|EXHIBIT|Exhibit|APPENDIX|Appendix|PART|CHAPTER)\b",
                line,
                re.IGNORECASE,
            ):
                pending_title = line
            elif pending_title:
                pending_title = f"{pending_title} {line}"

        # Dedupe same title/page pairs while preserving order
        seen: set[tuple[str, int]] = set()
        deduped: list[dict] = []
        for section in sections:
            key = (section["title"], section["page"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(section)

        return deduped

    def _infer_toc_level(self, title: str) -> int:
        """Infer hierarchy level from TOC entry title."""
        t = title.strip().upper()
        if re.match(r"^(ARTICLE|PART|CHAPTER|SCHEDULE|EXHIBIT|APPENDIX)\b", t):
            return 1
        if re.match(r"^SECTION\s+\d+(\.\d+)?", t):
            return 2
        if re.match(r"^\([A-Z0-9]+\)", t):
            return 3
        return 2

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

    def _augment_special_sections(self, doc, root: DocumentNode) -> None:
        """Add top-level nodes for Schedules/Exhibits/Appendices found in body pages.

        TOCs often omit page numbers for these trailing sections. Without these nodes,
        later pages can be incorrectly attributed to the final numbered section.
        """
        title_patterns = [
            re.compile(r"^(SCHEDULE(?:S)?\s*[A-Z0-9\-]*)\b", re.IGNORECASE),
            re.compile(r"^(EXHIBIT(?:S)?\s*[A-Z0-9\-]*)\b", re.IGNORECASE),
            re.compile(r"^(APPENDIX(?:ES)?\s*[A-Z0-9\-]*)\b", re.IGNORECASE),
        ]

        existing_titles = {child.title.upper() for child in root.children}
        max_id = 0
        id_pattern = re.compile(r"node_(\d+)")
        all_nodes: list[DocumentNode] = []
        self._collect_nodes(root, all_nodes)
        for node in all_nodes:
            match = id_pattern.match(node.id or "")
            if match:
                max_id = max(max_id, int(match.group(1)))

        additions: list[DocumentNode] = []
        start_scan_idx = min(max(self.config.toc_check_pages, 1), max(len(doc) - 1, 0))
        for page_idx in range(start_scan_idx, len(doc)):
            page_num = page_idx + 1
            lines = [ln.strip() for ln in doc[page_idx].get_text().splitlines()[:40] if ln.strip()]
            for line in lines:
                normalized = re.sub(r"\s+", " ", line).strip(" .")
                for pattern in title_patterns:
                    m = pattern.match(normalized)
                    if not m:
                        continue
                    title = m.group(1).upper()
                    if title in {"SCHEDULES", "EXHIBITS", "APPENDICES"}:
                        continue
                    if title in existing_titles:
                        continue
                    max_id += 1
                    additions.append(
                        DocumentNode(
                            id=f"node_{max_id}",
                            title=title,
                            level=1,
                            start_page=page_num,
                        )
                    )
                    existing_titles.add(title)
                    break

        if additions:
            root.children.extend(additions)
            root.children.sort(key=lambda n: (n.start_page or 1, n.title))
