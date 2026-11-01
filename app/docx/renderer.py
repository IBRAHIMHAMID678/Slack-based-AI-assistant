"""Proposal DOCX document renderer.

Generates beautifully structured DOCX documents from draft section models
with headers, footers, cover formatting, and isolated section regeneration.
"""

from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from app.docx.styles import (
    COLOR_MUTED_GRAY,
    COLOR_PRIMARY_NAVY,
    COLOR_SECONDARY_BLUE,
    apply_document_styles,
)
from app.errors import DocxRenderError
from app.logging import get_logger

logger = get_logger("docx_renderer")


def configure_header_footer(doc: Any, company_name: str, version: int) -> None:
    """Add confidential header and provenance footer across document sections."""
    for sec in doc.sections:
        header = sec.header
        header_para = header.paragraphs[0]
        header_para.text = f"Confidential Proposal | Prepared for {company_name}"
        header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if header_para.runs:
            header_para.runs[0].font.size = Pt(8.5)
            header_para.runs[0].font.color.rgb = COLOR_MUTED_GRAY

        footer = sec.footer
        footer_para = footer.paragraphs[0]
        footer_para.text = (
            f"Proposal Version {version} | Verifiable Factual Provenance | Strictly Confidential"
        )
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if footer_para.runs:
            footer_para.runs[0].font.size = Pt(8.5)
            footer_para.runs[0].font.color.rgb = COLOR_MUTED_GRAY


def render_cover_section(doc: Any, title: str, content: str) -> None:
    """Render distinctive title page and insert page break."""
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(40)
    p_title.paragraph_format.space_after = Pt(12)
    run_title = p_title.add_run("MANAGEMENT CONSULTING PROPOSAL")
    run_title.font.size = Pt(22)
    run_title.font.bold = True
    run_title.font.color.rgb = COLOR_PRIMARY_NAVY

    for line in content.splitlines():
        line_s = line.strip()
        if not line_s:
            continue
        p = doc.add_paragraph()
        if ":" in line_s:
            label, val = line_s.split(":", 1)
            r_lbl = p.add_run(f"{label.strip()}: ")
            r_lbl.bold = True
            r_lbl.font.color.rgb = COLOR_SECONDARY_BLUE
            p.add_run(val.strip())
        else:
            p.add_run(line_s)
        p.paragraph_format.space_after = Pt(4)

    doc.add_page_break()


def render_content_section(doc: Any, title: str, content: str) -> None:
    """Render a standard proposal body section with styled headings and lists."""
    h = doc.add_heading(title, level=1)
    h.paragraph_format.space_before = Pt(16)
    h.paragraph_format.space_after = Pt(6)

    for line in content.splitlines():
        line_s = line.strip()
        if not line_s:
            continue
        if line_s.startswith(("- ", "* ", "• ")):
            p = doc.add_paragraph(line_s[2:].strip(), style="List Bullet")
            p.paragraph_format.space_after = Pt(3)
        elif line_s.startswith("### "):
            h3 = doc.add_heading(line_s[4:].strip(), level=2)
            h3.paragraph_format.space_before = Pt(10)
        elif "not confirmed on the call" in line_s.lower() or "to be agreed" in line_s.lower():
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25)
            run = p.add_run(f"⚠️ {line_s}")
            run.italic = True
            run.font.color.rgb = RGBColor(180, 100, 0)
        else:
            p = doc.add_paragraph(line_s)
            p.paragraph_format.space_after = Pt(5)


def render_proposal_docx(
    sections: list[dict[str, Any]],
    company_name: str = "Brightline Retail Group",
    version: int = 1,
    output_path: str | Path | None = None,
) -> BytesIO:
    """Render complete multi-section proposal into DOCX byte stream or file."""
    try:
        doc = Document()
        apply_document_styles(doc)
        configure_header_footer(doc, company_name, version)

        for sec in sections:
            sec_key = sec.get("section_key", "").lower()
            title = sec.get("title", "Section")
            content = sec.get("content", "")

            if sec_key == "cover":
                render_cover_section(doc, title, content)
            else:
                render_content_section(doc, title, content)

        stream = BytesIO()
        doc.save(stream)
        stream.seek(0)

        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "wb") as f:
                f.write(stream.getvalue())
            logger.info("proposal_docx_saved", path=str(out_p), version=version)

        return stream
    except Exception as exc:
        logger.error("docx_rendering_failed", error=str(exc))
        raise DocxRenderError(f"Failed to render proposal DOCX: {exc}") from exc
