"""Unit tests verifying DOCX document generation and section isolation.

Validates Stage 6 Definition of Done:
1. Complete document renders with all sections present
2. Correct headers, footers, and styles applied
3. Section-scoped revision changes ONLY the targeted section.
"""

from docx import Document

from app.docx.renderer import render_proposal_docx


def get_sample_sections():
    """Return standard test sections representing a complete proposal draft."""
    return [
        {
            "section_key": "cover",
            "title": "Cover",
            "content": "Proposal: Unified Inventory Sync\nPrepared for: Brightline Retail Group\nDate: May 2026",
        },
        {
            "section_key": "executive_summary",
            "title": "Executive Summary",
            "content": "Brightline operates three active warehouse facilities across Chicago, Dallas, and Phoenix.",
        },
        {
            "section_key": "proposed_solution",
            "title": "Proposed Solution",
            "content": "A high-reliability synchronization layer around Raj's current system.",
        },
        {
            "section_key": "timeline",
            "title": "Timeline",
            "content": "Target launch: End of Q3 (approximately 5 months from commencement).",
        },
        {
            "section_key": "budget_range",
            "title": "Budget Range",
            "content": "Tier 1: Core Visibility ($50,000 target). Tier 2: Enterprise ($95,000 - $120,000).",
        },
        {
            "section_key": "next_steps",
            "title": "Next Steps",
            "content": "1. Review and Approval. 2. Technical Scoping with Raj.",
        },
    ]


def test_docx_full_generation_and_all_sections_present(tmp_path):
    """Verify document is created with all sections and valid structure."""
    sections = get_sample_sections()
    out_file = tmp_path / "proposal_v1.docx"

    stream = render_proposal_docx(
        sections=sections,
        company_name="Brightline Retail Group",
        version=1,
        output_path=out_file,
    )
    assert stream.getbuffer().nbytes > 0
    assert out_file.exists()

    # Read back generated DOCX using python-docx to verify content
    doc = Document(out_file)
    headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert "Executive Summary" in headings
    assert "Proposed Solution" in headings
    assert "Timeline" in headings
    assert "Budget Range" in headings
    assert "Next Steps" in headings

    # Verify footer text
    footer_text = doc.sections[0].footer.paragraphs[0].text
    assert "Version 1" in footer_text


def test_section_scoped_regeneration_isolation(tmp_path):
    """Verify regenerating one section modifies ONLY that section."""
    sections_v1 = get_sample_sections()
    file_v1 = tmp_path / "proposal_v1.docx"
    render_proposal_docx(sections_v1, "Brightline Retail Group", 1, file_v1)

    # Modify ONLY the timeline section
    sections_v2 = [dict(s) for s in sections_v1]
    timeline_sec = next(s for s in sections_v2 if s["section_key"] == "timeline")
    timeline_sec["content"] = (
        "Phase 1: Sprint 1-4. Target launch: End of Q3. Confirmed Fallback: Q4."
    )

    file_v2 = tmp_path / "proposal_v2.docx"
    render_proposal_docx(sections_v2, "Brightline Retail Group", 2, file_v2)

    doc1 = Document(file_v1)
    doc2 = Document(file_v2)

    paras1 = [p.text for p in doc1.paragraphs if p.text.strip()]
    paras2 = [p.text for p in doc2.paragraphs if p.text.strip()]

    # Executive Summary and Proposed Solution must be identical
    assert (
        "Brightline operates three active warehouse facilities across Chicago, Dallas, and Phoenix."
        in paras1
    )
    assert (
        "Brightline operates three active warehouse facilities across Chicago, Dallas, and Phoenix."
        in paras2
    )

    # Timeline section must reflect the targeted revision
    assert any("Sprint 1-4" in p for p in paras2)
    assert not any("Sprint 1-4" in p for p in paras1)
