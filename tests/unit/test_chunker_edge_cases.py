"""Extensive edge case unit tests for text chunking and normalization.

Tests abbreviation handling, excessive whitespace, extreme token counts,
multiline headings, empty documents, and special characters.
"""

from app.rag.chunker import (
    HeadingAwareChunker,
    clean_untrusted_text,
    estimate_tokens,
    is_heading,
    split_into_sentences,
)


def test_clean_untrusted_text_handles_none_and_empty():
    assert clean_untrusted_text("") == ""
    assert clean_untrusted_text(None) == ""  # type: ignore


def test_clean_untrusted_text_normalizes_crlf_and_newlines():
    raw = "Line 1\r\n\r\n\r\n\r\nLine 2"
    cleaned = clean_untrusted_text(raw)
    assert "\r" not in cleaned
    assert "\n\n\n" not in cleaned
    assert "Line 1\n\nLine 2" == cleaned


def test_estimate_tokens_calculation():
    text = "This is a short ten word test sentence to estimate tokens."
    tokens = estimate_tokens(text)
    assert tokens >= 10
    assert tokens <= 25


def test_is_heading_edge_cases():
    assert is_heading("") is False
    assert is_heading("A" * 120) is False
    assert is_heading("### SUB-SECTION 3.1") is True
    assert is_heading("== SECTION HEADER ==") is True
    assert is_heading("PROPOSAL - CLOUD MIGRATION") is True
    assert is_heading("NOT A HEADING.") is False


def test_split_into_sentences_abbreviations():
    text = "Dr. Smith met with Mr. Marcus Webb at 9 a.m. to discuss Q1 goals. They agreed on the timeline."
    sentences = split_into_sentences(text)
    assert len(sentences) >= 1
    assert "Dr. Smith" in sentences[0]


def test_chunker_handles_single_giant_sentence():
    giant = "This is an extremely long sentence without any punctuation " * 40 + "."
    chunker = HeadingAwareChunker(target_tokens=50, overlap_tokens=10)
    chunks = chunker.chunk_document(giant, "test_doc", "proposal")
    assert len(chunks) >= 1
    assert chunks[0].metadata["source_id"] == "test_doc"


def test_chunker_handles_multiple_consecutive_headings():
    doc = "# PROPOSAL\n## PHASE 1\n### DISCOVERY\nWe begin with a two week discovery audit."
    chunker = HeadingAwareChunker(target_tokens=100, overlap_tokens=20)
    chunks = chunker.chunk_document(doc, "multi_head", "proposal")
    assert len(chunks) == 1
    assert "DISCOVERY" in chunks[0].metadata["heading_path"]


def test_chunker_custom_metadata_passthrough():
    chunker = HeadingAwareChunker(target_tokens=100)
    chunks = chunker.chunk_document(
        "Simple test body content.",
        source_id="custom_id",
        source_type="transcript",
        industry="retail",
        extra_metadata={"session_id": "sess_999", "tenant": "corp"},
    )
    assert chunks[0].metadata["session_id"] == "sess_999"
    assert chunks[0].metadata["tenant"] == "corp"
    assert chunks[0].metadata["industry"] == "retail"
