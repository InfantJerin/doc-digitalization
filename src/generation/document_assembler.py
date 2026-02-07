"""
Document Assembler.

Assembles generated sections into a final document (DOCX, PDF, Markdown).
"""

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core.models import GeneratedSection, GenerationRun
from ..core.config_loader import GenerationPipelineConfig
from ..core.exceptions import DocumentAssemblyError

logger = logging.getLogger(__name__)

# Optional imports for document generation
try:
    from docx import Document as DocxDocument
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx not installed. DOCX generation unavailable.")

try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False


class DocumentAssembler:
    """
    Assembles generated sections into final documents.

    Supports:
    - DOCX (Microsoft Word)
    - PDF (via conversion)
    - Markdown
    """

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir) if output_dir else Path("/tmp/generated_docs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def assemble(
        self,
        run: GenerationRun,
        config: GenerationPipelineConfig
    ) -> str:
        """
        Assemble sections into a final document.

        Args:
            run: The generation run with sections
            config: Pipeline configuration

        Returns:
            Path to the generated document
        """
        output_format = config.output.format.lower()

        # Generate filename
        filename = config.output.filename_template.format(
            pipeline_id=config.id,
            deal_id=run.deal_id,
            date=datetime.now().strftime("%Y%m%d"),
            format=output_format
        )
        output_path = self.output_dir / filename

        logger.info(f"Assembling document: {filename}")

        match output_format:
            case "docx":
                await self._assemble_docx(run.sections, output_path, config)
            case "pdf":
                # Generate DOCX first, then convert
                docx_path = output_path.with_suffix(".docx")
                await self._assemble_docx(run.sections, docx_path, config)
                await self._convert_to_pdf(docx_path, output_path)
            case "markdown" | "md":
                await self._assemble_markdown(run.sections, output_path, config)
            case _:
                raise DocumentAssemblyError(f"Unsupported format: {output_format}")

        logger.info(f"Document assembled: {output_path}")
        return str(output_path)

    async def _assemble_docx(
        self,
        sections: list[GeneratedSection],
        output_path: Path,
        config: GenerationPipelineConfig
    ):
        """Assemble sections into a DOCX document."""
        if not DOCX_AVAILABLE:
            raise DocumentAssemblyError("python-docx not installed")

        doc = DocxDocument()

        # Add title
        title = doc.add_heading(config.name, 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Add metadata
        doc.add_paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        doc.add_paragraph()

        # Add each section
        for section in sections:
            # Section heading
            doc.add_heading(section.section_name, 1)

            # Convert markdown content to paragraphs
            paragraphs = self._markdown_to_paragraphs(section.content)
            for para in paragraphs:
                if para.startswith("## "):
                    doc.add_heading(para[3:], 2)
                elif para.startswith("### "):
                    doc.add_heading(para[4:], 3)
                elif para.startswith("- "):
                    # Bullet point
                    doc.add_paragraph(para[2:], style="List Bullet")
                elif para.startswith("1. ") or para.startswith("2. "):
                    # Numbered list
                    doc.add_paragraph(para[3:], style="List Number")
                elif para.strip():
                    doc.add_paragraph(para)

            # Add spacing between sections
            doc.add_paragraph()

        # Save document
        doc.save(str(output_path))

    async def _assemble_markdown(
        self,
        sections: list[GeneratedSection],
        output_path: Path,
        config: GenerationPipelineConfig
    ):
        """Assemble sections into a Markdown document."""
        lines = []

        # Add title
        lines.append(f"# {config.name}")
        lines.append("")
        lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Add table of contents
        lines.append("## Table of Contents")
        lines.append("")
        for i, section in enumerate(sections, 1):
            anchor = section.section_name.lower().replace(" ", "-")
            lines.append(f"{i}. [{section.section_name}](#{anchor})")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Add sections
        for section in sections:
            lines.append(f"## {section.section_name}")
            lines.append("")
            lines.append(section.content)
            lines.append("")

            # Add conflict warnings if any
            if section.data_points and section.data_points.has_conflicts:
                lines.append("> **Note:** This section contains data point conflicts "
                           "that require review.")
                lines.append("")

        # Write file
        output_path.write_text("\n".join(lines))

    async def _convert_to_pdf(self, docx_path: Path, pdf_path: Path):
        """Convert DOCX to PDF."""
        # This would typically use a library like docx2pdf or an external service
        # For now, just log a warning
        logger.warning(
            f"PDF conversion not implemented. DOCX created at {docx_path}"
        )
        # Could use: subprocess.run(['libreoffice', '--convert-to', 'pdf', str(docx_path)])

    def _markdown_to_paragraphs(self, content: str) -> list[str]:
        """Split markdown content into paragraphs."""
        lines = content.split("\n")
        paragraphs = []
        current = []

        for line in lines:
            if line.strip() == "":
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
            else:
                # Check if it's a heading or list item (don't merge these)
                if line.startswith("#") or line.startswith("-") or \
                   line.startswith("1.") or line.startswith("2."):
                    if current:
                        paragraphs.append(" ".join(current))
                        current = []
                    paragraphs.append(line)
                else:
                    current.append(line)

        if current:
            paragraphs.append(" ".join(current))

        return paragraphs

    def get_document_bytes(
        self,
        run: GenerationRun,
        format: str = "markdown"
    ) -> bytes:
        """
        Get document content as bytes for download.

        Used for API responses.
        """
        if format == "markdown":
            content = self._sections_to_markdown(run.sections)
            return content.encode("utf-8")
        else:
            raise DocumentAssemblyError(f"Byte output not supported for {format}")

    def _sections_to_markdown(self, sections: list[GeneratedSection]) -> str:
        """Convert sections to markdown string."""
        parts = []
        for section in sections:
            parts.append(f"## {section.section_name}\n\n{section.content}\n")
        return "\n".join(parts)
