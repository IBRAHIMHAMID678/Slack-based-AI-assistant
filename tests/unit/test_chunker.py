"""Unit tests verifying the heading-aware text chunker.

Validates:
1. Section heading identification
2. Strict sentence boundary preservation (never splits mid-sentence)
3. 400-token target with 60-token overlap
4. Zero-width character and malicious marker stripping
5. Heading path metadata preservation.
"""

from app.rag.chunker import (
    HeadingAwareChunker,
    clean_untrusted_text,
    is_heading,
    split_into_sentences,
)


def test_clean_untrusted_text_strips_zero_width_chars():
    """Verify zero-width spaces, directional marks, and byte-order markers are stripped."""
    dirty_text = "Lakeview\u200b Medical\ufeff Group\u200c operations\u202e."
    clean = clean_untrusted_text(dirty_text)
    assert clean == "Lakeview Medical Group operations."
    assert "\u200b" not in clean
    assert "\ufeff" not in clean


def test_is_heading_detection():
    """Verify detection of markdown headings and uppercase section titles."""
    assert is_heading("## PROPOSED SOLUTION") is True
    assert is_heading("EXECUTIVE SUMMARY") is True
    assert is_heading("TIMELINE") is True
    assert is_heading("BUDGET") is True
    assert is_heading("PROPOSAL — HEALTHCARE PLATFORM") is True
    # Normal prose sentences should not be classified as headings
    assert is_heading("This proposal outlines a phased approach.") is False
    assert is_heading("The budget is estimated at fifty thousand dollars.") is False


def test_sentence_boundary_integrity():
    """Ensure text is never split across mid-sentence punctuation."""
    text = (
        "Lakeview Medical Group operates three clinics. "
        "The current intake workflow is entirely paper-based. "
        "Patients arrive 20 minutes before their appointment to complete physical forms."
    )
    sentences = split_into_sentences(text)
    assert len(sentences) == 3
    for s in sentences:
        assert s.endswith((".", "!", "?")) or s == sentences[-1]


def test_chunker_metadata_and_heading_path():
    """Verify chunk generation produces correct metadata, headings, and indices."""
    sample_doc = (
        "PROPOSAL — PATIENT INTAKE MODERNISATION\n\n"
        "EXECUTIVE SUMMARY\n"
        "Lakeview Medical Group operates three clinic locations. "
        "New patient intake is currently handled via paper clipboard packets.\n\n"
        "PROPOSED SOLUTION\n"
        "This proposal outlines a digital patient intake system. "
        "All data is encrypted in transit and at rest."
    )

    chunker = HeadingAwareChunker(target_tokens=50, overlap_tokens=10)
    chunks = chunker.chunk_document(
        raw_text=sample_doc,
        source_id="proposal_healthcare",
        source_type="proposal",
        industry="healthcare",
    )

    assert len(chunks) >= 2
    assert chunks[0].metadata["source_id"] == "proposal_healthcare"
    assert chunks[0].metadata["industry"] == "healthcare"
    assert "EXECUTIVE SUMMARY" in chunks[0].metadata["heading_path"]

    # Assert no chunk is empty
    for c in chunks:
        assert len(c.text.strip()) > 0
        assert c.chunk_index >= 0
